"""
Map Loader

Load environment maps from JSON files.
"""

import json
from typing import Dict, Any
from .map import Environment
from .obstacles import RectangleObstacle


class MapLoader:
    """
    Load maps from JSON configuration files.
    """

    @staticmethod
    def load(filepath: str) -> Environment:
        """
        Load map from JSON file.

        Expected JSON format:
        {
            "name": "Map Name",
            "width": 10.0,
            "height": 10.0,
            "obstacles": [
                {"type": "rectangle", "x": 2.0, "y": 2.0, "width": 1.0, "height": 3.0}
            ],
            "start_position": {"x": 1.0, "y": 1.0, "theta": 0.0},
            "goal_position": {"x": 9.0, "y": 9.0}
        }

        Args:
            filepath: Path to JSON file

        Returns:
            Environment object

        Raises:
            ValueError: If JSON is invalid
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            # Validate
            if not MapLoader.validate(data):
                raise ValueError("Invalid map format")

            # Create environment
            env = Environment(
                width=data.get('width', 10.0),
                height=data.get('height', 10.0),
                name=data.get('name', 'Unnamed Map')
            )

            # Clear default obstacles
            env.clear_obstacles()

            # Add obstacles
            for obs_data in data.get('obstacles', []):
                obstacle = MapLoader._create_obstacle(obs_data)
                if obstacle:
                    env.add_obstacle(obstacle)

            # Re-add boundaries
            env._create_boundaries()

            # Set start position
            if 'start_position' in data:
                start = data['start_position']
                env.set_start_position(
                    start.get('x', 1.0),
                    start.get('y', 1.0),
                    start.get('theta', 0.0)
                )

            # Set goal
            if 'goal_position' in data:
                goal = data['goal_position']
                env.set_goal(goal.get('x', 9.0), goal.get('y', 9.0))

            return env

        except FileNotFoundError:
            raise ValueError(f"Map file not found: {filepath}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON in file: {filepath}")

    @staticmethod
    def save(environment: Environment, filepath: str) -> None:
        """
        Save environment to JSON file.

        Args:
            environment: Environment to save
            filepath: Output file path
        """
        # Build JSON structure
        data = {
            'name': environment.name,
            'width': environment.width,
            'height': environment.height,
            'obstacles': [],
            'start_position': {
                'x': environment.start_position[0],
                'y': environment.start_position[1],
                'theta': environment.start_position[2]
            },
            'goal_position': {
                'x': environment.goal[0],
                'y': environment.goal[1]
            }
        }

        # Add obstacles (skip boundaries)
        for obstacle in environment.obstacles:
            if isinstance(obstacle, RectangleObstacle):
                # Skip thin walls (boundaries)
                if obstacle.width > 0.2 and obstacle.height > 0.2:
                    data['obstacles'].append({
                        'type': 'rectangle',
                        'x': obstacle.x,
                        'y': obstacle.y,
                        'width': obstacle.width,
                        'height': obstacle.height
                    })

        # Write to file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def validate(data: Dict[str, Any]) -> bool:
        """
        Validate map data structure.

        Args:
            data: Map dictionary

        Returns:
            True if valid
        """
        required_keys = ['width', 'height']
        for key in required_keys:
            if key not in data:
                return False

        # Validate obstacles
        if 'obstacles' in data:
            if not isinstance(data['obstacles'], list):
                return False

        return True

    @staticmethod
    def _create_obstacle(obs_data: Dict[str, Any]):
        """
        Create obstacle from dictionary.

        Args:
            obs_data: Obstacle data dictionary

        Returns:
            Obstacle object or None
        """
        obs_type = obs_data.get('type', 'rectangle')

        if obs_type == 'rectangle':
            return RectangleObstacle(
                x=obs_data.get('x', 0.0),
                y=obs_data.get('y', 0.0),
                width=obs_data.get('width', 1.0),
                height=obs_data.get('height', 1.0)
            )

        return None
