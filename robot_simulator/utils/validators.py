"""
Input Validators

Validate user inputs and configuration.
"""

from typing import Any


def validate_positive_float(value: Any, name: str = "value") -> float:
    """
    Validate that value is a positive float.

    Args:
        value: Value to validate
        name: Parameter name for error message

    Returns:
        Validated float

    Raises:
        ValueError: If validation fails
    """
    try:
        val = float(value)
        if val <= 0:
            raise ValueError(f"{name} must be positive")
        return val
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a positive number")


def validate_range(value: Any, min_val: float, max_val: float, name: str = "value") -> float:
    """
    Validate that value is in range.

    Args:
        value: Value to validate
        min_val: Minimum value
        max_val: Maximum value
        name: Parameter name

    Returns:
        Validated float

    Raises:
        ValueError: If out of range
    """
    try:
        val = float(value)
        if not (min_val <= val <= max_val):
            raise ValueError(f"{name} must be between {min_val} and {max_val}")
        return val
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid {name}: {e}")


def validate_position(x: Any, y: Any, bounds: tuple) -> tuple:
    """
    Validate position within bounds.

    Args:
        x: X coordinate
        y: Y coordinate
        bounds: (min_x, min_y, max_x, max_y)

    Returns:
        (x, y) tuple

    Raises:
        ValueError: If out of bounds
    """
    min_x, min_y, max_x, max_y = bounds

    x = float(x)
    y = float(y)

    if not (min_x <= x <= max_x):
        raise ValueError(f"X position {x} out of bounds [{min_x}, {max_x}]")
    if not (min_y <= y <= max_y):
        raise ValueError(f"Y position {y} out of bounds [{min_y}, {max_y}]")

    return (x, y)
