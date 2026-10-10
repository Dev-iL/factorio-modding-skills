"""One error type for failures the user can act on, and the CLI wrapper that prints it."""

from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Callable, Sequence
from typing import NoReturn

from .redact import redact

EXIT_FAILED = 1  # the thing under test failed (a broken mod, a failed check)
EXIT_USAGE = 2  # the environment or the arguments need fixing before the tool can run
EXIT_INTERNAL = 70


class ToolkitError(Exception):
    """A failure with a known cause. `message` says what went wrong, `hint` says what to do next."""

    def __init__(self, message: str, hint: str | None = None, exit_code: int = EXIT_USAGE) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.exit_code = exit_code

    def render(self) -> str:
        text = f"error: {self.message}"
        if self.hint:
            text += f"\n  next step: {self.hint}"
        return redact(text)


def cli_main(main: Callable[[Sequence[str]], int]) -> NoReturn:
    """Run `main(argv)` and exit with its code; turn errors into one clear message, not a traceback.

    Set FM_DEBUG=1 to see the traceback of an unexpected error.
    """
    try:
        code = main(sys.argv[1:])
    except ToolkitError as exc:
        print(exc.render(), file=sys.stderr)
        code = exc.exit_code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        code = 130
    except Exception as exc:  # noqa: BLE001 - last-resort boundary: never show a raw traceback
        print(
            redact(f"error: unexpected {type(exc).__name__}: {exc}\n"
                   "  next step: re-run with FM_DEBUG=1 for the traceback and report it"),
            file=sys.stderr,
        )
        if os.environ.get("FM_DEBUG"):
            print(redact(traceback.format_exc()), file=sys.stderr)
        code = EXIT_INTERNAL
    sys.exit(code)
