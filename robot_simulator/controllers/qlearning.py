"""
Q-Learning Reinforcement Learning Agent

Implements a basic Q-learning algorithm for robot navigation.
"""

import numpy as np
import pickle
from typing import Tuple, Dict, Any, List, Optional
from .base import Controller


class QLearningAgent(Controller):
    """
    Q-Learning Agent for robot navigation.

    Uses tabular Q-learning with discretized state space.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01
    ):
        """
        Initialize Q-Learning agent.

        Args:
            learning_rate: Alpha (learning rate)
            discount_factor: Gamma (future reward discount)
            epsilon: Initial exploration rate
            epsilon_decay: Epsilon decay rate per episode
            epsilon_min: Minimum epsilon value
        """
        super().__init__(name="Q-Learning Agent")

        self.alpha = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

        # Q-table: dictionary mapping (state, action) -> Q-value
        self.q_table: Dict[Tuple, float] = {}

        # Action space (discrete)
        self.actions = [
            (1.0, 0.0),    # Forward
            (1.0, 0.5),    # Forward-right
            (1.0, -0.5),   # Forward-left
            (0.0, 1.0),    # Rotate right
            (0.0, -1.0),   # Rotate left
            (0.5, 0.0),    # Slow forward
        ]

        # State discretization parameters
        self.distance_bins = 10
        self.angle_bins = 8
        self.obstacle_bins = 5

        # Episode tracking
        self.episode_count = 0
        self.total_reward = 0.0
        self.episode_rewards: List[float] = []

        # Current episode state
        self.previous_state: Optional[Tuple] = None
        self.previous_action: Optional[int] = None

        self.telemetry_data = {
            'episode_rewards': [],
            'epsilon_values': [],
            'q_table_size': 0,
            'success_rate': []
        }

    def compute_control(
        self,
        robot_state: Dict[str, float],
        environment: Any,
        goal: Tuple[float, float]
    ) -> Tuple[float, float]:
        """
        Compute control using Q-learning policy.

        Args:
            robot_state: Current robot state
            environment: Environment (for obstacle sensing)
            goal: Target position

        Returns:
            (v, omega): Velocities selected by policy
        """
        # Discretize current state
        current_state = self._discretize_state(robot_state, goal, environment)

        # Select action (epsilon-greedy)
        action_index = self._select_action(current_state)
        v, omega = self.actions[action_index]

        # Calculate reward (if we have previous state)
        if self.previous_state is not None and self.previous_action is not None:
            reward = self._calculate_reward(robot_state, goal, environment)
            self.total_reward += reward

            # Q-learning update
            self._update_q_table(
                self.previous_state,
                self.previous_action,
                reward,
                current_state
            )

        # Store current state-action for next update
        self.previous_state = current_state
        self.previous_action = action_index

        return v, omega

    def _discretize_state(
        self,
        robot_state: Dict[str, float],
        goal: Tuple[float, float],
        environment: Any
    ) -> Tuple[int, int, int]:
        """
        Convert continuous state to discrete state representation.

        State features:
        1. Distance to goal (binned)
        2. Angle to goal (binned into 8 directions)
        3. Nearest obstacle distance (binned)

        Args:
            robot_state: Current robot state
            goal: Goal position
            environment: Environment for obstacle detection

        Returns:
            Discrete state tuple (distance_bin, angle_bin, obstacle_bin)
        """
        x, y = robot_state['x'], robot_state['y']
        theta = robot_state['theta']

        # 1. Distance to goal
        distance = np.hypot(goal[0] - x, goal[1] - y)
        distance_bin = min(int(distance * 2), self.distance_bins - 1)  # bins of 0.5m

        # 2. Angle to goal
        angle_to_goal = np.arctan2(goal[1] - y, goal[0] - x)
        relative_angle = self._normalize_angle(angle_to_goal - theta)
        # Map [-pi, pi] to [0, 7]
        angle_bin = int((relative_angle + np.pi) / (2 * np.pi) * self.angle_bins) % self.angle_bins

        # 3. Nearest obstacle distance — pulled from the robot's distance
        # sensor when one is attached (Robot owns the sensor; we look up
        # the live reading via robot_state if it was injected, otherwise
        # via environment.last_min_distance set by the engine).
        obstacle_distance = robot_state.get(
            'min_obstacle_distance',
            getattr(environment, 'last_min_distance', 5.0),
        )
        obstacle_bin = min(int(obstacle_distance), self.obstacle_bins - 1)

        return (distance_bin, angle_bin, obstacle_bin)

    def _select_action(self, state: Tuple[int, int, int]) -> int:
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Discrete state

        Returns:
            Action index
        """
        if np.random.random() < self.epsilon:
            # Explore: random action
            return np.random.randint(len(self.actions))
        else:
            # Exploit: best action from Q-table
            q_values = [self._get_q_value(state, a) for a in range(len(self.actions))]
            return int(np.argmax(q_values))

    def _get_q_value(self, state: Tuple, action: int) -> float:
        """
        Get Q-value for state-action pair.

        Args:
            state: Discrete state
            action: Action index

        Returns:
            Q-value (0.0 if not in table)
        """
        return self.q_table.get((state, action), 0.0)

    def _update_q_table(
        self,
        state: Tuple,
        action: int,
        reward: float,
        next_state: Tuple
    ) -> None:
        """
        Update Q-table using Q-learning update rule.

        Q(s,a) <- Q(s,a) + α * [r + γ * max_a' Q(s',a') - Q(s,a)]

        Args:
            state: Previous state
            action: Action taken
            reward: Reward received
            next_state: Resulting state
        """
        # Current Q-value
        current_q = self._get_q_value(state, action)

        # Max Q-value for next state
        next_max_q = max([self._get_q_value(next_state, a) for a in range(len(self.actions))])

        # Q-learning update
        new_q = current_q + self.alpha * (reward + self.gamma * next_max_q - current_q)

        # Update table
        self.q_table[(state, action)] = new_q

    def _calculate_reward(
        self,
        robot_state: Dict[str, float],
        goal: Tuple[float, float],
        environment: Any
    ) -> float:
        """
        Calculate reward for current state.

        Reward structure:
        - Distance to goal: -0.1 * distance (closer is better)
        - Reached goal: +100
        - Collision: -50
        - Time penalty: -1 (encourage efficiency)

        Args:
            robot_state: Current robot state
            goal: Goal position
            environment: Environment (for collision detection)

        Returns:
            Reward value
        """
        x, y = robot_state['x'], robot_state['y']
        distance = np.hypot(goal[0] - x, goal[1] - y)

        reward = -0.1 * distance  # Distance penalty
        reward -= 1.0  # Time penalty

        # Check if goal reached
        if distance < 0.3:  # Goal radius
            reward += 100.0

        # Collision penalty (engine injects 'collision' into robot_state).
        if robot_state.get('collision'):
            reward -= 50.0

        return reward

    def on_episode_end(self, success: bool = False) -> None:
        """
        Called at the end of each episode.

        Args:
            success: Whether episode ended successfully
        """
        # Record episode reward
        self.episode_rewards.append(self.total_reward)
        self.telemetry_data['episode_rewards'].append(self.total_reward)

        # Decay epsilon
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay

        self.telemetry_data['epsilon_values'].append(self.epsilon)
        self.telemetry_data['q_table_size'] = len(self.q_table)

        # Update success rate (last 100 episodes)
        if len(self.episode_rewards) >= 100:
            recent_success = sum(1 for r in self.episode_rewards[-100:] if r > 50)
            self.telemetry_data['success_rate'].append(recent_success / 100.0)

        # Reset episode
        self.episode_count += 1
        self.total_reward = 0.0
        self.previous_state = None
        self.previous_action = None

    def save_q_table(self, filepath: str) -> None:
        """
        Save Q-table to file.

        Args:
            filepath: Path to save file
        """
        with open(filepath, 'wb') as f:
            pickle.dump(self.q_table, f)
        print(f"Q-table saved to {filepath}")

    def load_q_table(self, filepath: str) -> None:
        """
        Load Q-table from file.

        Args:
            filepath: Path to saved file
        """
        with open(filepath, 'rb') as f:
            self.q_table = pickle.load(f)
        print(f"Q-table loaded from {filepath} ({len(self.q_table)} entries)")

    def set_training_mode(self, training: bool) -> None:
        """
        Set training mode (exploration vs evaluation).

        Args:
            training: If False, epsilon = 0 (pure exploitation)
        """
        if not training:
            self.epsilon = 0.0
        else:
            self.epsilon = max(self.epsilon, 0.1)

    def reset(self) -> None:
        """Reset episode state (but keep Q-table)."""
        self.previous_state = None
        self.previous_action = None
        self.total_reward = 0.0

    def get_telemetry(self) -> Dict[str, Any]:
        """Get RL training telemetry."""
        return self.telemetry_data

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        """Normalize angle to [-pi, pi]."""
        while angle > np.pi:
            angle -= 2 * np.pi
        while angle < -np.pi:
            angle += 2 * np.pi
        return angle
