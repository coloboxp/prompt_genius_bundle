"""Inspect the prompts that went to the LLM backend in the last generation.

Reads from :mod:`prompt_genius.core.llm_trace`. Each parallel proposer call
gets its own tab: the exact prompt fed to ``claude -p`` / ``codex exec`` on
the left, the raw model output on the right, with a header showing backend,
direction, latency, return code.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from prompt_genius.core.llm_trace import recent


def _mono_text(text: str) -> QPlainTextEdit:
    edit = QPlainTextEdit(text)
    edit.setReadOnly(True)
    edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
    font = QFont("Menlo")
    font.setStyleHint(QFont.StyleHint.Monospace)
    edit.setFont(font)
    return edit


class LlmTraceDialog(QDialog):
    """Show the captured prompt / output for each LLM call in the last generation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Last LLM prompts")
        self.resize(1100, 720)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        calls = recent()

        if not calls:
            root.addWidget(QLabel(
                "<i>No LLM calls captured yet. Run a generation with backend "
                "set to <b>claude</b> or <b>codex</b>, then come back here.</i>"
            ))
        else:
            header = QLabel(
                f"<b>{len(calls)} call(s)</b> captured from the last generation. "
                "Tabs are ordered by start time."
            )
            header.setWordWrap(True)
            root.addWidget(header)

            self.tabs = QTabWidget()
            for index, call in enumerate(calls, 1):
                self.tabs.addTab(self._make_call_tab(call), f"#{index} · {call.direction or call.backend}")
            root.addWidget(self.tabs, stretch=1)

        bottom = QHBoxLayout()
        copy_btn = QPushButton("Copy prompt")
        copy_btn.setToolTip("Copy the prompt of the currently-open tab to the clipboard.")
        copy_btn.clicked.connect(self._copy_current_prompt)
        copy_btn.setEnabled(bool(calls))
        bottom.addWidget(copy_btn)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        bottom.addWidget(buttons)
        root.addLayout(bottom)

    # ------------------------------------------------------------------ tabs

    def _make_call_tab(self, call) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(6)

        status_color = "#2e8b57" if call.returncode == 0 else "#c0392b"
        meta = QLabel(
            f"<span style='color:gray'>backend:</span> <b>{call.backend}</b>"
            f"   <span style='color:gray'>binary:</span> {call.binary}"
            f"   <span style='color:gray'>args:</span> {' '.join(call.args) or '—'}"
            f"<br>"
            f"<span style='color:gray'>direction:</span> {call.direction or '—'}"
            f"   <span style='color:gray'>latency:</span> {call.elapsed_seconds:.1f}s"
            f"   <span style='color:gray'>rc:</span> "
            f"<span style='color:{status_color}'><b>{call.returncode}</b></span>"
            f"   <span style='color:gray'>prompt:</span> {len(call.prompt):,} chars"
            f"   <span style='color:gray'>output:</span> {len(call.output):,} chars"
        )
        meta.setTextFormat(Qt.TextFormat.RichText)
        meta.setWordWrap(True)
        layout.addWidget(meta)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.addWidget(QLabel("<b>Prompt (input)</b>"))
        prompt_view = _mono_text(call.prompt)
        prompt_view.setToolTip("Exact prompt fed to the backend via stdin or positional argv.")
        left_layout.addWidget(prompt_view, stretch=1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.addWidget(QLabel("<b>Raw output</b>"))
        out_view = _mono_text(call.output or "<no output>")
        out_view.setToolTip("Raw stdout from the LLM CLI — pre-parsing.")
        right_layout.addWidget(out_view, stretch=1)
        splitter.addWidget(right)

        splitter.setSizes([600, 480])
        layout.addWidget(splitter, stretch=1)
        # Stash the prompt on the widget so the Copy button can find it.
        widget.setProperty("_pg_prompt", call.prompt)
        return widget

    def _copy_current_prompt(self) -> None:
        if not hasattr(self, "tabs"):
            return
        current = self.tabs.currentWidget()
        if current is None:
            return
        prompt = current.property("_pg_prompt") or ""
        QApplication.clipboard().setText(str(prompt))
