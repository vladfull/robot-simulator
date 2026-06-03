"""
Environment Module

Contains map representation, obstacles, and map loading.
"""

from .map import Environment
from .obstacles import Obstacle, RectangleObstacle
from .loader import MapLoader

__all__ = ['Environment', 'Obstacle', 'RectangleObstacle', 'MapLoader']
