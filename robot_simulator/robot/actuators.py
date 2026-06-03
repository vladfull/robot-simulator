"""
Robot Actuators

Implements differential drive actuator.
"""

import numpy as np
from typing import Tuple


class DifferentialDrive:
    """
    Differential drive actuator.

    Converts (v, omega) to left/right wheel velocities.
    """

    def __init__(self, wheel_radius: float, wheel_base: float):
        """
        Initialize differential drive.

        Args:
            wheel_radius: Wheel radius in meters
            wheel_base: Distance between wheels in meters
        """
        self.wheel_radius = wheel_radius
        self.wheel_base = wheel_base

        # Wheel velocities (rad/s)
        self.left_wheel_velocity = 0.0
        self.right_wheel_velocity = 0.0

        # Velocity limits
        self.max_wheel_velocity = 20.0  # rad/s

    def set_velocities(self, v: float, omega: float) -> None:
        """
        Set robot velocities and compute wheel velocities.

        Differential drive kinematics:
        v_left = (v - omega * L/2) / r
        v_right = (v + omega * L/2) / r

        where:
        - v: linear velocity
        - omega: angular velocity
        - L: wheel base
        - r: wheel radius

        Args:
            v: Linear velocity (m/s)
            omega: Angular velocity (rad/s)
        """
        # Compute wheel velocities
        v_left = (v - omega * self.wheel_base / 2) / self.wheel_radius
        v_right = (v + omega * self.wheel_base / 2) / self.wheel_radius

        # Clamp to limits
        self.left_wheel_velocity = np.clip(
            v_left,
            -self.max_wheel_velocity,
            self.max_wheel_velocity
        )
        self.right_wheel_velocity = np.clip(
            v_right,
            -self.max_wheel_velocity,
            self.max_wheel_velocity
        )

    def get_wheel_velocities(self) -> Tuple[float, float]:
        """
        Get current wheel velocities.

        Returns:
            (left_velocity, right_velocity) in rad/s
        """
        return (self.left_wheel_velocity, self.right_wheel_velocity)

    def compute_robot_velocities(self) -> Tuple[float, float]:
        """
        Compute robot (v, omega) from wheel velocities (inverse kinematics).

        Returns:
            (v, omega): Linear and angular velocities
        """
        # Inverse kinematics
        v = (self.right_wheel_velocity + self.left_wheel_velocity) * self.wheel_radius / 2
        omega = (self.right_wheel_velocity - self.left_wheel_velocity) * self.wheel_radius / self.wheel_base

        return (v, omega)
