"""Curation, usage ledger, quality time-decay."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prompt_genius.core.config import Config
from prompt_genius.core.curation import bulk_set_status, promote_curated_subset
from prompt_genius.core.quality import recompute_quality_scores, top_and_bottom
from prompt_genius.core.usage import read_usage, record_usage


def test_promote_curated_subset_changes_status(tmp_path: Path, catalog_dir: Path, schemas_dir: Path) -> None:
    # Copy a small slice of the catalog into a tmp dir so we don't mutate the repo state.
    target = tmp_path / "catalog"
    target.mkdir()
    for src in (catalog_dir / "styles").glob("*.json"):
        (target / src.name).write_text(src.read_text(encoding="utf-8"))
    # Force every copied item to draft.
    for path in target.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "draft"
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    changed = promote_curated_subset(target, schemas_dir)
    assert any(cid.startswith("style_") for cid in changed)


def test_bulk_set_status_filters_by_type(tmp_path: Path, catalog_dir: Path, schemas_dir: Path) -> None:
    target = tmp_path / "catalog"
    target.mkdir()
    # Copy entire camera folder
    for src in (catalog_dir / "camera").glob("*.json"):
        (target / src.name).write_text(src.read_text(encoding="utf-8"))
    changed = bulk_set_status(target, schemas_dir, types=["camera_pattern"], new_status="deprecated")
    assert len(changed) >= 1
    sample = json.loads(next(target.glob("*.json")).read_text(encoding="utf-8"))
    assert sample["status"] == "deprecated"


def test_usage_ledger_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    record_usage(["a", "b"], event="generated", card_id="card-1", ledger_path=path)
    record_usage(["a"], event="saved", card_id="card-1", ledger_path=path)
    rows = read_usage(path)
    assert len(rows) == 3
    assert any(r["event"] == "saved" for r in rows)


def test_quality_decay_with_old_feedback(tmp_path: Path, catalog_dir: Path) -> None:
    feedback = tmp_path / "feedback.jsonl"
    history = tmp_path / "history"; history.mkdir()
    usage = tmp_path / "usage.jsonl"

    sample_id = "style_premium_enterprise_001"
    card = {
        "id": "card-old",
        "title": "old hero",
        "mode": "static_image",
        "selected_patterns": [sample_id],
        "compiled": {"text": "x", "negative_text": ""},
    }
    (history / "card-old.json").write_text(json.dumps(card))

    # Feedback from 2 years ago should be heavily decayed.
    old = datetime.now(timezone.utc) - timedelta(days=730)
    feedback.write_text(json.dumps({
        "card_id": "card-old",
        "rating": "bad",
        "recorded_at": old.isoformat(),
    }) + "\n")

    cfg = Config.default()
    cfg.quality.half_life_days = 30.0
    scores = recompute_quality_scores(
        catalog_dir, feedback, history, usage_path=usage, apply=False, config=cfg,
    )
    assert sample_id in scores
    # decayed weight should leave the score close to curator base
    assert scores[sample_id] >= 0.4


def test_top_and_bottom() -> None:
    out = top_and_bottom({"a": 0.9, "b": 0.1, "c": 0.5}, k=2)
    assert out["top"][0][0] == "a"
    assert out["bottom"][0][0] == "b"
