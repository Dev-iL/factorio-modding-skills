"""HTTP access for the toolkit: one client factory, retries with exponential backoff, clear errors, cached downloads.

Everything that can reach an exception message or the terminal passes through `redact`, because the mod
portal's download URLs carry `?username=...&token=...` and httpx2 puts the full URL into its error text.
"""

from __future__ import annotations

import email.utils
import json
import os
import random
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx2

from .errors import ToolkitError
from .redact import redact

USER_AGENT = "factorio-modding-skills/0.1 (+https://github.com/Dev-iL/factorio-modding-skills)"
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})

type JsonValue = dict[str, JsonValue] | list[JsonValue] | str | int | float | bool | None
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True)
class RetryPolicy:
    """How often and how long to retry. `sleep` and `rng` are injectable so tests run instantly."""

    max_attempts: int = 4
    base_delay: float = 1.0
    max_delay: float = 30.0
    max_retry_after: float = 120.0  # a longer Retry-After is reported instead of waited out
    jitter: float = 0.25  # up to this fraction of the delay is added at random
    sleep: Callable[[float], None] = field(default=time.sleep, repr=False)
    rng: Callable[[], float] = field(default=random.random, repr=False)

    def delay(self, attempt: int) -> float:
        """Seconds to wait after failed attempt number `attempt` (1-based): 1, 2, 4, ... plus jitter."""
        base = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
        return base + base * self.jitter * self.rng()


DEFAULT_POLICY = RetryPolicy()


def make_client(
    *,
    transport: httpx2.BaseTransport | None = None,
    timeout: float = 30.0,
    follow_redirects: bool = False,
) -> httpx2.Client:
    """A client with the toolkit User-Agent and timeouts. Pass `transport` to mock the network in tests."""
    return httpx2.Client(
        transport=transport,
        timeout=httpx2.Timeout(timeout, connect=10.0),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=follow_redirects,
    )


def fail(message: str, hint: str | None = None, *, secrets: Iterable[str] = ()) -> ToolkitError:
    """A ToolkitError whose message and hint are already redacted (so `exc.message` is safe to print)."""
    secrets = tuple(secrets)
    return ToolkitError(redact(message, secrets), redact(hint, secrets) if hint else None)


def _retry_after_seconds(response: httpx2.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if not value:
        return None
    if value.strip().isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def _server_message(response: httpx2.Response) -> str:
    """The portal answers errors with `{"message": ...}`; fall back to a short slice of the body."""
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()[:200]
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        return body["message"]
    return response.text.strip()[:200]


def _status_error(
    response: httpx2.Response,
    what: str,
    *,
    attempts: int,
    not_found_hint: str | None,
    auth_hint: str | None,
    secrets: Iterable[str],
) -> ToolkitError:
    status = response.status_code
    host = urlsplit(str(response.request.url)).netloc
    detail = _server_message(response)
    suffix = f": {detail}" if detail else ""
    if status == 404:
        return fail(
            f"{what} was not found (HTTP 404 from {host}){suffix}.",
            not_found_hint or "check the spelling of the name or version.",
            secrets=secrets,
        )
    if status in (401, 403):
        return fail(
            f"{host} refused the request for {what} (HTTP {status}){suffix}.",
            auth_hint or f"{host} requires authorization for this request.",
            secrets=secrets,
        )
    if status in RETRYABLE_STATUSES:
        reason = "rate limited you" if status == 429 else f"is failing (HTTP {status})"
        return fail(
            f"{host} {reason} while fetching {what}; gave up after {attempts} attempts{suffix}.",
            "wait a minute and run the command again." if status == 429 else "the service may be down; try again later.",
            secrets=secrets,
        )
    return fail(f"{host} answered HTTP {status} for {what}{suffix}.", "check the arguments and try again.", secrets=secrets)


def send(
    client: httpx2.Client,
    method: str,
    url: str,
    *,
    what: str,
    params: Mapping[str, str | int] | None = None,
    json_body: object | None = None,
    policy: RetryPolicy = DEFAULT_POLICY,
    not_found_hint: str | None = None,
    auth_hint: str | None = None,
    secrets: Iterable[str] = (),
) -> httpx2.Response:
    """Send a request and return it only if the final status is below 400.

    Connect and read timeouts, 429 and 5xx are retried with exponential backoff (a Retry-After header wins when
    longer). Everything else, and exhausted retries, raises a ToolkitError that names the cause and the next step.
    `what` is a short description of the thing being fetched, e.g. "mod 'foo'".
    """
    secrets = tuple(secrets)
    for attempt in range(1, policy.max_attempts + 1):
        last = attempt == policy.max_attempts
        try:
            response = client.request(method, url, params=params, json=json_body)
        except httpx2.TransportError as exc:
            if last:
                kind = "timed out" if isinstance(exc, httpx2.TimeoutException) else "failed"
                raise fail(
                    f"the request for {what} {kind} after {attempt} attempts ({type(exc).__name__}: {exc}).",
                    "check your internet connection or proxy settings and run the command again.",
                    secrets=secrets,
                ) from exc
            policy.sleep(policy.delay(attempt))
            continue
        except httpx2.InvalidURL as exc:
            raise fail(f"invalid URL for {what}: {exc}", "check the name or version you passed.", secrets=secrets) from exc
        if response.status_code < 400:
            return response
        if response.status_code not in RETRYABLE_STATUSES or last:
            raise _status_error(response, what, attempts=attempt, not_found_hint=not_found_hint, auth_hint=auth_hint, secrets=secrets)
        delay = policy.delay(attempt)
        asked = _retry_after_seconds(response)
        if asked is not None:
            if asked > policy.max_retry_after:
                raise fail(
                    f"{urlsplit(url).netloc} asked to wait {asked:.0f}s before the next request for {what}.",
                    "try again after that time.",
                    secrets=secrets,
                )
            delay = max(delay, asked)
        policy.sleep(delay)
    raise AssertionError("unreachable: the last attempt returns or raises")  # pragma: no cover


def json_object(response: httpx2.Response, what: str, *, secrets: Iterable[str] = ()) -> JsonObject:
    """Parse a JSON object body, or raise a ToolkitError saying the answer was not what the API documents."""
    try:
        body: JsonValue = response.json()
    except ValueError as exc:
        raise fail(
            f"the answer for {what} was not valid JSON (starts with {response.text[:60]!r}).",
            "an error page or a proxy may be in the way; run the command again, or check your network.",
            secrets=secrets,
        ) from exc
    if not isinstance(body, dict):
        raise fail(f"the answer for {what} was not a JSON object.", "the service may have changed its format; report this.", secrets=secrets)
    return body


def cached_download(
    client: httpx2.Client,
    url: str,
    dest: Path,
    *,
    what: str,
    validate: Callable[[bytes], None] | None = None,
    force: bool = False,
    policy: RetryPolicy = DEFAULT_POLICY,
    not_found_hint: str | None = None,
) -> bool:
    """Download `url` to `dest` unless it is already there. Returns True when a download happened.

    `validate` checks the bytes before they are stored and raises ToolkitError for a bad payload, so an error
    page is never cached. The file is written next to `dest` and renamed into place, so an interrupted run
    never leaves a half-written file behind.
    """
    if dest.is_file() and not force:
        return False
    data = send(client, "GET", url, what=what, policy=policy, not_found_hint=not_found_hint).content
    if validate is not None:
        validate(data)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(f"{dest.name}.{os.getpid()}.part")
    try:
        partial.write_bytes(data)
        os.replace(partial, dest)
    finally:
        partial.unlink(missing_ok=True)
    return True


def parse_json_bytes(data: bytes, what: str) -> JsonObject:
    """Decode a JSON object from bytes (used by validators and cache readers)."""
    try:
        body: JsonValue = json.loads(data)
    except ValueError as exc:
        raise fail(f"{what} is not valid JSON ({exc}).", "delete the cached file or run with --refresh, then try again.") from exc
    if not isinstance(body, dict):
        raise fail(f"{what} is not a JSON object.", "delete the cached file or run with --refresh, then try again.")
    return body
