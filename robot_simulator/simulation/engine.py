"""
Simulation Engine

Fixed-timestep loop that ties together physics, robot kinematics, sensors,
controller, and CSV logging. Designed to be driven step-by-step from a
QTimer in the UI as well as in batch mode (run()).
"""

from typing import Optional, Tuple

from controllers.base import Controller
from environment.map import Environment
from robot.robot import Robot
from utils.logger import DataLogger

from .physics import PhysicsWorld


class SimulationEngine:
    """
    Orchestrates one robot, one controller, one environment.

    Owns the PhysicsWorld and rebuilds it whenever the environment changes.
    Exposes step() for tick-driven UIs and run() for headless batches.
    """

    def __init__(
        self,
        robot: Robot,
        environment: Environment,
        controller: Controller,
        dt: float = 0.02,
    ):
        """
        Initialize simulation engine.

        Args:
            robot: Robot instance.
            environment: Environment instance.
            controller: Controller instance.
            dt: Fixed timestep in seconds (default 50 Hz).
        """
        self.robot = robot
        self.environment = environment
        self.controller = controller
        self.dt = dt

        # Wire up physics for this environment.
        self.physics = PhysicsWorld(dt=dt)
        self.physics.build_from_environment(environment)
        self.robot.attach_physics(self.physics)

        # Simulation state
        self.time = 0.0
        self.is_running = False
        self.goal_reached = False
        self.timed_out = False

        # Logger
        self.logger = DataLogger()
        self.step_count = 0

    # ------------------------------------------------------------------
    # Step / run
    # ------------------------------------------------------------------
    def step(self) -> bool:
        """
        Advance one tick.

        Returns:
            True if the simulation should keep running, False if the
            terminal condition (goal reached or timeout) was met.
        """
        # 1. Advance physics (no-op for static-only worlds, but keeps the
        #    space ready for future dynamic bodies).
        self.physics.step(self.dt)

        # 2. Sensors first, on the *current* pose. Collision is the result
        #    of last step's resolution, so controllers see a consistent view.
        self.physics.check_collision(self.robot.get_corners())
        self.robot.update_sensors(self.environment)
        sensor_data = self.robot.get_sensor_data()

        state = self.robot.get_state()
        state['min_obstacle_distance'] = self.robot.distance_sensor.get_minimum_distance()
        state['collision'] = sensor_data['collision']
        self.environment.last_min_distance = state['min_obstacle_distance']

        # 3. Compute control commands.
        v, omega = self.controller.compute_control(
            state, self.environment, self.environment.goal
        )

        # 4. Apply control to the robot.
        self.robot.apply_control(v, omega)

        # 5. Integrate kinematics with swept-axis sliding so the robot
        #    physically can't cross obstacles AND can grind along walls.
        #    Strategy:
        #      a) Try the full (dx, dy) move.
        #      b) If it collides, try X-only (dy = 0). If that's free,
        #         accept it.
        #      c) Else try Y-only (dx = 0). If that's free, accept it.
        #      d) Else neither axis fits — stay put and zero v so naive
        #         controllers don't keep ramming.
        #    Orientation is always free to update.
        prev_x = self.robot.state['x']
        prev_y = self.robot.state['y']
        self.robot.update(self.dt)
        new_x = self.robot.state['x']
        new_y = self.robot.state['y']

        bounced = False
        if self._collides_now():
            # Try X-only.
            self.robot.state['x'] = new_x
            self.robot.state['y'] = prev_y
            if not self._collides_now():
                # Slid along the X axis; Y blocked but X kept moving.
                pass
            else:
                # X-only didn't work — try Y-only.
                self.robot.state['x'] = prev_x
                self.robot.state['y'] = new_y
                if not self._collides_now():
                    # Slid along the Y axis.
                    pass
                else:
                    # Fully wedged. Stay put and stop pushing.
                    self.robot.state['x'] = prev_x
                    self.robot.state['y'] = prev_y
                    self.robot.state['v'] = 0.0
            bounced = True
            self.physics.set_robot_pose(
                self.robot.state['x'], self.robot.state['y'], self.robot.state['theta']
            )

        # Refresh collision flag after resolution.
        is_colliding = bounced or self.physics.check_collision(self.robot.get_corners())

        # 6. Log data.
        self._log_step(v, omega, is_colliding)

        # 7. Bookkeeping & termination.
        self.time += self.dt
        self.step_count += 1

        if self._check_goal_reached():
            self.goal_reached = True
            return False
        if self.time > 120.0:
            self.timed_out = True
            return False
        return True

    def _collides_now(self) -> bool:
        """Re-test collision against the live robot corners."""
        return self.physics.check_collision(self.robot.get_corners())

    def run(self, max_steps: Optional[int] = None) -> None:
        """
        Run continuously until termination (or max_steps).

        Args:
            max_steps: Optional cap; None means run to natural termination.
        """
        self.is_running = True
        step = 0
        while self.is_running:
            if not self.step():
                break
            step += 1
            if max_steps is not None and step >= max_steps:
                break
        self.is_running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reset clock, controller, robot pose, and logged data."""
        self.time = 0.0
        self.step_count = 0
        self.goal_reached = False
        self.timed_out = False
        self.is_running = False

        sx, sy, st = self.environment.start_position
        self.robot.set_position(sx, sy, st)
        self.robot.reset_trajectory()

        self.controller.reset()
        self.logger.clear()
        self.physics.reset_collisions()

        # Refresh sensor readings at the new pose so the viewport doesn't
        # render stale ray endpoints from before the reset.
        self.robot.update_sensors(self.environment)

    def pause(self) -> None:
        self.is_running = False

    def resume(self) -> None:
        self.is_running = True

    # ------------------------------------------------------------------
    # Mutation helpers used by the UI
    # ------------------------------------------------------------------
    def set_controller(self, controller: Controller) -> None:
        """Switch to a different controller and reset its state."""
        controller.reset()
        self.controller = controller

    def set_environment(self, environment: Environment) -> None:
        """Swap to a new environment, rebuilding physics + robot pose."""
        self.environment = environment
        # Rebuild physics from scratch — the old shapes are released.
        self.physics = PhysicsWorld(dt=self.dt)
        self.physics.build_from_environment(environment)
        self.robot.attach_physics(self.physics)
        self.reset()

    def get_time(self) -> float:
        return self.time

    def save_log(self, filepath: str) -> None:
        self.logger.save_to_csv(filepath)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _check_goal_reached(self) -> bool:
        state = self.robot.get_state()
        gx, gy = self.environment.goal
        return ((state['x'] - gx) ** 2 + (state['y'] - gy) ** 2) ** 0.5 < 0.3

    def _log_step(self, control_v: float, control_omega: float, collision: bool) -> None:
        state = self.robot.get_state()
        self.logger.log({
            'timestamp': self.time,
            'x': state['x'],
            'y': state['y'],
            'theta': state['theta'],
            'v': state['v'],
            'omega': state['omega'],
            'control_v': control_v,
            'control_omega': control_omega,
            'collision': collision,
        })
