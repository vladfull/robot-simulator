"""
Design system: tokens + QSS stylesheet.

Single source of truth for colors, fonts, spacing, and component styling.
Modelled after VS Code / JetBrains / Unity for an engineering-tool feel.

Usage:
    from ui.theme import apply_theme
    apply_theme(app)

Token naming:
    BG.*       — surface backgrounds (deep < base < elevated < overlay)
    BORDER.*   — strokes (subtle / default / strong)
    TEXT.*     — content (primary / secondary / muted / disabled)
    ACCENT.*   — primary brand action
    SEMANTIC.* — success / warning / error / info
    SYNTAX.*   — code highlighter palette
    VIEWPORT.* — colours used by PyGame inside the simulation canvas
"""

from __future__ import annotations

from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
class BG:
    DEEP = "#0d1014"
    BASE = "#14171c"
    ELEVATED = "#1a1f26"
    OVERLAY = "#232830"
    HOVER = "#1f242c"


class BORDER:
    SUBTLE = "#1f242c"
    DEFAULT = "#2c333d"
    STRONG = "#3a424d"


class TEXT:
    PRIMARY = "#e6edf3"
    SECONDARY = "#98a2b3"
    MUTED = "#5e6776"
    DISABLED = "#3e4754"


class ACCENT:
    BASE = "#4f8cff"
    HOVER = "#6c9eff"
    PRESSED = "#3a78e8"
    SUBTLE = "#1f2c45"   # accent-tinted surface (selection, focus bg)


class SEMANTIC:
    SUCCESS = "#3fb950"
    SUCCESS_HOVER = "#56c46a"
    WARNING = "#d29922"
    ERROR = "#f85149"
    INFO = "#58a6ff"


class SYNTAX:
    KEYWORD = "#cf8e6d"      # def, if, return — warm orange-brown
    BUILTIN = "#8eb8ff"      # min, max, len   — soft blue
    SELF = "#94558d"
    NUMBER = "#2aacb8"
    STRING = "#6aab73"
    COMMENT = "#7a8390"
    DECORATOR = "#b8a957"
    FUNCTION_NAME = "#ffc66d"


class VIEWPORT:
    """Colours used inside the PyGame surface (RGB tuples for pygame)."""
    BG = (13, 16, 20)               # matches BG.DEEP
    GRID_FAINT = (28, 33, 41)
    GRID_AXIS = (52, 60, 73)
    OBSTACLE = (38, 44, 53)
    OBSTACLE_BORDER = (88, 100, 117)
    BOUNDARY = (64, 73, 88)
    ROBOT_BODY = (79, 140, 255)
    ROBOT_OUTLINE = (190, 210, 255)
    ROBOT_FRONT = (255, 211, 92)
    RAY_FREE = (95, 184, 120)
    RAY_HIT = (245, 90, 78)
    GOAL = (63, 185, 80)
    GOAL_RING = (220, 240, 220)
    TRAIL = (108, 158, 255)
    PATH = (210, 153, 34)
    HUD_TEXT = (180, 196, 215)
    HUD_TEXT_MUTED = (130, 145, 165)
    HUD_PILL_BG = (26, 31, 38)
    HUD_PILL_BORDER = (60, 70, 85)


# ---------------------------------------------------------------------------
# Spacing scale (4-px base)
# ---------------------------------------------------------------------------
class SPACING:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
UI_FONT_FAMILIES = '"Segoe UI Variable", "Segoe UI", "Inter", "Helvetica Neue", system-ui'
MONO_FONT_FAMILIES = '"JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", "Menlo"'


def ui_font(point_size: int = 9, weight: int = QFont.Normal) -> QFont:
    f = QFont()
    f.setFamilies(["Segoe UI Variable", "Segoe UI", "Inter", "Helvetica Neue"])
    f.setStyleHint(QFont.SansSerif)
    f.setPointSize(point_size)
    f.setWeight(weight)
    return f


def mono_font(point_size: int = 10) -> QFont:
    f = QFont()
    f.setFamilies(["JetBrains Mono", "Cascadia Code", "Fira Code", "Consolas", "Menlo"])
    f.setStyleHint(QFont.Monospace)
    f.setPointSize(point_size)
    return f


# ---------------------------------------------------------------------------
# QSS stylesheet
# ---------------------------------------------------------------------------
def _qss() -> str:
    return f"""
/* =========================================================
   Base / windowing
   ========================================================= */
QMainWindow,
QDialog,
QWidget#CentralWidget {{
    background: {BG.BASE};
    color: {TEXT.PRIMARY};
}}

QWidget {{
    color: {TEXT.PRIMARY};
    font-family: {UI_FONT_FAMILIES};
    font-size: 12px;
    selection-background-color: {ACCENT.SUBTLE};
    selection-color: {TEXT.PRIMARY};
}}

QToolTip {{
    background: {BG.OVERLAY};
    color: {TEXT.PRIMARY};
    border: 1px solid {BORDER.DEFAULT};
    padding: 6px 8px;
}}

/* =========================================================
   Splitters, dock separators
   ========================================================= */
QSplitter::handle {{
    background: {BG.BASE};
}}
QSplitter::handle:horizontal {{
    width: 1px;
    background: {BORDER.SUBTLE};
}}
QSplitter::handle:vertical {{
    height: 1px;
    background: {BORDER.SUBTLE};
}}

QDockWidget {{
    color: {TEXT.SECONDARY};
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background: {BG.BASE};
    padding: 6px 10px;
    border-bottom: 1px solid {BORDER.SUBTLE};
    font-weight: 600;
    text-align: left;
}}

/* =========================================================
   Toolbar
   ========================================================= */
QToolBar {{
    background: {BG.DEEP};
    border: none;
    border-bottom: 1px solid {BORDER.SUBTLE};
    padding: 6px 8px;
    spacing: 6px;
}}
QToolBar QLabel {{
    color: {TEXT.SECONDARY};
    padding: 0 4px;
    font-size: 12px;
}}
QToolBar::separator {{
    background: {BORDER.SUBTLE};
    width: 1px;
    margin: 4px 6px;
}}

/* =========================================================
   Buttons
   ========================================================= */
QPushButton {{
    background: {BG.ELEVATED};
    color: {TEXT.PRIMARY};
    border: 1px solid {BORDER.DEFAULT};
    border-radius: 4px;
    padding: 6px 12px;
    min-height: 22px;
}}
QPushButton:hover {{
    background: {BG.OVERLAY};
    border-color: {BORDER.STRONG};
}}
QPushButton:pressed {{
    background: {BG.HOVER};
}}
QPushButton:disabled {{
    color: {TEXT.DISABLED};
    border-color: {BORDER.SUBTLE};
}}
QPushButton[variant="primary"] {{
    background: {ACCENT.BASE};
    border-color: {ACCENT.BASE};
    color: white;
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{
    background: {ACCENT.HOVER};
    border-color: {ACCENT.HOVER};
}}
QPushButton[variant="primary"]:pressed {{
    background: {ACCENT.PRESSED};
}}
QPushButton[variant="success"] {{
    background: {SEMANTIC.SUCCESS};
    border-color: {SEMANTIC.SUCCESS};
    color: #08130c;
    font-weight: 600;
}}
QPushButton[variant="success"]:hover {{
    background: {SEMANTIC.SUCCESS_HOVER};
    border-color: {SEMANTIC.SUCCESS_HOVER};
}}
QPushButton[variant="ghost"] {{
    background: transparent;
    border-color: transparent;
    color: {TEXT.SECONDARY};
}}
QPushButton[variant="ghost"]:hover {{
    background: {BG.OVERLAY};
    color: {TEXT.PRIMARY};
}}

/* =========================================================
   Combo & line inputs
   ========================================================= */
QComboBox {{
    background: {BG.ELEVATED};
    color: {TEXT.PRIMARY};
    border: 1px solid {BORDER.DEFAULT};
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 22px;
    min-width: 100px;
}}
QComboBox:hover {{
    border-color: {BORDER.STRONG};
}}
QComboBox:focus {{
    border-color: {ACCENT.BASE};
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {TEXT.SECONDARY};
    margin-right: 8px;
    width: 0;
    height: 0;
}}
QComboBox QAbstractItemView {{
    background: {BG.ELEVATED};
    color: {TEXT.PRIMARY};
    border: 1px solid {BORDER.DEFAULT};
    selection-background-color: {ACCENT.SUBTLE};
    selection-color: {TEXT.PRIMARY};
    padding: 4px;
    outline: none;
}}

QLineEdit, QSpinBox, QDoubleSpinBox {{
    background: {BG.ELEVATED};
    color: {TEXT.PRIMARY};
    border: 1px solid {BORDER.DEFAULT};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {ACCENT.SUBTLE};
}}
QLineEdit:focus {{
    border-color: {ACCENT.BASE};
}}

/* =========================================================
   Sliders
   ========================================================= */
QSlider::groove:horizontal {{
    background: {BG.OVERLAY};
    height: 4px;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT.BASE};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {TEXT.PRIMARY};
    border: none;
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
}}
QSlider::handle:horizontal:hover {{
    background: {ACCENT.HOVER};
}}

/* =========================================================
   Tabs
   ========================================================= */
QTabWidget::pane {{
    background: {BG.ELEVATED};
    border: 1px solid {BORDER.SUBTLE};
    border-top: none;
}}
QTabBar::tab {{
    background: {BG.BASE};
    color: {TEXT.SECONDARY};
    padding: 8px 16px;
    margin-right: 1px;
    border: 1px solid {BORDER.SUBTLE};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background: {BG.ELEVATED};
    color: {TEXT.PRIMARY};
    border-bottom: 2px solid {ACCENT.BASE};
}}
QTabBar::tab:hover:!selected {{
    background: {BG.HOVER};
    color: {TEXT.PRIMARY};
}}

/* =========================================================
   Group boxes (used by Inspector cards)
   ========================================================= */
QGroupBox {{
    background: {BG.ELEVATED};
    border: 1px solid {BORDER.SUBTLE};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
    font-weight: 600;
    color: {TEXT.PRIMARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    margin-left: 8px;
    background: {BG.ELEVATED};
    color: {TEXT.SECONDARY};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* =========================================================
   Status bar
   ========================================================= */
QStatusBar {{
    background: {BG.DEEP};
    color: {TEXT.SECONDARY};
    border-top: 1px solid {BORDER.SUBTLE};
    padding: 4px 8px;
    font-size: 11px;
}}
QStatusBar QLabel {{
    color: {TEXT.SECONDARY};
    padding: 0 8px;
    border-right: 1px solid {BORDER.SUBTLE};
}}
QStatusBar QLabel[severity="success"] {{ color: {SEMANTIC.SUCCESS}; }}
QStatusBar QLabel[severity="warning"] {{ color: {SEMANTIC.WARNING}; }}
QStatusBar QLabel[severity="error"]   {{ color: {SEMANTIC.ERROR}; }}
QStatusBar QLabel[role="last"] {{ border-right: none; }}

/* =========================================================
   Scrollbars (minimal, IDE-like)
   ========================================================= */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER.STRONG};
    min-height: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT.MUTED};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER.STRONG};
    min-width: 24px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT.MUTED};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* =========================================================
   List widget (docs nav, examples)
   ========================================================= */
QListWidget {{
    background: {BG.BASE};
    color: {TEXT.PRIMARY};
    border: none;
    padding: 4px;
    outline: 0;
}}
QListWidget::item {{
    padding: 6px 10px;
    border-radius: 4px;
}}
QListWidget::item:hover {{
    background: {BG.OVERLAY};
}}
QListWidget::item:selected {{
    background: {ACCENT.SUBTLE};
    color: {TEXT.PRIMARY};
}}

/* =========================================================
   Plain text edits (editor + console)
   ========================================================= */
QPlainTextEdit, QTextBrowser {{
    background: {BG.ELEVATED};
    color: {TEXT.PRIMARY};
    border: none;
    selection-background-color: {ACCENT.SUBTLE};
    selection-color: {TEXT.PRIMARY};
}}
QPlainTextEdit:disabled, QTextBrowser:disabled {{
    background: {BG.BASE};
    color: {TEXT.DISABLED};
    selection-background-color: transparent;
}}

/* =========================================================
   Mode banner shown above the editor when it's disabled.
   ========================================================= */
QFrame#ModeBanner {{
    background: rgba(210, 153, 34, 0.10);
    border: 1px solid rgba(210, 153, 34, 0.35);
    border-radius: 6px;
}}
QFrame#ModeBanner QLabel {{
    color: {SEMANTIC.WARNING};
    background: transparent;
    border: none;
    padding: 6px 12px;
    font-size: 12px;
}}

/* =========================================================
   Labels with semantic roles
   ========================================================= */
QLabel[role="caption"] {{
    color: {TEXT.MUTED};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QLabel[role="value"] {{
    color: {TEXT.PRIMARY};
    font-family: {MONO_FONT_FAMILIES};
}}
QLabel[role="metric"] {{
    color: {TEXT.PRIMARY};
    font-family: {MONO_FONT_FAMILIES};
    font-size: 13px;
}}
QLabel[role="badge-success"] {{
    background: rgba(63, 185, 80, 0.15);
    color: {SEMANTIC.SUCCESS};
    border-radius: 9px;
    padding: 2px 10px;
    font-weight: 600;
    font-size: 11px;
}}
QLabel[role="badge-warning"] {{
    background: rgba(210, 153, 34, 0.15);
    color: {SEMANTIC.WARNING};
    border-radius: 9px;
    padding: 2px 10px;
    font-weight: 600;
    font-size: 11px;
}}
QLabel[role="badge-error"] {{
    background: rgba(248, 81, 73, 0.15);
    color: {SEMANTIC.ERROR};
    border-radius: 9px;
    padding: 2px 10px;
    font-weight: 600;
    font-size: 11px;
}}
QLabel[role="badge-idle"] {{
    background: {BG.OVERLAY};
    color: {TEXT.SECONDARY};
    border-radius: 9px;
    padding: 2px 10px;
    font-weight: 600;
    font-size: 11px;
}}
"""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def apply_theme(app: QApplication) -> None:
    """Install the dark theme + base font on a QApplication."""
    app.setStyleSheet(_qss())
    app.setFont(ui_font(10))
