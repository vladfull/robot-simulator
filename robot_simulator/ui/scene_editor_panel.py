"""
Scene Editor side panel.

Sits inside the right-hand Inspector as a single themed card. While
Edit Mode is off, the controls inside are present-but-inert (an
edit-toggle button at the top is the only thing you can interact with).
When Edit Mode is enabled the rest of the card lights up.

The panel is a thin view: it owns no editor state of its own — every
interaction calls a method on the supplied :class:`EditorController`
or emits a signal the main window connects to file operations.
"""

from __future__ import annotations

import os
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from scene_editor.editor_controller import EditorController
from scene_editor.map_serializer import MapModel

from .theme import SPACING


class SceneEditorPanel(QWidget):
    """Sidebar card with all scene-editing controls."""

    # Emitted when the user toggles Edit Mode (so MainWindow can pause
    # simulation, route mouse events, etc.).
    editModeToggled = pyqtSignal(bool)
    # Emitted after a successful load/save/new so the main window can
    # refresh the map dropdown or persist the new file location.
    mapPathChanged = pyqtSignal(str)
    # Emitted when the user accepts the current model as the simulation
    # environment (Apply To Simulation button). MainWindow rebuilds the
    # engine from controller.model.
    applyRequested = pyqtSignal()

    def __init__(self, controller: EditorController, maps_dir: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._controller = controller
        self._maps_dir = maps_dir

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(SPACING.SM)
        outer.addWidget(self._build_card())

        # Sync UI when the controller's state changes elsewhere.
        controller.modelChanged.connect(self._refresh_from_model)
        controller.dirtyChanged.connect(self._on_dirty_changed)

        self._refresh_from_model()
        self._set_tools_enabled(False)

    # ------------------------------------------------------------------
    # Card build
    # ------------------------------------------------------------------
    def _build_card(self) -> QWidget:
        # The tab title already says "Scene Editor", so we drop the
        # GroupBox header entirely and use a plain container — keeps the
        # vertical rhythm tight and removes a duplicate label.
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(SPACING.MD, SPACING.MD, SPACING.MD, SPACING.MD)
        layout.setSpacing(SPACING.SM)

        # --- Master toggle ---
        self._edit_toggle = QPushButton("Enable Edit Mode")
        self._edit_toggle.setCheckable(True)
        self._edit_toggle.setProperty("variant", "primary")
        self._edit_toggle.toggled.connect(self._on_edit_toggle)
        layout.addWidget(self._edit_toggle)

        # --- Tool radio group ---
        tools_cap = QLabel("Tool")
        tools_cap.setProperty("role", "caption")
        layout.addWidget(tools_cap)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)
        tool_row = QVBoxLayout()
        tool_row.setSpacing(2)
        self._tool_buttons = {}
        for name, label in [
            ("select", "Select / Move / Delete"),
            ("add_obstacle", "Add Obstacle (drag)"),
            ("set_start", "Set Start (drag for heading)"),
            ("set_goal", "Set Goal"),
        ]:
            btn = QRadioButton(label)
            btn.setProperty("tool_name", name)
            btn.toggled.connect(self._on_tool_radio_toggled)
            self._tool_buttons[name] = btn
            self._tool_group.addButton(btn)
            tool_row.addWidget(btn)
        self._tool_buttons["select"].setChecked(True)
        layout.addLayout(tool_row)

        # --- Snap controls ---
        snap_row = QHBoxLayout()
        self._snap_check = QCheckBox("Snap to grid")
        self._snap_check.setChecked(True)
        self._snap_check.toggled.connect(self._controller.set_snap)
        self._snap_step = QDoubleSpinBox()
        self._snap_step.setRange(0.05, 2.0)
        self._snap_step.setSingleStep(0.05)
        self._snap_step.setDecimals(2)
        self._snap_step.setValue(0.5)
        self._snap_step.setSuffix(" m")
        self._snap_step.valueChanged.connect(self._controller.set_grid_step)
        snap_row.addWidget(self._snap_check, 1)
        snap_row.addWidget(self._snap_step)
        layout.addLayout(snap_row)

        # --- World size + name ---
        size_form = QFormLayout()
        size_form.setSpacing(6)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Map name")
        self._name_edit.editingFinished.connect(self._on_name_edited)
        self._width_spin = QDoubleSpinBox()
        self._width_spin.setRange(2.0, 50.0)
        self._width_spin.setSingleStep(0.5)
        self._width_spin.setSuffix(" m")
        self._width_spin.editingFinished.connect(self._on_world_size_edited)
        self._height_spin = QDoubleSpinBox()
        self._height_spin.setRange(2.0, 50.0)
        self._height_spin.setSingleStep(0.5)
        self._height_spin.setSuffix(" m")
        self._height_spin.editingFinished.connect(self._on_world_size_edited)
        name_cap = QLabel("Name"); name_cap.setProperty("role", "caption")
        w_cap = QLabel("Width"); w_cap.setProperty("role", "caption")
        h_cap = QLabel("Height"); h_cap.setProperty("role", "caption")
        size_form.addRow(name_cap, self._name_edit)
        size_form.addRow(w_cap, self._width_spin)
        size_form.addRow(h_cap, self._height_spin)
        layout.addLayout(size_form)

        # --- Bulk actions ---
        actions_cap = QLabel("Map actions")
        actions_cap.setProperty("role", "caption")
        layout.addWidget(actions_cap)

        actions_row1 = QHBoxLayout()
        self._new_btn = QPushButton("New")
        self._load_btn = QPushButton("Load…")
        self._new_btn.clicked.connect(self._on_new)
        self._load_btn.clicked.connect(self._on_load)
        actions_row1.addWidget(self._new_btn)
        actions_row1.addWidget(self._load_btn)
        layout.addLayout(actions_row1)

        actions_row2 = QHBoxLayout()
        self._save_btn = QPushButton("Save")
        self._save_as_btn = QPushButton("Save As…")
        self._save_btn.clicked.connect(self._on_save)
        self._save_as_btn.clicked.connect(self._on_save_as)
        actions_row2.addWidget(self._save_btn)
        actions_row2.addWidget(self._save_as_btn)
        layout.addLayout(actions_row2)

        # --- Selection / Apply ---
        actions_row3 = QHBoxLayout()
        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.setProperty("variant", "ghost")
        self._delete_btn.clicked.connect(self._controller.delete_selected)
        actions_row3.addWidget(self._delete_btn)
        layout.addLayout(actions_row3)

        self._apply_btn = QPushButton("Apply to Simulation")
        self._apply_btn.setProperty("variant", "success")
        self._apply_btn.setToolTip(
            "Replace the simulation's environment with this map and "
            "exit Edit Mode."
        )
        self._apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(self._apply_btn)

        # --- Status line ---
        self._status_label = QLabel("Idle")
        self._status_label.setProperty("role", "caption")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        return box

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_edit_toggle(self, checked: bool) -> None:
        self._edit_toggle.setText("Disable Edit Mode" if checked else "Enable Edit Mode")
        self._set_tools_enabled(checked)
        self.editModeToggled.emit(checked)
        if checked:
            self._set_status("Edit mode on — pick a tool and click on the viewport")
        else:
            self._set_status("Edit mode off")

    def _on_tool_radio_toggled(self, checked: bool) -> None:
        # We only care about the newly-checked button.
        if not checked:
            return
        button = self.sender()
        name = button.property("tool_name") if button else "select"
        self._controller.set_tool(name)

    def _on_name_edited(self) -> None:
        self._controller.set_map_name(self._name_edit.text().strip() or "Untitled Map")

    def _on_world_size_edited(self) -> None:
        self._controller.set_world_size(self._width_spin.value(),
                                        self._height_spin.value())

    def _on_new(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        self._controller.new_map(width=self._width_spin.value() or 10.0,
                                 height=self._height_spin.value() or 10.0)
        self._set_status("New map created")
        self.mapPathChanged.emit("")

    def _on_load(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Load map for editing", self._maps_dir,
            "Map files (*.json);;All files (*.*)"
        )
        if not path:
            return
        try:
            self._controller.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Load failed", str(exc))
            return
        self._set_status(f"Loaded {os.path.basename(path)}")
        self.mapPathChanged.emit(path)

    def _on_save(self) -> None:
        if self._controller.current_path() is None:
            self._on_save_as()
            return
        try:
            saved = self._controller.save()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._set_status(f"Saved to {os.path.basename(saved)}")
        self.mapPathChanged.emit(saved)

    def _on_save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save map as", self._maps_dir, "Map files (*.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self._controller.save(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Save failed", str(exc))
            return
        self._set_status(f"Saved to {os.path.basename(path)}")
        self.mapPathChanged.emit(path)

    def _on_apply(self) -> None:
        self.applyRequested.emit()
        self._set_status("Applied to simulation")

    def _on_dirty_changed(self, dirty: bool) -> None:
        path = self._controller.current_path()
        base = os.path.basename(path) if path else "(unsaved)"
        marker = "•  " if dirty else ""
        self._save_btn.setText(f"{marker}Save" if dirty else "Save")
        self._set_status(f"Editing {marker}{base}")

    def _refresh_from_model(self) -> None:
        m = self._controller.model
        # Blocking signals prevents editingFinished feedback loops when
        # we set fields programmatically.
        self._name_edit.blockSignals(True)
        self._width_spin.blockSignals(True)
        self._height_spin.blockSignals(True)
        self._name_edit.setText(m.name)
        self._width_spin.setValue(m.width)
        self._height_spin.setValue(m.height)
        self._name_edit.blockSignals(False)
        self._width_spin.blockSignals(False)
        self._height_spin.blockSignals(False)

        # Tool radios.
        active = self._controller.tool_name()
        for name, btn in self._tool_buttons.items():
            if name == active and not btn.isChecked():
                btn.blockSignals(True)
                btn.setChecked(True)
                btn.blockSignals(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_tools_enabled(self, enabled: bool) -> None:
        for w in (
            self._tool_buttons["select"],
            self._tool_buttons["add_obstacle"],
            self._tool_buttons["set_start"],
            self._tool_buttons["set_goal"],
            self._snap_check,
            self._snap_step,
            self._name_edit,
            self._width_spin,
            self._height_spin,
            self._new_btn,
            self._load_btn,
            self._save_btn,
            self._save_as_btn,
            self._delete_btn,
            self._apply_btn,
        ):
            w.setEnabled(enabled)

    def _set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def _confirm_discard_if_dirty(self) -> bool:
        if not self._controller.is_dirty():
            return True
        answer = QMessageBox.question(
            self, "Discard unsaved changes?",
            "The current map has unsaved changes. Discard them?",
            QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        return answer == QMessageBox.Discard

    # ------------------------------------------------------------------
    # Public helpers used by MainWindow
    # ------------------------------------------------------------------
    def set_edit_mode(self, enabled: bool) -> None:
        """Programmatic toggle (e.g., from a toolbar action)."""
        if self._edit_toggle.isChecked() != enabled:
            self._edit_toggle.setChecked(enabled)

    def is_edit_mode(self) -> bool:
        return self._edit_toggle.isChecked()
