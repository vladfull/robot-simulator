"""
Inspector (formerly ControlPanel)

Right-hand sidebar that exposes the simulation's tunables, organised as
themed cards:

  ▸ Robot      — physical limits (max v, max ω)
  ▸ Algorithm  — selector + per-controller parameter sliders
  ▸ Telemetry  — live read-out (updated externally via update_telemetry)

The Map dropdown lives on the workflow toolbar (single source of truth)
and the Scene Editor lives in the left-side tab strip — neither belongs
in this column anymore, which keeps the right side narrow and stable on
small monitors.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .theme import SPACING, mono_font

CONTROLLER_NAMES = ["PID Controller", "A* Path Planner",
                    "Q-Learning Agent", "Manual Control"]


class _LabeledSlider(QWidget):
    """Compact slider row: caption, value (mono), slider."""

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        label: str,
        minimum: float,
        maximum: float,
        value: float,
        step: float = 0.01,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._scale = 1.0 / step
        self._label_text = label

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self._caption = QLabel(label)
        self._caption.setProperty("role", "caption")

        self._value = QLabel(self._format_value(value))
        self._value.setProperty("role", "value")
        self._value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._value.setFont(mono_font(10))

        header.addWidget(self._caption)
        header.addStretch(1)
        header.addWidget(self._value)
        outer.addLayout(header)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setMinimum(int(minimum * self._scale))
        self._slider.setMaximum(int(maximum * self._scale))
        self._slider.setValue(int(value * self._scale))
        self._slider.valueChanged.connect(self._on_slider_changed)
        outer.addWidget(self._slider)

    def value(self) -> float:
        return self._slider.value() / self._scale

    def setValue(self, v: float) -> None:  # noqa: N802
        self._slider.setValue(int(v * self._scale))

    def _format_value(self, value: float) -> str:
        return f"{value:.2f}"

    def _on_slider_changed(self, _ival: int) -> None:
        v = self.value()
        self._value.setText(self._format_value(v))
        self.valueChanged.emit(v)


class ControlPanel(QWidget):
    """Right-hand inspector panel."""

    # Public signals — preserved from the previous design.
    startClicked = pyqtSignal()
    pauseClicked = pyqtSignal()
    resetClicked = pyqtSignal()
    mapChanged = pyqtSignal(str)
    controllerChanged = pyqtSignal(str)
    parameterChanged = pyqtSignal(str, float)

    def __init__(
        self,
        maps_dir: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._maps_dir = maps_dir
        self._param_widgets: Dict[str, _LabeledSlider] = {}

        self.setMinimumWidth(280)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING.MD, SPACING.MD, SPACING.MD, SPACING.MD)
        root.setSpacing(SPACING.MD)

        # The Scene/Map dropdown lives on the top workflow toolbar — there
        # is no need to mirror it here. Robot → Algorithm → Telemetry is
        # the natural reading order in the inspector.
        root.addWidget(self._build_robot_card())
        self._algo_card = self._build_algorithm_card()
        root.addWidget(self._algo_card)
        root.addWidget(self._build_telemetry_card())
        root.addStretch(1)

        self._populate_controller_parameters(CONTROLLER_NAMES[0])

    # ------------------------------------------------------------------
    # Public update hooks
    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        # Status is now shown in the main status bar; keep this method
        # for back-compat with existing call sites.
        pass

    def current_controller_name(self) -> str:
        return self._controller_combo.currentText()

    def update_telemetry(self, fields: List[Tuple[str, str]]) -> None:
        """Push key→value pairs into the Telemetry card."""
        for i in range(self._telemetry_form.rowCount()):
            self._telemetry_form.removeRow(0)
        for caption, value in fields:
            cap = QLabel(caption)
            cap.setProperty("role", "caption")
            val = QLabel(value)
            val.setProperty("role", "value")
            val.setFont(mono_font(10))
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._telemetry_form.addRow(cap, val)

    # ------------------------------------------------------------------
    # Card builders
    # ------------------------------------------------------------------
    def _build_robot_card(self) -> QGroupBox:
        box = QGroupBox("ROBOT")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(SPACING.MD, SPACING.LG, SPACING.MD, SPACING.MD)
        layout.setSpacing(SPACING.SM)

        self._max_v = _LabeledSlider("Max linear speed (m/s)", 0.1, 2.0, 1.0, step=0.05)
        self._max_omega = _LabeledSlider("Max angular speed (rad/s)", 0.5, 3.0, 2.0, step=0.05)
        self._max_v.valueChanged.connect(
            lambda v: self.parameterChanged.emit("max_linear_velocity", v)
        )
        self._max_omega.valueChanged.connect(
            lambda v: self.parameterChanged.emit("max_angular_velocity", v)
        )
        layout.addWidget(self._max_v)
        layout.addWidget(self._max_omega)
        return box

    def _build_algorithm_card(self) -> QGroupBox:
        box = QGroupBox("ALGORITHM")
        outer = QVBoxLayout(box)
        outer.setContentsMargins(SPACING.MD, SPACING.LG, SPACING.MD, SPACING.MD)
        outer.setSpacing(SPACING.SM)

        cap = QLabel("Built-in selection")
        cap.setProperty("role", "caption")
        outer.addWidget(cap)

        self._controller_combo = QComboBox()
        self._controller_combo.addItems(CONTROLLER_NAMES)
        self._controller_combo.currentTextChanged.connect(self._on_controller_changed)
        outer.addWidget(self._controller_combo)

        params_label = QLabel("Parameters")
        params_label.setProperty("role", "caption")
        outer.addWidget(params_label)

        self._params_holder = QWidget()
        self._params_layout = QVBoxLayout(self._params_holder)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        self._params_layout.setSpacing(SPACING.SM)
        outer.addWidget(self._params_holder)
        return box

    def _build_telemetry_card(self) -> QGroupBox:
        box = QGroupBox("TELEMETRY")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(SPACING.MD, SPACING.LG, SPACING.MD, SPACING.MD)
        layout.setSpacing(SPACING.SM)

        form_holder = QWidget()
        self._telemetry_form = QFormLayout(form_holder)
        self._telemetry_form.setContentsMargins(0, 0, 0, 0)
        self._telemetry_form.setSpacing(6)
        layout.addWidget(form_holder)

        return box

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_controller_changed(self, name: str) -> None:
        self._populate_controller_parameters(name)
        self.controllerChanged.emit(name)

    def _populate_controller_parameters(self, name: str) -> None:
        for widget in self._param_widgets.values():
            widget.deleteLater()
        self._param_widgets.clear()

        if name == "PID Controller":
            specs = [
                ("kp", "Kp",        0.0, 10.0, 2.0, 0.1),
                ("ki", "Ki",        0.0,  1.0, 0.1, 0.01),
                ("kd", "Kd",        0.0,  5.0, 0.5, 0.1),
            ]
        elif name == "A* Path Planner":
            specs = [
                ("grid_resolution",     "Grid resolution (m)", 0.1, 0.5, 0.2, 0.05),
                ("lookahead_distance",  "Lookahead (m)",       0.2, 1.5, 0.5, 0.1),
            ]
        elif name == "Q-Learning Agent":
            specs = [
                ("alpha",   "Learning rate α", 0.01, 0.5,  0.1,  0.01),
                ("gamma",   "Discount γ",      0.5,  0.99, 0.95, 0.01),
                ("epsilon", "Exploration ε",   0.0,  1.0,  0.3,  0.05),
            ]
        else:
            specs = []

        if not specs:
            placeholder = QLabel("No parameters for this algorithm.")
            placeholder.setProperty("role", "caption")
            self._params_layout.addWidget(placeholder)
            self._param_widgets["__placeholder__"] = placeholder  # type: ignore[assignment]
            return

        for key, label, lo, hi, val, step in specs:
            slider = _LabeledSlider(label, lo, hi, val, step=step)
            slider.valueChanged.connect(
                lambda v, k=key: self.parameterChanged.emit(k, v)
            )
            self._params_layout.addWidget(slider)
            self._param_widgets[key] = slider
