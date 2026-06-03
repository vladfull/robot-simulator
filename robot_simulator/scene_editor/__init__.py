"""
Scene editor module.

Self-contained MVC layer for visually building simulation maps:

    MapModel / ObstacleModel / StartPosition / GoalPosition  (data)
    MapSerializer                                            (JSON I/O)
    Tool subclasses                                          (mouse → model)
    EditorController                                         (orchestration)
    SceneEditorPanel                                         (sidebar UI, in ui/)

The editor knows nothing about the live simulation engine; the only
exposed conversion utility is
``MapSerializer.to_environment(model)`` which the main window calls when
the user toggles Edit Mode off so the engine can run the freshly-edited
map.
"""

from .editor_controller import EditorController
from .editor_tools import (
    AddObstacleTool,
    SelectTool,
    SetGoalTool,
    SetStartTool,
    Tool,
)
from .map_serializer import (
    GoalPosition,
    MapModel,
    MapSerializer,
    ObstacleModel,
    StartPosition,
)

__all__ = [
    "EditorController",
    "Tool",
    "SelectTool",
    "AddObstacleTool",
    "SetStartTool",
    "SetGoalTool",
    "MapModel",
    "ObstacleModel",
    "StartPosition",
    "GoalPosition",
    "MapSerializer",
]
