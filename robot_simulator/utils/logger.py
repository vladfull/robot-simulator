"""
Data Logger

Logs simulation data to CSV files.
"""

import csv
from typing import Dict, Any, List


class DataLogger:
    """
    Logger for simulation data.

    Records robot state and control data to CSV.
    """

    def __init__(self):
        """Initialize logger."""
        self.data: List[Dict[str, Any]] = []

        # CSV columns
        self.columns = [
            'timestamp',
            'x',
            'y',
            'theta',
            'v',
            'omega',
            'control_v',
            'control_omega',
            'collision'
        ]

    def log(self, entry: Dict[str, Any]) -> None:
        """
        Log a data entry.

        Args:
            entry: Dictionary with data fields
        """
        self.data.append(entry.copy())

    def clear(self) -> None:
        """Clear all logged data."""
        self.data = []

    def get_data(self) -> List[Dict[str, Any]]:
        """
        Get all logged data.

        Returns:
            List of data entries
        """
        return self.data.copy()

    def save_to_csv(self, filepath: str) -> None:
        """
        Save logged data to CSV file.

        Args:
            filepath: Output file path
        """
        if not self.data:
            print("No data to save")
            return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.columns)
                writer.writeheader()

                for entry in self.data:
                    # Write only columns that exist
                    row = {col: entry.get(col, '') for col in self.columns}
                    writer.writerow(row)

            print(f"Data saved to {filepath} ({len(self.data)} entries)")

        except Exception as e:
            print(f"Error saving data: {e}")

    def load_from_csv(self, filepath: str) -> bool:
        """
        Load data from CSV file.

        Args:
            filepath: Input file path

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                self.data = list(reader)

            print(f"Loaded {len(self.data)} entries from {filepath}")
            return True

        except Exception as e:
            print(f"Error loading data: {e}")
            return False

    def get_trajectory(self) -> List[tuple]:
        """
        Extract trajectory from logged data.

        Returns:
            List of (x, y) tuples
        """
        return [(float(entry['x']), float(entry['y'])) for entry in self.data if 'x' in entry and 'y' in entry]

    def get_statistics(self) -> Dict[str, float]:
        """
        Calculate statistics from logged data.

        Returns:
            Dictionary with statistics
        """
        if not self.data:
            return {}

        # Calculate path length
        path_length = 0.0
        for i in range(1, len(self.data)):
            x1, y1 = float(self.data[i-1]['x']), float(self.data[i-1]['y'])
            x2, y2 = float(self.data[i]['x']), float(self.data[i]['y'])
            path_length += ((x2 - x1)**2 + (y2 - y1)**2)**0.5

        # Duration
        duration = float(self.data[-1]['timestamp']) if self.data else 0.0

        # Collision count
        collision_count = sum(1 for entry in self.data if entry.get('collision', False))

        return {
            'path_length': path_length,
            'duration': duration,
            'collision_count': collision_count,
            'num_steps': len(self.data)
        }
