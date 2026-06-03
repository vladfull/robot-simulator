"""
Robot Sensors

Distance sensor (lidar-like, 16 rays) and collision sensor.
Both sensors plug into the PhysicsWorld for queries; the PhysicsWorld can
be set lazily so the Robot can be constructed before the world exists.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class DistanceSensor:
    """
    Ray-cast distance sensor.

    Uses PhysicsWorld.raycast() under the hood. If no PhysicsWorld is
    attached, falls back to analytical ray-vs-AABB tests against
    Environment.obstacles so that the sensor still works in headless
    or unit-test contexts.
    """

    def __init__(self, num_rays: int = 16, max_range: float = 5.0):
        """
        Initialize sensor.

        Args:
            num_rays: Number of rays evenly distributed around 360°.
            max_range: Maximum sensing range (metres).
        """
        self.num_rays = num_rays
        self.max_range = max_range
        self.ray_angles = np.linspace(0, 2 * np.pi, num_rays, endpoint=False)

        self.distances: List[float] = [max_range] * num_rays
        self.hit_points: List[Tuple[float, float]] = [(0.0, 0.0)] * num_rays

        self._physics: Any = None  # set by Robot.attach_physics()

    def attach_physics(self, physics_world: Any) -> None:
        """Attach a PhysicsWorld for accelerated ray queries."""
        self._physics = physics_world

    def measure(self, robot_state: Dict[str, float], environment: Any) -> None:
        """Update all ray distances given the current robot pose."""
        x, y = robot_state["x"], robot_state["y"]
        theta = robot_state["theta"]

        # World bounds — the boundary obstacles *should* be hit by the
        # raycast, but their thinness (0.1 m) plus floating point can let
        # diagonal rays squeak past the corners. We pre-compute the world
        # AABB and use it as a hard cap on the ray endpoint, so a ray can
        # never report a hit past the playable area.
        world_w = float(getattr(environment, "width", 0.0))
        world_h = float(getattr(environment, "height", 0.0))

        for i, local_angle in enumerate(self.ray_angles):
            global_angle = theta + local_angle
            dx = np.cos(global_angle)
            dy = np.sin(global_angle)

            # Effective range: the smaller of max_range and the distance to
            # the nearest world boundary along this ray direction.
            eff_range = self.max_range
            if world_w > 0 and world_h > 0:
                eff_range = min(eff_range,
                                _distance_to_aabb_edge(x, y, dx, dy, 0.0, 0.0, world_w, world_h))

            end_x = x + eff_range * dx
            end_y = y + eff_range * dy

            distance, hit_point = self._raycast(
                (x, y), (end_x, end_y), environment
            )
            # Treat a hit at exactly the world edge as "no obstacle in
            # range" — keep colour scheme intuitive (green = open space).
            if distance >= eff_range - 1e-3 and eff_range < self.max_range:
                distance = eff_range
                hit_point = (end_x, end_y)
            self.distances[i] = distance
            self.hit_points[i] = hit_point

    # ------------------------------------------------------------------
    # Ray casting
    # ------------------------------------------------------------------
    def _raycast(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        environment: Any,
    ) -> Tuple[float, Tuple[float, float]]:
        """Return (distance, hit_point) for a single ray."""
        if self._physics is not None:
            _hit, distance, point = self._physics.raycast(start, end)
            return distance, point

        # Analytical fallback: test each rectangle obstacle.
        return self._raycast_analytical(start, end, environment)

    @staticmethod
    def _raycast_analytical(
        start: Tuple[float, float],
        end: Tuple[float, float],
        environment: Any,
    ) -> Tuple[float, Tuple[float, float]]:
        """
        Liang–Barsky-ish slab test against axis-aligned rectangles.

        Returns the closest hit (smallest t in [0, 1]) over all obstacles.
        """
        sx, sy = start
        ex, ey = end
        dx = ex - sx
        dy = ey - sy
        max_distance = (dx * dx + dy * dy) ** 0.5

        best_t = 1.0
        best_point = (ex, ey)
        for obstacle in getattr(environment, "obstacles", []):
            t = _ray_aabb_t(
                sx, sy, dx, dy,
                obstacle.x - obstacle.width / 2,
                obstacle.y - obstacle.height / 2,
                obstacle.x + obstacle.width / 2,
                obstacle.y + obstacle.height / 2,
            )
            if t is not None and 0.0 <= t < best_t:
                best_t = t
                best_point = (sx + dx * t, sy + dy * t)

        return best_t * max_distance, best_point

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    def get_distances(self) -> List[float]:
        """Latest measured distances."""
        return self.distances.copy()

    def get_ray_endpoints(
        self, robot_state: Dict[str, float]
    ) -> List[Tuple[float, float]]:
        """World-space endpoints corresponding to current distances."""
        x, y = robot_state["x"], robot_state["y"]
        theta = robot_state["theta"]
        endpoints: List[Tuple[float, float]] = []
        for i, local_angle in enumerate(self.ray_angles):
            global_angle = theta + local_angle
            d = self.distances[i]
            endpoints.append(
                (x + d * np.cos(global_angle), y + d * np.sin(global_angle))
            )
        return endpoints

    def get_minimum_distance(self) -> float:
        """Closest obstacle in any direction."""
        return min(self.distances) if self.distances else self.max_range


def _distance_to_aabb_edge(
    sx: float,
    sy: float,
    dx: float,
    dy: float,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
) -> float:
    """
    Distance from (sx, sy) along (dx, dy) (unit vector) to the nearest
    edge of the AABB [minx,miny]–[maxx,maxy], assuming (sx, sy) is inside.

    Used to clamp sensor range so rays never visually escape the world
    even if the boundary-wall raycast doesn't catch them.
    """
    t = float("inf")
    if dx > 1e-9:
        t = min(t, (maxx - sx) / dx)
    elif dx < -1e-9:
        t = min(t, (minx - sx) / dx)
    if dy > 1e-9:
        t = min(t, (maxy - sy) / dy)
    elif dy < -1e-9:
        t = min(t, (miny - sy) / dy)
    return max(0.0, t)


def _ray_aabb_t(
    sx: float,
    sy: float,
    dx: float,
    dy: float,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
) -> Optional[float]:
    """Return earliest t in [0, 1] where the ray enters the AABB, else None."""
    tmin = 0.0
    tmax = 1.0
    for p, q, lo, hi in (
        (sx, dx, minx, maxx),
        (sy, dy, miny, maxy),
    ):
        if abs(q) < 1e-12:
            if p < lo or p > hi:
                return None
            continue
        t1 = (lo - p) / q
        t2 = (hi - p) / q
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > tmin:
            tmin = t1
        if t2 < tmax:
            tmax = t2
        if tmin > tmax:
            return None
    return tmin if tmin >= 0.0 else None


class CollisionSensor:
    """Wraps PhysicsWorld collision flags into a simple boolean sensor."""

    def __init__(self) -> None:
        self.is_collision = False
        self.collision_count = 0
        self._physics: Any = None

    def attach_physics(self, physics_world: Any) -> None:
        """Attach a PhysicsWorld so collision queries hit the live space."""
        self._physics = physics_world

    def update(self, _physics_body: Any = None) -> None:
        """
        Refresh state from the physics world.

        The unused argument keeps backward-compat with the previous API
        (Robot.update_sensors used to pass robot.body).
        """
        if self._physics is not None:
            self.is_collision = self._physics.is_colliding()
            self.collision_count = self._physics.get_collision_count()
        else:
            self.is_collision = False

    def is_colliding(self) -> bool:
        return self.is_collision

    def get_collision_count(self) -> int:
        return self.collision_count

    def reset(self) -> None:
        self.is_collision = False
        self.collision_count = 0
        if self._physics is not None:
            self._physics.reset_collisions()
