"""
ScriptedController

Adapter that lets the SimulationEngine drive a user-written
``control_step(robot)`` script. It is the bridge between two worlds:

  * Engine side: expects a Controller with ``compute_control(state, env, goal)``
    returning ``(v, omega)``.
  * User side: writes ``control_step(robot)`` that queries a RobotAPI and
    issues ``robot.set_velocity(v, w)``.

The trick is order of operations. A normal Controller computes velocities
*before* the engine applies them. Here, the user's ``control_step`` writes
the velocity directly through ``api.set_velocity`` (which calls
``Robot.apply_control``). So our ``compute_control`` runs the user code
and then *reads back* the freshly-applied velocities so the engine's
``apply_control(v, omega)`` line is a no-op (it re-sets the same values).
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from api.robot_api import RobotAPI
from execution.execution_engine import ExecutionEngine

from .base import Controller


class ScriptedController(Controller):
    """
    Wraps an ExecutionEngine + a Robot reference behind the Controller API.
    """

    def __init__(
        self,
        execution_engine: ExecutionEngine,
        robot: Any,
        environment: Any,
        get_sim_time: Any = None,
        console: Any = None,
    ):
        super().__init__(name="User Code")
        self._engine = execution_engine
        self._robot = robot
        self._environment = environment
        self._api = RobotAPI(
            robot=robot,
            environment=environment,
            get_sim_time=get_sim_time,
            console=console,
        )
        self._last_result: str | None = None

    # Allow the host to swap robot/environment without rebuilding controller.
    def rebind(
        self,
        robot: Any,
        environment: Any,
        get_sim_time: Any = None,
        console: Any = None,
    ) -> None:
        self._robot = robot
        self._environment = environment
        self._api = RobotAPI(
            robot=robot,
            environment=environment,
            get_sim_time=get_sim_time,
            console=console,
        )

    # ------------------------------------------------------------------
    # Controller interface
    # ------------------------------------------------------------------
    def compute_control(
        self,
        robot_state: Dict[str, float],
        environment: Any,
        goal: Tuple[float, float],
    ) -> Tuple[float, float]:
        """Run user code; return whatever velocity it set."""
        self._last_result = self._engine.execute_step(self._api)
        return float(self._robot.state.get("v", 0.0)), float(
            self._robot.state.get("omega", 0.0)
        )

    def reset(self) -> None:
        """Forget transient error state."""
        self._engine.reset()
        # Stop the robot at reset.
        self._robot.apply_control(0.0, 0.0)

    def get_telemetry(self) -> Dict[str, Any]:
        return {
            "is_loaded": self._engine.is_loaded,
            "last_result": self._last_result,
            "last_error": self._engine.get_last_error(),
        }
