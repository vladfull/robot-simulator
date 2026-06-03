"""
Replay Engine

Load and replay simulation from log files.
"""

import csv
from typing import List, Dict, Any


class ReplayEngine:
    """
    Replay simulation from logged data.

    Loads CSV log and plays back robot motion.
    """

    def __init__(self):
        """Initialize replay engine."""
        self.log_data: List[Dict[str, Any]] = []
        self.current_index = 0
        self.is_playing = False

    def load_log(self, filepath: str) -> bool:
        """
        Load simulation log from CSV file.

        Args:
            filepath: Path to CSV log file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                self.log_data = list(reader)

            # Convert string values to floats
            for entry in self.log_data:
                for key in ['timestamp', 'x', 'y', 'theta', 'v', 'omega', 'control_v', 'control_omega']:
                    if key in entry:
                        entry[key] = float(entry[key])
                if 'collision' in entry:
                    entry['collision'] = entry['collision'].lower() == 'true'

            self.current_index = 0
            return True

        except Exception as e:
            print(f"Error loading log: {e}")
            return False

    def get_current_state(self) -> Dict[str, Any]:
        """
        Get state at current replay index.

        Returns:
            State dictionary
        """
        if 0 <= self.current_index < len(self.log_data):
            return self.log_data[self.current_index]
        return {}

    def step(self) -> bool:
        """
        Advance to next replay step.

        Returns:
            True if more data available, False if end reached
        """
        self.current_index += 1
        return self.current_index < len(self.log_data)

    def seek(self, index: int) -> None:
        """
        Jump to specific index.

        Args:
            index: Target index
        """
        self.current_index = max(0, min(index, len(self.log_data) - 1))

    def reset(self) -> None:
        """Reset to beginning."""
        self.current_index = 0

    def get_progress(self) -> float:
        """
        Get replay progress.

        Returns:
            Progress as fraction (0.0 - 1.0)
        """
        if len(self.log_data) == 0:
            return 0.0
        return self.current_index / len(self.log_data)

    def get_duration(self) -> float:
        """
        Get total duration of replay.

        Returns:
            Duration in seconds
        """
        if len(self.log_data) == 0:
            return 0.0
        return self.log_data[-1]['timestamp']
