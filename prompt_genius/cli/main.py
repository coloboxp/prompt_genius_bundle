"""Typer CLI shell for Prompt Genius.

This is the only place in the package that touches stdin/stdout. All logic
lives in :mod:`prompt_genius.core`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from prompt_genius.core.adapters import list_adapters, load_adapters, resolve_adapter
from prompt_genius.core.brand import brand_fit_score, load_brand_profile
from prompt_genius.core.brief_parsers import make_parser as make_brief_parser
from prompt_genius.core.curation import bulk_set_status, promote_curated_subset
from prompt_genius.core.ingest import apply_plan, plan_ingest, write_stub_adapter_if_missing
from prompt_genius.core.catalog import load_catalog
from prompt_genius.core.compiler import compile_prompt
from prompt_genius.core.convert import static_to_video
from prompt_genius.core.export import export_card, list_exporters
from prompt_genius.core.generate import card_to_card_dict, generate_campaign, generate_cards
from prompt_genius.core.models import StructuredPrompt, to_dict
from prompt_genius.core.quality import recompute_quality_scores
from prompt_genius.core.storage import save_card as core_save_card
from prompt_genius.core.storage import save_feedback as core_save_feedback
from prompt_genius.core.validator import validate_card
from prompt_genius.core.versioning import diff_cards, save_version

from prompt_genius.cli.formatters import (
    adapter_table,
    cards_as_json,
    cards_summary,
)

app = typer.Typer(
    add_completion=False,
    help="Prompt Genius — assemble model-agnostic prompts for image and video.",
)

_KNOWN_MODES = [
    "static_image",
    "image_editing",
    "text_to_video",
    "image_to_video",
    "storyboard",
    "keyframe",
]


def _adapters_dir_opt() -> Path:
    return Path("examples/adapters")


def _catalog_dir_opt() -> Path:
    return Path("catalog")


def _schemas_dir_opt() -> Path:
    return Path("schemas")


@app.command("list-adapters")
def cmd_list_adapters(
    adapters_dir: Annotated[Path, typer.Option(help="Adapter JSON directory.")] = _adapters_dir_opt(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit as JSON.")] = False,
) -> None:
    """List available adapters."""

    adapters = load_adapters(adapters_dir)
    rows = list_adapters(adapters)
    if as_json:
        typer.echo(json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        typer.echo(adapter_table(rows))


@app.command("list-modes")
def cmd_list_modes() -> None:
    """List supported prompt modes."""

    for mode in _KNOWN_MODES:
        typer.echo(mode)


@app.command()
def generate(
    brief: Annotated[str, typer.Option("--brief", "-b", help="User brief.")],
    mode: Annotated[str, typer.Option("--mode", "-m", help="Prompt mode.")] = "static_image",
    target: Annotated[
        str | None, typer.Option("--target", "-t", help="Adapter id; default 'generic'.")
    ] = None,
    n: Annotated[int, typer.Option("--n", "-n", help="Number of cards to return.")] = 5,
    risk: Annotated[str, typer.Option("--risk", help="safe | creative | experimental.")] = "safe",
    allow_drafts: Annotated[
        bool,
        typer.Option(
            "--allow-drafts/--no-allow-drafts",
            help="Allow draft catalog items. Default True (catalog ships as draft).",
        ),
    ] = True,
    brand_profile: Annotated[
        Path | None, typer.Option("--brand-profile", help="Path to a brand profile JSON.")
    ] = None,
    brief_parser: Annotated[
        str,
        typer.Option(
            "--brief-parser",
            help="heuristic | claude | codex | auto. Default heuristic (no subprocess).",
        ),
    ] = "heuristic",
    dense_embeddings: Annotated[
        bool, typer.Option("--dense-embeddings", help="Use sentence-transformers backend.")
    ] = False,
    embeddings_model: Annotated[
        str | None, typer.Option("--embeddings-model", help="Override embedding model name.")
    ] = None,
    adapters_dir: Annotated[Path, typer.Option(help="Adapter JSON directory.")] = _adapters_dir_opt(),
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
    schemas_dir: Annotated[Path, typer.Option(help="Schema directory.")] = _schemas_dir_opt(),
    as_json: Annotated[bool, typer.Option("--json", help="Emit cards as JSON on stdout.")] = False,
) -> None:
    """Generate N prompt cards from a brief."""

    cards = generate_cards(
        brief,
        mode=mode,
        target_model=target,
        n=n,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        allow_drafts=allow_drafts,
        risk_level=risk,
        brand_profile=brand_profile,
        prefer_dense_embeddings=dense_embeddings,
        embeddings_model=embeddings_model,
        brief_parser=make_brief_parser(backend=brief_parser),
    )

    # Validate each card; surface any schema errors to stderr.
    for card in cards:
        card_dict = card_to_card_dict(card)
        if isinstance(card.structured, list):
            # Storyboard / keyframe: validate as storyboard schema by promoting fields.
            promoted = {
                "id": card.id,
                "title": card.title,
                "target_model": card.target_model,
                "user_brief": brief,
                "total_duration_seconds": sum(
                    (s.duration_seconds or 0) for s in card.structured
                ) or len(card.structured),
                "aspect_ratio": (card.structured[0].video_parameters or {}).get(
                    "aspect_ratio", "16:9"
                ),
                "shots": [
                    {
                        "shot_number": s.shot_number or idx,
                        "duration_seconds": s.duration_seconds or 1,
                        "description": s.why_this_works,
                        "prompt": (c.text if not isinstance(card.compiled, list) else card.compiled[idx - 1].text),
                    }
                    for idx, (s, c) in enumerate(zip(card.structured, card.compiled if isinstance(card.compiled, list) else [card.compiled] * len(card.structured)), start=1)
                ],
                "mode": card.mode,
            }
            errors = validate_card(promoted, schemas_dir)
        elif card.mode in {"text_to_video", "image_to_video"}:
            errors = validate_card(
                {
                    "id": card.id,
                    "mode": card.mode,
                    "title": card.title,
                    "target_model": card.target_model,
                    "user_brief": brief,
                    "creative_intent": card.structured.creative_intent,
                    "video_parameters": card.structured.video_parameters or {
                        "duration_seconds": 1, "aspect_ratio": "16:9",
                        "camera_motion": "static", "pacing": "calm",
                    },
                    "prompt": card.compiled.text if not isinstance(card.compiled, list) else card.compiled[0].text,
                    "negative_prompt": (card.compiled.negative_text if not isinstance(card.compiled, list) else card.compiled[0].negative_text),
                    "evaluation_criteria": ["assembled by Prompt Genius Phase 1"],
                },
                schemas_dir,
            )
        else:
            errors = validate_card(
                {
                    "id": card.id,
                    "mode": card.mode,
                    "title": card.title,
                    "target_model": card.target_model,
                    "user_brief": brief,
                    "selected_patterns": card.selected_patterns,
                    "creative_intent": card.structured.creative_intent,
                    "visual_parameters": card.structured.visual_parameters,
                    "video_parameters": card.structured.video_parameters,
                    "prompt": card.compiled.text if not isinstance(card.compiled, list) else card.compiled[0].text,
                    "negative_prompt": (card.compiled.negative_text if not isinstance(card.compiled, list) else card.compiled[0].negative_text),
                    "evaluation_criteria": ["assembled by Prompt Genius Phase 1"],
                    "status": "draft",
                },
                schemas_dir,
            )
        for err in errors:
            typer.echo(f"validation: {err.path}: {err.message}", err=True)
        card_dict["_validation_errors"] = [{"path": e.path, "message": e.message} for e in errors]

    if as_json or not sys.stdout.isatty():
        typer.echo(cards_as_json(cards))
    else:
        typer.echo(cards_summary(cards))


@app.command()
def compile(  # noqa: A001 — intentional CLI verb name
    card_file: Annotated[Path, typer.Option("--card-file", help="Path to a card JSON.")],
    target: Annotated[str, typer.Option("--target", "-t", help="Adapter id.")],
    adapters_dir: Annotated[Path, typer.Option(help="Adapter JSON directory.")] = _adapters_dir_opt(),
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
) -> None:
    """Recompile an existing card for a different target adapter."""

    card_data = json.loads(card_file.read_text(encoding="utf-8"))
    adapters = load_adapters(adapters_dir)
    adapter = resolve_adapter(adapters, target)
    catalog = load_catalog(catalog_dir)

    structured_data = card_data.get("structured")
    if isinstance(structured_data, list):
        results = [
            compile_prompt(_structured_from_dict(d, target), adapter, catalog)
            for d in structured_data
        ]
    else:
        results = compile_prompt(
            _structured_from_dict(structured_data, target), adapter, catalog
        )

    typer.echo(json.dumps(to_dict(results), indent=2, ensure_ascii=False))


def _structured_from_dict(data: dict, target: str) -> StructuredPrompt:
    return StructuredPrompt(
        mode=data["mode"],
        target_model=target,
        creative_intent=dict(data.get("creative_intent") or {}),
        selected_patterns=list(data.get("selected_patterns") or []),
        why_this_works=data.get("why_this_works", ""),
        negative_fragments=list(data.get("negative_fragments") or []),
        visual_parameters=data.get("visual_parameters"),
        video_parameters=data.get("video_parameters"),
        shot_number=data.get("shot_number"),
        duration_seconds=data.get("duration_seconds"),
        frame_role=data.get("frame_role"),
    )


@app.command()
def validate(
    card_file: Annotated[Path, typer.Option("--card-file", help="Path to a card JSON.")],
    schemas_dir: Annotated[Path, typer.Option(help="Schema directory.")] = _schemas_dir_opt(),
) -> None:
    """Validate a card JSON against its schema."""

    data = json.loads(card_file.read_text(encoding="utf-8"))
    errors = validate_card(data, schemas_dir)
    if not errors:
        typer.echo("valid")
        raise typer.Exit(code=0)
    for err in errors:
        typer.echo(f"{err.path}: {err.message}", err=True)
    raise typer.Exit(code=1)


@app.command()
def save(
    card_file: Annotated[Path, typer.Option("--card-file", help="Path to a card JSON.")],
    to: Annotated[Path, typer.Option("--to", help="Destination directory.")] = Path("data/history"),
) -> None:
    """Save a card to the history directory."""

    data = json.loads(card_file.read_text(encoding="utf-8"))
    written = core_save_card(data, to)
    typer.echo(str(written))


@app.command()
def feedback(
    card_id: Annotated[str, typer.Option("--card-id", help="ID of the card being rated.")],
    rating: Annotated[
        str, typer.Option("--rating", help="good | bad | too_generic | off_brand | wrong_style")
    ],
    note: Annotated[str, typer.Option("--note", help="Free-text note.")] = "",
    out: Annotated[Path, typer.Option("--out", help="Feedback JSONL path.")] = Path("data/feedback.jsonl"),
) -> None:
    """Append a feedback record."""

    path = core_save_feedback(
        {"card_id": card_id, "rating": rating, "note": note}, out
    )
    typer.echo(str(path))


@app.command()
def refine(
    card_file: Annotated[Path, typer.Option("--card-file", help="Path to a card JSON.")],
    change: Annotated[
        list[str],
        typer.Option(
            "--change",
            help="Key=value override; repeat. Targets video_parameters or visual_parameters.",
        ),
    ] = [],
    target: Annotated[
        str | None, typer.Option("--target", "-t", help="Adapter id to recompile against.")
    ] = None,
    adapters_dir: Annotated[Path, typer.Option(help="Adapter JSON directory.")] = _adapters_dir_opt(),
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
) -> None:
    """Apply ad-hoc key=value overrides to a card's parameters and recompile."""

    card_data = json.loads(card_file.read_text(encoding="utf-8"))
    overrides: dict[str, str] = {}
    for raw in change:
        if "=" not in raw:
            raise typer.BadParameter(f"--change requires key=value, got: {raw!r}")
        key, value = raw.split("=", 1)
        overrides[key.strip()] = value.strip()

    structured = card_data.get("structured")
    if isinstance(structured, list):
        for entry in structured:
            _apply_overrides(entry, overrides)
    else:
        _apply_overrides(structured, overrides)

    adapter_id = target or card_data.get("target_model") or "generic"
    adapters = load_adapters(adapters_dir)
    adapter = resolve_adapter(adapters, adapter_id)
    catalog = load_catalog(catalog_dir)

    if isinstance(structured, list):
        results = [
            compile_prompt(_structured_from_dict(s, adapter.model_id), adapter, catalog)
            for s in structured
        ]
    else:
        results = compile_prompt(
            _structured_from_dict(structured, adapter.model_id), adapter, catalog
        )

    card_data["structured"] = structured
    card_data["compiled"] = to_dict(results)
    card_data["target_model"] = adapter.model_id
    typer.echo(json.dumps(card_data, indent=2, ensure_ascii=False))


def _apply_overrides(entry: dict, overrides: dict[str, str]) -> None:
    targets = []
    if entry.get("visual_parameters") is not None:
        targets.append(entry["visual_parameters"])
    if entry.get("video_parameters") is not None:
        targets.append(entry["video_parameters"])
    if not targets:
        entry.setdefault("visual_parameters", {})
        targets.append(entry["visual_parameters"])
    for target in targets:
        for key, value in overrides.items():
            target[key] = value


@app.command()
def convert(
    card_file: Annotated[Path, typer.Option("--card-file", help="Source static card JSON.")],
    target_mode: Annotated[str, typer.Option("--target-mode", help="Video mode to convert into.")],
    target: Annotated[
        str | None, typer.Option("--target", "-t", help="Adapter id. Default 'generic'.")
    ] = None,
    adapters_dir: Annotated[Path, typer.Option(help="Adapter JSON directory.")] = _adapters_dir_opt(),
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
) -> None:
    """Convert a static card into a video card (Phase 2)."""

    card_data = json.loads(card_file.read_text(encoding="utf-8"))
    adapters = load_adapters(adapters_dir)
    adapter = resolve_adapter(adapters, target)
    catalog = load_catalog(catalog_dir)
    structured, compiled = static_to_video(
        card_data, target_mode=target_mode, adapter=adapter, catalog=catalog,
    )
    typer.echo(json.dumps({
        "mode": target_mode,
        "target_model": adapter.model_id,
        "structured": to_dict(structured),
        "compiled": to_dict(compiled),
    }, indent=2, ensure_ascii=False))


@app.command()
def export(
    card_file: Annotated[Path, typer.Option("--card-file", help="Card JSON to export.")],
    fmt: Annotated[str, typer.Option("--format", help="plain | markdown | json")] = "plain",
    out: Annotated[Path | None, typer.Option("--out", help="Write to file.")] = None,
) -> None:
    """Export a card in a designer-friendly format (Phase 6)."""

    card = json.loads(card_file.read_text(encoding="utf-8"))
    suffix, text = export_card(card, fmt)
    if out:
        path = out if out.suffix else out.with_suffix(suffix)
        path.write_text(text, encoding="utf-8")
        typer.echo(str(path))
    else:
        typer.echo(text)


@app.command("list-exports")
def cmd_list_exports() -> None:
    """List available export formats."""

    for name in list_exporters():
        typer.echo(name)


@app.command()
def campaign(
    brief: Annotated[str, typer.Option("--brief", "-b", help="User brief.")],
    image_target: Annotated[str | None, typer.Option("--image-target")] = None,
    video_target: Annotated[str | None, typer.Option("--video-target")] = None,
    brand_profile: Annotated[Path | None, typer.Option("--brand-profile")] = None,
    adapters_dir: Annotated[Path, typer.Option(help="Adapter JSON directory.")] = _adapters_dir_opt(),
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
) -> None:
    """Generate a coordinated campaign pack (Phase 4)."""

    pack = generate_campaign(
        brief,
        image_target=image_target,
        video_target=video_target,
        adapters_dir=adapters_dir,
        catalog_dir=catalog_dir,
        brand_profile=brand_profile,
    )
    typer.echo(json.dumps(
        {role: [card_to_card_dict(c) for c in cards] for role, cards in pack.items()},
        indent=2,
        ensure_ascii=False,
    ))


@app.command()
def quality(
    apply_scores: Annotated[bool, typer.Option("--apply", help="Write new scores back to catalog.")] = False,
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
    feedback_path: Annotated[Path, typer.Option(help="Feedback JSONL path.")] = Path("data/feedback.jsonl"),
    history_dir: Annotated[Path, typer.Option(help="Card history dir.")] = Path("data/history"),
) -> None:
    """Recompute catalog quality scores from feedback (Phase 5)."""

    scores = recompute_quality_scores(
        catalog_dir, feedback_path, history_dir, apply=apply_scores,
    )
    typer.echo(json.dumps(scores, indent=2, ensure_ascii=False))


@app.command()
def version(
    card_file: Annotated[Path, typer.Option("--card-file", help="Card JSON to snapshot.")],
    note: Annotated[str, typer.Option("--note", help="Change summary.")] = "",
    out: Annotated[Path, typer.Option("--out", help="Version JSONL path.")] = Path("data/versions.jsonl"),
) -> None:
    """Append a card snapshot to the version history (Phase 5)."""

    card = json.loads(card_file.read_text(encoding="utf-8"))
    path = save_version(card, out, change_summary=note or None)
    typer.echo(str(path))


@app.command()
def diff(
    card_a: Annotated[Path, typer.Option("--a", help="First card JSON.")],
    card_b: Annotated[Path, typer.Option("--b", help="Second card JSON.")],
    field: Annotated[str, typer.Option("--field", help="prompt|negative|why|patterns")] = "prompt",
) -> None:
    """Unified text diff between two cards (Phase 5)."""

    a = json.loads(card_a.read_text(encoding="utf-8"))
    b = json.loads(card_b.read_text(encoding="utf-8"))
    out = diff_cards(a, b, field=field)
    typer.echo(out or "(no difference)")


@app.command("brand-fit")
def cmd_brand_fit(
    card_file: Annotated[Path, typer.Option("--card-file", help="Card JSON.")],
    brand_profile: Annotated[Path, typer.Option("--brand-profile", help="Brand profile JSON.")],
) -> None:
    """Score a card against a brand profile (Phase 5)."""

    card = json.loads(card_file.read_text(encoding="utf-8"))
    brand = load_brand_profile(brand_profile)
    score = brand_fit_score(card, brand)
    typer.echo(f"{score:.3f}")


@app.command()
def promote(
    ids: Annotated[
        list[str], typer.Option("--id", help="Specific catalog item id; repeat.")
    ] = [],
    types: Annotated[
        list[str], typer.Option("--type", help="Promote all items of this type; repeat.")
    ] = [],
    status: Annotated[
        str, typer.Option("--status", help="draft | active | deprecated | archived")
    ] = "active",
    curated: Annotated[
        bool, typer.Option("--curated", help="Promote the built-in curated subset to active.")
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
    schemas_dir: Annotated[Path, typer.Option(help="Schema directory.")] = _schemas_dir_opt(),
) -> None:
    """Promote / deprecate catalog items in bulk."""

    if curated:
        changed = promote_curated_subset(catalog_dir, schemas_dir, dry_run=dry_run)
    else:
        changed = bulk_set_status(
            catalog_dir, schemas_dir, ids=ids, types=types, new_status=status, dry_run=dry_run,
        )
    typer.echo(json.dumps({"changed": changed, "count": len(changed)}, indent=2))


@app.command()
def index(
    catalog_dir: Annotated[Path, typer.Option(help="Catalog directory.")] = _catalog_dir_opt(),
    corpus_dir: Annotated[Path, typer.Option(help="Raw corpus directory.")] = Path("raw_corpus"),
    backend: Annotated[
        str, typer.Option(help="tfidf | bm25 | dense | hybrid")
    ] = "hybrid",
    embeddings_model: Annotated[
        str, typer.Option(help="Sentence-transformers model id.")
    ] = "all-MiniLM-L6-v2",
    cache_dir: Annotated[
        Path, typer.Option(help="Embeddings cache directory.")
    ] = Path(".cache/embeddings"),
    rebuild: Annotated[
        bool, typer.Option("--rebuild", help="Rebuild caches even when fresh.")
    ] = False,
) -> None:
    """Pre-build and cache every retrieval index (catalog + corpus + vocab)."""

    import time
    from prompt_genius.core.corpus import load_or_build_corpus_index
    from prompt_genius.core.vocab import load_or_build_vocab

    def _emit(stage: str, t0: float) -> None:
        typer.echo(f"  {stage:<22}  {time.time() - t0:>5.2f}s")

    typer.echo("Building indexes:")
    t0 = time.time()
    catalog = load_catalog(
        catalog_dir, backend=backend,
        model_name=embeddings_model, cache_dir=cache_dir,
    )
    _emit(f"catalog ({backend})", t0)

    t0 = time.time()
    corpus = load_or_build_corpus_index(corpus_dir, rebuild=rebuild)
    _emit("corpus BM25", t0)

    t0 = time.time()
    vocab = load_or_build_vocab(corpus_dir, rebuild=rebuild)
    _emit("corpus vocab", t0)

    typer.echo(
        json.dumps(
            {
                "catalog_items": len(catalog.items),
                "catalog_backend": backend,
                "corpus_rows": len(corpus),
                "vocab_categories": {
                    cat: len(pairs) for cat, pairs in vocab.by_category.items()
                },
            },
            indent=2,
        )
    )


@app.command()
def ingest(
    files: Annotated[
        list[Path],
        typer.Argument(help="One or more CSV files to ingest."),
    ],
    raw_corpus_dir: Annotated[
        Path, typer.Option("--into", help="Where to write the new CSVs.")
    ] = Path("raw_corpus"),
    adapters_dir: Annotated[
        Path, typer.Option("--adapters-dir", help="Where to drop auto-created stub adapters.")
    ] = _adapters_dir_opt(),
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Show the plan without writing.")
    ] = False,
    auto_adapter: Annotated[
        bool, typer.Option("--auto-adapter/--no-auto-adapter", help="Create a stub adapter when a new model id appears.")
    ] = True,
) -> None:
    """Ingest CSV prompt datasets into the corpus (delta against current content)."""

    if not files:
        raise typer.BadParameter("Pass at least one CSV file.")
    summary: list[dict] = []
    for csv_file in files:
        plan = plan_ingest(csv_file, raw_corpus_dir)
        entry = plan.summary()
        if plan.fmt.missing_required:
            entry["error"] = (
                f"missing required columns {plan.fmt.missing_required}; "
                f"detected {plan.fmt.detected_columns}"
            )
            summary.append(entry)
            continue
        written: Path | None = None
        adapter_path: Path | None = None
        if not dry_run:
            written = apply_plan(plan, raw_corpus_dir)
            if auto_adapter:
                adapter_path = write_stub_adapter_if_missing(plan.fmt.model_id, adapters_dir)
        entry["written"] = str(written) if written else None
        entry["stub_adapter"] = str(adapter_path) if adapter_path else None
        summary.append(entry)
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
