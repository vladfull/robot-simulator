"""
Robot Controllers Module

This module provides various control algorithms for the robot:
- PID Controller
- A* Path Planner
- Q-Learning Agent
- Manual Control
"""

from .base import Controller
from .pid import PIDController
from .astar import AStarPlanner
from .qlearning import QLearningAgent
from .manual import ManualController

__all__ = [
    'Controller',
    'PIDController',
    'AStarPlanner',
    'QLearningAgent',
    'ManualController'
]
