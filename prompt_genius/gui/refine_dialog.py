"""Image critique → prompt refinement dialog.

Designer flow:

1. Drop / paste / pick the image that came out of the previous generation.
2. The previous prompt is pre-filled when a card is selected; editable.
3. Designer writes what's wrong in COMMENTS.
4. Picks the backend (claude / codex), hits Refine.
5. LLM looks at the image (via the CLI's file-reading tool) and proposes both
   a granular delta and a complete rewritten prompt.
6. Designer hits "Apply as new card" / "Replace current card" / "Copy".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QThread, Qt, Signal
from PySide6.QtGui import (
    QClipboard,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from prompt_genius.core.refine import RefineResult, refine_prompt


class ImageDropArea(QLabel):
    """A QLabel that accepts drag-drop files, clipboard paste, and a fallback "Pick…"."""

    image_loaded = Signal(object)  # bytes or Path; consumers can branch

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setText(
            "Drop an image here\n"
            "or paste from clipboard (⌘V)\n"
            "or use “Pick file…”"
        )
        self.setStyleSheet(
            "QLabel { border: 2px dashed rgba(127,127,127,0.55); border-radius: 8px;"
            " padding: 20px; color: gray; min-height: 220px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._image_path: Path | None = None
        self._image_bytes: bytes | None = None
        self._original_pixmap: QPixmap | None = None

        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self._on_paste)

    # ------------------------------------------------- public

    def image_source(self) -> bytes | Path | None:
        if self._image_path is not None:
            return self._image_path
        return self._image_bytes

    def clear_image(self) -> None:
        self._image_path = None
        self._image_bytes = None
        self._original_pixmap = None
        self.setPixmap(QPixmap())
        self.setText(
            "Drop an image here\n"
            "or paste from clipboard (⌘V)\n"
            "or use “Pick file…”"
        )

    # ------------------------------------------------- drag & drop

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls() or mime.hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    self._adopt_path(Path(url.toLocalFile()))
                    event.acceptProposedAction()
                    return
        if mime.hasImage():
            image = mime.imageData()
            if isinstance(image, QImage):
                self._adopt_image(image)
                event.acceptProposedAction()

    # ------------------------------------------------- paste

    def _on_paste(self) -> None:
        clipboard = QGuiApplication.clipboard()
        mime = clipboard.mimeData()
        if mime.hasImage():
            image = clipboard.image()
            if not image.isNull():
                self._adopt_image(image)
                return
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    self._adopt_path(Path(url.toLocalFile()))
                    return

    # ------------------------------------------------- adopt helpers

    def _adopt_path(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Image", f"Couldn't load image: {path}")
            return
        self._image_path = path
        self._image_bytes = None
        self._original_pixmap = pixmap
        self._render()
        self.image_loaded.emit(path)

    def _adopt_image(self, image: QImage) -> None:
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        data: QByteArray = buffer.data()
        self._image_bytes = bytes(data)
        self._image_path = None
        self._original_pixmap = QPixmap.fromImage(image)
        self._render()
        self.image_loaded.emit(self._image_bytes)

    def _render(self) -> None:
        if self._original_pixmap is None:
            return
        scaled = self._original_pixmap.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setText("")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render()


# ----------------------------------------------------------- worker

class RefineWorker(QThread):
    finished_ok = Signal(object)  # RefineResult
    finished_err = Signal(str)

    def __init__(
        self,
        parent: QObject | None,
        image_source: Any,
        original_prompt: str,
        comments: str,
        backend: str,
        timeout_seconds: float,
        claude_binary: str = "claude",
        codex_binary: str = "codex",
    ) -> None:
        super().__init__(parent)
        self._image = image_source
        self._prompt = original_prompt
        self._comments = comments
        self._backend = backend
        self._timeout = timeout_seconds
        self._claude_binary = claude_binary
        self._codex_binary = codex_binary
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = refine_prompt(
                self._image, self._prompt, self._comments,
                backend=self._backend, timeout_seconds=self._timeout,
                claude_binary=self._claude_binary,
                codex_binary=self._codex_binary,
            )
            if self._cancelled:
                return
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            if self._cancelled:
                return
            self.finished_err.emit(f"{type(exc).__name__}: {exc}")


# ----------------------------------------------------------- dialog

class RefineDialog(QDialog):
    """Modal: image + prompt + comments → refined prompt."""

    applied_new_card = Signal(str)       # refined prompt text — host creates a new card
    replaced_current = Signal(str)       # refined prompt text — host updates current card

    def __init__(
        self,
        parent: QWidget | None,
        *,
        original_prompt: str = "",
        default_backend: str = "claude",
        claude_binary: str = "claude",
        codex_binary: str = "codex",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Refine from feedback")
        self.resize(1100, 740)
        self._worker: RefineWorker | None = None
        self._last_result: RefineResult | None = None
        self._claude_binary = claude_binary
        self._codex_binary = codex_binary

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)

        # Top row: image area + form
        top = QHBoxLayout()
        top.setSpacing(14)
        self.image_area = ImageDropArea(self)
        top.addWidget(self.image_area, stretch=3)

        form_panel = QWidget(self)
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("Claude (claude -p)", userData="claude")
        self.backend_combo.addItem("Codex (codex exec)", userData="codex")
        for index in range(self.backend_combo.count()):
            if self.backend_combo.itemData(index) == default_backend:
                self.backend_combo.setCurrentIndex(index)
        form.addRow("LLM", self.backend_combo)

        pick_btn = QPushButton("Pick image file…")
        pick_btn.clicked.connect(self._pick_image)
        form.addRow("Image", pick_btn)

        clear_btn = QPushButton("Clear image")
        clear_btn.clicked.connect(self.image_area.clear_image)
        form.addRow("", clear_btn)

        form_layout.addLayout(form)

        form_layout.addWidget(_section("Original prompt"))
        self.prompt_edit = QPlainTextEdit(original_prompt)
        self.prompt_edit.setMinimumHeight(120)
        form_layout.addWidget(self.prompt_edit)

        form_layout.addWidget(_section("What's wrong (comments)"))
        self.comments_edit = QPlainTextEdit()
        self.comments_edit.setPlaceholderText(
            "What needs fixing? e.g. 'lighting is too harsh, hands look broken, "
            "background should be warmer.'"
        )
        self.comments_edit.setMinimumHeight(120)
        form_layout.addWidget(self.comments_edit)

        top.addWidget(form_panel, stretch=4)
        outer.addLayout(top, stretch=3)

        # Progress + status
        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        progress_row.addWidget(self.progress, stretch=1)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        progress_row.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignRight)
        outer.addLayout(progress_row)

        # Result panel
        outer.addWidget(_section("Refined prompt"))
        self.result_edit = QPlainTextEdit()
        self.result_edit.setPlaceholderText("The refined prompt will appear here.")
        outer.addWidget(self.result_edit, stretch=2)

        outer.addWidget(_section("What changed"))
        self.delta_label = QLabel("(no refinement yet)")
        self.delta_label.setWordWrap(True)
        self.delta_label.setStyleSheet("color: gray;")
        outer.addWidget(self.delta_label)

        # Buttons
        buttons = QHBoxLayout()
        self.refine_btn = QPushButton("Refine")
        self.refine_btn.setDefault(True)
        self.refine_btn.clicked.connect(self._on_refine)
        buttons.addWidget(self.refine_btn)
        self.cancel_btn = QPushButton("Cancel run")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel)
        buttons.addWidget(self.cancel_btn)
        buttons.addStretch(1)
        copy_btn = QPushButton("Copy refined prompt")
        copy_btn.clicked.connect(self._copy_result)
        buttons.addWidget(copy_btn)
        replace_btn = QPushButton("Replace current card")
        replace_btn.clicked.connect(self._replace_current)
        buttons.addWidget(replace_btn)
        apply_btn = QPushButton("Apply as new card")
        apply_btn.clicked.connect(self._apply_new)
        buttons.addWidget(apply_btn)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(close_btn)
        outer.addLayout(buttons)

    # ----------------------------------------------------- actions

    def _pick_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Pick an image", "", "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        )
        if path:
            self.image_area._adopt_path(Path(path))

    def _on_refine(self) -> None:
        prompt = self.prompt_edit.toPlainText().strip()
        comments = self.comments_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.information(self, "Refine", "Please paste or write the original prompt.")
            return
        if not comments:
            QMessageBox.information(self, "Refine", "Please describe what's wrong.")
            return
        backend = self.backend_combo.currentData() or "claude"
        self.refine_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.status_label.setText(f"Asking {backend}… (this can take 20–60s)")
        self._worker = RefineWorker(
            self, self.image_area.image_source(), prompt, comments,
            backend=backend, timeout_seconds=180.0,
            claude_binary=self._claude_binary,
            codex_binary=self._codex_binary,
        )
        self._worker.finished_ok.connect(self._on_done)
        self._worker.finished_err.connect(self._on_err)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.status_label.setText("Cancelled.")
            self.refine_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            self.progress.setVisible(False)

    def _on_done(self, result: RefineResult) -> None:
        self._last_result = result
        self.result_edit.setPlainText(result.whole)
        self.delta_label.setText(_render_delta(result))
        self.status_label.setText(f"{result.backend} returned a refinement.")
        self.progress.setVisible(False)
        self.refine_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_err(self, message: str) -> None:
        self.status_label.setText("")
        self.progress.setVisible(False)
        self.refine_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        QMessageBox.warning(self, "Refine failed", message)

    def _copy_result(self) -> None:
        text = self.result_edit.toPlainText().strip()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        self.status_label.setText("Copied to clipboard.")

    def _replace_current(self) -> None:
        text = self.result_edit.toPlainText().strip()
        if not text:
            return
        self.replaced_current.emit(text)
        self.accept()

    def _apply_new(self) -> None:
        text = self.result_edit.toPlainText().strip()
        if not text:
            return
        self.applied_new_card.emit(text)
        self.accept()


# ----------------------------------------------------------- helpers


def _render_delta(result: RefineResult) -> str:
    if not result.delta:
        return result.rationale or "(no granular delta provided — only the rewritten prompt)"
    lines = []
    if result.rationale:
        lines.append(result.rationale)
        lines.append("")
    for entry in result.delta:
        lines.append(f"• [{entry.action} → {entry.target}] {entry.text}")
    return "\n".join(lines)


def _section(label: str) -> QLabel:
    widget = QLabel(f"<b>{label}</b>")
    widget.setStyleSheet("margin-top: 4px;")
    return widget
