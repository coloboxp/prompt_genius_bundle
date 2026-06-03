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


def test_bundled_config_rebases_read_only_paths(monkeypatch, tmp_path: Path) -> None:
    import sys

    old_bundle = tmp_path / "old" / "Contents" / "Resources"
    current_bundle = tmp_path / "current" / "Contents" / "Resources"
    for resource in (
        current_bundle / "catalog",
        current_bundle / "examples" / "adapters",
        current_bundle / "schemas",
        current_bundle / "templates",
    ):
        resource.mkdir(parents=True)

    path = tmp_path / "cfg.json"
    cfg = Config.default()
    cfg.paths.catalog_dir = str(old_bundle / "catalog")
    cfg.paths.adapters_dir = str(old_bundle / "examples" / "adapters")
    cfg.paths.schemas_dir = str(old_bundle / "schemas")
    cfg.paths.templates_dir = str(old_bundle / "templates")
    cfg.save(path)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(current_bundle), raising=False)

    loaded = load_or_init(path)

    assert loaded.paths.catalog_dir == str(current_bundle / "catalog")
    assert loaded.paths.adapters_dir == str(current_bundle / "examples" / "adapters")
    assert loaded.paths.schemas_dir == str(current_bundle / "schemas")
    assert loaded.paths.templates_dir == str(current_bundle / "templates")
