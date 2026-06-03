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

    from prompt_genius.core.config import Config
    from prompt_genius.gui.app import MainWindow

    app = QApplication.instance() or QApplication([])
    config = Config.default()
    config.embeddings.backend = "tfidf"
    config.embeddings.prewarm_on_launch = False
    window = MainWindow(config=config, adapters_dir=adapters_dir, catalog_dir=catalog_dir)
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


def test_example_json_is_naturalized() -> None:
    from prompt_genius.gui.app import _naturalize_example_text

    raw = """{
      "image_generation_prompt": {
        "subject_and_pose": "A young East Asian woman looking away.",
        "outfit": "A monochrome {argument name="outfit color" default="beige-tan"} co-ord set.",
        "lighting_and_shot": "A full-length fashion photography shot."
      }
    }"""

    text = _naturalize_example_text(raw)

    assert "{" not in text
    assert "image_generation_prompt" not in text
    assert "Subject and pose: A young East Asian woman looking away." in text
    assert "beige-tan co-ord set" in text
    assert "Lighting and shot: A full-length fashion photography shot." in text


def test_all_raw_corpus_examples_are_insertable(repo_root: Path) -> None:
    from prompt_genius.core.corpus import iter_rows
    from prompt_genius.gui.app import _naturalize_example_text

    failures: list[str] = []
    for row in iter_rows(repo_root / "raw_corpus", min_length=80):
        text = _naturalize_example_text(row.content)
        stripped = text.lstrip()
        raw_jsonish = stripped.startswith("{") or stripped.startswith(("[{", '["'))
        unresolved_arg = "{argument" in text
        if raw_jsonish or unresolved_arg:
            failures.append(row.id)

    assert not failures
