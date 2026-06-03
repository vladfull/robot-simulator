"""
Obstacle Avoidance — reactive (potential-fields style)

Drives toward the goal when the path is clear; if a sensor detects an
obstacle within `safe_distance`, steers away from the closest reading.

Key API used:
    robot.get_sensor_data()      -> list of distances, one per ray
    robot.get_sensor_count()
    robot.get_sensor_max_range()
    robot.angle_to_goal(), robot.get_orientation()
    robot.distance_to_goal()ропоирои
    robot.set_velocity(v, w)
"""


def control_step(robot):
    safe_distance = 0.8  # metres
    distances = robot.get_sensor_data()
    n = len(distances)
    max_range = robot.get_sensor_max_range()

    # Find the nearest reading and at which local angle.
    nearest_idx = min(range(n), key=lambda i: distances[i])
    nearest = distances[nearest_idx]

    if robot.distance_to_goal() < 0.25:
        robot.set_velocity(0.0, 0.0)
        return

    if nearest < safe_distance:
        # Local angle of the closest ray (rays are evenly spaced over 2pi).
        local_angle = (2 * math.pi) * nearest_idx / n
        # Steer away: turn so the obstacle ends up behind us.
        # Positive local_angle ∈ (0, pi)  → obstacle on the left → turn right.
        if local_angle > math.pi:
            local_angle -= 2 * math.pi  # now in (-pi, pi]
        avoid_angular = -1.5 * (1.0 if local_angle >= 0 else -1.0) * (1.0 - nearest / safe_distance)
        # Move slowly while avoiding.
        robot.set_velocity(0.25, avoid_angular)
        return

    # Path is clear — head for the goal.
    heading_error = robot.angle_to_goal() - robot.get_orientation()
    while heading_error > math.pi:
        heading_error -= 2 * math.pi
    while heading_error < -math.pi:
        heading_error += 2 * math.pi

    forward = 1.0 if abs(heading_error) < math.pi / 6 else 0.4
    robot.set_velocity(forward, 1.8 * heading_error)
