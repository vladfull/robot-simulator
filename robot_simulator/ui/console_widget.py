"""
Console Widget

Read-only output panel for `api.log()` messages and error tracebacks.
Each line is composed of three parts:
  1. a coloured severity marker (single bullet in the level's colour);
  2. a muted monospaced timestamp;
  3. the message body in the appropriate text colour.

Implements TS §1.4 ФВ-4 (errors are visible to the user).
"""

from __future__ import annotations

from PyQt5.QtCore import QTime, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import QPlainTextEdit, QWidget

from .theme import SEMANTIC, TEXT, mono_font


class ConsoleWidget(QPlainTextEdit):
    """Read-only console for user algorithm output and errors."""

    messageWritten = pyqtSignal(str)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(mono_font(10))
        self.setPlaceholderText(
            "Console output from your algorithm will appear here."
        )
        self.setMaximumBlockCount(2000)
        self.setFrameStyle(0)

    # ------------------------------------------------------------------
    # Public surface used by ExecutionEngine + RobotAPI
    # ------------------------------------------------------------------
    def write(self, text: str) -> None:
        """Plain-info line."""
        self._append(text, QColor(TEXT.PRIMARY), QColor(TEXT.SECONDARY))

    def write_error(self, text: str) -> None:
        """Errors stand out in semantic red."""
        self._append(text, QColor(SEMANTIC.ERROR), QColor(SEMANTIC.ERROR))

    def write_warning(self, text: str) -> None:
        self._append(text, QColor(SEMANTIC.WARNING), QColor(SEMANTIC.WARNING))

    def write_success(self, text: str) -> None:
        self._append(text, QColor(SEMANTIC.SUCCESS), QColor(SEMANTIC.SUCCESS))

    def clear_output(self) -> None:
        self.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _append(self, text: str, body_color: QColor, marker_color: QColor) -> None:
        text = str(text).rstrip()
        if not text:
            return

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)

        marker_fmt = QTextCharFormat()
        marker_fmt.setForeground(marker_color)

        time_fmt = QTextCharFormat()
        time_fmt.setForeground(QColor(TEXT.MUTED))

        body_fmt = QTextCharFormat()
        body_fmt.setForeground(body_color)

        if cursor.position() != 0:
            cursor.insertText("\n")

        timestamp = QTime.currentTime().toString("HH:mm:ss")
        cursor.insertText("● ", marker_fmt)
        cursor.insertText(f"{timestamp}  ", time_fmt)

        # Multi-line messages (e.g. tracebacks) get indented continuations
        # so the timestamp gutter stays aligned.
        lines = text.split("\n")
        cursor.insertText(lines[0], body_fmt)
        for extra in lines[1:]:
            cursor.insertText("\n" + " " * 12 + extra, body_fmt)

        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.messageWritten.emit(text)
