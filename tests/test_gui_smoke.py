"""GUI smoke test: import + offscreen launch + worker round-trip.

Skipped when PySide6 is not installed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_gui_window_launches_and_generates(catalog_dir: Path, adapters_dir: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from prompt_genius.gui.app import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(adapters_dir=adapters_dir, catalog_dir=catalog_dir)
    window.show()
    window.brief_edit.setPlainText("Premium enterprise hero image")
    window.mode_combo.setCurrentText("static_image")
    window.n_spin.setValue(2)

    received: list[list] = []

    def capture(cards: list) -> None:
        received.append(cards)
        app.quit()

    window._on_generate()
    assert window._worker is not None
    window._worker.cards_ready.connect(capture)
    QTimer.singleShot(8000, app.quit)
    app.exec()
    assert received, "worker did not emit cards within timeout"
    assert len(received[0]) == 2
