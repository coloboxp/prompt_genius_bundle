#!/usr/bin/env python3
"""Seed the normalized catalog under ``catalog/`` with reusable patterns.

Patterns are synthesized from recurring families observed in ``raw_corpus/``:
- Nano Banana Pro rows → style / camera / lighting / composition / negative / task patterns
- Seedance 2.0 rows → motion / shot / transition / pacing / continuity patterns

Each item has ``prompt_fragments.generic`` only — no per-model phrasing, per the
generic-first rule. Items are written as ``status: draft`` so a human reviewer
must approve them before they go active.

Idempotent: rerunning overwrites the same file paths.

Usage:
    python scripts/seed_catalog.py catalog/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _item(
    item_id: str,
    type_name: str,
    category: str,
    name: str,
    description: str,
    applies_to: list[str],
    fragment: str,
    *,
    tags: list[str],
    compatible_with: list[str] | None = None,
    avoid_with: list[str] | None = None,
    not_recommended_for: list[str] | None = None,
    parameters: dict[str, Any] | None = None,
    quality_score: float = 0.72,
    source_note: str = "synthesized from recurring patterns observed in raw_corpus/",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "type": type_name,
        "category": category,
        "name": name,
        "description": description,
        "applies_to": applies_to,
        "not_recommended_for": not_recommended_for or [],
        "prompt_fragments": {"generic": fragment},
        "parameters": parameters or {},
        "compatible_with": compatible_with or [],
        "avoid_with": avoid_with or [],
        "tags": tags,
        "quality_score": quality_score,
        "status": "draft",
        "version": "0.1",
        "notes": source_note,
        "source": {
            "file": "raw_corpus/",
            "method": "human-synthesis from recurring families",
        },
    }


IMAGE_MODES = ["static_image", "image_editing"]
VIDEO_MODES = ["text_to_video", "image_to_video", "storyboard", "keyframe"]
ALL_MODES = IMAGE_MODES + VIDEO_MODES


def styles() -> list[dict[str, Any]]:
    return [
        _item(
            "style_premium_enterprise_001",
            "style_pattern", "enterprise_brand_style",
            "Premium enterprise visual",
            "Trustworthy, calm, modern B2B aesthetic for identity, security, fintech, SaaS, product launches.",
            ALL_MODES,
            "premium enterprise visual style, calm trust-focused mood, clean modern B2B aesthetic, refined details, professional finish",
            tags=["premium", "enterprise", "b2b", "trust", "clean"],
            compatible_with=["b2b", "identity", "security", "fintech", "saas"],
            avoid_with=["cyberpunk", "chaotic", "glitch_heavy"],
        ),
        _item(
            "style_cinematic_editorial_001",
            "style_pattern", "editorial_cinematic",
            "Cinematic editorial photography",
            "Magazine-grade cinematic photography with shallow depth of field, deliberate composition, refined color.",
            IMAGE_MODES,
            "cinematic editorial photography style, deliberate composition, shallow depth of field, refined color grading, magazine-grade finish",
            tags=["cinematic", "editorial", "magazine", "photography", "premium"],
            compatible_with=["fashion", "campaign", "lifestyle", "portrait"],
            avoid_with=["flat_ui", "icon"],
        ),
        _item(
            "style_makoto_shinkai_anime_001",
            "style_pattern", "anime_cinematic",
            "Makoto Shinkai inspired anime",
            "Anime cinematic style, soft bloom, dreamy atmosphere, rich color, narrow detailed scenes.",
            IMAGE_MODES + ["text_to_video"],
            "anime cinematic style inspired by Makoto Shinkai, soft bloom, dreamy atmosphere, narrow detailed scene, rich color palette, lens flare",
            tags=["anime", "cinematic", "dreamy", "illustration"],
            compatible_with=["dreamy", "narrative", "character"],
            avoid_with=["technical_diagram", "ui_mockup"],
        ),
        _item(
            "style_flat_startup_illustration_001",
            "style_pattern", "flat_illustration",
            "Flat startup illustration",
            "Bright, simple, vector-flat illustration for product marketing pages and onboarding screens.",
            IMAGE_MODES,
            "flat startup-style vector illustration, bright colors, simple shapes, clean and professional design, no text",
            tags=["flat", "vector", "startup", "illustration", "marketing"],
            compatible_with=["product", "onboarding", "saas"],
            avoid_with=["photorealistic", "cinematic"],
        ),
        _item(
            "style_eco_luxury_product_001",
            "style_pattern", "product_photography",
            "Eco-luxury product photography",
            "High-end commercial product photography with organic surroundings, dew, soft diffused light.",
            IMAGE_MODES,
            "high-end commercial product photography, organic eco-luxury aesthetic, dewy textures, soft diffused lighting, ultra-detailed surfaces, bright minimal background",
            tags=["product", "eco", "luxury", "commercial", "photography"],
            compatible_with=["skincare", "beauty", "wellness"],
        ),
        _item(
            "style_photorealistic_portrait_001",
            "style_pattern", "portrait_photography",
            "Photorealistic cinematic portrait",
            "Photorealistic portrait with shallow depth of field, natural skin tones, cinematic framing.",
            IMAGE_MODES,
            "photorealistic cinematic portrait photography, natural skin tones, shallow depth of field, deliberate cinematic framing, soft natural light",
            tags=["portrait", "photorealistic", "cinematic", "human"],
            compatible_with=["human", "fashion", "campaign"],
            avoid_with=["flat", "icon"],
        ),
        _item(
            "style_vintage_film_001",
            "style_pattern", "vintage_film",
            "Vintage film aesthetic",
            "Warm grain, faded color, soft contrast, evokes 1970s-80s film photography.",
            IMAGE_MODES + ["text_to_video"],
            "vintage film aesthetic, warm grain, faded color palette, soft contrast, gentle highlight roll-off, 1970s film photography mood",
            tags=["vintage", "film", "warm", "nostalgic"],
            compatible_with=["nostalgic", "editorial"],
            avoid_with=["sci-fi", "neon"],
        ),
        _item(
            "style_isometric_3d_001",
            "style_pattern", "isometric_illustration",
            "Isometric 3D scene",
            "Clean isometric 3D illustration suited for product diagrams, UI hero scenes, infographics.",
            IMAGE_MODES,
            "clean isometric 3D illustration, soft shadows, pastel palette, precise geometry, infographic-friendly composition",
            tags=["isometric", "3d", "infographic", "diagram"],
            compatible_with=["technical", "saas", "explainer"],
            avoid_with=["photorealistic", "portrait"],
        ),
    ]


def cameras() -> list[dict[str, Any]]:
    return [
        _item(
            "camera_lens_85mm_portrait_001",
            "camera_pattern", "lens",
            "85mm portrait lens",
            "Shallow depth of field, elegant subject separation, premium portrait photography.",
            IMAGE_MODES + ["image_to_video"],
            "85mm lens, shallow depth of field, elegant subject separation, premium portrait photography",
            tags=["lens", "85mm", "portrait", "premium"],
            compatible_with=["portrait", "premium", "human"],
            avoid_with=["wide_environment", "flat_ui"],
            parameters={"lens": "85mm", "depth_of_field": "shallow"},
        ),
        _item(
            "camera_lens_35mm_environmental_001",
            "camera_pattern", "lens",
            "35mm environmental lens",
            "Subject in context with natural environmental framing.",
            IMAGE_MODES + VIDEO_MODES,
            "35mm lens, environmental framing, subject in context, natural perspective",
            tags=["lens", "35mm", "environmental", "documentary"],
            compatible_with=["documentary", "lifestyle"],
            parameters={"lens": "35mm", "depth_of_field": "medium"},
        ),
        _item(
            "camera_lens_macro_product_001",
            "camera_pattern", "lens",
            "Macro product lens",
            "Macro focus on surface texture and product details.",
            IMAGE_MODES,
            "macro lens, close-up product detail, shallow depth of field focused on surface texture",
            tags=["lens", "macro", "product", "detail"],
            compatible_with=["product", "skincare", "jewelry"],
            avoid_with=["wide_environment"],
            parameters={"lens": "macro", "depth_of_field": "very shallow"},
        ),
        _item(
            "camera_angle_low_hero_001",
            "camera_pattern", "angle",
            "Low hero angle",
            "Slight low angle for hero subject impact without distorting the figure.",
            IMAGE_MODES + ["image_to_video"],
            "slight low angle, hero framing, subject made prominent without distortion",
            tags=["angle", "low", "hero"],
            compatible_with=["product_hero", "portrait"],
        ),
        _item(
            "camera_framing_centered_hero_001",
            "camera_pattern", "framing",
            "Centered hero framing",
            "Subject centered with deliberate negative space for headline copy.",
            IMAGE_MODES,
            "centered hero framing, deliberate negative space for headline text, balanced composition",
            tags=["framing", "centered", "hero", "negative_space"],
            compatible_with=["hero_image", "landing_page"],
        ),
    ]


def lighting() -> list[dict[str, Any]]:
    return [
        _item(
            "lighting_soft_studio_001",
            "lighting_pattern", "studio",
            "Soft studio lighting",
            "Gentle highlights, clean shadows, polished product photography feel.",
            ALL_MODES,
            "soft studio lighting, gentle highlights, clean shadows, polished product photography feel",
            tags=["lighting", "studio", "soft", "clean", "premium"],
            compatible_with=["product", "enterprise", "portrait"],
            avoid_with=["harsh_flash", "neon", "noir"],
        ),
        _item(
            "lighting_natural_window_001",
            "lighting_pattern", "natural",
            "Natural window light",
            "Soft directional daylight from a window, gentle falloff, realistic skin tones.",
            IMAGE_MODES + ["image_to_video"],
            "natural window light, soft directional daylight, gentle falloff, realistic skin tones",
            tags=["lighting", "natural", "window", "daylight"],
            compatible_with=["portrait", "lifestyle", "interior"],
        ),
        _item(
            "lighting_golden_hour_001",
            "lighting_pattern", "outdoor",
            "Golden hour outdoor",
            "Warm low-angle sunlight, long shadows, rich color, ideal for lifestyle and brand stories.",
            ALL_MODES,
            "golden hour sunlight, warm low-angle light, long soft shadows, rich color palette",
            tags=["lighting", "golden_hour", "warm", "outdoor"],
            compatible_with=["lifestyle", "campaign", "outdoor"],
            avoid_with=["noir", "studio_only"],
        ),
        _item(
            "lighting_dramatic_low_key_001",
            "lighting_pattern", "dramatic",
            "Dramatic low-key lighting",
            "High-contrast directional lighting with deep shadows for dramatic mood.",
            IMAGE_MODES + ["text_to_video"],
            "dramatic low-key lighting, high contrast, deep shadows, strong key light, moody atmosphere",
            tags=["lighting", "dramatic", "low_key", "moody"],
            compatible_with=["editorial", "fashion", "noir"],
            avoid_with=["clean_enterprise", "infographic"],
        ),
    ]


def composition() -> list[dict[str, Any]]:
    return [
        _item(
            "composition_negative_space_hero_001",
            "composition_pattern", "hero_layout",
            "Hero composition with negative space",
            "Clean hero layout with deliberate negative space for headline text.",
            IMAGE_MODES,
            "clean hero composition, deliberate negative space for headline copy, balanced focal subject placement",
            tags=["composition", "hero", "negative_space"],
            compatible_with=["landing_page", "campaign"],
        ),
        _item(
            "composition_rule_of_thirds_001",
            "composition_pattern", "rule_of_thirds",
            "Rule of thirds",
            "Subject placed on a third intersection for natural balance.",
            ALL_MODES,
            "rule of thirds composition, subject placed on a third intersection, balanced negative space",
            tags=["composition", "thirds", "balance"],
        ),
        _item(
            "composition_minimal_centered_001",
            "composition_pattern", "minimal_centered",
            "Minimal centered subject",
            "Single subject centered in a minimal frame, generous breathing room.",
            IMAGE_MODES,
            "minimal centered composition, single subject, generous breathing room, calm balance",
            tags=["composition", "minimal", "centered"],
            compatible_with=["product", "icon", "brand"],
        ),
        _item(
            "composition_environmental_wide_001",
            "composition_pattern", "wide_environment",
            "Environmental wide shot",
            "Subject embedded in a wider environment, contextual scale.",
            ALL_MODES,
            "environmental wide composition, subject embedded in surroundings, contextual scale, layered depth",
            tags=["composition", "wide", "environment"],
            compatible_with=["narrative", "lifestyle"],
            avoid_with=["macro_detail"],
        ),
    ]


def motion() -> list[dict[str, Any]]:
    return [
        _item(
            "motion_slow_push_in_001",
            "motion_pattern", "camera_motion",
            "Slow camera push-in",
            "Calm push-in that draws attention to the subject without losing layout.",
            VIDEO_MODES,
            "slow camera push-in, calm controlled motion, stable subject, smooth premium pacing",
            tags=["motion", "push-in", "calm", "premium"],
            compatible_with=["product_video", "hero_animation"],
            avoid_with=["fast_motion", "shaky"],
            parameters={"camera_motion": "slow push-in", "motion_intensity": "low"},
        ),
        _item(
            "motion_orbit_subject_001",
            "motion_pattern", "camera_motion",
            "Orbit around subject",
            "Smooth orbit around a centered subject, preserves identity and product shape.",
            VIDEO_MODES,
            "smooth orbit around subject, preserve identity and product shape, even pacing",
            tags=["motion", "orbit", "product"],
            compatible_with=["product_video", "3d_render"],
            parameters={"camera_motion": "orbit", "motion_intensity": "medium"},
        ),
        _item(
            "motion_handheld_subtle_001",
            "motion_pattern", "camera_motion",
            "Subtle handheld",
            "Light handheld breathing for documentary realism without distracting shake.",
            VIDEO_MODES,
            "subtle handheld camera, light breathing motion, documentary realism, no distracting shake",
            tags=["motion", "handheld", "documentary"],
            compatible_with=["documentary", "lifestyle"],
            avoid_with=["product_render"],
            parameters={"camera_motion": "handheld", "motion_intensity": "low"},
        ),
        _item(
            "motion_static_locked_001",
            "motion_pattern", "camera_motion",
            "Static locked camera",
            "Camera does not move; motion comes from subject and lighting only.",
            VIDEO_MODES,
            "static locked camera, no camera movement, motion comes from subject and lighting only",
            tags=["motion", "static", "locked"],
            compatible_with=["interview", "ui_animation"],
            parameters={"camera_motion": "static", "motion_intensity": "none"},
        ),
        _item(
            "motion_pacing_calm_001",
            "motion_pattern", "pacing",
            "Calm pacing",
            "Smooth premium pacing for brand-safe content.",
            VIDEO_MODES,
            "calm pacing, smooth premium rhythm, brand-safe tempo",
            tags=["motion", "pacing", "calm"],
            parameters={"pacing": "calm"},
        ),
        _item(
            "motion_pacing_energetic_001",
            "motion_pattern", "pacing",
            "Energetic pacing",
            "Faster cuts and motion intensity for upbeat campaign content.",
            VIDEO_MODES,
            "energetic pacing, faster cuts, higher motion intensity, upbeat campaign rhythm",
            tags=["motion", "pacing", "energetic"],
            parameters={"pacing": "energetic"},
        ),
        _item(
            "motion_continuity_preserve_product_001",
            "motion_pattern", "continuity",
            "Preserve product continuity",
            "Continuity constraint: product shape, color, and logo remain stable across frames.",
            VIDEO_MODES,
            "preserve product shape, color, and logo across frames; no geometry drift",
            tags=["continuity", "product", "stability"],
            parameters={"continuity": ["preserve_product_shape", "preserve_logo", "preserve_color"]},
        ),
        _item(
            "motion_continuity_preserve_face_001",
            "motion_pattern", "continuity",
            "Preserve face continuity",
            "Continuity constraint: subject face and identity stay consistent across frames.",
            VIDEO_MODES,
            "preserve subject face and identity across frames; consistent features, no morphing",
            tags=["continuity", "face", "identity"],
            parameters={"continuity": ["preserve_face", "preserve_identity"]},
        ),
    ]


def shots() -> list[dict[str, Any]]:
    return [
        _item(
            "shot_opening_calm_001",
            "shot_pattern", "opening",
            "Calm opening shot",
            "Slow opening establishing the subject and tone.",
            VIDEO_MODES,
            "calm opening shot, slow establishing pace, sets tone and subject",
            tags=["shot", "opening", "establishing"],
            parameters={"shot_role": "opening", "duration_hint_seconds": 3},
        ),
        _item(
            "shot_detail_closeup_001",
            "shot_pattern", "detail",
            "Detail close-up",
            "Tight close-up on a product detail or expression.",
            VIDEO_MODES,
            "tight close-up on a product detail or human expression, stable framing",
            tags=["shot", "closeup", "detail"],
            parameters={"shot_role": "detail", "duration_hint_seconds": 2},
        ),
        _item(
            "shot_reveal_pullback_001",
            "shot_pattern", "reveal",
            "Pull-back reveal",
            "Camera pulls back to reveal context or product in environment.",
            VIDEO_MODES,
            "pull-back reveal, camera retreats to expose subject in context",
            tags=["shot", "reveal", "pullback"],
            parameters={"shot_role": "reveal", "duration_hint_seconds": 4},
        ),
        _item(
            "shot_closing_brand_001",
            "shot_pattern", "closing",
            "Closing brand frame",
            "Final brand-message frame with stable composition and space for copy.",
            VIDEO_MODES,
            "closing brand frame, stable composition with negative space for copy and logo",
            tags=["shot", "closing", "brand"],
            parameters={"shot_role": "closing", "duration_hint_seconds": 3},
        ),
    ]


def transitions() -> list[dict[str, Any]]:
    return [
        _item(
            "transition_match_cut_001",
            "transition_pattern", "cut",
            "Match cut",
            "Match-cut transition aligning shape, motion, or color between two shots.",
            ["storyboard"],
            "match-cut transition aligning subject shape, motion vector, or color between shots",
            tags=["transition", "match_cut"],
            parameters={"transition": "match_cut"},
        ),
        _item(
            "transition_soft_fade_001",
            "transition_pattern", "fade",
            "Soft fade",
            "Soft luminance fade between shots for calm pacing.",
            ["storyboard"],
            "soft luminance fade between shots, calm pacing, no hard cut",
            tags=["transition", "fade", "calm"],
            parameters={"transition": "fade"},
        ),
        _item(
            "transition_camera_move_001",
            "transition_pattern", "camera_move",
            "Camera-move transition",
            "Continuous camera motion that bridges two shots without a hard cut.",
            ["storyboard"],
            "continuous camera move bridging shots, no hard cut, preserves spatial continuity",
            tags=["transition", "camera_move"],
            parameters={"transition": "camera_move"},
        ),
    ]


def negatives() -> list[dict[str, Any]]:
    return [
        _item(
            "negative_avoid_cyberpunk_001",
            "negative_pattern", "brand_safety",
            "Avoid cyberpunk and surveillance feel",
            "For identity, security, biometric, enterprise visuals that must avoid dystopian or hacker tone.",
            ALL_MODES,
            "avoid cyberpunk, hacker visuals, surveillance feeling, dystopian lighting, glitch effects, aggressive neon, dark sci-fi mood",
            tags=["negative", "cyberpunk", "brand_safe", "enterprise"],
            compatible_with=["enterprise", "identity", "trust"],
            quality_score=0.9,
        ),
        _item(
            "negative_avoid_fake_text_001",
            "negative_pattern", "artifact_avoidance",
            "Avoid fake/garbled text",
            "Prevents the model from inventing unreadable or misspelled text in the output.",
            ALL_MODES,
            "no fake text, no garbled lettering, no misspelled words; if text is needed, leave readable placeholder",
            tags=["negative", "text", "artifact"],
            quality_score=0.88,
        ),
        _item(
            "negative_avoid_warping_001",
            "negative_pattern", "video_artifact",
            "Avoid warping and morphing",
            "Video stability: prevent geometry drift, warping, morphing across frames.",
            VIDEO_MODES,
            "no geometry drift, no warping, no morphing, stable subject shape across all frames",
            tags=["negative", "warping", "stability", "video"],
            quality_score=0.9,
        ),
        _item(
            "negative_avoid_flicker_001",
            "negative_pattern", "video_artifact",
            "Avoid flicker and unstable lighting",
            "Video stability: prevent flicker, exposure jumps, unstable lighting transitions.",
            VIDEO_MODES,
            "no flicker, no exposure jumps, stable lighting across all frames",
            tags=["negative", "flicker", "stability", "video"],
            quality_score=0.88,
        ),
        _item(
            "negative_avoid_extra_fingers_001",
            "negative_pattern", "anatomy",
            "Avoid anatomical errors",
            "Prevents extra fingers, distorted hands, malformed limbs.",
            IMAGE_MODES + ["image_to_video"],
            "no extra fingers, no distorted hands, no malformed limbs, anatomically correct",
            tags=["negative", "anatomy", "hands"],
            quality_score=0.85,
        ),
    ]


def tasks() -> list[dict[str, Any]]:
    return [
        _item(
            "task_landing_hero_image_001",
            "task_template", "hero_image",
            "Landing page hero image",
            "Static hero image for a product landing page with space for headline and CTA.",
            IMAGE_MODES,
            "landing page hero image, premium production-ready visual with clear negative space for headline and CTA",
            tags=["task", "hero", "landing", "marketing"],
            compatible_with=["b2b", "saas", "campaign"],
            quality_score=0.78,
        ),
        _item(
            "task_product_render_001",
            "task_template", "product_render",
            "Product render",
            "Clean product render on a brand-safe background.",
            IMAGE_MODES,
            "clean product render, brand-safe background, premium commercial photography feel",
            tags=["task", "product", "render"],
            quality_score=0.78,
        ),
        _item(
            "task_linkedin_video_teaser_001",
            "task_template", "social_video",
            "LinkedIn product teaser video",
            "Short-form B2B teaser optimized for LinkedIn auto-play.",
            VIDEO_MODES,
            "short LinkedIn product teaser, B2B tone, calm pacing, readable on mute, 6-15 seconds",
            tags=["task", "linkedin", "social", "video"],
            compatible_with=["b2b", "saas"],
            quality_score=0.78,
        ),
        _item(
            "task_explainer_storyboard_001",
            "task_template", "explainer_storyboard",
            "Explainer video storyboard",
            "Short explainer video storyboard with opening, detail, reveal, closing shots.",
            ["storyboard"],
            "explainer video storyboard: opening shot, detail shot, reveal shot, closing brand frame",
            tags=["task", "explainer", "storyboard"],
            compatible_with=["product", "saas", "campaign"],
            quality_score=0.8,
        ),
    ]


CATEGORIES: dict[str, callable] = {
    "styles": styles,
    "camera": cameras,
    "lighting": lighting,
    "composition": composition,
    "motion": motion,
    "shots": shots,
    "transitions": transitions,
    "negative": negatives,
    "tasks": tasks,
}


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python seed_catalog.py <catalog_dir> [--force]")
        return 2
    catalog_dir = Path(sys.argv[1])
    force = "--force" in sys.argv[2:]
    total = 0
    skipped = 0
    for folder, builder in CATEGORIES.items():
        out_dir = catalog_dir / folder
        out_dir.mkdir(parents=True, exist_ok=True)
        for entry in builder():
            out_path = out_dir / f"{entry['id']}.json"
            if out_path.exists() and not force:
                # Preserve manual edits (status promotion, edits to fragments, etc).
                # Only re-seed when --force is passed.
                skipped += 1
                continue
            out_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            total += 1
    print(f"Seeded {total} new catalog items, preserved {skipped} existing files in {catalog_dir}")
    if not force and skipped:
        print("Re-run with --force to overwrite existing items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
