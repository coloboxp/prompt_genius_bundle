"""Adapter loading + schema conformance."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from prompt_genius.core.adapters import list_adapters, load_adapters, resolve_adapter


def test_generic_is_default(adapters_dir: Path) -> None:
    adapters = load_adapters(adapters_dir)
    assert "generic" in adapters
    assert resolve_adapter(adapters, None).model_id == "generic"


def test_all_adapters_pass_schema(adapters_dir: Path, schemas_dir: Path) -> None:
    schema = json.loads((schemas_dir / "model-adapter.schema.json").read_text())
    validator = Draft202012Validator(schema)
    failures: list[str] = []
    for path in sorted(adapters_dir.glob("*_adapter.json")):
        data = json.loads(path.read_text())
        for err in validator.iter_errors(data):
            failures.append(f"{path.name}: {err.message}")
    assert not failures, "\n".join(failures)


def test_resolve_unknown_raises(adapters_dir: Path) -> None:
    adapters = load_adapters(adapters_dir)
    with pytest.raises(KeyError):
        resolve_adapter(adapters, "this_does_not_exist")


def test_list_adapters_includes_status(adapters_dir: Path) -> None:
    rows = list_adapters(load_adapters(adapters_dir))
    statuses = {row["adapter_status"] for row in rows}
    assert statuses >= {"default", "verified_from_corpus", "stub_unverified"}
