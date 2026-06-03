"""
Math Utilities

Common mathematical functions for robotics.
"""

import numpy as np
from typing import Tuple


def normalize_angle(angle: float) -> float:
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


def distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Calculate Euclidean distance between two points.

    Args:
        p1: First point (x, y)
        p2: Second point (x, y)

    Returns:
        Distance
    """
    return np.hypot(p2[0] - p1[0], p2[1] - p1[1])


def angle_between_points(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """
    Calculate angle from p1 to p2.

    Args:
        p1: Start point (x, y)
        p2: End point (x, y)

    Returns:
        Angle in radians
    """
    return np.arctan2(p2[1] - p1[1], p2[0] - p1[0])


def rotate_point(point: Tuple[float, float], angle: float) -> Tuple[float, float]:
    """
    Rotate a point around origin.

    Args:
        point: Point (x, y)
        angle: Rotation angle in radians

    Returns:
        Rotated point
    """
    x, y = point
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)

    x_rot = x * cos_a - y * sin_a
    y_rot = x * sin_a + y * cos_a

    return (x_rot, y_rot)


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp value to range.

    Args:
        value: Input value
        min_val: Minimum value
        max_val: Maximum value

    Returns:
        Clamped value
    """
    return max(min_val, min(value, max_val))
