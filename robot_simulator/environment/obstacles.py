"""
Obstacle Classes

Defines different types of obstacles.
"""

from abc import ABC, abstractmethod
from typing import Tuple, List


class Obstacle(ABC):
    """
    Abstract base class for obstacles.
    """

    def __init__(self, x: float, y: float):
        """
        Initialize obstacle.

        Args:
            x: Center X position
            y: Center Y position
        """
        self.x = x
        self.y = y

    @abstractmethod
    def contains_point(self, x: float, y: float) -> bool:
        """
        Check if point is inside obstacle.

        Args:
            x: Point X
            y: Point Y

        Returns:
            True if point is inside
        """
        pass

    @abstractmethod
    def get_vertices(self) -> List[Tuple[float, float]]:
        """
        Get obstacle vertices for rendering.

        Returns:
            List of (x, y) vertices
        """
        pass


class RectangleObstacle(Obstacle):
    """
    Rectangular obstacle.
    """

    def __init__(self, x: float, y: float, width: float, height: float):
        """
        Initialize rectangle obstacle.

        Args:
            x: Center X position
            y: Center Y position
            width: Rectangle width
            height: Rectangle height
        """
        super().__init__(x, y)
        self.width = width
        self.height = height

    def contains_point(self, x: float, y: float) -> bool:
        """
        Check if point is inside rectangle.

        Args:
            x: Point X
            y: Point Y

        Returns:
            True if inside
        """
        half_width = self.width / 2
        half_height = self.height / 2

        return (
            self.x - half_width <= x <= self.x + half_width and
            self.y - half_height <= y <= self.y + half_height
        )

    def get_vertices(self) -> List[Tuple[float, float]]:
        """
        Get rectangle corners.

        Returns:
            List of 4 corner points
        """
        half_width = self.width / 2
        half_height = self.height / 2

        return [
            (self.x - half_width, self.y - half_height),  # Bottom-left
            (self.x + half_width, self.y - half_height),  # Bottom-right
            (self.x + half_width, self.y + half_height),  # Top-right
            (self.x - half_width, self.y + half_height),  # Top-left
        ]

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """
        Get bounding box.

        Returns:
            (min_x, min_y, max_x, max_y)
        """
        half_width = self.width / 2
        half_height = self.height / 2

        return (
            self.x - half_width,
            self.y - half_height,
            self.x + half_width,
            self.y + half_height
        )
