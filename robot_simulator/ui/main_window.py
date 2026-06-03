"""
Main Window — modern dark IDE layout.

Layout
======
    ┌──────────────────────────────────────────────────────────────────┐
    │ Toolbar  Mode▼  Map▼  Example▼   ▶ Run  ⏸ Pause  ⟲ Reset       │
    ├───────────────────────┬───────────────────────┬──────────────────┤
    │  Editor / Docs        │  Simulation Viewport  │   Inspector      │
    │  (tabs)               │  (dominant, dark,     │   (cards)        │
    │                       │   floating HUD)       │                  │
    │                       │                       │                  │
    ├───────────────────────┤                       │                  │
    │  Console              │                       │                  │
    ├───────────────────────┴───────────────────────┴──────────────────┤
    │ ● Running  •  complex_maze.json  •  User Code  •  t=12.34s  •…  │
    └──────────────────────────────────────────────────────────────────┘

Why this shape?
  * The viewport is the centre of attention — moved out of the right edge
    and given the largest pane.
  * Editor + console live together on the left; reading a traceback while
    looking at the code matches the natural debug loop.
  * The Inspector replaces the cramped left dock — parameters live in
    themed cards with breathing room.
  * Toolbar exposes the entire workflow primary path: pick mode →
    pick map/example → Run.
  * Status bar is the always-on telemetry strip (state badge + time + …).
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QShortcut,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from controllers.astar import AStarPlanner
from controllers.base import Controller
from controllers.manual import ManualController
from controllers.pid import PIDController
from controllers.qlearning import QLearningAgent
from controllers.scripted import ScriptedController
from environment.loader import MapLoader
from execution.execution_engine import ExecutionEngine
from robot.robot import Robot
from scene_editor.editor_controller import EditorController
from scene_editor.map_serializer import MapSerializer
from simulation.engine import SimulationEngine

from .code_editor import CodeEditor
from .console_widget import ConsoleWidget
from .control_panel import CONTROLLER_NAMES, ControlPanel
from .docs_widget import DocsWidget
from .scene_editor_panel import SceneEditorPanel
from .simulation_view import SimulationView
from .theme import SPACING


SIMULATION_HZ = 50
RENDER_HZ = 60
TELEMETRY_HZ = 10

MODE_USER_CODE = "User Code"
MODE_BUILTIN = "Built-in"


# Template inserted by the "New" button. Gives beginners a runnable
# skeleton plus an inline API cheat-sheet so they don't have to flip
# to the Documentation tab right away.
NEW_FILE_TEMPLATE = '''\
"""
My algorithm.

Each simulation tick the platform calls control_step(robot). Read state
through the robot facade and command motion with robot.set_velocity.

RobotAPI quick reference
    robot.get_position()       -> (x, y)
    robot.get_orientation()    -> theta in radians
    robot.get_velocity()       -> (v, omega)
    robot.get_goal_position()  -> (gx, gy)
    robot.distance_to_goal()   -> float
    robot.angle_to_goal()      -> bearing to goal in radians
    robot.get_sensor_data()    -> list of distances (m), one per ray
    robot.is_collision()       -> bool
    robot.get_time()           -> simulated seconds
    robot.set_velocity(v, w)
    robot.log("message")

The math and random modules are already available — no imports needed.
"""


def control_step(robot):
    # TODO: write your algorithm here.
    # As a placeholder, stay still:
    robot.set_velocity(0.0, 0.0)
'''


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self, project_root: str):
        super().__init__()
        self.setWindowTitle("Information System for Robotic Platform Simulation with an Integrated Environment for Control Algorithm Development")
        self.resize(1480, 880)

        self._project_root = project_root
        self._maps_dir = os.path.join(project_root, "data", "maps")
        self._logs_dir = os.path.join(project_root, "data", "logs")
        self._examples_dir = os.path.join(project_root, "examples")
        self._docs_dir = os.path.join(project_root, "docs")
        os.makedirs(self._logs_dir, exist_ok=True)

        self._engine: Optional[SimulationEngine] = None
        self._mode = MODE_USER_CODE

        # ------ child widgets ------
        self._console = ConsoleWidget()
        self._editor = CodeEditor()
        self._docs = DocsWidget(docs_dir=self._docs_dir)
        self._exec_engine = ExecutionEngine(console=self._console)
        self._inspector = ControlPanel(maps_dir=self._maps_dir)
        self._view = SimulationView(
            get_engine=lambda: self._engine,
            on_key_press=self._on_view_key_press,
            on_key_release=self._on_view_key_release,
        )
        # Scene editor — controller is shared between the panel and the view.
        self._editor_ctrl = EditorController(parent=self)
        self._view.set_editor_controller(self._editor_ctrl)
        self._scene_panel = SceneEditorPanel(
            controller=self._editor_ctrl, maps_dir=self._maps_dir
        )
        # The Scene Editor lives as a left-side tab next to Editor/Docs.
        # It used to sit in the right Inspector, but at smaller window
        # sizes the right column ran out of vertical room and widgets
        # piled onto each other. A tab gives the editor its own dedicated
        # surface and lets the right column stay compact.

        # ------ assembly ------
        self._build_toolbar()
        self._build_central_layout()
        self._build_status_bar()

        # ------ wiring ------
        self._inspector.startClicked.connect(self._on_run)
        self._inspector.pauseClicked.connect(self._on_pause)
        self._inspector.resetClicked.connect(self._on_reset)
        # mapChanged is no longer fired (the inspector no longer owns the
        # map dropdown — only the workflow toolbar does).
        self._inspector.controllerChanged.connect(self._on_controller_changed)
        self._inspector.parameterChanged.connect(self._on_parameter_changed)
        # Scene editor wiring
        self._scene_panel.editModeToggled.connect(self._on_edit_mode_toggled)
        self._scene_panel.applyRequested.connect(self._on_apply_editor_map)
        self._scene_panel.mapPathChanged.connect(self._on_edited_map_path_changed)
        self._editor_ctrl.modelChanged.connect(self._view.render_frame)

        # ------ timers ------
        self._sim_timer = QTimer(self)
        self._sim_timer.setTimerType(Qt.PreciseTimer)
        self._sim_timer.setInterval(int(1000 / SIMULATION_HZ))
        self._sim_timer.timeout.connect(self._tick_sim)

        self._render_timer = QTimer(self)
        self._render_timer.setInterval(int(1000 / RENDER_HZ))
        self._render_timer.timeout.connect(self._view.render_frame)
        self._render_timer.start()

        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(int(1000 / TELEMETRY_HZ))
        self._telemetry_timer.timeout.connect(self._refresh_telemetry)
        self._telemetry_timer.start()

        # ------ shortcuts ------
        QShortcut(QKeySequence.New, self, activated=self._on_new_file)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._on_save_file)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._on_open_file)
        QShortcut(QKeySequence("F5"), self, activated=self._on_run)

        # ------ initial mode visuals (editor active in User Code mode) ------
        self._apply_mode_visuals()

        # ------ bootstrap ------
        self._load_default_example()
        first_map = self._toolbar_map_combo.currentData() or ""
        if first_map:
            self._build_engine(first_map)
            self._set_status_state("idle", "Idle")
        else:
            self._set_status_state("warning", "No maps in data/maps")

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_central_layout(self) -> None:
        # --- editor side: code + docs tabs ---
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        editor_panel = QWidget()
        ev = QVBoxLayout(editor_panel)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(0)
        ev.addWidget(self._build_editor_action_bar())
        self._mode_banner = self._build_mode_banner()
        ev.addWidget(self._mode_banner)
        ev.addWidget(self._editor, 1)
        self._tabs.addTab(editor_panel, "Editor")

        # Scene Editor tab — scrollable wrapper so the panel never gets
        # squeezed when the user shrinks the left column.
        scene_scroll = QScrollArea()
        scene_scroll.setWidgetResizable(True)
        scene_scroll.setFrameShape(QFrame.NoFrame)
        scene_scroll.setWidget(self._scene_panel)
        self._tabs.addTab(scene_scroll, "Scene Editor")
        self._tabs.addTab(self._docs, "Documentation")

        # --- editor split: code+docs above, console below ---
        left_split = QSplitter(Qt.Vertical)
        left_split.addWidget(self._tabs)
        left_split.addWidget(self._console)
        left_split.setStretchFactor(0, 4)
        left_split.setStretchFactor(1, 1)
        left_split.setSizes([560, 200])
        left_split.setHandleWidth(1)

        # --- main 3-column split: editor | viewport | inspector ---
        outer = QSplitter(Qt.Horizontal)
        outer.addWidget(left_split)
        outer.addWidget(self._view)
        outer.addWidget(self._inspector)
        outer.setStretchFactor(0, 4)
        outer.setStretchFactor(1, 6)
        outer.setStretchFactor(2, 0)
        outer.setSizes([520, 700, 320])
        outer.setHandleWidth(1)
        outer.setObjectName("CentralWidget")

        self.setCentralWidget(outer)

    def _build_editor_action_bar(self) -> QWidget:
        """Compact bar above the editor with file, example, and zoom controls."""
        bar = QWidget()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(SPACING.MD, SPACING.SM, SPACING.MD, SPACING.SM)
        layout.setSpacing(SPACING.SM)

        ex_label = QLabel("Example")
        ex_label.setProperty("role", "caption")
        layout.addWidget(ex_label)

        self._examples_combo = QComboBox()
        self._examples_combo.addItem("(none)", None)
        for name, path in self._discover_examples():
            self._examples_combo.addItem(name, path)
        self._examples_combo.currentIndexChanged.connect(self._on_example_chosen)
        layout.addWidget(self._examples_combo)

        layout.addStretch(1)

        # Font-zoom cluster: −  size  +
        self._font_minus_btn = QPushButton("A−")
        self._font_minus_btn.setToolTip("Decrease editor font size (Ctrl −)")
        self._font_minus_btn.setProperty("variant", "ghost")
        self._font_minus_btn.setFixedWidth(34)
        self._font_minus_btn.clicked.connect(self._editor.zoom_out)

        self._font_size_label = QLabel(f"{self._editor.font_size()} pt")
        self._font_size_label.setProperty("role", "caption")
        self._font_size_label.setFixedWidth(40)
        self._font_size_label.setAlignment(Qt.AlignCenter)

        self._font_plus_btn = QPushButton("A+")
        self._font_plus_btn.setToolTip("Increase editor font size (Ctrl +)")
        self._font_plus_btn.setProperty("variant", "ghost")
        self._font_plus_btn.setFixedWidth(34)
        self._font_plus_btn.clicked.connect(self._editor.zoom_in)

        layout.addWidget(self._font_minus_btn)
        layout.addWidget(self._font_size_label)
        layout.addWidget(self._font_plus_btn)

        # Separator before file actions.
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Plain)
        sep.setStyleSheet("color: #2c333d;")
        sep.setFixedHeight(22)
        layout.addWidget(sep)

        self._new_btn = QPushButton("New")
        self._new_btn.setToolTip("Start a fresh algorithm file (Ctrl+N)")
        self._open_btn = QPushButton("Open…")
        self._save_btn = QPushButton("Save")
        for b in (self._new_btn, self._open_btn, self._save_btn):
            b.setProperty("variant", "ghost")
        self._new_btn.clicked.connect(self._on_new_file)
        self._open_btn.clicked.connect(self._on_open_file)
        self._save_btn.clicked.connect(self._on_save_file)
        layout.addWidget(self._new_btn)
        layout.addWidget(self._open_btn)
        layout.addWidget(self._save_btn)

        # Repaint label when the editor changes font size by any path
        # (keyboard shortcut, Ctrl+wheel, or these buttons).
        # We poll on a short timer because QPlainTextEdit doesn't emit
        # a font-change signal; the cost is negligible.
        from PyQt5.QtCore import QTimer
        timer = QTimer(self)
        timer.setInterval(300)
        timer.timeout.connect(self._sync_font_size_label)
        timer.start()
        self._font_label_timer = timer

        return bar

    def _build_mode_banner(self) -> QFrame:
        """Subtle banner that appears above the editor in Built-in mode."""
        banner = QFrame()
        banner.setObjectName("ModeBanner")
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(SPACING.MD, SPACING.XS, SPACING.MD, SPACING.XS)
        label = QLabel(
            "Built-in algorithm selected — the editor is read-only. "
            "Switch Mode to “User Code” to write your own algorithm."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        banner.setVisible(False)  # hidden in User Code mode
        return banner

    def _sync_font_size_label(self) -> None:
        if hasattr(self, "_font_size_label"):
            self._font_size_label.setText(f"{self._editor.font_size()} pt")

    def _build_toolbar(self) -> None:
        bar = QToolBar("Workflow")
        bar.setMovable(False)
        bar.setIconSize(bar.iconSize())  # respect platform default
        self.addToolBar(Qt.TopToolBarArea, bar)

        # Mode picker
        mode_label = QLabel("Mode")
        mode_label.setProperty("role", "caption")
        bar.addWidget(mode_label)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems([MODE_USER_CODE, MODE_BUILTIN])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        bar.addWidget(self._mode_combo)
        bar.addSeparator()

        # Map picker (mirrored from inspector for one-click access)
        map_label = QLabel("Map")
        map_label.setProperty("role", "caption")
        bar.addWidget(map_label)
        self._toolbar_map_combo = QComboBox()
        for name, path in self._discover_maps():
            self._toolbar_map_combo.addItem(name, path)
        self._toolbar_map_combo.currentIndexChanged.connect(
            lambda _i: self._on_map_changed(self._toolbar_map_combo.currentData() or "")
        )
        bar.addWidget(self._toolbar_map_combo)
        bar.addSeparator()

        # Run controls — primary action is visually loud.
        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setProperty("variant", "success")
        self._run_btn.clicked.connect(self._on_run)
        bar.addWidget(self._run_btn)

        self._pause_btn = QPushButton("⏸  Pause")
        self._pause_btn.clicked.connect(self._on_pause)
        bar.addWidget(self._pause_btn)

        self._reset_btn = QPushButton("⟲  Reset")
        self._reset_btn.setProperty("variant", "ghost")
        self._reset_btn.clicked.connect(self._on_reset)
        bar.addWidget(self._reset_btn)

        # Right-side actions.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        bar.addWidget(spacer)

        save_log_action = QAction("Save log…", self)
        save_log_action.triggered.connect(self._on_save_log)
        save_log_btn = QPushButton("Save log…")
        save_log_btn.setProperty("variant", "ghost")
        save_log_btn.clicked.connect(self._on_save_log)
        bar.addWidget(save_log_btn)

    def _build_status_bar(self) -> None:
        sb = QStatusBar(self)
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)

        self._status_state = QLabel("Idle")
        self._status_state.setProperty("role", "badge-idle")

        self._status_map = QLabel("—")
        self._status_mode = QLabel(self._mode)
        self._status_time = QLabel("t = 0.00 s")
        self._status_velocity = QLabel("v = 0.00 m/s")
        self._status_min_ray = QLabel("min ray = — m")
        self._status_min_ray.setProperty("role", "last")

        for w in (self._status_state, self._status_map, self._status_mode,
                  self._status_time, self._status_velocity, self._status_min_ray):
            sb.addWidget(w)

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------
    def _build_engine(self, map_path: str) -> None:
        try:
            environment = MapLoader.load(map_path)
        except ValueError as exc:
            self._set_status_state("error", f"Map load failed: {exc}")
            self._console.write_error(f"Map load failed: {exc}")
            return

        sx, sy, st = environment.start_position
        robot = Robot(initial_position=(sx, sy), initial_orientation=st)
        controller = self._make_active_controller(robot=robot, environment=environment)
        self._engine = SimulationEngine(
            robot=robot, environment=environment, controller=controller,
            dt=1.0 / SIMULATION_HZ,
        )
        if isinstance(controller, ScriptedController):
            controller.rebind(
                robot=robot, environment=environment,
                get_sim_time=lambda: self._engine.time,
                console=self._console,
            )

        self._status_map.setText(os.path.basename(map_path))
        self._status_mode.setText(self._mode)
        self._set_status_state("idle", "Loaded")
        self.statusBar().showMessage(f"Loaded {os.path.basename(map_path)}", 3000)

    def _make_active_controller(self, robot, environment) -> Controller:
        if self._mode == MODE_USER_CODE:
            return ScriptedController(
                execution_engine=self._exec_engine,
                robot=robot,
                environment=environment,
                console=self._console,
            )
        name = self._inspector.current_controller_name()
        return self._make_builtin_controller(name)

    def _make_builtin_controller(self, name: str) -> Controller:
        if name == "PID Controller":
            return PIDController(kp=2.0, ki=0.1, kd=0.5)
        if name == "A* Path Planner":
            return AStarPlanner(grid_resolution=0.2)
        if name == "Q-Learning Agent":
            agent = QLearningAgent(learning_rate=0.1)
            agent.epsilon = 0.3
            return agent
        if name == "Manual Control":
            return ManualController()
        return PIDController()

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------
    def _tick_sim(self) -> None:
        if self._engine is None:
            return
        keep_going = self._engine.step()
        if not keep_going:
            self._sim_timer.stop()
            if self._engine.goal_reached:
                self._set_status_state("success", "Goal reached")
                self._console.write_success(
                    f"Goal reached at t={self._engine.time:.2f}s"
                )
            elif self._engine.timed_out:
                self._set_status_state("warning", "Timed out")
                self._console.write_warning(
                    f"Timeout at t={self._engine.time:.2f}s"
                )
            self._auto_save_log()

    def _refresh_telemetry(self) -> None:
        if self._engine is None:
            return
        state = self._engine.robot.get_state()
        min_ray = self._engine.robot.distance_sensor.get_minimum_distance()
        self._status_time.setText(f"t = {self._engine.time:5.2f} s")
        self._status_velocity.setText(
            f"v = {state['v']:+.2f} m/s   ω = {state['omega']:+.2f} rad/s"
        )
        self._status_min_ray.setText(f"min ray = {min_ray:.2f} m")

        self._inspector.update_telemetry([
            ("Time",        f"{self._engine.time:6.2f} s"),
            ("Position X",  f"{state['x']:+6.2f} m"),
            ("Position Y",  f"{state['y']:+6.2f} m"),
            ("Heading",     f"{np.degrees(state['theta']):+6.1f}°"),
            ("Linear v",    f"{state['v']:+5.2f} m/s"),
            ("Angular ω",   f"{state['omega']:+5.2f} rad/s"),
            ("Min ray",     f"{min_ray:5.2f} m"),
            ("Goal dist",   f"{((state['x']-self._engine.environment.goal[0])**2 + (state['y']-self._engine.environment.goal[1])**2)**0.5:5.2f} m"),
            ("Steps",       f"{self._engine.step_count}"),
            ("Collisions",  f"{self._engine.physics.get_collision_count()}"),
        ])

    # ------------------------------------------------------------------
    # Slots — run controls
    # ------------------------------------------------------------------
    def _on_run(self) -> None:
        # If the user hits Run while in Edit Mode, commit their map first
        # so the simulation runs against the new scene instead of the
        # previously-loaded one.
        if self._scene_panel.is_edit_mode():
            self._on_apply_editor_map()

        if self._engine is None:
            return
        if self._mode == MODE_USER_CODE:
            source = self._editor.toPlainText()
            ok = self._exec_engine.load_code(source)
            if not ok:
                self._set_status_state("error", "Compilation failed")
                return
        if self._engine.goal_reached or self._engine.timed_out or self._engine.step_count > 0:
            self._engine.reset()
        self._sim_timer.start()
        self._set_status_state("success", "Running")
        self._view.setFocus()

    def _on_pause(self) -> None:
        if self._sim_timer.isActive():
            self._sim_timer.stop()
            self._set_status_state("warning", "Paused")

    def _on_reset(self) -> None:
        if self._engine is not None:
            self._sim_timer.stop()
            self._engine.reset()
            self._set_status_state("idle", "Reset")

    # ------------------------------------------------------------------
    # Slots — scene / mode / controller / params
    # ------------------------------------------------------------------
    def _on_mode_changed(self, mode: str) -> None:
        self._mode = mode
        self._status_mode.setText(mode)
        self._apply_mode_visuals()
        if self._engine is None:
            return
        self._sim_timer.stop()
        new_ctrl = self._make_active_controller(self._engine.robot, self._engine.environment)
        self._engine.set_controller(new_ctrl)
        if isinstance(new_ctrl, ScriptedController):
            new_ctrl.rebind(
                robot=self._engine.robot,
                environment=self._engine.environment,
                get_sim_time=lambda: self._engine.time,
                console=self._console,
            )
        self._set_status_state("idle", f"Mode: {mode}")

    def _apply_mode_visuals(self) -> None:
        """
        Reflect the active mode in the editor pane.

        In *Built-in* mode the user's code is irrelevant — the simulator
        runs PID / A* / Q-Learning / Manual from the algorithm dropdown.
        We mark that visually so the student doesn't waste time editing
        code that won't be executed:

          * editor → read-only and dimmed (QSS `:disabled` rule);
          * example / open / save controls → disabled;
          * font zoom remains enabled so the user can still *read* the
            code as reference;
          * a warning banner explains the state.
        """
        is_user = self._mode == MODE_USER_CODE

        self._editor.setReadOnly(not is_user)
        self._editor.setEnabled(is_user)
        self._examples_combo.setEnabled(is_user)
        self._open_btn.setEnabled(is_user)
        self._save_btn.setEnabled(is_user)

        if hasattr(self, "_mode_banner"):
            self._mode_banner.setVisible(not is_user)

        # In Built-in mode, jumping to the Editor tab is misleading.
        # Stay on whatever tab the user has open, but ensure the
        # Documentation tab is accessible even when editor is disabled.
        if not is_user:
            # Encourage the user to look at the algorithm card on the right.
            self._inspector._controller_combo.setFocus()

    def _on_map_changed(self, path: str) -> None:
        if not path:
            return
        # Single source of truth is the toolbar combo now.
        combo = self._toolbar_map_combo
        for i in range(combo.count()):
            if combo.itemData(i) == path:
                combo.blockSignals(True)
                combo.setCurrentIndex(i)
                combo.blockSignals(False)
                break
        was_running = self._sim_timer.isActive()
        self._sim_timer.stop()
        self._build_engine(path)
        if was_running:
            self._sim_timer.start()
        self._view.setFocus()

    def _on_controller_changed(self, name: str) -> None:
        if self._engine is None or self._mode != MODE_BUILTIN:
            return
        self._engine.set_controller(self._make_builtin_controller(name))
        self._set_status_state("idle", f"Controller: {name}")
        self._view.setFocus()

    def _on_parameter_changed(self, key: str, value: float) -> None:
        if self._engine is None:
            return
        ctrl = self._engine.controller

        if key == "max_linear_velocity":
            self._engine.robot.max_linear_velocity = value
            if hasattr(ctrl, "max_linear_velocity"):
                ctrl.max_linear_velocity = value
            if hasattr(ctrl, "max_velocity"):
                ctrl.max_velocity = value
            return
        if key == "max_angular_velocity":
            self._engine.robot.max_angular_velocity = value
            if hasattr(ctrl, "max_angular_velocity"):
                ctrl.max_angular_velocity = value
            return
        if key in ("kp", "ki", "kd") and hasattr(ctrl, "set_parameters"):
            ctrl.set_parameters({key: value})
            return
        if key == "grid_resolution" and hasattr(ctrl, "grid_resolution"):
            ctrl.grid_resolution = value
            ctrl.path = []
            return
        if key == "lookahead_distance" and hasattr(ctrl, "lookahead_distance"):
            ctrl.lookahead_distance = value
            return
        if key == "alpha" and hasattr(ctrl, "alpha"):
            ctrl.alpha = value
            return
        if key == "gamma" and hasattr(ctrl, "gamma"):
            ctrl.gamma = value
            return
        if key == "epsilon" and hasattr(ctrl, "epsilon"):
            ctrl.epsilon = value

    # ------------------------------------------------------------------
    # Slots — editor / file
    # ------------------------------------------------------------------
    def _on_example_chosen(self, _i: int) -> None:
        path = self._examples_combo.currentData()
        if path:
            self._editor.load_path(path)
            self._console.write(f"Loaded example: {os.path.basename(path)}")

    def _on_new_file(self) -> None:
        """
        Start a fresh algorithm.

        Replaces the editor contents with a minimal control_step
        template that includes an inline RobotAPI cheat-sheet, clears
        any associated file path so Save prompts for a new location,
        and resets the example dropdown so the user can tell they're
        no longer editing an example.
        """
        # If the user has unsaved work, ask before overwriting.
        if self._editor.document().isModified() and self._editor.toPlainText().strip():
            from PyQt5.QtWidgets import QMessageBox
            answer = QMessageBox.question(
                self,
                "Discard current code?",
                "Your current code has not been saved. "
                "Create a new file and discard your changes?",
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if answer != QMessageBox.Discard:
                return

        self._editor.new_file(template=NEW_FILE_TEMPLATE)

        # Reset example dropdown to "(none)" so it doesn't mislead the user.
        if self._examples_combo.count() > 0:
            self._examples_combo.blockSignals(True)
            self._examples_combo.setCurrentIndex(0)
            self._examples_combo.blockSignals(False)

        # Make sure the editor tab is active and focused.
        if hasattr(self, "_tabs"):
            self._tabs.setCurrentIndex(0)
        self._editor.setFocus()

        self._console.write("New file created. Edit and press Run when ready.")

    def _on_open_file(self) -> None:
        self._editor.open_file(default_dir=self._examples_dir)

    def _on_save_file(self) -> None:
        path = self._editor.save_file(default_dir=self._examples_dir)
        if path:
            self.statusBar().showMessage(f"Saved {os.path.basename(path)}", 3000)

    def _on_save_log(self) -> None:
        if self._engine is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", self._logs_dir, "CSV files (*.csv)"
        )
        if not path:
            return
        self._engine.save_log(path)
        self.statusBar().showMessage(f"Log saved to {path}", 3000)

    # ------------------------------------------------------------------
    # Scene editor lifecycle
    # ------------------------------------------------------------------
    def _on_edit_mode_toggled(self, enabled: bool) -> None:
        """
        Enter or leave Edit Mode.

        Entering:
          * Pause the simulation timer (TS: simulation pauses automatically).
          * Seed the editor with a snapshot of the current environment so
            the user starts from whatever map is loaded.
          * Tell the viewport to render from the model and route mouse
            events to the editor controller.

        Leaving (without applying):
          * The user can keep their edits and re-enable later, but the
            engine still shows the previously-loaded environment.
          * The viewport switches back to live render.
        """
        if enabled:
            if self._sim_timer.isActive():
                self._sim_timer.stop()
                self._set_status_state("warning", "Paused (Edit Mode)")
            if self._engine is not None and not self._editor_ctrl.model.obstacles \
                    and not self._editor_ctrl.is_dirty():
                # Only auto-seed on the first entry into a fresh editor;
                # don't clobber an in-progress edit.
                self._editor_ctrl.import_from_environment(self._engine.environment)
            self._view.set_edit_mode(True)
            self._view.render_frame()
            self._console.write("Edit Mode enabled")
        else:
            self._view.set_edit_mode(False)
            self._view.render_frame()
            self._set_status_state("idle", "Idle")
            self._console.write("Edit Mode disabled")

    def _on_apply_editor_map(self) -> None:
        """
        Rebuild the simulation engine from the edited model and exit
        edit mode. The new environment is also written to a temp JSON in
        the maps folder so the user can find it later.
        """
        try:
            environment = MapSerializer.to_environment(self._editor_ctrl.model)
        except Exception as exc:  # noqa: BLE001
            self._console.write_error(f"Apply failed: {exc}")
            return

        if self._engine is None:
            sx, sy, st = environment.start_position
            robot = Robot(initial_position=(sx, sy), initial_orientation=st)
            controller = self._make_active_controller(robot=robot, environment=environment)
            self._engine = SimulationEngine(
                robot=robot, environment=environment, controller=controller,
                dt=1.0 / SIMULATION_HZ,
            )
            if isinstance(controller, ScriptedController):
                controller.rebind(
                    robot=robot, environment=environment,
                    get_sim_time=lambda: self._engine.time,
                    console=self._console,
                )
        else:
            self._engine.set_environment(environment)

        self._scene_panel.set_edit_mode(False)
        self._status_map.setText(self._editor_ctrl.model.name)
        self._set_status_state("success", "Map applied")
        self._console.write_success(
            f"Map “{self._editor_ctrl.model.name}” applied to simulation"
        )
        self._view.setFocus()

    def _on_edited_map_path_changed(self, path: str) -> None:
        """Refresh the toolbar map combo after a load/save."""
        if not path:
            return
        maps = self._discover_maps()
        combo = self._toolbar_map_combo
        combo.blockSignals(True)
        combo.clear()
        for name, p in maps:
            combo.addItem(name, p)
        for i in range(combo.count()):
            if combo.itemData(i) == path:
                combo.setCurrentIndex(i)
                break
        combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Manual controller key forwarding
    # ------------------------------------------------------------------
    def _on_view_key_press(self, name: str) -> None:
        if self._engine is None:
            return
        ctrl = self._engine.controller
        if isinstance(ctrl, ManualController):
            ctrl.press(name)

    def _on_view_key_release(self, name: str) -> None:
        if self._engine is None:
            return
        ctrl = self._engine.controller
        if isinstance(ctrl, ManualController):
            ctrl.release(name)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _auto_save_log(self) -> None:
        if self._engine is None:
            return
        path = os.path.join(self._logs_dir, "last_run.csv")
        try:
            self._engine.save_log(path)
            self.statusBar().showMessage(f"Log saved to {path}", 4000)
        except Exception as exc:  # pragma: no cover
            self.statusBar().showMessage(f"Log save failed: {exc}", 4000)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _discover_examples(self) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        if not os.path.isdir(self._examples_dir):
            return out
        for name in sorted(os.listdir(self._examples_dir)):
            if name.endswith(".py"):
                out.append((name, os.path.join(self._examples_dir, name)))
        return out

    def _discover_maps(self) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        if not os.path.isdir(self._maps_dir):
            return out
        for name in sorted(os.listdir(self._maps_dir)):
            if name.endswith(".json"):
                out.append((name, os.path.join(self._maps_dir, name)))
        return out

    def _load_default_example(self) -> None:
        target = os.path.join(self._examples_dir, "move_to_goal.py")
        if os.path.isfile(target):
            self._editor.load_path(target)
            for i in range(self._examples_combo.count()):
                if self._examples_combo.itemData(i) == target:
                    self._examples_combo.setCurrentIndex(i)
                    break

    def _set_status_state(self, severity: str, text: str) -> None:
        """Update the leftmost badge in the status bar."""
        prop = {
            "success": "badge-success",
            "warning": "badge-warning",
            "error":   "badge-error",
            "idle":    "badge-idle",
        }.get(severity, "badge-idle")
        self._status_state.setProperty("role", prop)
        self._status_state.setText(text)
        # Force re-polish so the new role styles take effect.
        self._status_state.style().unpolish(self._status_state)
        self._status_state.style().polish(self._status_state)
