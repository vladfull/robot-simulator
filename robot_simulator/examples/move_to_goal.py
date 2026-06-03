"""
Move To Goal

Simplest possible algorithm: rotate to face the goal, then drive forward.
Ignores obstacles entirely. Use this as a baseline when comparing smarter
algorithms.

Available on the RobotAPI passed in as `robot`:
    robot.get_position()      -> (x, y)
    robot.get_orientation()   -> theta in radians
    robot.get_goal_position() -> (gx, gy)
    robot.distance_to_goal()  -> float
    robot.angle_to_goal()     -> bearing to goal in radians
    robot.set_velocity(v, w)
"""


def control_step(robot):
    # Are we close enough? Stop.
    if robot.distance_to_goal() < 0.2:
        robot.set_velocity(0.0, 0.0)
        ssss
        return

    # Heading error in [-pi, pi]: positive means goal is to the left.
    heading_error = robot.angle_to_goal() - robot.get_orientation()
    while heading_error > math.pi:
        heading_error -= 2 * math.pi
    while heading_error < -math.pi:
        heading_error += 2 * math.pi

    # Slow down while turning sharply, full speed when facing the goal.
    forward = 1.0 if abs(heading_error) < math.pi / 6 else 0.3
    angular = 2.0 * heading_error  # P-controller on heading

    robot.set_velocity(forward, angular)
