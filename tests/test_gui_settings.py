"""Settings dialog binds to every config field and persists changes."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_settings_dialog_round_trip(tmp_path: Path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from prompt_genius.core.config import Config
    from prompt_genius.gui.settings_dialog import SettingsDialog

    app = QApplication.instance() or QApplication([])

    config = Config.default()
    config.gui.theme = "dark"
    config.llm.backend = "claude"
    config.retrieval.tag_weight = 7.5
    config.video.default_shot_count = 5

    dialog = SettingsDialog(None, config)
    collected = dialog._collect_config()

    assert collected.gui.theme == "dark"
    assert collected.llm.backend == "claude"
    assert collected.retrieval.tag_weight == 7.5
    assert collected.video.default_shot_count == 5

    # Save round-trips through disk too.
    path = tmp_path / "cfg.json"
    collected.save(path)
    reloaded = Config.load(path)
    assert reloaded == collected
