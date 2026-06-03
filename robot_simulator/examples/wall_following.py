"""
Wall Following (right-hand rule)

Keeps the wall on the robot's right side at a target distance. Useful for
maze exploration and as a building block in combined navigation.

Strategy:
  * Look at three sectors of the lidar: front, right, right-front.
  * If the front is blocked  → turn left.
  * Else if right is too far → turn right (look for a wall).
  * Else if right is too close → turn left (back off the wall).
  * Else drive straight.
"""


def _sector_min(distances, start, end):
    """Smallest distance in distances[start:end] (handles wrap-around)."""
    n = len(distances)
    if start < end:
        return min(distances[start:end])
    return min(distances[start:] + distances[:end])


def control_step(robot):
    distances = robot.get_sensor_data()
    n = len(distances)
    target = 0.6

    # 16 rays evenly spaced. Index 0 is forward, indices grow CCW.
    # Front sector: ±22.5°; right sector: -45°…-90°; right-front: 0°…-45°.
    front = _sector_min(distances, n - 1, 2)         # 337.5°…22.5°
    right = _sector_min(distances, n * 6 // 8, n * 7 // 8)  # 270°…315°
    right_front = _sector_min(distances, n * 7 // 8, n)     # 315°…360°

    if front < target:
        # Wall ahead — turn sharply left.
        robot.set_velocity(0.1, 1.5)
    elif right > target * 1.5:
        # Lost the wall — turn right gently to re-acquire.
        robot.set_velocity(0.4, -0.8)
    elif right < target * 0.7 or right_front < target:
        # Too close — peel left.
        robot.set_velocity(0.3, 0.6)
    else:
        # All good — cruise.
        robot.set_velocity(0.6, 0.0)
