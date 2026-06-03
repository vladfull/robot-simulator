"""
Environment/Map Class

Represents the simulation environment with obstacles and goal.
"""

from typing import List, Tuple
from .obstacles import Obstacle


class Environment:
    """
    Simulation environment containing map, obstacles, and goal.
    """

    def __init__(
        self,
        width: float = 10.0,
        height: float = 10.0,
        name: str = "Default Map"
    ):
        """
        Initialize environment.

        Args:
            width: Map width in meters
            height: Map height in meters
            name: Map name
        """
        self.name = name
        self.width = width
        self.height = height

        # Obstacles
        self.obstacles: List[Obstacle] = []

        # Start and goal positions
        self.start_position: Tuple[float, float, float] = (1.0, 1.0, 0.0)  # (x, y, theta)
        self.goal: Tuple[float, float] = (9.0, 9.0)

        # Add boundary walls
        self._create_boundaries()

    def add_obstacle(self, obstacle: Obstacle) -> None:
        """
        Add an obstacle to the environment.

        Args:
            obstacle: Obstacle object
        """
        self.obstacles.append(obstacle)

    def remove_obstacle(self, obstacle: Obstacle) -> None:
        """
        Remove an obstacle from the environment.

        Args:
            obstacle: Obstacle to remove
        """
        if obstacle in self.obstacles:
            self.obstacles.remove(obstacle)

    def clear_obstacles(self) -> None:
        """Remove all obstacles (except boundaries)."""
        self.obstacles = []
        self._create_boundaries()

    def set_start_position(self, x: float, y: float, theta: float = 0.0) -> None:
        """
        Set robot start position.

        Args:
            x: Start X position
            y: Start Y position
            theta: Start orientation (radians)
        """
        self.start_position = (x, y, theta)

    def set_goal(self, x: float, y: float) -> None:
        """
        Set goal position.

        Args:
            x: Goal X position
            y: Goal Y position
        """
        self.goal = (x, y)

    def get_obstacles(self) -> List[Obstacle]:
        """
        Get all obstacles.

        Returns:
            List of obstacles
        """
        return self.obstacles.copy()

    def is_point_in_obstacle(self, x: float, y: float) -> bool:
        """
        Check if a point collides with any obstacle.

        Args:
            x: Point X coordinate
            y: Point Y coordinate

        Returns:
            True if point is inside an obstacle
        """
        for obstacle in self.obstacles:
            if obstacle.contains_point(x, y):
                return True
        return False

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """
        Get environment bounds.

        Returns:
            (min_x, min_y, max_x, max_y)
        """
        return (0.0, 0.0, self.width, self.height)

    def _create_boundaries(self) -> None:
        """Create boundary walls around the map."""
        from .obstacles import RectangleObstacle

        wall_thickness = 0.1

        # Top wall
        self.obstacles.append(RectangleObstacle(
            x=self.width / 2,
            y=self.height + wall_thickness / 2,
            width=self.width,
            height=wall_thickness
        ))

        # Bottom wall
        self.obstacles.append(RectangleObstacle(
            x=self.width / 2,
            y=-wall_thickness / 2,
            width=self.width,
            height=wall_thickness
        ))

        # Left wall
        self.obstacles.append(RectangleObstacle(
            x=-wall_thickness / 2,
            y=self.height / 2,
            width=wall_thickness,
            height=self.height
        ))

        # Right wall
        self.obstacles.append(RectangleObstacle(
            x=self.width + wall_thickness / 2,
            y=self.height / 2,
            width=wall_thickness,
            height=self.height
        ))
