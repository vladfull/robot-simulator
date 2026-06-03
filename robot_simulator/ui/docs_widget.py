"""
Documentation viewer widget.

Renders Markdown files from the project's `docs/` directory in a
QTextBrowser. Two columns: left list of available pages, right scrollable
content. Internal links between docs (e.g. `api_reference.md`) work
because we keep the current directory as the base URL.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


# A tiny Markdown-to-HTML converter. Qt's QTextBrowser also accepts
# `setMarkdown(...)` (Qt 5.14+) — we use that directly when available
# and fall back to this small renderer otherwise. We DO NOT use any
# external Markdown library because we keep the dependency footprint
# small (TS §1.6: no heavy frameworks).
def _simple_markdown_to_html(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    in_list = False

    def flush_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in lines:
        line = raw.rstrip()

        if line.startswith("```"):
            flush_list()
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                out.append("<pre style='background:#f4f4f4;padding:6px;'>")
                in_code = True
            continue

        if in_code:
            out.append(_html_escape(line))
            continue

        if line.startswith("# "):
            flush_list()
            out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            flush_list()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            flush_list()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("> "):
            flush_list()
            out.append(
                f"<blockquote style='border-left:3px solid #ccc;"
                f"padding-left:8px;color:#444;'>{_inline(line[2:])}</blockquote>"
            )
        elif re.match(r"^\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            content = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{_inline(content)}</li>")
        elif line.strip() == "":
            flush_list()
            out.append("<br/>")
        elif re.match(r"^\s*\|", line):
            # Tables: render as preformatted to keep alignment.
            flush_list()
            out.append(f"<pre>{_html_escape(line)}</pre>")
        else:
            flush_list()
            out.append(f"<p>{_inline(line)}</p>")

    if in_code:
        out.append("</pre>")
    flush_list()

    return "\n".join(out)


def _html_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    """Inline markdown: code, bold, italics, links."""
    text = _html_escape(text)
    # `code`
    text = re.sub(r"`([^`]+)`", r"<code style='background:#f4f4f4;padding:0 3px;'>\1</code>", text)
    # **bold**
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # *italic*
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    # [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2'>\1</a>", text)
    return text


class DocsWidget(QWidget):
    """Two-pane Markdown viewer for the docs/ directory."""

    def __init__(self, docs_dir: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._docs_dir = docs_dir

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Documentation")
        title.setStyleSheet("font-weight:bold; padding:6px;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        self._list = QListWidget()
        self._list.setMaximumWidth(200)
        self._list.itemSelectionChanged.connect(self._on_selected)
        splitter.addWidget(self._list)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_anchor)
        splitter.addWidget(self._browser)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._populate()

    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._list.clear()
        if not os.path.isdir(self._docs_dir):
            return
        # Stable order: index first, then alphabetical.
        files = sorted(
            (f for f in os.listdir(self._docs_dir) if f.endswith(".md")),
            key=lambda n: (n != "index.md", n),
        )
        for name in files:
            self._list.addItem(name)

        if self._list.count() > 0:
            self._list.setCurrentRow(0)

    def _on_selected(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        path = os.path.join(self._docs_dir, item.text())
        self._show_path(path)

    def _show_path(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            self._browser.setHtml(f"<p>Cannot open {path}: {exc}</p>")
            return

        # Prefer Qt's native Markdown rendering when available.
        if hasattr(self._browser, "setMarkdown"):
            self._browser.setMarkdown(text)
            self._browser.setSearchPaths([self._docs_dir])
        else:
            html = _simple_markdown_to_html(text)
            self._browser.setHtml(html)

    def _on_anchor(self, url: QUrl) -> None:
        ref = url.toString()
        if ref.endswith(".md"):
            target = os.path.join(self._docs_dir, ref)
            if os.path.isfile(target):
                # Update the list selection to match.
                for i in range(self._list.count()):
                    if self._list.item(i).text() == ref:
                        self._list.setCurrentRow(i)
                        return
                self._show_path(target)
            return
        # External or anchor links: ignore for offline-first MVP.
