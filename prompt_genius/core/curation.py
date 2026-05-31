"""Catalog curation: promote / deprecate items in bulk.

Pure file I/O on the catalog directory. Bulk operations always validate the
resulting JSON against ``schemas/catalog-item.schema.json`` so a bad rule can
never corrupt the catalog.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


def _load_schema(schemas_dir: Path) -> Draft202012Validator:
    schema = json.loads((schemas_dir / "catalog-item.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema)


def bulk_set_status(
    catalog_dir: str | Path,
    schemas_dir: str | Path,
    *,
    ids: Iterable[str] | None = None,
    types: Iterable[str] | None = None,
    new_status: str,
    dry_run: bool = False,
) -> list[str]:
    """Set ``status`` on selected items.

    Selection is by explicit ``ids`` and/or by ``types`` (union). Returns the
    list of item ids that were (or would be) changed.
    """

    if new_status not in {"draft", "active", "deprecated", "archived"}:
        raise ValueError(f"Invalid status: {new_status!r}")

    catalog_root = Path(catalog_dir)
    validator = _load_schema(Path(schemas_dir))
    target_ids = set(ids or [])
    target_types = set(types or [])
    changed: list[str] = []

    for path in sorted(catalog_root.rglob("*.json")):
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        item_id = data.get("id")
        item_type = data.get("type")
        if target_ids and item_id not in target_ids:
            continue
        if target_types and item_type not in target_types:
            continue
        if not target_ids and not target_types:
            continue
        if data.get("status") == new_status:
            continue
        data["status"] = new_status
        errors = list(validator.iter_errors(data))
        if errors:
            raise ValueError(
                f"refusing to write invalid item {path.name}: "
                + "; ".join(err.message for err in errors)
            )
        changed.append(str(item_id))
        if not dry_run:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return sorted(changed)


# A small curator-vetted set we promote on a clean install. These are the items
# whose generic fragments map to recurring, broadly-useful patterns observed in
# the corpus. Adjust this list as the catalog matures.
CURATED_ACTIVE_IDS: tuple[str, ...] = (
    "style_premium_enterprise_001",
    "style_cinematic_editorial_001",
    "style_photorealistic_portrait_001",
    "style_eco_luxury_product_001",
    "style_flat_startup_illustration_001",
    "style_makoto_shinkai_anime_001",
    "style_vintage_film_001",
    "style_isometric_3d_001",
    "camera_lens_85mm_portrait_001",
    "camera_lens_35mm_environmental_001",
    "camera_lens_macro_product_001",
    "camera_framing_centered_hero_001",
    "lighting_soft_studio_001",
    "lighting_natural_window_001",
    "lighting_golden_hour_001",
    "composition_negative_space_hero_001",
    "composition_rule_of_thirds_001",
    "composition_minimal_centered_001",
    "motion_slow_push_in_001",
    "motion_orbit_subject_001",
    "motion_static_locked_001",
    "motion_pacing_calm_001",
    "motion_continuity_preserve_product_001",
    "motion_continuity_preserve_face_001",
    "shot_opening_calm_001",
    "shot_detail_closeup_001",
    "shot_reveal_pullback_001",
    "shot_closing_brand_001",
    "transition_match_cut_001",
    "transition_soft_fade_001",
    "negative_avoid_cyberpunk_001",
    "negative_avoid_fake_text_001",
    "negative_avoid_warping_001",
    "negative_avoid_flicker_001",
    "negative_avoid_extra_fingers_001",
    "task_landing_hero_image_001",
    "task_product_render_001",
    "task_linkedin_video_teaser_001",
    "task_explainer_storyboard_001",
)


def promote_curated_subset(
    catalog_dir: str | Path,
    schemas_dir: str | Path,
    *,
    dry_run: bool = False,
) -> list[str]:
    """Promote the curated subset to ``status: active``."""

    return bulk_set_status(
        catalog_dir,
        schemas_dir,
        ids=CURATED_ACTIVE_IDS,
        new_status="active",
        dry_run=dry_run,
    )
