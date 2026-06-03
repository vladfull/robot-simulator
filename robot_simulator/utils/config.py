"""
Configuration Manager

Load and save application configuration.
"""

import json
from typing import Dict, Any


class Config:
    """
    Configuration manager for application settings.
    """

    DEFAULT_CONFIG = {
        'simulation': {
            'dt': 0.02,
            'max_episode_time': 120.0,
            'fps': 50
        },
        'robot': {
            'width': 0.3,
            'length': 0.4,
            'wheel_radius': 0.05,
            'wheel_base': 0.25,
            'mass': 5.0,
            'max_linear_velocity': 1.0,
            'max_angular_velocity': 2.0
        },
        'sensors': {
            'num_distance_rays': 16,
            'max_sensor_range': 5.0
        },
        'controllers': {
            'pid': {
                'kp': 2.0,
                'ki': 0.1,
                'kd': 0.5
            },
            'astar': {
                'grid_resolution': 0.2
            },
            'qlearning': {
                'learning_rate': 0.1,
                'discount_factor': 0.95,
                'epsilon': 1.0,
                'epsilon_decay': 0.995,
                'epsilon_min': 0.01
            }
        },
        'ui': {
            'window_width': 1200,
            'window_height': 800,
            'simulation_view_width': 800,
            'simulation_view_height': 600
        }
    }

    def __init__(self):
        """Initialize configuration with defaults."""
        self.config = self.DEFAULT_CONFIG.copy()

    def load(self, filepath: str) -> bool:
        """
        Load configuration from JSON file.

        Args:
            filepath: Path to config file

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'r') as f:
                loaded_config = json.load(f)

            # Merge with defaults
            self._deep_update(self.config, loaded_config)
            return True

        except FileNotFoundError:
            print(f"Config file not found: {filepath}, using defaults")
            return False
        except json.JSONDecodeError:
            print(f"Invalid JSON in config file: {filepath}")
            return False

    def save(self, filepath: str) -> None:
        """
        Save configuration to JSON file.

        Args:
            filepath: Output file path
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"Configuration saved to {filepath}")
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get configuration value.

        Args:
            *keys: Nested keys (e.g., 'simulation', 'dt')
            default: Default value if not found

        Returns:
            Configuration value
        """
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys: str, value: Any) -> None:
        """
        Set configuration value.

        Args:
            *keys: Nested keys
            value: Value to set
        """
        config = self.config
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        config[keys[-1]] = value

    def _deep_update(self, base: Dict, update: Dict) -> None:
        """
        Deep update dictionary.

        Args:
            base: Base dictionary (modified in place)
            update: Update dictionary
        """
        for key, value in update.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value
