"""
Robot Class

Main robot model with differential drive kinematics.
"""

import numpy as np
from typing import Dict, Tuple, List, Any
from .sensors import DistanceSensor, CollisionSensor
from .actuators import DifferentialDrive


class Robot:
    """
    Differential drive mobile robot.

    Manages robot state, sensors, and actuators.
    Integrates with PyBox2D for physics simulation.
    """

    def __init__(
        self,
        initial_position: Tuple[float, float] = (1.0, 1.0),
        initial_orientation: float = 0.0,
        width: float = 0.3,
        length: float = 0.4,
        wheel_radius: float = 0.05,
        wheel_base: float = 0.25,
        mass: float = 5.0
    ):
        """
        Initialize robot.

        Args:
            initial_position: Starting (x, y) in meters
            initial_orientation: Starting angle in radians
            width: Robot width in meters
            length: Robot length in meters
            wheel_radius: Wheel radius in meters
            wheel_base: Distance between wheels in meters
            mass: Robot mass in kg
        """
        # Geometry
        self.width = width
        self.length = length
        self.wheel_radius = wheel_radius
        self.wheel_base = wheel_base
        self.mass = mass

        # State variables
        self.state: Dict[str, float] = {
            'x': initial_position[0],
            'y': initial_position[1],
            'theta': initial_orientation,
            'v': 0.0,        # Linear velocity
            'omega': 0.0     # Angular velocity
        }

        # Velocity limits
        self.max_linear_velocity = 1.0  # m/s
        self.max_angular_velocity = 2.0  # rad/s

        # Sensors
        self.distance_sensor = DistanceSensor(num_rays=16, max_range=5.0)
        self.collision_sensor = CollisionSensor()

        # Actuators
        self.drive = DifferentialDrive(wheel_radius, wheel_base)

        # Physics body / world (set by simulation engine).
        self.body = None
        self.physics: Any = None

        # Trajectory history
        self.trajectory: List[Tuple[float, float]] = []

    def attach_physics(self, physics_world: Any) -> None:
        """
        Bind the robot (and its sensors) to a PhysicsWorld.

        The world becomes the source of truth for ray-cast queries and
        collision reporting; the kinematic body is created lazily here so
        that callers can reuse Robot instances across map changes.
        """
        self.physics = physics_world
        self.body = physics_world.create_robot_body(
            position=(self.state['x'], self.state['y']),
            angle=self.state['theta'],
            width=self.width,
            length=self.length,
        )
        self.distance_sensor.attach_physics(physics_world)
        self.collision_sensor.attach_physics(physics_world)

    def get_state(self) -> Dict[str, float]:
        """
        Get current robot state.

        Returns:
            State dictionary
        """
        return self.state.copy()

    def set_position(self, x: float, y: float, theta: float) -> None:
        """
        Set robot position (for initialization/reset).

        Args:
            x: Position X
            y: Position Y
            theta: Orientation
        """
        self.state['x'] = x
        self.state['y'] = y
        self.state['theta'] = theta
        self.state['v'] = 0.0
        self.state['omega'] = 0.0
        if self.physics is not None:
            self.physics.set_robot_pose(x, y, theta)
            self.physics.reset_collisions()

    def apply_control(self, v: float, omega: float) -> None:
        """
        Apply velocity control commands.

        Args:
            v: Linear velocity (m/s)
            omega: Angular velocity (rad/s)
        """
        # Clamp to limits
        v = np.clip(v, -self.max_linear_velocity, self.max_linear_velocity)
        omega = np.clip(omega, -self.max_angular_velocity, self.max_angular_velocity)

        self.state['v'] = v
        self.state['omega'] = omega

        # Update actuators
        self.drive.set_velocities(v, omega)

    def update(self, dt: float) -> None:
        """
        Update robot state (kinematics integration).

        Uses differential drive kinematics:
        dx/dt = v * cos(theta)
        dy/dt = v * sin(theta)
        dtheta/dt = omega

        Args:
            dt: Time step in seconds
        """
        v = self.state['v']
        omega = self.state['omega']
        theta = self.state['theta']

        # Update position
        self.state['x'] += v * np.cos(theta) * dt
        self.state['y'] += v * np.sin(theta) * dt
        self.state['theta'] += omega * dt

        # Normalize angle to [-pi, pi]
        self.state['theta'] = self._normalize_angle(self.state['theta'])

        # Sync physics body so ray queries see the new pose.
        if self.physics is not None:
            self.physics.set_robot_pose(
                self.state['x'], self.state['y'], self.state['theta']
            )

        # Store trajectory point
        self.trajectory.append((self.state['x'], self.state['y']))

    def update_sensors(self, environment: Any) -> None:
        """
        Update all sensor measurements.

        Args:
            environment: Environment object for ray casting
        """
        self.distance_sensor.measure(self.state, environment)
        self.collision_sensor.update(self.body)

    def get_sensor_data(self) -> Dict[str, Any]:
        """
        Get all sensor readings.

        Returns:
            Dictionary with sensor data
        """
        return {
            'distances': self.distance_sensor.get_distances(),
            'collision': self.collision_sensor.is_colliding()
        }

    def reset_trajectory(self) -> None:
        """Clear trajectory history."""
        self.trajectory = []

    def get_trajectory(self) -> List[Tuple[float, float]]:
        """
        Get robot trajectory.

        Returns:
            List of (x, y) positions
        """
        return self.trajectory.copy()

    def get_corners(self) -> List[Tuple[float, float]]:
        """
        Get robot corner positions (for visualization).

        Returns:
            List of 4 corner points in world coordinates
        """
        x, y, theta = self.state['x'], self.state['y'], self.state['theta']

        # Local corners (robot frame)
        half_width = self.width / 2
        half_length = self.length / 2

        local_corners = [
            (half_length, half_width),
            (half_length, -half_width),
            (-half_length, -half_width),
            (-half_length, half_width)
        ]

        # Transform to world frame
        cos_theta = np.cos(theta)
        sin_theta = np.sin(theta)

        world_corners = []
        for lx, ly in local_corners:
            wx = x + lx * cos_theta - ly * sin_theta
            wy = y + lx * sin_theta + ly * cos_theta
            world_corners.append((wx, wy))

        return world_corners

    def get_front_position(self) -> Tuple[float, float]:
        """
        Get position of robot front (for direction indicator).

        Returns:
            (x, y) of front center point
        """
        x, y, theta = self.state['x'], self.state['y'], self.state['theta']
        front_x = x + (self.length / 2) * np.cos(theta)
        front_y = y + (self.length / 2) * np.sin(theta)
        return (front_x, front_y)

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
