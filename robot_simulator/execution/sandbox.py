"""
Sandbox for user code.

Implements TS §5.5: a whitelist of safe builtins plus the ``math`` and
``random`` modules. Anything else (``os``, ``sys``, ``subprocess``,
``open``, ``exec``, ``eval``, ``__import__``, file I/O, network, threads)
is unavailable to user code.

Important caveats — also covered in TS §7.1:

* Python sandboxes are *not* a security boundary. A determined attacker
  can escape almost any in-process Python sandbox. We treat this layer
  as a guardrail against accidents (forgotten `os.remove`, infinite
  imports, runaway file writes), not as protection from malice.
* The whitelist intentionally omits ``__import__``; the only way user
  code can reach a module is through the names we pre-bind in
  ``build_safe_globals`` (currently ``math`` and ``random``).
"""

from __future__ import annotations

import builtins as _builtins
import math
import random
from typing import Dict


# Functions that are safe to expose. Keep this list short and audited.
SAFE_BUILTINS = (
    # Iteration / collections
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "frozenset", "int", "len", "list", "map", "max", "min", "range",
    "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple",
    "zip",
    # Inspection (read-only)
    "isinstance", "issubclass", "hasattr", "getattr",
    # Misc
    "divmod", "pow", "print", "repr", "type",
)


def _blocked_import(*_args, **_kwargs):
    """Replacement for __import__ that flatly refuses."""
    raise ImportError(
        "Imports are disabled inside user code. "
        "The math and random modules are pre-imported and ready to use."
    )


def build_safe_globals() -> Dict[str, object]:
    """
    Construct the globals dict for a freshly compiled user script.

    The returned dict already contains:
      * ``__builtins__`` — restricted to ``SAFE_BUILTINS`` plus a stub
        ``__import__`` that always raises ``ImportError``.
      * ``math`` — the standard math module.
      * ``random`` — the standard random module.

    Anything else the user wants must be defined inside the user code
    itself. ``__name__`` is set to ``"user_code"`` to give clean
    tracebacks.
    """
    safe_bi: Dict[str, object] = {
        name: getattr(_builtins, name)
        for name in SAFE_BUILTINS
        if hasattr(_builtins, name)
    }
    # Block imports explicitly even if a user finds an alternate path.
    safe_bi["__import__"] = _blocked_import

    return {
        "__builtins__": safe_bi,
        "__name__": "user_code",
        "math": math,
        "random": random,
    }
