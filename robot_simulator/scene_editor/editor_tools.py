"""
Editor tools (Strategy pattern).

Each tool is a small state machine that reacts to mouse press/move/release
events translated into world coordinates by the viewport. Tools mutate the
:class:`EditorController` state — they never touch UI directly. The
controller is responsible for emitting modelChanged and re-rendering.

Mouse buttons are passed as the strings "left" / "right" / "middle" so
the tools stay independent of Qt.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from .map_serializer import ObstacleModel

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .editor_controller import EditorController


# Minimum obstacle size in metres — anything smaller is treated as a
# stray click and discarded so users don't end up with pixel-sized walls.
MIN_OBSTACLE_SIZE = 0.15


class Tool:
    """Base class. Subclasses override the three event hooks."""

    name: str = "select"

    def activated(self, ctrl: "EditorController") -> None:  # noqa: D401
        """Called when this tool becomes the active one."""
        ctrl.selected_obstacle_index = None
        ctrl.preview_obstacle = None
        ctrl.drag_state = None

    def on_press(self, ctrl: "EditorController", x: float, y: float, button: str) -> None:
        pass

    def on_move(self, ctrl: "EditorController", x: float, y: float) -> None:
        pass

    def on_release(self, ctrl: "EditorController", x: float, y: float, button: str) -> None:
        pass


# ---------------------------------------------------------------------------
# Select — click obstacle to highlight, drag to move, right-click to delete.
# ---------------------------------------------------------------------------
class SelectTool(Tool):
    name = "select"

    def on_press(self, ctrl, x, y, button):
        idx = ctrl.hit_test_obstacle(x, y)

        if button == "right":
            if idx is not None:
                ctrl.delete_obstacle(idx)
            return

        if idx is None:
            # Empty click clears the current selection.
            ctrl.selected_obstacle_index = None
            ctrl.drag_state = None
            ctrl.emit_changed()
            return

        ctrl.selected_obstacle_index = idx
        obs = ctrl.model.obstacles[idx]
        ctrl.drag_state = {
            "kind": "move_obstacle",
            "index": idx,
            "press_x": x,
            "press_y": y,
            "orig_x": obs.x,
            "orig_y": obs.y,
        }
        ctrl.emit_changed()

    def on_move(self, ctrl, x, y):
        drag = ctrl.drag_state
        if not drag or drag.get("kind") != "move_obstacle":
            return
        idx = drag["index"]
        if idx >= len(ctrl.model.obstacles):
            return
        obs = ctrl.model.obstacles[idx]
        dx = x - drag["press_x"]
        dy = y - drag["press_y"]
        new_x = ctrl.snap(drag["orig_x"] + dx)
        new_y = ctrl.snap(drag["orig_y"] + dy)
        obs.x = ctrl.clamp_into_world(new_x, obs.width / 2,
                                      ctrl.model.width - obs.width / 2)
        obs.y = ctrl.clamp_into_world(new_y, obs.height / 2,
                                      ctrl.model.height - obs.height / 2)
        ctrl.mark_dirty()
        ctrl.emit_changed()

    def on_release(self, ctrl, x, y, button):
        if ctrl.drag_state and ctrl.drag_state.get("kind") == "move_obstacle":
            ctrl.drag_state = None
            ctrl.emit_changed()


# ---------------------------------------------------------------------------
# Add Obstacle — press-drag rectangle, release to commit.
# ---------------------------------------------------------------------------
class AddObstacleTool(Tool):
    name = "add_obstacle"

    def on_press(self, ctrl, x, y, button):
        if button != "left":
            return
        sx = ctrl.snap(x)
        sy = ctrl.snap(y)
        ctrl.drag_state = {
            "kind": "draw_obstacle",
            "start_x": sx,
            "start_y": sy,
        }
        ctrl.preview_obstacle = ObstacleModel(x=sx, y=sy, width=0.0, height=0.0)
        ctrl.emit_changed()

    def on_move(self, ctrl, x, y):
        drag = ctrl.drag_state
        if not drag or drag.get("kind") != "draw_obstacle":
            return
        ex = ctrl.snap(x)
        ey = ctrl.snap(y)
        sx = drag["start_x"]
        sy = drag["start_y"]
        cx = (sx + ex) / 2
        cy = (sy + ey) / 2
        w = abs(ex - sx)
        h = abs(ey - sy)
        ctrl.preview_obstacle = ObstacleModel(x=cx, y=cy, width=w, height=h)
        ctrl.emit_changed()

    def on_release(self, ctrl, x, y, button):
        drag = ctrl.drag_state
        ctrl.drag_state = None
        preview = ctrl.preview_obstacle
        ctrl.preview_obstacle = None
        if not preview or not drag:
            return
        if preview.width < MIN_OBSTACLE_SIZE or preview.height < MIN_OBSTACLE_SIZE:
            ctrl.emit_changed()
            return
        # Clamp the rectangle so it stays inside the world.
        preview.x = ctrl.clamp_into_world(preview.x, preview.width / 2,
                                          ctrl.model.width - preview.width / 2)
        preview.y = ctrl.clamp_into_world(preview.y, preview.height / 2,
                                          ctrl.model.height - preview.height / 2)
        ctrl.model.add_obstacle(preview)
        ctrl.selected_obstacle_index = len(ctrl.model.obstacles) - 1
        ctrl.mark_dirty()
        ctrl.emit_changed()


# ---------------------------------------------------------------------------
# Set Start — click places it, optional drag sets theta.
# ---------------------------------------------------------------------------
class SetStartTool(Tool):
    name = "set_start"

    def on_press(self, ctrl, x, y, button):
        if button != "left":
            return
        sx = ctrl.snap(x)
        sy = ctrl.snap(y)
        ctrl.model.start.x = ctrl.clamp_into_world(sx, 0.1, ctrl.model.width - 0.1)
        ctrl.model.start.y = ctrl.clamp_into_world(sy, 0.1, ctrl.model.height - 0.1)
        ctrl.drag_state = {
            "kind": "drag_theta",
            "anchor_x": ctrl.model.start.x,
            "anchor_y": ctrl.model.start.y,
            "moved": False,
        }
        ctrl.mark_dirty()
        ctrl.emit_changed()

    def on_move(self, ctrl, x, y):
        drag = ctrl.drag_state
        if not drag or drag.get("kind") != "drag_theta":
            return
        dx = x - drag["anchor_x"]
        dy = y - drag["anchor_y"]
        if dx * dx + dy * dy < 0.05 ** 2:
            return  # too small a movement to define a direction
        drag["moved"] = True
        ctrl.model.start.theta = math.atan2(dy, dx)
        ctrl.mark_dirty()
        ctrl.emit_changed()

    def on_release(self, ctrl, x, y, button):
        if ctrl.drag_state and ctrl.drag_state.get("kind") == "drag_theta":
            ctrl.drag_state = None
            ctrl.emit_changed()


# ---------------------------------------------------------------------------
# Set Goal — single click.
# ---------------------------------------------------------------------------
class SetGoalTool(Tool):
    name = "set_goal"

    def on_press(self, ctrl, x, y, button):
        if button != "left":
            return
        ctrl.model.goal.x = ctrl.clamp_into_world(ctrl.snap(x), 0.1, ctrl.model.width - 0.1)
        ctrl.model.goal.y = ctrl.clamp_into_world(ctrl.snap(y), 0.1, ctrl.model.height - 0.1)
        ctrl.mark_dirty()
        ctrl.emit_changed()
