"""Open the Prompt Genius help.

Bundled .app: hands off to macOS Help Viewer via AppleScript, so it gets
the native search index, history, and ⌘F find.

Source mode (no .help bundle on disk): opens an in-app QTextBrowser dialog
that renders the Markdown directly from ``docs/help/`` — saves a round-trip
through the build script during development.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


_BOOK_ID = "com.innovatrics.promptgenius.help"
_SECTION_LABELS = {
    "tutorials": "Tutorials",
    "how-to": "How-to guides",
    "reference": "Reference",
    "explanation": "Explanation",
}


# --------------------------------------------------------------------- paths

def _bundled_help_book() -> Path | None:
    """Locate the PromptGenius.help bundle inside the .app, if we're frozen.

    build_mac_app.sh moves the .help bundle into Contents/Resources/ so
    Apple's Help Viewer finds it via CFBundleHelpBookFolder. Older builds
    leave it in Contents/Frameworks/ — try both.
    """

    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve()
    contents_dir = exe.parent.parent  # Contents/
    for relative in ("Resources/PromptGenius.help", "Frameworks/PromptGenius.help"):
        candidate = contents_dir / relative
        if candidate.exists():
            return candidate
    return None


def _source_docs_dir() -> Path | None:
    """Locate docs/help/ in the source tree."""

    # Walk upward from this file to find docs/help (works from any cwd).
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "docs" / "help"
        if candidate.is_dir():
            return candidate
    cwd_candidate = Path.cwd() / "docs" / "help"
    return cwd_candidate if cwd_candidate.is_dir() else None


# ------------------------------------------------------------ macOS handler

def _open_with_help_viewer(book_id: str) -> bool:
    """Open the registered Help Book in macOS Help Viewer.

    Returns True on success, False if we couldn't dispatch.
    """

    if sys.platform != "darwin":
        return False
    osa = shutil.which("osascript")
    if not osa:
        return False
    script = (
        f'tell application "Help Viewer" to activate\n'
        f'tell application "Help Viewer" to open help book "{book_id}"\n'
    )
    try:
        res = subprocess.run(
            [osa, "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        return res.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ------------------------------------------------ in-app QTextBrowser dialog


class HelpBrowserDialog(QDialog):
    """Source-mode fallback: render docs/help/*.md inside the app."""

    def __init__(self, parent: QWidget | None, *, docs_dir: Path) -> None:
        super().__init__(parent)
        self.setWindowTitle("🦊 Prompt Genius Help")
        self.resize(980, 720)
        self._docs_dir = docs_dir

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        # ----- left: section list of pages -----
        self.toc = QListWidget()
        self.toc.setToolTip("Diátaxis-organised pages from docs/help/.")
        self.toc.currentItemChanged.connect(self._on_pick)
        splitter.addWidget(self.toc)

        # ----- right: rendered page -----
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setOpenLinks(False)  # we route internal links by hand
        self.view.anchorClicked.connect(self._on_anchor)
        splitter.addWidget(self.view)
        splitter.setSizes([260, 720])
        root.addWidget(splitter, stretch=1)

        bottom = QHBoxLayout()
        external_btn = QPushButton("Open docs folder")
        external_btn.setToolTip("Reveal docs/help/ in Finder.")
        external_btn.clicked.connect(self._reveal_in_finder)
        bottom.addWidget(external_btn)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        bottom.addWidget(buttons)
        root.addLayout(bottom)

        self._populate_toc()
        if self.toc.count() > 0:
            self.toc.setCurrentRow(0)

    # --------------------------------------------------------------- toc

    def _populate_toc(self) -> None:
        for section, label in _SECTION_LABELS.items():
            section_dir = self._docs_dir / section
            if not section_dir.is_dir():
                continue
            # Section header (non-selectable).
            header = QListWidgetItem(label)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            font = header.font(); font.setBold(True); header.setFont(font)
            self.toc.addItem(header)
            for md_path in sorted(section_dir.glob("*.md")):
                title = self._read_title(md_path)
                item = QListWidgetItem(f"   {title}")
                item.setData(Qt.ItemDataRole.UserRole, str(md_path))
                item.setToolTip(str(md_path))
                self.toc.addItem(item)

    @staticmethod
    def _read_title(path: Path) -> str:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()
        except OSError:
            pass
        return path.stem.replace("-", " ").title()

    # ----------------------------------------------------------- render

    def _on_pick(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if current is None:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        try:
            md = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.view.setPlainText(f"Couldn't read {path}: {exc}")
            return
        # QTextBrowser supports CommonMark natively via setMarkdown — no
        # build-time conversion needed in source mode.
        self.view.setMarkdown(md)
        # Set a base URL so relative anchors resolve under docs/help/.
        self.view.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent) + "/"))

    def _on_anchor(self, url: QUrl) -> None:
        # Cross-page links in the markdown look like ../how-to/foo.html.
        # In source mode we want to load the corresponding .md instead.
        if url.scheme() in ("http", "https"):
            QDesktopServices.openUrl(url)
            return
        local = url.toLocalFile() or url.path()
        if local.endswith(".html"):
            local = local[:-5] + ".md"
        candidate = Path(local)
        if not candidate.is_absolute():
            candidate = (self._docs_dir / candidate).resolve()
        if candidate.is_file():
            # Find that item in the TOC and select it (also re-renders).
            for index in range(self.toc.count()):
                item = self.toc.item(index)
                if item.data(Qt.ItemDataRole.UserRole) == str(candidate):
                    self.toc.setCurrentRow(index)
                    return
        # Unknown link → just try to open externally.
        QDesktopServices.openUrl(url)

    def _reveal_in_finder(self) -> None:
        if sys.platform == "darwin" and shutil.which("open"):
            subprocess.run(["open", str(self._docs_dir)], check=False)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._docs_dir)))


# ------------------------------------------------------------ entry point

def open_help(parent: QWidget | None = None) -> None:
    """Open the help in the best available viewer."""

    book = _bundled_help_book()
    if book is not None and _open_with_help_viewer(_BOOK_ID):
        return
    docs = _source_docs_dir()
    if docs is None:
        # Last resort: tell the user where to look.
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            parent,
            "Help",
            "Help content isn't available in this build.\n\n"
            "Run the source tree (`prompt-genius-gui`) to see the in-app "
            "viewer, or rebuild the .app with packaging/build_mac_app.sh.",
        )
        return
    HelpBrowserDialog(parent, docs_dir=docs).exec()
