"""
Code Editor

QPlainTextEdit + line-number gutter + Python syntax highlighter.
Implements the editor portion of TS §1.4 ФВ-3.

Public API:
    CodeEditor(parent=None)
        .toPlainText()
        .setPlainText(text)
        .open_file()                # opens file dialog, loads .py
        .save_file()                # save dialog
        .load_path(path)
"""

from __future__ import annotations

import os
from typing import Optional

from PyQt5.QtCore import QRegExp, QRect, QSize, Qt
from PyQt5.QtGui import (
    QColor,
    QFont,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
    QTextFormat,
)
from PyQt5.QtWidgets import (
    QFileDialog,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

from .theme import BG, BORDER, SYNTAX, TEXT, mono_font


# ---------------------------------------------------------------------------
# Syntax highlighter
# ---------------------------------------------------------------------------
PYTHON_KEYWORDS = (
    "False None True and as assert async await break class continue def del "
    "elif else except finally for from global if import in is lambda "
    "nonlocal not or pass raise return try while with yield"
).split()

PYTHON_BUILTINS = (
    "abs all any bool dict enumerate filter float frozenset int len list map "
    "max min print range repr reversed round set sorted str sum tuple type zip "
    "isinstance hasattr getattr divmod pow"
).split()


class _PythonHighlighter(QSyntaxHighlighter):
    """Lightweight regex-based Python highlighter."""

    def __init__(self, document):
        super().__init__(document)

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor(SYNTAX.KEYWORD))
        kw_fmt.setFontWeight(QFont.Medium)

        builtin_fmt = QTextCharFormat()
        builtin_fmt.setForeground(QColor(SYNTAX.BUILTIN))

        self_fmt = QTextCharFormat()
        self_fmt.setForeground(QColor(SYNTAX.SELF))
        self_fmt.setFontItalic(True)

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor(SYNTAX.NUMBER))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor(SYNTAX.STRING))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor(SYNTAX.COMMENT))
        comment_fmt.setFontItalic(True)

        decorator_fmt = QTextCharFormat()
        decorator_fmt.setForeground(QColor(SYNTAX.DECORATOR))

        function_fmt = QTextCharFormat()
        function_fmt.setForeground(QColor(SYNTAX.FUNCTION_NAME))

        self._rules = []

        # Keywords: \bword\b
        for word in PYTHON_KEYWORDS:
            self._rules.append((QRegExp(rf"\b{word}\b"), kw_fmt))
        for word in PYTHON_BUILTINS:
            self._rules.append((QRegExp(rf"\b{word}\b"), builtin_fmt))

        self._rules.append((QRegExp(r"\bself\b"), self_fmt))

        # def NAME and class NAME
        self._rules.append((QRegExp(r"\bdef\s+(\w+)"), function_fmt))
        self._rules.append((QRegExp(r"\bclass\s+(\w+)"), function_fmt))

        # Numbers
        self._rules.append((QRegExp(r"\b[0-9]+(\.[0-9]+)?\b"), number_fmt))

        # Strings (single/double, no triple — handled separately as a fallback)
        self._rules.append((QRegExp(r'"[^"\\]*(\\.[^"\\]*)*"'), string_fmt))
        self._rules.append((QRegExp(r"'[^'\\]*(\\.[^'\\]*)*'"), string_fmt))

        # Decorators
        self._rules.append((QRegExp(r"^\s*@\w+"), decorator_fmt))

        # Comments — applied last so the rest is overridden.
        self._rules.append((QRegExp(r"#[^\n]*"), comment_fmt))

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt naming)
        for pattern, fmt in self._rules:
            i = pattern.indexIn(text, 0)
            while i >= 0:
                length = pattern.matchedLength()
                self.setFormat(i, length, fmt)
                i = pattern.indexIn(text, i + length)


# ---------------------------------------------------------------------------
# Line-number gutter
# ---------------------------------------------------------------------------
class _LineNumberArea(QWidget):
    def __init__(self, editor: "CodeEditor"):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event):  # noqa: N802
        self._editor.line_number_area_paint(event)


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------
class CodeEditor(QPlainTextEdit):
    """Python-aware editor with line numbers and current-line highlight."""

    # Font-size scale bounds (in pt). Roomy enough for both 4K and 13" laptops.
    MIN_FONT_SIZE = 9
    MAX_FONT_SIZE = 22
    DEFAULT_FONT_SIZE = 12

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._font_size = self.DEFAULT_FONT_SIZE
        self._apply_font_size(self._font_size)
        # Editor surfaces are drawn by QSS; we just ensure smooth rendering.
        self.setFrameStyle(0)

        self._line_area = _LineNumberArea(self)
        self._highlighter = _PythonHighlighter(self.document())

        self.blockCountChanged.connect(self._update_line_area_width)
        self.updateRequest.connect(self._update_line_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)

        self._update_line_area_width(0)
        self._highlight_current_line()

        self._current_path: Optional[str] = None

    # ------------------------------------------------------------------
    # File operations (used by the toolbar)
    # ------------------------------------------------------------------
    def open_file(self, default_dir: str = "") -> Optional[str]:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open algorithm", default_dir, "Python files (*.py);;All files (*.*)"
        )
        if path:
            self.load_path(path)
        return path or None

    def save_file(self, default_dir: str = "") -> Optional[str]:
        path = self._current_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save algorithm", default_dir, "Python files (*.py)"
            )
        if not path:
            return None
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
        except OSError:
            return None
        self._current_path = path
        return path

    def save_file_as(self, default_dir: str = "") -> Optional[str]:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save algorithm as", default_dir, "Python files (*.py)"
        )
        if not path:
            return None
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
        except OSError:
            return None
        self._current_path = path
        return path

    def load_path(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setPlainText(f.read())
        except OSError:
            return False
        self._current_path = path
        self.document().setModified(False)
        return True

    def new_file(self, template: str = "") -> None:
        """
        Reset the editor to a blank (or templated) file.

        Clears the on-disk path so the next Save asks for a location,
        seeds the editor with the supplied template (helpful for
        beginners), and marks the document unmodified so leaving the
        page right away doesn't trigger an "unsaved changes" prompt.
        """
        self._current_path = None
        self.setPlainText(template)
        # Park the cursor at the first TODO line if there's one, else at the end.
        cursor = self.textCursor()
        idx = template.find("# TODO")
        if idx >= 0:
            cursor.setPosition(idx)
        else:
            cursor.movePosition(cursor.End)
        self.setTextCursor(cursor)
        self.document().setModified(False)
        self.setFocus()

    def current_path(self) -> Optional[str]:
        return self._current_path

    # ------------------------------------------------------------------
    # Font size
    # ------------------------------------------------------------------
    def font_size(self) -> int:
        """Current editor font size in pt."""
        return self._font_size

    def set_font_size(self, size: int) -> None:
        """Clamp and apply a new editor font size (also rescales gutter)."""
        size = max(self.MIN_FONT_SIZE, min(self.MAX_FONT_SIZE, int(size)))
        if size == self._font_size:
            return
        self._font_size = size
        self._apply_font_size(size)

    def zoom_in(self) -> None:
        self.set_font_size(self._font_size + 1)

    def zoom_out(self) -> None:
        self.set_font_size(self._font_size - 1)

    def zoom_reset(self) -> None:
        self.set_font_size(self.DEFAULT_FONT_SIZE)

    def _apply_font_size(self, size: int) -> None:
        font = mono_font(size)
        self.setFont(font)
        # Tab visual width follows the new font metrics.
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        # Repaint the gutter so its width matches the new metrics.
        self._update_line_area_width(0) if hasattr(self, "_line_area") else None

    # ------------------------------------------------------------------
    # Auto-indent on Enter, plus Ctrl+= / Ctrl+- / Ctrl+0 zoom
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):  # noqa: N802
        # Editor zoom shortcuts — standard IDE bindings.
        if event.modifiers() & Qt.ControlModifier:
            if event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self.zoom_in()
                return
            if event.key() == Qt.Key_Minus:
                self.zoom_out()
                return
            if event.key() == Qt.Key_0:
                self.zoom_reset()
                return

        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            cursor.insertText("\n")
            block_text = cursor.block().previous().text()
            indent = ""
            for ch in block_text:
                if ch in (" ", "\t"):
                    indent += ch
                else:
                    break
            stripped = block_text.rstrip()
            if stripped.endswith(":"):
                indent += "    "
            cursor.insertText(indent)
            self.setTextCursor(cursor)
            return

        if event.key() == Qt.Key_Tab:
            self.textCursor().insertText("    ")
            return

        super().keyPressEvent(event)

    def wheelEvent(self, event):  # noqa: N802
        # Ctrl + wheel zooms (matches VS Code / PyCharm).
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    # ------------------------------------------------------------------
    # Line number gutter
    # ------------------------------------------------------------------
    def line_number_area_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 8 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_area_width(self, _new_block_count: int) -> None:
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_area(self, rect: QRect, dy: int) -> None:
        if dy:
            self._line_area.scroll(0, dy)
        else:
            self._line_area.update(0, rect.y(), self._line_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_line_area_width(0)

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_area.setGeometry(QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height()))

    def line_number_area_paint(self, event) -> None:
        painter = QPainter(self._line_area)
        painter.fillRect(event.rect(), QColor(BG.BASE))
        # Subtle separator between gutter and code.
        painter.setPen(QColor(BORDER.SUBTLE))
        right = self._line_area.width() - 1
        painter.drawLine(right, event.rect().top(), right, event.rect().bottom())

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        current_line = self.textCursor().blockNumber()
        muted = QColor(TEXT.MUTED)
        primary = QColor(TEXT.PRIMARY)
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(primary if block_number == current_line else muted)
                painter.drawText(
                    0, top, self._line_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignRight, number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    # ------------------------------------------------------------------
    # Current line highlight
    # ------------------------------------------------------------------
    def _highlight_current_line(self) -> None:
        selections = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(BG.OVERLAY))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            selections.append(sel)
        self.setExtraSelections(selections)
        # Repaint the gutter so the active number lights up.
        self._line_area.update()
