"""Config round-trip + Settings dialog binding hooks."""

from __future__ import annotations

from pathlib import Path

from prompt_genius.core.config import (
    Config,
    GuiConfig,
    LlmConfig,
    QualityWeights,
    RetrievalWeights,
    VideoDefaults,
    load_or_init,
)


def test_default_config_round_trips(tmp_path: Path) -> None:
    cfg = Config.default()
    path = tmp_path / "cfg.json"
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded == cfg


def test_mutated_config_round_trips(tmp_path: Path) -> None:
    cfg = Config.default()
    cfg.llm.backend = "claude"
    cfg.embeddings.prefer_dense = True
    cfg.retrieval.tag_weight = 5.0
    cfg.quality.half_life_days = 30.0
    cfg.video.default_shot_count = 5
    cfg.video.artifact_avoidance = ("no warping",)
    cfg.gui.theme = "dark"
    path = tmp_path / "cfg.json"
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded.llm.backend == "claude"
    assert loaded.embeddings.prefer_dense is True
    assert loaded.retrieval.tag_weight == 5.0
    assert loaded.quality.half_life_days == 30.0
    assert loaded.video.default_shot_count == 5
    assert loaded.video.artifact_avoidance == ("no warping",)
    assert loaded.gui.theme == "dark"


def test_load_or_init_creates_default(tmp_path: Path) -> None:
    path = tmp_path / "fresh.json"
    cfg = load_or_init(path)
    assert path.exists()
    assert cfg == Config.default()
