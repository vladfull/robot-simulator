"""
ExecutionEngine

Owns the user code's compiled state and a reference to the per-step entry
point ``control_step(robot)``. Every simulation tick calls
:py:meth:`execute_step`, which runs the user function with the live
``RobotAPI`` and captures any error so the host application keeps running
(TS §1.4 НФВ-3).
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Optional

from .sandbox import build_safe_globals


class ExecutionEngine:
    """Compile + execute user-supplied control algorithms safely."""

    def __init__(self, console: Optional[Any] = None):
        self.console = console
        self.user_globals: dict = {}
        self.control_function: Optional[Callable[[Any], None]] = None
        self.last_error: Optional[str] = None
        self.is_loaded: bool = False

    # ------------------------------------------------------------------
    # Compile
    # ------------------------------------------------------------------
    def load_code(self, source: str) -> bool:
        """
        Compile and prime user code.

        Looks up a top-level ``control_step`` callable; if missing,
        ``load_code`` reports an error and refuses to mark itself loaded.

        Returns:
            True on success, False on any compilation/lookup error.
        """
        self.last_error = None
        try:
            self.user_globals = build_safe_globals()
            compiled = compile(source, "<user_code>", "exec")
            exec(compiled, self.user_globals)  # noqa: S102 — sandboxed
        except SyntaxError as exc:
            self._record_error(self._format_syntax_error(exc))
            self.is_loaded = False
            return False
        except Exception:  # noqa: BLE001 — we catch anything to keep host alive
            self._record_error(traceback.format_exc())
            self.is_loaded = False
            return False

        cs = self.user_globals.get("control_step")
        if not callable(cs):
            self._record_error(
                "User code must define a callable named 'control_step(robot)'."
            )
            self.is_loaded = False
            return False

        self.control_function = cs
        self.is_loaded = True
        self._info("Code loaded successfully.")
        return True

    # ------------------------------------------------------------------
    # Run a single tick
    # ------------------------------------------------------------------
    def execute_step(self, api: Any) -> Optional[str]:
        """
        Invoke the user's ``control_step(api)`` once.

        Returns:
            ``None`` on success.
            ``"no_code"`` when no code is loaded yet.
            ``"runtime_error"`` if the user function raised.

        On error, the engine flips ``is_loaded`` to False so we don't
        spam the console every tick — the user re-Runs after fixing.
        """
        if not self.is_loaded or self.control_function is None:
            return "no_code"
        try:
            self.control_function(api)
            return None
        except Exception:  # noqa: BLE001
            self._record_error(traceback.format_exc())
            self.is_loaded = False
            return "runtime_error"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Drop the most recent error message; keep code loaded."""
        self.last_error = None

    def unload(self) -> None:
        """Tear down compiled state (used when the user clears the editor)."""
        self.user_globals = {}
        self.control_function = None
        self.is_loaded = False
        self.last_error = None

    def get_last_error(self) -> Optional[str]:
        return self.last_error

    # ------------------------------------------------------------------
    # Console plumbing
    # ------------------------------------------------------------------
    def _record_error(self, text: str) -> None:
        self.last_error = text
        if self.console is not None and hasattr(self.console, "write_error"):
            try:
                self.console.write_error(text)
                return
            except Exception:
                pass
        # Always echo to stdout for headless test runners.
        print(text)

    def _info(self, text: str) -> None:
        if self.console is not None and hasattr(self.console, "write"):
            try:
                self.console.write(text)
                return
            except Exception:
                pass
        print(text)

    # ------------------------------------------------------------------
    # Pretty syntax errors so the user sees position, not just a stack.
    # ------------------------------------------------------------------
    @staticmethod
    def _format_syntax_error(exc: SyntaxError) -> str:
        lineno = exc.lineno or 1
        col = exc.offset or 0
        msg = exc.msg or "syntax error"
        text = (exc.text or "").rstrip("\n")
        pointer = " " * max(0, col - 1) + "^"
        return (
            f"SyntaxError: {msg} (line {lineno}, column {col})\n"
            f"    {text}\n"
            f"    {pointer}"
        )
