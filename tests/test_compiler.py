"""Compiler — per-adapter whitelisting, stub warnings, negative formatting."""

from __future__ import annotations

from pathlib import Path

import pytest

from prompt_genius.core.adapters import load_adapters, resolve_adapter
from prompt_genius.core.assembler import assemble
from prompt_genius.core.brief import parse_brief
from prompt_genius.core.catalog import load_catalog, search
from prompt_genius.core.compiler import compile_prompt

_BRIEF = "Premium enterprise hero image for biometric onboarding, avoid cyberpunk"


@pytest.fixture()
def baseline(catalog_dir: Path, adapters_dir: Path):
    adapters = load_adapters(adapters_dir)
    catalog = load_catalog(catalog_dir)
    intent = parse_brief(_BRIEF)
    return adapters, catalog, intent


def test_compiled_params_are_adapter_subset(baseline) -> None:
    adapters, catalog, intent = baseline
    for adapter_id, adapter in adapters.items():
        mode = "static_image" if adapter.supports_mode("static_image") else (
            "text_to_video" if adapter.supports_mode("text_to_video") else None
        )
        if mode is None:
            continue
        matches = search(catalog, intent, mode, allow_drafts=True)
        structured = assemble(intent, matches, adapter, mode)
        compiled = compile_prompt(structured, adapter, catalog)
        allowed = adapter.supported_parameters()
        leaked = set(compiled.parameters.keys()) - allowed
        assert not leaked, f"adapter {adapter_id} leaked params: {leaked}"


def test_stub_adapter_emits_warning(baseline) -> None:
    adapters, catalog, intent = baseline
    firefly = resolve_adapter(adapters, "firefly")
    matches = search(catalog, intent, "static_image", allow_drafts=True)
    structured = assemble(intent, matches, firefly, "static_image")
    compiled = compile_prompt(structured, firefly, catalog)
    codes = {w.code for w in compiled.warnings}
    assert "adapter_stub" in codes


def test_midjourney_uses_no_flag(baseline) -> None:
    adapters, catalog, intent = baseline
    mj = resolve_adapter(adapters, "midjourney")
    matches = search(catalog, intent, "static_image", allow_drafts=True)
    structured = assemble(intent, matches, mj, "static_image")
    compiled = compile_prompt(structured, mj, catalog)
    assert compiled.negative_text.startswith("--no ") or "--no" in compiled.text


def test_seedance_emits_shot_timing(catalog_dir: Path, adapters_dir: Path) -> None:
    adapters = load_adapters(adapters_dir)
    seedance = resolve_adapter(adapters, "seedance_2_0")
    catalog = load_catalog(catalog_dir)
    intent = parse_brief("15-second product storyboard")
    matches = search(catalog, intent, "storyboard", allow_drafts=True)
    structured = assemble(intent, matches, seedance, "storyboard", shot_count=3)
    compiled = [compile_prompt(s, seedance, catalog) for s in structured]
    assert any("（" in c.text and "秒）" in c.text for c in compiled)


def test_generic_compiles_for_all_modes(catalog_dir: Path, adapters_dir: Path) -> None:
    adapters = load_adapters(adapters_dir)
    generic = resolve_adapter(adapters, None)
    catalog = load_catalog(catalog_dir)
    intent = parse_brief(_BRIEF)
    for mode in [
        "static_image", "image_editing",
        "text_to_video", "image_to_video",
    ]:
        matches = search(catalog, intent, mode, allow_drafts=True)
        structured = assemble(intent, matches, generic, mode)
        compiled = compile_prompt(structured, generic, catalog)
        assert compiled.text, f"empty text for mode {mode}"
