"""
Physics World Integration

Pymunk-based 2D physics wrapper.

Pymunk replaces PyBox2D here for two reasons:
  1. PyBox2D has no working pip wheels for modern Python on Windows; it
     requires SWIG + MSVC and reliably breaks the install.
  2. The MVP only needs two things from physics: fast ray queries and
     contact tests. Pymunk's `segment_query_first` is purpose-built for
     the 16-ray sensor, and we keep collisions analytical (AABB-vs-AABB
     against the robot footprint) — that gives deterministic results,
     keeps the engine independent of body warping quirks, and runs in
     pure NumPy if the user later swaps physics out.

Public surface:
  PhysicsWorld
    .build_from_environment(env)     populate static obstacle bodies
    .raycast(start, end)             → (hit, distance, point)
    .check_collision(corners)        → bool   (analytical AABB test)
    .get_collision_count()           cumulative contact-begin count
    .reset_collisions()              clear the counter & live flag
    .step(dt)                        advance space (no-op for MVP, kept
                                     for future dynamic bodies)
"""

from typing import Any, List, Optional, Tuple

import pymunk

CATEGORY_OBSTACLE = 0b0010


class PhysicsWorld:
    """Static-obstacle world used purely for ray queries in the MVP."""

    def __init__(self, dt: float = 0.02):
        """
        Args:
            dt: Default timestep used by step() when called without an arg.
        """
        self.space = pymunk.Space()
        self.space.gravity = (0.0, 0.0)
        self.dt = dt

        self._obstacle_bodies: List[pymunk.Body] = []
        self._obstacle_aabbs: List[Tuple[float, float, float, float]] = []  # min_x, min_y, max_x, max_y

        self._collision_active = False
        self._collision_count = 0

    # ------------------------------------------------------------------
    # World population
    # ------------------------------------------------------------------
    def build_from_environment(self, environment: Any) -> None:
        """Populate the space with static obstacles from an Environment."""
        self.clear_obstacles()
        for obstacle in environment.obstacles:
            self.create_obstacle(
                position=(obstacle.x, obstacle.y),
                width=obstacle.width,
                height=obstacle.height,
            )

    def create_obstacle(
        self,
        position: Tuple[float, float],
        width: float,
        height: float,
    ) -> pymunk.Body:
        """Create a static rectangular obstacle (centre, width, height)."""
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = position
        shape = pymunk.Poly.create_box(body, (width, height))
        shape.friction = 0.3
        shape.filter = pymunk.ShapeFilter(categories=CATEGORY_OBSTACLE)
        self.space.add(body, shape)
        self._obstacle_bodies.append(body)

        cx, cy = position
        self._obstacle_aabbs.append(
            (cx - width / 2, cy - height / 2, cx + width / 2, cy + height / 2)
        )
        return body

    # Compatibility shims (kept so future PhysicsBackend implementations
    # can drop in without changing Robot/Engine).
    def create_robot_body(self, *_args, **_kwargs) -> None:
        return None

    def set_robot_pose(self, *_args, **_kwargs) -> None:
        return None

    # ------------------------------------------------------------------
    # Stepping & queries
    # ------------------------------------------------------------------
    def step(self, dt: Optional[float] = None) -> None:
        """Advance the physics space (no dynamic bodies in MVP, but free)."""
        self.space.step(dt if dt is not None else self.dt)

    def raycast(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
    ) -> Tuple[bool, float, Tuple[float, float]]:
        """
        Cast a ray and return the first hit against any obstacle.

        Returns:
            (hit, distance, point):
                hit: True if an obstacle was struck.
                distance: Distance start→hit (or full ray length if no hit).
                point: World-space hit point (or `end` if no hit).
        """
        sx, sy = start
        ex, ey = end
        max_distance = ((ex - sx) ** 2 + (ey - sy) ** 2) ** 0.5

        ray_filter = pymunk.ShapeFilter(mask=CATEGORY_OBSTACLE)
        info = self.space.segment_query_first(start, end, 0.0, ray_filter)
        if info is None:
            return False, max_distance, end

        hit_point = (info.point.x, info.point.y)
        hit_distance = (
            (hit_point[0] - sx) ** 2 + (hit_point[1] - sy) ** 2
        ) ** 0.5
        return True, hit_distance, hit_point

    def check_collision(self, robot_corners: List[Tuple[float, float]]) -> bool:
        """
        Analytical SAT-light test: any of the robot's corner points inside
        any obstacle AABB? Cheap and good enough for our rectangular world.

        For thin obstacles whose extent is smaller than the robot footprint,
        we also test obstacle corners against the robot AABB.
        """
        if not robot_corners:
            return False

        # Robot AABB.
        rx_min = min(c[0] for c in robot_corners)
        rx_max = max(c[0] for c in robot_corners)
        ry_min = min(c[1] for c in robot_corners)
        ry_max = max(c[1] for c in robot_corners)

        for (mnx, mny, mxx, mxy) in self._obstacle_aabbs:
            # AABB-vs-AABB overlap.
            if rx_max < mnx or rx_min > mxx:
                continue
            if ry_max < mny or ry_min > mxy:
                continue
            self._collision_active = True
            self._collision_count += 1
            return True

        self._collision_active = False
        return False

    def is_colliding(self) -> bool:
        return self._collision_active

    def get_collision_count(self) -> int:
        return self._collision_count

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def clear_obstacles(self) -> None:
        for body in self._obstacle_bodies:
            for shape in list(body.shapes):
                self.space.remove(shape)
            self.space.remove(body)
        self._obstacle_bodies.clear()
        self._obstacle_aabbs.clear()

    def reset_collisions(self) -> None:
        self._collision_active = False
        self._collision_count = 0
