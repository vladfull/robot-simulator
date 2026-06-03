"""
Base Controller Class

All robot controllers must inherit from this abstract base class.
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any


class Controller(ABC):
    """
    Abstract base class for all robot controllers.

    Defines the interface that all control algorithms must implement.
    Uses the Strategy pattern to allow interchangeable controllers.
    """

    def __init__(self, name: str = "BaseController"):
        """
        Initialize the controller.

        Args:
            name: Human-readable name for this controller
        """
        self.name = name
        self.telemetry_data = {}

    @abstractmethod
    def compute_control(
        self,
        robot_state: Dict[str, float],
        environment: Any,
        goal: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Compute control commands for the robot.

        Args:
            robot_state: Dictionary containing:
                - x: float (position x in meters)
                - y: float (position y in meters)
                - theta: float (orientation in radians)
                - v: float (linear velocity in m/s)
                - omega: float (angular velocity in rad/s)
            environment: Environment object containing map and obstacles
            goal: Target position as (x, y) tuple

        Returns:
            Tuple of (v, omega):
                - v: linear velocity command (m/s)
                - omega: angular velocity command (rad/s)
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Reset the controller's internal state.

        Called when:
        - Starting a new simulation
        - Switching controllers
        - Resetting the environment
        """
        pass

    @abstractmethod
    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get telemetry data for visualization and logging.

        Returns:
            Dictionary containing controller-specific telemetry data.
            Common keys might include:
                - error: current error value
                - output: control output
                - timestamp: current time
        """
        pass

    def get_name(self) -> str:
        """
        Get the controller name.

        Returns:
            Controller name string
        """
        return self.name

    def set_parameters(self, params: Dict[str, Any]) -> None:
        """
        Update controller parameters (optional, can be overridden).

        Args:
            params: Dictionary of parameter names and values
        """
        pass
