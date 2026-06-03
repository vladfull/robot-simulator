"""
Combined Navigation — Bug-style with PID heading

Switches between two modes:
  * GO_TO_GOAL  : PID toward the goal as long as the path is clear.
  * AVOID       : sidestep when something gets close, then resume.

Demonstrates persistent state (mode flag) and reuse of two simpler
techniques in one algorithm.
"""

KP = 2.0
SAFE = 0.6
GIVEUP = 0.18  # goal-reached radius

_state = {"mode": "GO_TO_GOAL"}


def control_step(robot):
    if robot.distance_to_goal() < GIVEUP:
        robot.set_velocity(0.0, 0.0)
        robot.log("Goal reached")
        return

    distances = robot.get_sensor_data()
    nearest = min(distances)
    nearest_idx = distances.index(nearest)
    n = len(distances)

    # Mode switch with hysteresis to avoid flapping.
    if _state["mode"] == "GO_TO_GOAL" and nearest < SAFE:
        _state["mode"] = "AVOID"
        robot.log(f"Switching to AVOID, nearest={nearest:.2f}m")
    elif _state["mode"] == "AVOID" and nearest > SAFE * 1.4:
        _state["mode"] = "GO_TO_GOAL"
        robot.log("Path clear, resuming GO_TO_GOAL")

    if _state["mode"] == "GO_TO_GOAL":
        # PID-ish heading control toward the goal.
        error = robot.angle_to_goal() - robot.get_orientation()
        while error > math.pi:
            error -= 2 * math.pi
        while error < -math.pi:
            error += 2 * math.pi
        forward = 0.9 if abs(error) < math.pi / 5 else 0.4
        robot.set_velocity(forward, KP * error)
    else:
        # Steer away from the nearest reading.
        local_angle = (2 * math.pi) * nearest_idx / n
        if local_angle > math.pi:
            local_angle -= 2 * math.pi
        sign = -1.0 if local_angle >= 0 else 1.0  # turn opposite direction
        robot.set_velocity(0.25, sign * 1.4)
