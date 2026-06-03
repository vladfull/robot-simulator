"""
Map data model + JSON I/O.

The on-disk shape is the exact format the existing :mod:`environment.loader`
understands, so a map saved here loads in production without any
adaptation:

    {
      "name": "...",
      "width": 10.0,
      "height": 10.0,
      "obstacles": [
        {"type": "rectangle", "x": .., "y": .., "width": .., "height": ..}
      ],
      "start_position": {"x": .., "y": .., "theta": ..},
      "goal_position":  {"x": .., "y": ..}
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data classes — kept dumb on purpose. Mutation goes through EditorController
# so we can track "dirty" state and emit signals.
# ---------------------------------------------------------------------------
@dataclass
class ObstacleModel:
    """An axis-aligned rectangle in world metres (centre + extent)."""
    x: float
    y: float
    width: float
    height: float
    type: str = "rectangle"


@dataclass
class StartPosition:
    x: float = 1.0
    y: float = 1.0
    theta: float = 0.0


@dataclass
class GoalPosition:
    x: float = 9.0
    y: float = 9.0


@dataclass
class MapModel:
    """Editable representation of a map. Mirrors the JSON schema 1:1."""
    name: str = "Untitled Map"
    width: float = 10.0
    height: float = 10.0
    obstacles: List[ObstacleModel] = field(default_factory=list)
    start: StartPosition = field(default_factory=StartPosition)
    goal: GoalPosition = field(default_factory=GoalPosition)

    # ------------------------------------------------------------------
    # Convenience mutators (used by the editor controller).
    # ------------------------------------------------------------------
    def add_obstacle(self, obstacle: ObstacleModel) -> int:
        self.obstacles.append(obstacle)
        return len(self.obstacles) - 1

    def remove_obstacle(self, index: int) -> Optional[ObstacleModel]:
        if 0 <= index < len(self.obstacles):
            return self.obstacles.pop(index)
        return None

    def clear_obstacles(self) -> None:
        self.obstacles.clear()


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------
class MapSerializer:
    """Convert :class:`MapModel` to/from JSON and to a live ``Environment``."""

    # --- JSON dict ----------------------------------------------------
    @staticmethod
    def to_json(model: MapModel) -> Dict[str, Any]:
        return {
            "name": model.name,
            "width": float(model.width),
            "height": float(model.height),
            "obstacles": [
                {
                    "type": obs.type,
                    "x": float(obs.x),
                    "y": float(obs.y),
                    "width": float(obs.width),
                    "height": float(obs.height),
                }
                for obs in model.obstacles
            ],
            "start_position": {
                "x": float(model.start.x),
                "y": float(model.start.y),
                "theta": float(model.start.theta),
            },
            "goal_position": {
                "x": float(model.goal.x),
                "y": float(model.goal.y),
            },
        }

    @staticmethod
    def from_json(data: Dict[str, Any]) -> MapModel:
        obstacles = [
            ObstacleModel(
                x=float(o.get("x", 0.0)),
                y=float(o.get("y", 0.0)),
                width=float(o.get("width", 1.0)),
                height=float(o.get("height", 1.0)),
                type=str(o.get("type", "rectangle")),
            )
            for o in data.get("obstacles", [])
            if o.get("type", "rectangle") == "rectangle"
        ]
        start_raw = data.get("start_position", {})
        goal_raw = data.get("goal_position", {})
        return MapModel(
            name=str(data.get("name", "Untitled Map")),
            width=float(data.get("width", 10.0)),
            height=float(data.get("height", 10.0)),
            obstacles=obstacles,
            start=StartPosition(
                x=float(start_raw.get("x", 1.0)),
                y=float(start_raw.get("y", 1.0)),
                theta=float(start_raw.get("theta", 0.0)),
            ),
            goal=GoalPosition(
                x=float(goal_raw.get("x", 9.0)),
                y=float(goal_raw.get("y", 9.0)),
            ),
        )

    # --- file I/O -----------------------------------------------------
    @staticmethod
    def save(model: MapModel, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(MapSerializer.to_json(model), f, indent=2)

    @staticmethod
    def load(path: str) -> MapModel:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return MapSerializer.from_json(data)

    # --- bridges to the simulation layer ------------------------------
    @staticmethod
    def from_environment(environment) -> MapModel:
        """
        Snapshot a live :class:`environment.map.Environment` into a
        :class:`MapModel`. Boundary walls are stripped — the model
        represents only user-placed obstacles.
        """
        obstacles: List[ObstacleModel] = []
        for obs in getattr(environment, "obstacles", []):
            # Skip the thin boundary walls (width or height == wall_thickness).
            if getattr(obs, "width", 0) < 0.15 or getattr(obs, "height", 0) < 0.15:
                continue
            obstacles.append(
                ObstacleModel(
                    x=float(obs.x), y=float(obs.y),
                    width=float(obs.width), height=float(obs.height),
                )
            )
        sx, sy, st = getattr(environment, "start_position", (1.0, 1.0, 0.0))
        gx, gy = getattr(environment, "goal", (9.0, 9.0))
        return MapModel(
            name=str(getattr(environment, "name", "Untitled Map")),
            width=float(getattr(environment, "width", 10.0)),
            height=float(getattr(environment, "height", 10.0)),
            obstacles=obstacles,
            start=StartPosition(x=float(sx), y=float(sy), theta=float(st)),
            goal=GoalPosition(x=float(gx), y=float(gy)),
        )

    @staticmethod
    def to_environment(model: MapModel):
        """
        Build a fresh :class:`environment.map.Environment` (with boundary
        walls) from a :class:`MapModel`. Use this when the user leaves
        Edit Mode so the simulation engine sees the new map.
        """
        # Local imports keep scene_editor decoupled from environment when
        # the module is used in isolation (e.g. headless tests).
        from environment.map import Environment
        from environment.obstacles import RectangleObstacle

        env = Environment(width=model.width, height=model.height, name=model.name)
        env.clear_obstacles()  # also re-creates boundaries
        for obs in model.obstacles:
            env.add_obstacle(
                RectangleObstacle(
                    x=obs.x, y=obs.y, width=obs.width, height=obs.height
                )
            )
        env.set_start_position(model.start.x, model.start.y, model.start.theta)
        env.set_goal(model.goal.x, model.goal.y)
        return env
