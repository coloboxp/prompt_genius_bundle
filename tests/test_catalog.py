"""Catalog loading + bias guard."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from prompt_genius.core.brief import parse_brief
from prompt_genius.core.catalog import load_catalog, search


def test_catalog_loads(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)
    assert len(catalog.all()) >= 45


def test_every_item_has_generic_fragment(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir)
    missing = [item.id for item in catalog.all() if "generic" not in item.prompt_fragments]
    assert not missing, f"items missing 'generic' fragment: {missing}"


def test_no_per_model_fragment_paraphrases_generic(catalog_dir: Path) -> None:
    """Bias guard: per-adapter fragments must materially differ from generic."""

    catalog = load_catalog(catalog_dir)
    offenders: list[str] = []
    for item in catalog.all():
        generic = (item.prompt_fragments.get("generic") or "").strip().casefold()
        if not generic:
            continue
        for adapter_id, fragment in item.prompt_fragments.items():
            if adapter_id == "generic":
                continue
            value = (fragment or "").strip().casefold()
            if value == generic:
                offenders.append(f"{item.id}:{adapter_id}")
    assert not offenders, (
        "These per-model fragments are identical to generic — drop them: " + ", ".join(offenders)
    )


def test_all_items_validate_against_schema(catalog_dir: Path, schemas_dir: Path) -> None:
    schema = json.loads((schemas_dir / "catalog-item.schema.json").read_text())
    validator = Draft202012Validator(schema)
    failures: list[str] = []
    for path in sorted(catalog_dir.rglob("*.json")):
        data = json.loads(path.read_text())
        for err in validator.iter_errors(data):
            failures.append(f"{path.name}: {err.message}")
    assert not failures, "\n".join(failures)


def test_portrait_search_stays_out_of_product_enterprise_lane(catalog_dir: Path) -> None:
    catalog = load_catalog(catalog_dir, backend="tfidf", prefer_dense=False)
    intent = parse_brief(
        "A fashion portrait of a woman model with a nose piercing and shoulder "
        "tattoo, natural studio light, 85mm lens, editorial portrait photography."
    )

    matches = search(catalog, intent, "static_image", allow_drafts=True, per_type_limit=10)
    ids = {match.item.id for bucket in matches.values() for match in bucket}

    assert "task_human_portrait_001" in ids
    assert "task_product_render_001" not in ids
    assert "task_landing_hero_image_001" not in ids
    assert "negative_avoid_cyberpunk_001" not in ids
    assert "style_eco_luxury_product_001" not in ids
    assert "camera_lens_macro_product_001" not in ids
