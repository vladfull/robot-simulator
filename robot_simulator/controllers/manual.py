"""
Manual Control

Keyboard-driven controller. The UI layer feeds it the set of currently
pressed direction keys; compute_control() turns that into (v, omega)
each simulation tick.
"""

from typing import Any, Dict, Set, Tuple

from .base import Controller


class ManualController(Controller):
    """
    Manual keyboard control.

    Inputs:
        - 'up'    : forward
        - 'down'  : reverse
        - 'left'  : turn left
        - 'right' : turn right
    """

    def __init__(
        self,
        max_velocity: float = 1.0,
        max_angular_velocity: float = 2.0,
    ):
        """
        Initialize manual controller.

        Args:
            max_velocity: Maximum forward/reverse speed (m/s).
            max_angular_velocity: Maximum turn rate (rad/s).
        """
        super().__init__(name="Manual Control")
        self.max_velocity = max_velocity
        self.max_angular_velocity = max_angular_velocity

        # Set of currently held direction names.
        self._pressed: Set[str] = set()

        # Last computed command (kept for telemetry/UI display).
        self.command_v = 0.0
        self.command_omega = 0.0

    # ------------------------------------------------------------------
    # Input from UI
    # ------------------------------------------------------------------
    def press(self, key: str) -> None:
        """Mark a direction key as pressed (keep responsive on next tick)."""
        if key in {"up", "down", "left", "right"}:
            self._pressed.add(key)

    def release(self, key: str) -> None:
        """Mark a direction key as released."""
        self._pressed.discard(key)

    def set_keys(self, keys: Set[str]) -> None:
        """Replace the entire pressed-keys set in one call."""
        self._pressed = {k for k in keys if k in {"up", "down", "left", "right"}}

    # Legacy hook still used in some places.
    def set_command(self, v: float, omega: float) -> None:
        self.command_v = v
        self.command_omega = omega

    # ------------------------------------------------------------------
    # Controller interface
    # ------------------------------------------------------------------
    def compute_control(
        self,
        robot_state: Dict[str, float],
        environment: Any,
        goal: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Translate pressed keys into (v, omega)."""
        v = 0.0
        omega = 0.0

        if "up" in self._pressed:
            v += self.max_velocity
        if "down" in self._pressed:
            v -= self.max_velocity
        if "left" in self._pressed:
            omega += self.max_angular_velocity
        if "right" in self._pressed:
            omega -= self.max_angular_velocity

        self.command_v = v
        self.command_omega = omega
        return v, omega

    def reset(self) -> None:
        """Drop pressed keys and zero command."""
        self._pressed.clear()
        self.command_v = 0.0
        self.command_omega = 0.0

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "command_v": self.command_v,
            "command_omega": self.command_omega,
            "pressed": sorted(self._pressed),
        }
