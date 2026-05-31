"""CSV ingest: detect, delta, apply, stub-adapter."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from prompt_genius.core.ingest import (
    CANONICAL_COLUMNS,
    apply_plan,
    detect_format,
    existing_content_hashes,
    plan_ingest,
    propose_stub_adapter,
    write_stub_adapter_if_missing,
)


def _write_csv(path: Path, rows: list[dict]) -> Path:
    cols = list(rows[0].keys()) if rows else list(CANONICAL_COLUMNS)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def test_detect_canonical_columns(tmp_path: Path) -> None:
    src = _write_csv(tmp_path / "demo-prompts-20260529.csv", [
        {"id": "1", "title": "t", "content": "c", "description": "", "sourceLink": "",
         "sourcePublishedAt": "", "author": "", "sourceMedia": ""},
    ])
    fmt = detect_format(src)
    assert fmt.mapping["id"] == "id"
    assert fmt.mapping["content"] == "content"
    assert fmt.missing_required == []
    assert fmt.model_id == "demo"


def test_detect_synonym_columns(tmp_path: Path) -> None:
    src = _write_csv(tmp_path / "third-party.csv", [
        {"uuid": "x", "headline": "y", "prompt": "z"},
    ])
    fmt = detect_format(src)
    assert fmt.mapping["id"] == "uuid"
    assert fmt.mapping["title"] == "headline"
    assert fmt.mapping["content"] == "prompt"
    assert fmt.missing_required == []


def test_missing_required_columns(tmp_path: Path) -> None:
    src = _write_csv(tmp_path / "broken.csv", [
        {"id": "1", "title": "t"},   # no content / prompt at all
    ])
    fmt = detect_format(src)
    assert "content" in fmt.missing_required


def test_plan_deltas_against_existing(tmp_path: Path) -> None:
    corpus = tmp_path / "raw"
    corpus.mkdir()
    _write_csv(corpus / "existing.csv", [
        {"id": "1", "title": "a", "content": "shared prompt one",
         "description": "", "sourceLink": "", "sourcePublishedAt": "",
         "author": "", "sourceMedia": ""},
    ])
    incoming = _write_csv(tmp_path / "incoming.csv", [
        {"id": "11", "title": "a", "content": "shared prompt one",
         "description": "", "sourceLink": "", "sourcePublishedAt": "",
         "author": "", "sourceMedia": ""},
        {"id": "12", "title": "b", "content": "totally new prompt two",
         "description": "", "sourceLink": "", "sourcePublishedAt": "",
         "author": "", "sourceMedia": ""},
    ])
    plan = plan_ingest(incoming, corpus)
    assert plan.duplicate_rows == 1
    assert len(plan.new_rows) == 1
    assert plan.new_rows[0].canonical["content"] == "totally new prompt two"


def test_apply_plan_writes_and_invalidates(tmp_path: Path) -> None:
    corpus = tmp_path / "raw"
    corpus.mkdir()
    cache = tmp_path / "cache"
    (cache / "vocab").mkdir(parents=True)
    (cache / "vocab" / "marker.json").write_text("{}")
    incoming = _write_csv(tmp_path / "new.csv", [
        {"id": "1", "title": "t", "content": "fresh prompt",
         "description": "", "sourceLink": "", "sourcePublishedAt": "",
         "author": "", "sourceMedia": ""},
    ])
    plan = plan_ingest(incoming, corpus)
    written = apply_plan(plan, corpus, cache_dirs=[cache / "vocab"])
    assert written is not None and written.exists()
    # cache invalidated
    assert not (cache / "vocab").exists()
    # written rows match
    with written.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["content"] == "fresh prompt"


def test_existing_content_hashes_picks_up_existing(tmp_path: Path) -> None:
    _write_csv(tmp_path / "c.csv", [
        {"id": "1", "title": "", "content": "hello world", "description": "",
         "sourceLink": "", "sourcePublishedAt": "", "author": "", "sourceMedia": ""},
    ])
    hashes = existing_content_hashes(tmp_path)
    assert len(hashes) == 1


def test_propose_stub_adapter_shape() -> None:
    stub = propose_stub_adapter("grok_imagine")
    assert stub["model_id"] == "grok_imagine"
    assert stub["adapter_status"] == "stub_unverified"
    assert stub["supports"]["static_image"] is True


def test_write_stub_adapter_no_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "grok_imagine_adapter.json"
    target.write_text(json.dumps({"model_id": "grok_imagine", "manual": True}))
    out = write_stub_adapter_if_missing("grok_imagine", tmp_path)
    assert out is None
    data = json.loads(target.read_text())
    assert data["manual"] is True


def test_write_stub_adapter_creates_when_missing(tmp_path: Path) -> None:
    out = write_stub_adapter_if_missing("brand_new_model", tmp_path)
    assert out is not None and out.exists()
    data = json.loads(out.read_text())
    assert data["adapter_status"] == "stub_unverified"
