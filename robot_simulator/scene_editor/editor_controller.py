"""
Editor Controller.

Owns the editable :class:`MapModel`, the active :class:`Tool`, and the
transient drag/preview state. Exposes two Qt signals so the UI layer can
react without polling:

  * ``modelChanged`` — emitted whenever the model or any transient state
    changed (re-render the viewport, refresh side panel).
  * ``dirtyChanged(bool)`` — emitted when the unsaved-edit flag flips.

The controller is intentionally Qt-light: it only depends on QObject for
signalling. Tests can construct it without instantiating a QApplication
provided they don't connect signals.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from .editor_tools import (
    AddObstacleTool,
    SelectTool,
    SetGoalTool,
    SetStartTool,
    Tool,
)
from .map_serializer import MapModel, MapSerializer, ObstacleModel


# Map tool names → tool classes. The panel uses these names too.
TOOL_REGISTRY: Dict[str, type] = {
    "select": SelectTool,
    "add_obstacle": AddObstacleTool,
    "set_start": SetStartTool,
    "set_goal": SetGoalTool,
}


class EditorController(QObject):
    """High-level façade for the scene editor."""

    modelChanged = pyqtSignal()
    dirtyChanged = pyqtSignal(bool)

    def __init__(self, model: Optional[MapModel] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.model: MapModel = model or MapModel()
        self.tool: Tool = SelectTool()
        self.snap_to_grid: bool = True
        self.grid_step: float = 0.5

        # Transient state — read by the viewport renderer.
        self.selected_obstacle_index: Optional[int] = None
        self.drag_state: Optional[Dict[str, Any]] = None
        self.preview_obstacle: Optional[ObstacleModel] = None

        self._dirty: bool = False
        self._current_path: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_model(self, model: MapModel, path: Optional[str] = None,
                  dirty: bool = False) -> None:
        """Replace the editable model wholesale."""
        self.model = model
        self.selected_obstacle_index = None
        self.drag_state = None
        self.preview_obstacle = None
        self._current_path = path
        self._set_dirty(dirty)
        self.modelChanged.emit()

    def set_tool(self, name: str) -> None:
        """Activate a tool by registry name. Unknown names → select."""
        tool_cls = TOOL_REGISTRY.get(name, SelectTool)
        if isinstance(self.tool, tool_cls):
            return
        self.tool = tool_cls()
        self.tool.activated(self)
        self.modelChanged.emit()

    def tool_name(self) -> str:
        return self.tool.name

    def set_snap(self, enabled: bool) -> None:
        self.snap_to_grid = bool(enabled)

    def set_grid_step(self, step: float) -> None:
        self.grid_step = max(0.05, float(step))

    def set_world_size(self, width: float, height: float) -> None:
        self.model.width = max(1.0, float(width))
        self.model.height = max(1.0, float(height))
        # Re-clamp existing items so nothing escapes a shrunk world.
        for obs in self.model.obstacles:
            obs.x = self.clamp_into_world(obs.x, obs.width / 2,
                                          self.model.width - obs.width / 2)
            obs.y = self.clamp_into_world(obs.y, obs.height / 2,
                                          self.model.height - obs.height / 2)
        self.model.start.x = self.clamp_into_world(self.model.start.x, 0.1,
                                                   self.model.width - 0.1)
        self.model.start.y = self.clamp_into_world(self.model.start.y, 0.1,
                                                   self.model.height - 0.1)
        self.model.goal.x = self.clamp_into_world(self.model.goal.x, 0.1,
                                                  self.model.width - 0.1)
        self.model.goal.y = self.clamp_into_world(self.model.goal.y, 0.1,
                                                  self.model.height - 0.1)
        self.mark_dirty()
        self.modelChanged.emit()

    def set_map_name(self, name: str) -> None:
        if name != self.model.name:
            self.model.name = name
            self.mark_dirty()

    def is_dirty(self) -> bool:
        return self._dirty

    def current_path(self) -> Optional[str]:
        return self._current_path

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------
    def new_map(self, width: float = 10.0, height: float = 10.0,
                name: str = "Untitled Map") -> None:
        self.set_model(MapModel(name=name, width=width, height=height), path=None,
                       dirty=False)

    def load(self, path: str) -> None:
        model = MapSerializer.load(path)
        self.set_model(model, path=path, dirty=False)

    def save(self, path: Optional[str] = None) -> str:
        target = path or self._current_path
        if not target:
            raise ValueError("No save path given and no current path")
        MapSerializer.save(self.model, target)
        self._current_path = target
        self._set_dirty(False)
        return target

    def import_from_environment(self, environment) -> None:
        """Take a snapshot of a live engine environment to start editing."""
        self.set_model(MapSerializer.from_environment(environment),
                       path=None, dirty=False)

    # ------------------------------------------------------------------
    # Mouse routing (called by SimulationView)
    # ------------------------------------------------------------------
    def on_mouse_press(self, world_x: float, world_y: float, button: str) -> None:
        self.tool.on_press(self, world_x, world_y, button)

    def on_mouse_move(self, world_x: float, world_y: float) -> None:
        self.tool.on_move(self, world_x, world_y)

    def on_mouse_release(self, world_x: float, world_y: float, button: str) -> None:
        self.tool.on_release(self, world_x, world_y, button)

    # ------------------------------------------------------------------
    # Helpers used by tools
    # ------------------------------------------------------------------
    def snap(self, value: float) -> float:
        if not self.snap_to_grid:
            return value
        return round(value / self.grid_step) * self.grid_step

    @staticmethod
    def clamp_into_world(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def hit_test_obstacle(self, x: float, y: float) -> Optional[int]:
        """Return index of the obstacle under (x, y), or None.

        Iterates back-to-front so the visually top-most obstacle wins.
        """
        for i in range(len(self.model.obstacles) - 1, -1, -1):
            obs = self.model.obstacles[i]
            if (obs.x - obs.width / 2 <= x <= obs.x + obs.width / 2 and
                    obs.y - obs.height / 2 <= y <= obs.y + obs.height / 2):
                return i
        return None

    def delete_obstacle(self, index: int) -> None:
        if 0 <= index < len(self.model.obstacles):
            self.model.obstacles.pop(index)
            if self.selected_obstacle_index == index:
                self.selected_obstacle_index = None
            elif (self.selected_obstacle_index is not None
                  and self.selected_obstacle_index > index):
                self.selected_obstacle_index -= 1
            self.mark_dirty()
            self.modelChanged.emit()

    def delete_selected(self) -> None:
        if self.selected_obstacle_index is not None:
            self.delete_obstacle(self.selected_obstacle_index)

    def clear_obstacles(self) -> None:
        if self.model.obstacles:
            self.model.clear_obstacles()
            self.selected_obstacle_index = None
            self.mark_dirty()
            self.modelChanged.emit()

    def mark_dirty(self) -> None:
        self._set_dirty(True)

    def emit_changed(self) -> None:
        self.modelChanged.emit()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _set_dirty(self, dirty: bool) -> None:
        if dirty == self._dirty:
            return
        self._dirty = dirty
        self.dirtyChanged.emit(dirty)
