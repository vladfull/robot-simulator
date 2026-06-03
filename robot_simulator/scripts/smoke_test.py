"""
Headless smoke test.

Loads simple_maze.json, runs PID for a few seconds, prints the final state,
and exits. Use this to verify that simulation/physics/controllers wire up
without needing PyQt5 or a display:

    python scripts/smoke_test.py
"""

import os
import sys


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(here)
    sys.path.insert(0, project_root)

    from controllers.pid import PIDController
    from environment.loader import MapLoader
    from robot.robot import Robot
    from simulation.engine import SimulationEngine

    map_path = os.path.join(project_root, "data", "maps", "simple_maze.json")
    env = MapLoader.load(map_path)

    sx, sy, st = env.start_position
    robot = Robot(initial_position=(sx, sy), initial_orientation=st)
    controller = PIDController(kp=2.0, ki=0.0, kd=0.4)
    engine = SimulationEngine(robot=robot, environment=env, controller=controller, dt=0.02)

    # Run for at most 30 seconds of sim time.
    max_steps = 30 * 50
    for _ in range(max_steps):
        if not engine.step():
            break

    state = robot.get_state()
    print(f"sim time      : {engine.time:.2f} s")
    print(f"final pose    : x={state['x']:.2f}  y={state['y']:.2f}  theta={state['theta']:+.2f}")
    print(f"goal reached  : {engine.goal_reached}")
    print(f"timed out     : {engine.timed_out}")
    print(f"min ray (last): {robot.distance_sensor.get_minimum_distance():.2f} m")
    print(f"collisions    : {engine.physics.get_collision_count()}")
    return 0 if engine.goal_reached else 1


if __name__ == "__main__":
    sys.exit(main())
