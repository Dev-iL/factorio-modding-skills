"""Mod portal credentials: environment variables first, `player-data.json` only with explicit approval."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ToolkitError

ENV_USERNAME = "FACTORIO_USERNAME"
ENV_TOKEN = "FACTORIO_TOKEN"
ALLOW_FLAG = "--allow-player-data"


@dataclass(frozen=True)
class Credentials:
    """A portal username and API token. The token is left out of `repr` so it cannot leak through logging."""

    username: str
    token: str = field(repr=False)

    def as_query(self) -> dict[str, str]:
        return {"username": self.username, "token": self.token}


def _missing_message(missing: list[str]) -> ToolkitError:
    return ToolkitError(
        f"mod portal credentials are not set ({' and '.join(missing)} missing from the environment).",
        "set both variables where your agent host passes them to commands. Claude Code: add them under `env` in "
        "~/.claude/settings.json. Codex: add them under `[shell_environment_policy] set` in ~/.codex/config.toml. "
        "Your username and token are on https://factorio.com/profile. "
        f"As a last resort the script can read them from the game's player-data.json, but only if you approve that "
        f"in the conversation and the script is run with {ALLOW_FLAG}.",
    )


def _from_player_data(path: Path) -> Credentials:
    try:
        data = json.loads(path.read_text("utf-8"))
    except OSError as exc:
        raise ToolkitError(f"could not read {path}: {exc.strerror or exc}.", f"set {ENV_USERNAME} and {ENV_TOKEN} instead.") from exc
    except ValueError as exc:
        raise ToolkitError(f"{path} is not valid JSON.", f"set {ENV_USERNAME} and {ENV_TOKEN} instead.") from exc
    username = data.get("service-username") if isinstance(data, dict) else None
    token = data.get("service-token") if isinstance(data, dict) else None
    if not (isinstance(username, str) and username and isinstance(token, str) and token):
        raise ToolkitError(
            f"{path} has no service-username/service-token (the game is not logged in to factorio.com).",
            f"log in from the game's main menu, or set {ENV_USERNAME} and {ENV_TOKEN}.",
        )
    return Credentials(username, token)


def get_credentials(
    allow_player_data: bool = False,
    player_data_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> Credentials:
    """Return portal credentials from `FACTORIO_USERNAME`/`FACTORIO_TOKEN`.

    Only when they are unset and `allow_player_data` is true (the user approved it and passed the flag) is
    `player-data.json` read, from `player_data_path` or the located game's write-data directory.
    """
    env = os.environ if env is None else env
    username, token = env.get(ENV_USERNAME, ""), env.get(ENV_TOKEN, "")
    if username and token:
        return Credentials(username, token)
    if not allow_player_data:
        raise _missing_message([name for name, value in ((ENV_USERNAME, username), (ENV_TOKEN, token)) if not value])
    if player_data_path is None:
        from .paths import locate_game  # imported late: only the approved fallback needs the game install

        player_data_path = locate_game(env=env).player_data
    return _from_player_data(player_data_path)
