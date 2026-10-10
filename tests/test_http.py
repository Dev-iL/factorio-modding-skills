from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from _lib.errors import ToolkitError
from _lib.http import RetryPolicy, cached_download, json_object, make_client, send

SECRET = "fake-token-0000"


def client_for(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    return make_client(transport=httpx2.MockTransport(handler), follow_redirects=True)


def policy(slept: list[float], **kw: float) -> RetryPolicy:
    return RetryPolicy(sleep=slept.append, rng=lambda: 0.0, **kw)


def test_not_found_names_cause_and_next_step() -> None:
    client = client_for(lambda req: httpx2.Response(404, json={"message": "Mod not found"}))
    with pytest.raises(ToolkitError) as info:
        send(client, "GET", "https://mods.factorio.com/api/mods/nope/full", what="mod 'nope'", not_found_hint="run `portal.py list`")
    assert "mod 'nope' was not found" in info.value.message
    assert "Mod not found" in info.value.message
    assert info.value.hint == "run `portal.py list`"


def test_429_backs_off_exponentially_then_succeeds() -> None:
    answers = iter([429, 429, 200])
    client = client_for(lambda req: httpx2.Response(next(answers), json={"ok": True}))
    slept: list[float] = []
    response = send(client, "GET", "https://example.test/x", what="x", policy=policy(slept))
    assert response.status_code == 200
    assert slept == [1.0, 2.0]


def test_retry_after_header_wins_when_longer_than_backoff() -> None:
    answers = iter([429, 200])
    client = client_for(lambda req: httpx2.Response(next(answers), headers={"Retry-After": "7"}))
    slept: list[float] = []
    send(client, "GET", "https://example.test/x", what="x", policy=policy(slept))
    assert slept == [7.0]


def test_retry_after_beyond_the_cap_is_reported_not_waited() -> None:
    client = client_for(lambda req: httpx2.Response(429, headers={"Retry-After": "3600"}))
    slept: list[float] = []
    with pytest.raises(ToolkitError, match="asked to wait 3600s"):
        send(client, "GET", "https://example.test/x", what="x", policy=policy(slept))
    assert slept == []


def test_exhausted_429_says_rate_limited() -> None:
    client = client_for(lambda req: httpx2.Response(429))
    slept: list[float] = []
    with pytest.raises(ToolkitError) as info:
        send(client, "GET", "https://example.test/x", what="the list", policy=policy(slept, max_attempts=3))
    assert "rate limited" in info.value.message and "3 attempts" in info.value.message
    assert slept == [1.0, 2.0]


def test_server_errors_are_retried_but_client_errors_are_not() -> None:
    calls: list[int] = []

    def handler(req: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return httpx2.Response(400, json={"message": "Invalid factorio version"})

    with pytest.raises(ToolkitError, match="Invalid factorio version"):
        send(client_for(handler), "GET", "https://example.test/x", what="x", policy=policy([]))
    assert len(calls) == 1


def test_timeout_is_retried_then_reported() -> None:
    def handler(req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow", request=req)

    slept: list[float] = []
    with pytest.raises(ToolkitError) as info:
        send(client_for(handler), "GET", "https://example.test/x", what="x", policy=policy(slept, max_attempts=3))
    assert "timed out after 3 attempts" in info.value.message
    assert "internet connection" in (info.value.hint or "")
    assert slept == [1.0, 2.0]


def test_credentials_in_urls_never_reach_messages() -> None:
    url = f"https://mods.factorio.com/download/foo/abc?username=someone&token={SECRET}"

    def handler(req: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError(f"all connection attempts failed for {req.url}", request=req)

    with pytest.raises(ToolkitError) as info:
        send(client_for(handler), "GET", url, what="the download", policy=policy([], max_attempts=2), secrets=[SECRET])
    rendered = info.value.render()
    assert SECRET not in rendered and "someone" not in rendered
    assert "token=***" in rendered


def test_invalid_json_is_a_clear_error() -> None:
    response = httpx2.Response(200, text="<html>maintenance</html>")
    with pytest.raises(ToolkitError, match="not valid JSON"):
        json_object(response, "the mod list")


def test_cached_download_fetches_once(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(req: httpx2.Request) -> httpx2.Response:
        calls.append(str(req.url))
        return httpx2.Response(200, content=b'{"ok": 1}')

    client = client_for(handler)
    dest = tmp_path / "sub" / "doc.json"
    assert cached_download(client, "https://example.test/doc.json", dest, what="doc") is True
    assert cached_download(client, "https://example.test/doc.json", dest, what="doc") is False
    assert len(calls) == 1 and dest.read_bytes() == b'{"ok": 1}'
    assert list(dest.parent.glob("*.part")) == []


def test_cached_download_never_stores_a_payload_that_fails_validation(tmp_path: Path) -> None:
    def reject(data: bytes) -> None:
        raise ToolkitError("not the API document", "retry")

    dest = tmp_path / "doc.json"
    client = client_for(lambda req: httpx2.Response(200, content=b"<html>"))
    with pytest.raises(ToolkitError):
        cached_download(client, "https://example.test/doc.json", dest, what="doc", validate=reject)
    assert not dest.exists() and list(tmp_path.iterdir()) == []
