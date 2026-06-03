"""
PID Controller Implementation

Implements a PID controller for robot heading stabilization
and trajectory following.
"""

import numpy as np
from typing import Tuple, Dict, Any
from .base import Controller


class PIDController(Controller):
    """
    PID (Proportional-Integral-Derivative) Controller.

    Controls the robot's angular velocity to maintain heading or follow a path.
    """

    def __init__(
        self,
        kp: float = 2.0,
        ki: float = 0.1,
        kd: float = 0.5,
        max_linear_velocity: float = 1.0
    ):
        """
        Initialize PID controller.

        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            max_linear_velocity: Maximum forward speed (m/s)
        """
        super().__init__(name="PID Controller")

        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_linear_velocity = max_linear_velocity

        # Internal state
        self.integral = 0.0
        self.previous_error = 0.0
        self.telemetry_data = {
            'error': [],
            'p_term': [],
            'i_term': [],
            'd_term': [],
            'output': [],
            'timestamp': []
        }

    def compute_control(
        self,
        robot_state: Dict[str, float],
        environment: Any,
        goal: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Compute PID control based on heading error to goal.

        Strategy:
        1. Calculate desired heading to goal
        2. Compute heading error
        3. Apply PID control to angular velocity
        4. Set constant forward velocity

        Args:
            robot_state: Current robot state
            environment: Environment (not used in basic PID)
            goal: Target (x, y) position

        Returns:
            (v, omega): Linear and angular velocities
        """
        # Extract robot position and orientation
        x, y = robot_state['x'], robot_state['y']
        theta = robot_state['theta']

        # Calculate desired heading to goal
        goal_x, goal_y = goal
        desired_theta = np.arctan2(goal_y - y, goal_x - x)

        # Calculate heading error (normalized to [-pi, pi])
        error = self._normalize_angle(desired_theta - theta)

        # PID terms
        p_term = self.kp * error
        self.integral += error
        i_term = self.ki * self.integral
        d_term = self.kd * (error - self.previous_error)

        # Control output (angular velocity)
        omega = p_term + i_term + d_term

        # Clamp angular velocity
        omega = np.clip(omega, -2.0, 2.0)

        # Linear velocity (constant forward speed)
        v = self.max_linear_velocity

        # Reduce speed when turning sharply
        if abs(error) > np.pi / 4:
            v *= 0.5

        # Update state
        self.previous_error = error

        # Store telemetry
        self.telemetry_data['error'].append(error)
        self.telemetry_data['p_term'].append(p_term)
        self.telemetry_data['i_term'].append(i_term)
        self.telemetry_data['d_term'].append(d_term)
        self.telemetry_data['output'].append(omega)

        return v, omega

    def reset(self) -> None:
        """Reset PID internal state."""
        self.integral = 0.0
        self.previous_error = 0.0
        self.telemetry_data = {
            'error': [],
            'p_term': [],
            'i_term': [],
            'd_term': [],
            'output': [],
            'timestamp': []
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """
        Get PID telemetry data.

        Returns:
            Dictionary with error, P/I/D terms, and output
        """
        return self.telemetry_data

    def set_parameters(self, params: Dict[str, Any]) -> None:
        """
        Update PID gains.

        Args:
            params: Dictionary with keys 'kp', 'ki', 'kd'
        """
        if 'kp' in params:
            self.kp = params['kp']
        if 'ki' in params:
            self.ki = params['ki']
        if 'kd' in params:
            self.kd = params['kd']

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """
        Normalize angle to [-pi, pi] range.

        Args:
            angle: Angle in radians

        Returns:
            Normalized angle
        """
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
