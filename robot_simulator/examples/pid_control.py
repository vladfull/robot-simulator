"""
PID Heading Control

Classic PID controller on the heading error. Linear speed is constant
when the heading is roughly correct, halved when turning hard.

Tuning: edit KP / KI / KD at the top of the file.
"""

# --- gains -----------------------------------------------------------------
KP = 2.5
KI = 0.05
KD = 0.6

# --- persistent state ------------------------------------------------------
# Each control_step call shares this module-level state dict, which is
# the conventional way to keep state across ticks in a script-style
# controller (no class needed).
_state = {"integral": 0.0, "previous_error": 0.0, "previous_time": 0.0}


def control_step(robot):
    if robot.distance_to_goal() < 0.2:
        robot.set_velocity(0.0, 0.0)
        return

    now = robot.get_time()
    dt = now - _state["previous_time"]
    if dt <= 0.0:
        dt = 0.02  # fallback when called before time advances

    # Heading error normalised to [-pi, pi].
    error = robot.angle_to_goal() - robot.get_orientation()
    while error > math.pi:
        error -= 2 * math.pi
    while error < -math.pi:
        error += 2 * math.pi

    _state["integral"] += error * dt
    derivative = (error - _state["previous_error"]) / dt

    omega = KP * error + KI * _state["integral"] + KD * derivative
    # Saturate to a sane range.
    omega = max(-2.0, min(2.0, omega))

    forward = 1.0 if abs(error) < math.pi / 6 else 0.5

    robot.set_velocity(forward, omega)

    _state["previous_error"] = error
    _state["previous_time"] = now
