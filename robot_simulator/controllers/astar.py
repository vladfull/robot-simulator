"""
A* Path Planning Algorithm

Implements grid-based A* pathfinding with obstacle avoidance.
"""

import numpy as np
import heapq
from typing import Tuple, Dict, Any, List, Optional
from .base import Controller


class AStarPlanner(Controller):
    """
    A* Path Planning Controller.

    Uses A* algorithm to find optimal path from start to goal,
    then follows waypoints using Pure Pursuit algorithm.
    """

    def __init__(
        self,
        grid_resolution: float = 0.2,
        max_velocity: float = 1.0,
        robot_radius: float = 0.25,
    ):
        """
        Initialize A* planner.

        Args:
            grid_resolution: Size of grid cells in meters.
            max_velocity: Maximum robot velocity (m/s).
            robot_radius: Half the robot's longest dimension; used to
                inflate obstacles so the planned path leaves clearance.
        """
        super().__init__(name="A* Path Planner")

        self.grid_resolution = grid_resolution
        self.max_velocity = max_velocity
        self.robot_radius = robot_radius

        self.path: List[Tuple[float, float]] = []
        self.current_waypoint_index = 0
        self.lookahead_distance = 0.5  # Pure Pursuit lookahead (meters)
        self._grid_origin = (0.0, 0.0)
        self._grid_shape = (0, 0)

        self.telemetry_data = {
            'path': [],
            'current_waypoint': None,
            'distance_to_goal': []
        }

    def compute_control(
        self,
        robot_state: Dict[str, float],
        environment: Any,
        goal: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Compute control using A* path planning + Pure Pursuit.

        Steps:
        1. If no path exists, compute path using A*
        2. Find current target waypoint (lookahead)
        3. Steer towards waypoint using Pure Pursuit
        4. Move to next waypoint when close enough

        Args:
            robot_state: Current robot state
            environment: Environment with obstacles
            goal: Target position

        Returns:
            (v, omega): Velocities
        """
        x, y = robot_state['x'], robot_state['y']
        theta = robot_state['theta']

        # Compute path if needed
        if not self.path:
            self.path = self._compute_astar_path(
                (x, y),
                goal,
                environment
            )
            self.current_waypoint_index = 0
            self.telemetry_data['path'] = self.path.copy()

        # Check if path is empty (no solution found)
        if not self.path:
            return 0.0, 0.0

        # Get current target waypoint
        target_waypoint = self._get_lookahead_waypoint((x, y))

        if target_waypoint is None:
            # Reached goal
            return 0.0, 0.0

        # Pure Pursuit control
        v, omega = self._pure_pursuit_control(
            (x, y, theta),
            target_waypoint
        )

        # Update telemetry
        self.telemetry_data['current_waypoint'] = target_waypoint
        distance_to_goal = np.hypot(goal[0] - x, goal[1] - y)
        self.telemetry_data['distance_to_goal'].append(distance_to_goal)

        return v, omega

    def _compute_astar_path(
        self,
        start: Tuple[float, float],
        goal: Tuple[float, float],
        environment: Any
    ) -> List[Tuple[float, float]]:
        """
        Compute path using A* algorithm.

        Args:
            start: Start position (x, y)
            goal: Goal position (x, y)
            environment: Environment object

        Returns:
            List of waypoints [(x, y), ...]
        """
        # Build occupancy grid first so we know its dimensions for clamping.
        grid = self._create_occupancy_grid(environment)
        gx, gy = grid.shape

        # Convert world coordinates to grid indices, clamped into bounds.
        start_grid = self._world_to_grid(start)
        goal_grid = self._world_to_grid(goal)
        start_grid = (max(0, min(gx - 1, start_grid[0])),
                      max(0, min(gy - 1, start_grid[1])))
        goal_grid = (max(0, min(gx - 1, goal_grid[0])),
                     max(0, min(gy - 1, goal_grid[1])))

        # Allow the planner to start/finish even if the cell falls inside an
        # inflated obstacle (e.g. start near a wall). Without this, A* would
        # be stuck before its first expansion.
        grid[start_grid] = 0
        grid[goal_grid] = 0

        # A* search
        open_set = []
        heapq.heappush(open_set, (0, start_grid))

        came_from = {}
        g_score = {start_grid: 0}
        f_score = {start_grid: self._heuristic(start_grid, goal_grid)}

        while open_set:
            current = heapq.heappop(open_set)[1]

            if current == goal_grid:
                # Reconstruct path
                path = self._reconstruct_path(came_from, current)
                # Convert back to world coordinates
                return [self._grid_to_world(p) for p in path]

            for neighbor in self._get_neighbors(current, grid):
                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal_grid)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        # No path found
        return []

    def _create_occupancy_grid(self, environment: Any) -> np.ndarray:
        """
        Create a binary occupancy grid from the environment.

        Each rectangle obstacle is rasterised onto the grid and inflated
        by the robot's radius so the planned path leaves enough clearance
        for the body to pass.

        Args:
            environment: Environment with .width, .height, .obstacles.

        Returns:
            2D numpy array shape (gx, gy) where 1 = blocked, 0 = free.
        """
        width = float(getattr(environment, "width", 10.0))
        height = float(getattr(environment, "height", 10.0))

        gx = max(1, int(np.ceil(width / self.grid_resolution)))
        gy = max(1, int(np.ceil(height / self.grid_resolution)))
        grid = np.zeros((gx, gy), dtype=np.int8)

        self._grid_origin = (0.0, 0.0)
        self._grid_shape = (gx, gy)

        inflate = self.robot_radius

        for obstacle in getattr(environment, "obstacles", []):
            ox = float(obstacle.x)
            oy = float(obstacle.y)
            ow = float(getattr(obstacle, "width", 0.0))
            oh = float(getattr(obstacle, "height", 0.0))

            min_x = ox - ow / 2 - inflate
            max_x = ox + ow / 2 + inflate
            min_y = oy - oh / 2 - inflate
            max_y = oy + oh / 2 + inflate

            i0 = max(0, int(np.floor(min_x / self.grid_resolution)))
            i1 = min(gx - 1, int(np.ceil(max_x / self.grid_resolution)) - 1)
            j0 = max(0, int(np.floor(min_y / self.grid_resolution)))
            j1 = min(gy - 1, int(np.ceil(max_y / self.grid_resolution)) - 1)
            if i0 <= i1 and j0 <= j1:
                grid[i0:i1 + 1, j0:j1 + 1] = 1

        return grid

    def _pure_pursuit_control(
        self,
        robot_pose: Tuple[float, float, float],
        target: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Pure Pursuit steering control.

        Args:
            robot_pose: (x, y, theta)
            target: Target waypoint (x, y)

        Returns:
            (v, omega): Velocities
        """
        x, y, theta = robot_pose
        target_x, target_y = target

        # Calculate angle to target
        angle_to_target = np.arctan2(target_y - y, target_x - x)
        angle_error = self._normalize_angle(angle_to_target - theta)

        # Compute angular velocity (proportional to angle error)
        omega = 2.0 * angle_error

        # Linear velocity (reduce when turning)
        v = self.max_velocity
        if abs(angle_error) > np.pi / 4:
            v *= 0.5

        return v, omega

    def _get_lookahead_waypoint(
        self,
        robot_position: Tuple[float, float]
    ) -> Optional[Tuple[float, float]]:
        """
        Get waypoint at lookahead distance.

        Args:
            robot_position: Current (x, y)

        Returns:
            Waypoint (x, y) or None if goal reached
        """
        if self.current_waypoint_index >= len(self.path):
            return None

        # Find waypoint beyond lookahead distance
        for i in range(self.current_waypoint_index, len(self.path)):
            waypoint = self.path[i]
            distance = np.hypot(
                waypoint[0] - robot_position[0],
                waypoint[1] - robot_position[1]
            )

            if distance >= self.lookahead_distance:
                self.current_waypoint_index = i
                return waypoint

        # Return last waypoint if none beyond lookahead
        return self.path[-1]

    def _world_to_grid(self, pos: Tuple[float, float]) -> Tuple[int, int]:
        """Convert world coordinates to grid indices."""
        x, y = pos
        grid_x = int(x / self.grid_resolution)
        grid_y = int(y / self.grid_resolution)
        return (grid_x, grid_y)

    def _grid_to_world(self, grid_pos: Tuple[int, int]) -> Tuple[float, float]:
        """Convert grid indices to world coordinates."""
        grid_x, grid_y = grid_pos
        x = (grid_x + 0.5) * self.grid_resolution
        y = (grid_y + 0.5) * self.grid_resolution
        return (x, y)

    @staticmethod
    def _heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Euclidean distance heuristic."""
        return np.hypot(a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _get_neighbors(
        pos: Tuple[int, int],
        grid: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Get valid neighbor cells (8-connected grid).

        Args:
            pos: Current grid position
            grid: Occupancy grid

        Returns:
            List of neighbor positions
        """
        x, y = pos
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (0 <= nx < grid.shape[0] and
                    0 <= ny < grid.shape[1] and
                    grid[nx, ny] == 0):
                    neighbors.append((nx, ny))
        return neighbors

    @staticmethod
    def _reconstruct_path(
        came_from: Dict[Tuple[int, int], Tuple[int, int]],
        current: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """Reconstruct path from A* came_from map."""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle

    def reset(self) -> None:
        """Reset path and waypoint tracking."""
        self.path = []
        self.current_waypoint_index = 0
        self.telemetry_data = {
            'path': [],
            'current_waypoint': None,
            'distance_to_goal': []
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """Get path planning telemetry."""
        return self.telemetry_data
