"""
Robot API — the surface user code talks to.

This is a deliberate Facade (TS §5.3). User code never touches Robot,
World, or PhysicsWorld directly: it receives a single ``RobotAPI``
instance per simulation step and reads/writes through it. That gives us:

  * a stable contract documented in ``docs/api_reference.md``;
  * a chokepoint to validate inputs (e.g. saturate set_velocity);
  * a place to inject the user-facing console (so ``api.log("msg")``
    writes to the GUI console, not stdout).

Methods provided (all per TS §1.4 ФВ-2 and §5.3):

    get_position()            -> (x, y)         metres
    get_orientation()         -> theta          radians, normalised
    get_velocity()            -> (v, omega)
    get_sensor_data()         -> list[float]    distances, metres
    get_goal_position()       -> (gx, gy)
    distance_to_goal()        -> float
    get_time()                -> float          simulated seconds
    set_velocity(linear, angular)
    log(message)
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Tuple


class RobotAPI:
    """Read-only-on-state, write-only-via-set_velocity facade."""

    def __init__(
        self,
        robot: Any,
        environment: Any,
        get_sim_time: Optional[Any] = None,
        console: Optional[Any] = None,
    ):
        """
        Args:
            robot: The simulated Robot instance.
            environment: The Environment (gives goal & obstacles).
            get_sim_time: Optional zero-arg callable returning the engine's
                simulated time. We accept a callable rather than a back-ref
                to avoid cycles.
            console: Optional object with ``write(text)`` /
                ``write_error(text)`` methods used by ``log()``. Falls back
                to stdout if not supplied.
        """
        self._robot = robot
        self._env = environment
        self._get_time = get_sim_time
        self._console = console

    # ------------------------------------------------------------------
    # Read-only state queries
    # ------------------------------------------------------------------
    def get_position(self) -> Tuple[float, float]:
        """Current (x, y) in world metres."""
        return float(self._robot.state["x"]), float(self._robot.state["y"])

    def get_orientation(self) -> float:
        """Current heading in radians, normalised to [-pi, pi]."""
        return float(self._robot.state["theta"])

    def get_velocity(self) -> Tuple[float, float]:
        """Current (linear, angular) velocities."""
        return (
            float(self._robot.state["v"]),
            float(self._robot.state["omega"]),
        )

    def get_sensor_data(self) -> List[float]:
        """Latest distance readings, one per ray (metres)."""
        return list(self._robot.distance_sensor.get_distances())

    def get_sensor_count(self) -> int:
        """Number of distance rays (matches len(get_sensor_data()))."""
        return int(self._robot.distance_sensor.num_rays)

    def get_sensor_max_range(self) -> float:
        """Maximum sensing distance (a reading equal to this means 'no hit')."""
        return float(self._robot.distance_sensor.max_range)

    def get_goal_position(self) -> Tuple[float, float]:
        """Goal coordinates."""
        gx, gy = self._env.goal
        return float(gx), float(gy)

    def distance_to_goal(self) -> float:
        """Euclidean distance from robot to goal."""
        gx, gy = self.get_goal_position()
        x, y = self.get_position()
        return math.hypot(gx - x, gy - y)

    def angle_to_goal(self) -> float:
        """Bearing from the robot toward the goal in radians (-pi, pi]."""
        gx, gy = self.get_goal_position()
        x, y = self.get_position()
        return math.atan2(gy - y, gx - x)

    def get_time(self) -> float:
        """Simulated seconds since the simulation started."""
        if self._get_time is None:
            return 0.0
        try:
            return float(self._get_time())
        except Exception:
            return 0.0

    def is_collision(self) -> bool:
        """Whether the robot is currently in contact with an obstacle."""
        return bool(self._robot.collision_sensor.is_colliding())

    def get_world_size(self) -> Tuple[float, float]:
        """World bounds (width, height) in metres."""
        return float(self._env.width), float(self._env.height)

    # ------------------------------------------------------------------
    # Write side — the only way user code influences the robot.
    # ------------------------------------------------------------------
    def set_velocity(self, linear: float, angular: float) -> None:
        """
        Command the robot.

        Inputs are coerced to float and saturated to the robot's limits
        inside Robot.apply_control, so the API itself never raises on
        out-of-range values.
        """
        try:
            v = float(linear)
        except (TypeError, ValueError):
            v = 0.0
        try:
            w = float(angular)
        except (TypeError, ValueError):
            w = 0.0
        # NaN/inf protection.
        if not math.isfinite(v):
            v = 0.0
        if not math.isfinite(w):
            w = 0.0
        self._robot.apply_control(v, w)

    # ------------------------------------------------------------------
    # User-facing console
    # ------------------------------------------------------------------
    def log(self, message: Any) -> None:
        """
        Send a message to the user console.

        Accepts anything; we stringify it. If no console is wired up,
        falls back to stdout so headless contexts (smoke tests) still see
        the output.
        """
        text = f"[t={self.get_time():.2f}] {message}"
        if self._console is not None and hasattr(self._console, "write"):
            try:
                self._console.write(text)
                return
            except Exception:
                pass
        print(text)
