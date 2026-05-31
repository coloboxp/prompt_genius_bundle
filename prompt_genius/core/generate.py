"""High-level facade: brief + mode + target → list of PromptCard.

This is the single function a GUI is expected to call to fulfill a designer's
request. It orchestrates brief parsing → catalog search → assembly →
compilation → card construction. Nothing here touches stdin/stdout.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from prompt_genius.core.adapters import Adapter, load_adapters, resolve_adapter
from prompt_genius.core.assembler import assemble, shot_role_hints
from prompt_genius.core.brand import BrandProfile, apply_brand, load_brand_profile
from prompt_genius.core.brief_parsers import BriefParser, HeuristicBriefParser
from prompt_genius.core.config import Config
from prompt_genius.core.catalog import Catalog, load_catalog, search
from prompt_genius.core.compiler import compile_prompt
from prompt_genius.core.corpus import CorpusIndex, CorpusRow, load_or_build_corpus_index
from prompt_genius.core.proposer import (
    CardProposer,
    HeuristicProposer,
    ProposedCard,
    make_proposer_from_config,
)
from prompt_genius.core.usage import record_usage
from prompt_genius.core.models import (
    CompiledPrompt,
    Intent,
    Match,
    PromptCard,
    StructuredPrompt,
    Warning,
    to_dict,
)


def _title_for(intent: Intent, mode: str) -> str:
    """First sentence of the brief, capped, falling back to the parsed subject."""

    raw = (intent.raw_brief or "").strip()
    if raw:
        # First sentence, stripped of trailing punctuation, capped at 64 chars.
        head = raw.split(".")[0].split("\n")[0].strip()
        if len(head) > 64:
            head = head[:61].rstrip() + "…"
        if head:
            return head
    if intent.subject:
        return intent.subject.strip().title()
    return f"Untitled {mode}"


def _compile_one(
    structured: StructuredPrompt | list[StructuredPrompt],
    adapter: Adapter,
    catalog: Catalog,
) -> CompiledPrompt | list[CompiledPrompt]:
    if isinstance(structured, list):
        return [compile_prompt(s, adapter, catalog) for s in structured]
    return compile_prompt(structured, adapter, catalog)


def _aggregate_warnings(
    compiled: CompiledPrompt | list[CompiledPrompt],
) -> list[Warning]:
    if isinstance(compiled, list):
        seen: dict[str, Warning] = {}
        for c in compiled:
            for w in c.warnings:
                seen.setdefault(w.code, w)
        return list(seen.values())
    return list(compiled.warnings)


def _diversity_key(structured: StructuredPrompt | list[StructuredPrompt]) -> tuple[str, ...]:
    items = structured if isinstance(structured, list) else [structured]
    return tuple(sorted({pid for s in items for pid in s.selected_patterns}))


def generate_cards(
    brief_text: str,
    *,
    mode: str,
    target_model: str | None = None,
    n: int = 5,
    adapters_dir: str | Path = "examples/adapters",
    catalog_dir: str | Path = "catalog",
    allow_drafts: bool = True,
    risk_level: str = "safe",
    brand_profile: BrandProfile | str | Path | None = None,
    prefer_dense_embeddings: bool = False,
    embeddings_model: str | None = None,
    embeddings_cache_dir: str | Path = ".cache/embeddings",
    brief_parser: BriefParser | None = None,
    card_proposer: CardProposer | None = None,
    corpus_dir: str | Path | None = "raw_corpus",
    corpus_index: CorpusIndex | None = None,
    exemplars_per_card: int = 6,
    usage_ledger: str | Path | None = "data/usage.jsonl",
    config: Config | None = None,
    card_callback: Callable[[PromptCard], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[PromptCard]:
    """Top-level entry: brief → N :class:`PromptCard`.

    Phase 1 Notes:
    - ``allow_drafts`` defaults to True because the seeded catalog ships as draft.
      Production deployments should set it to False once items are reviewed.
    - ``should_cancel`` is checked between expensive steps so a GUI can
      interrupt long operations.
    """

    if should_cancel and should_cancel():
        return []

    adapters = load_adapters(adapters_dir)
    adapter = resolve_adapter(adapters, target_model)
    if not adapter.supports_mode(mode):
        raise ValueError(
            f"Adapter {adapter.model_id!r} does not support mode {mode!r}. "
            f"Supported: {sorted(name for name, ok in adapter.supports.items() if ok)}"
        )

    cfg_for_load = config or Config.default()
    catalog = get_or_load_catalog(
        catalog_dir,
        backend=cfg_for_load.embeddings.backend,
        prefer_dense=prefer_dense_embeddings or cfg_for_load.embeddings.prefer_dense,
        model_name=embeddings_model or cfg_for_load.embeddings.model_name,
        cache_dir=embeddings_cache_dir,
        bm25_k1=cfg_for_load.embeddings.bm25_k1,
        bm25_b=cfg_for_load.embeddings.bm25_b,
        rrf_k=cfg_for_load.embeddings.hybrid_rrf_k,
    )
    parser = brief_parser or HeuristicBriefParser()
    intent = parser.parse(brief_text)

    brand: BrandProfile | None
    if isinstance(brand_profile, (str, Path)):
        brand = load_brand_profile(brand_profile)
    else:
        brand = brand_profile
    intent = apply_brand(intent, brand)

    if should_cancel and should_cancel():
        return []

    cfg = config or Config.default()
    matches = search(
        catalog,
        intent,
        mode,
        allow_drafts=allow_drafts,
        per_type_limit=max(n, cfg.embeddings.per_type_limit),
        brand_boost_terms=brand.boost_terms() if brand else None,
        config=cfg,
    )

    # If a non-heuristic proposer is available, let it drive selection + params.
    proposer = card_proposer or (
        make_proposer_from_config(cfg.llm) if cfg.llm.backend != "heuristic" else HeuristicProposer()
    )

    # Pull exemplars from the raw corpus only when the LLM proposer actually
    # uses them. The heuristic proposer ignores exemplars, so skip the 100ms
    # BM25 sweep of 18k+ rows.
    exemplars: list[CorpusRow] = []
    if corpus_dir is not None and not isinstance(proposer, HeuristicProposer):
        try:
            index = corpus_index or _load_corpus_index_cached(Path(corpus_dir))
            exemplars = [row for row, _ in index.search(intent.raw_brief or "", k=exemplars_per_card)]
        except (OSError, ValueError):
            exemplars = []

    cards: list[PromptCard] = []
    seen_keys: set[tuple[str, ...]] = set()

    def _proposal_to_card(proposal: ProposedCard) -> PromptCard | None:
        """Turn a single ProposedCard into a finished PromptCard (or skip if dupe)."""

        if len(cards) >= n:
            return None
        forced_matches = _matches_from_ids(catalog, matches, proposal.selected_pattern_ids)
        structured = assemble(intent, forced_matches, adapter, mode, config=cfg)

        def _apply_extras(entry):
            target = entry.video_parameters if entry.video_parameters is not None else (entry.visual_parameters or {})
            target.update({k: v for k, v in proposal.parameters.items() if v is not None})
            if entry.visual_parameters is None and entry.video_parameters is None and proposal.parameters:
                entry.visual_parameters = {k: v for k, v in proposal.parameters.items() if v is not None}
            for extra in proposal.additional_negatives:
                if extra and extra not in entry.negative_fragments:
                    entry.negative_fragments.append(extra)
            for extra in proposal.additional_fragments:
                if extra and f"llm:{extra}" not in entry.selected_patterns:
                    entry.selected_patterns.append(f"llm:{extra}")

        if isinstance(structured, list):
            for entry in structured:
                _apply_extras(entry)
        else:
            _apply_extras(structured)
        key = _diversity_key(structured)
        if key in seen_keys:
            return None
        seen_keys.add(key)
        compiled = _compile_one(structured, adapter, catalog)
        warnings = _aggregate_warnings(compiled)
        why = proposal.why_this_works or (
            structured[0].why_this_works if isinstance(structured, list) and structured else ""
        )
        patterns = sorted({pid for s in (structured if isinstance(structured, list) else [structured]) for pid in s.selected_patterns})
        return PromptCard(
            id=str(uuid.uuid4()),
            title=_title_for(intent, mode),
            mode=mode,
            target_model=adapter.model_id,
            structured=structured,
            compiled=compiled,
            why_this_works=why,
            selected_patterns=patterns,
            risk_level=risk_level,
            warnings=warnings,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # As each LLM proposal lands (in parallel), turn it into a card and stream it.
    _cards_lock = __import__("threading").Lock()
    def _on_proposal(proposal: ProposedCard) -> None:
        with _cards_lock:
            new_card = _proposal_to_card(proposal)
            if new_card is None:
                return
            cards.append(new_card)
        if card_callback is not None:
            try:
                card_callback(new_card)
            except Exception:  # noqa: BLE001
                pass

    if not isinstance(proposer, HeuristicProposer):
        try:
            proposer.propose(
                intent=intent,
                adapter=adapter,
                catalog=catalog,
                matches=matches,
                exemplars=exemplars,
                n=n,
                mode=mode,
                on_proposal=_on_proposal,
            )
        except Exception:  # noqa: BLE001 — proposer must never crash the request
            pass

    attempt = 0
    while len(cards) < n and attempt < n * 3:
        attempt += 1
        if should_cancel and should_cancel():
            break

        # Rotate the per-type matches so each card gets a different lead pick.
        rotated = {
            t: ms[(attempt - 1) % len(ms):] + ms[: (attempt - 1) % len(ms)]
            for t, ms in matches.items()
            if ms
        }
        # Ensure at least the negatives still come through:
        for t, ms in matches.items():
            rotated.setdefault(t, ms)

        per_shot_matches: list[dict] | None = None
        if mode == "storyboard":
            per_shot_matches = _build_per_shot_matches(
                catalog,
                intent,
                allow_drafts=allow_drafts,
                brand_boost_terms=(brand.boost_terms() if brand else None),
                config=cfg,
            )
        structured = assemble(
            intent, rotated, adapter, mode,
            per_shot_matches=per_shot_matches,
            config=cfg,
        )
        key = _diversity_key(structured)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        compiled = _compile_one(structured, adapter, catalog)
        warnings = _aggregate_warnings(compiled)

        if isinstance(structured, list):
            why = structured[0].why_this_works if structured else ""
            patterns = sorted({pid for s in structured for pid in s.selected_patterns})
        else:
            why = structured.why_this_works
            patterns = list(structured.selected_patterns)

        new_card = PromptCard(
            id=str(uuid.uuid4()),
            title=_title_for(intent, mode),
            mode=mode,
            target_model=adapter.model_id,
            structured=structured,
            compiled=compiled,
            why_this_works=why,
            selected_patterns=patterns,
            risk_level=risk_level,
            warnings=warnings,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        cards.append(new_card)
        if card_callback is not None:
            try:
                card_callback(new_card)
            except Exception:  # noqa: BLE001
                pass

    if usage_ledger and cards:
        try:
            for card in cards:
                record_usage(
                    card.selected_patterns,
                    event="generated",
                    card_id=card.id,
                    ledger_path=usage_ledger,
                )
        except OSError:
            pass

    return cards


_CORPUS_CACHE: dict[str, CorpusIndex] = {}
_CATALOG_CACHE: dict[tuple, Catalog] = {}


def get_or_load_catalog(
    catalog_dir: str | Path,
    *,
    backend: str = "dense",
    prefer_dense: bool = True,
    model_name: str | None = None,
    cache_dir: str | Path = ".cache/embeddings",
    bm25_k1: float = 1.5,
    bm25_b: float = 0.75,
    rrf_k: int = 60,
) -> Catalog:
    """In-process catalog cache. Keyed on every parameter that would change the index.

    The first call builds and warms (model load + cache). Subsequent calls reuse
    the same :class:`Catalog` instance, so the dense backend's
    SentenceTransformer model stays resident in RAM.
    """

    abs_dir = str(Path(catalog_dir).resolve()) if Path(catalog_dir).exists() else str(catalog_dir)
    key = (
        abs_dir, backend, model_name or "default",
        str(cache_dir), bool(prefer_dense),
        bm25_k1, bm25_b, rrf_k,
    )
    if key not in _CATALOG_CACHE:
        _CATALOG_CACHE[key] = load_catalog(
            catalog_dir,
            backend=backend,
            prefer_dense=prefer_dense,
            model_name=model_name,
            cache_dir=cache_dir,
            bm25_k1=bm25_k1,
            bm25_b=bm25_b,
            rrf_k=rrf_k,
        )
        # Warm the embedding model up front so the first query doesn't pay the load.
        retriever = _CATALOG_CACHE[key].retriever
        if retriever is not None:
            try:
                retriever.score("warmup", list(_CATALOG_CACHE[key].items.values())[:1])
            except Exception:  # noqa: BLE001 — best-effort warmup
                pass
    return _CATALOG_CACHE[key]


def invalidate_catalog_cache() -> None:
    """Drop the in-process catalog cache. Call after ingest writes new patterns."""

    _CATALOG_CACHE.clear()


def _load_corpus_index_cached(corpus_dir: Path) -> CorpusIndex:
    key = str(corpus_dir.resolve()) if corpus_dir.exists() else str(corpus_dir)
    if key not in _CORPUS_CACHE:
        _CORPUS_CACHE[key] = load_or_build_corpus_index(corpus_dir)
    return _CORPUS_CACHE[key]


def _matches_from_ids(
    catalog: Catalog,
    matches: dict[str, list[Match]],
    ids: list[str],
) -> dict[str, list[Match]]:
    """Project an LLM-chosen id list back into the per-type matches map."""

    forced: dict[str, list[Match]] = {}
    for pid in ids:
        item = catalog.items.get(pid)
        if not item:
            continue
        forced.setdefault(item.type, []).append(Match(item=item, score=1.0, reasons=["llm pick"]))
    # Carry through negatives even if the LLM forgot them.
    for match in matches.get("negative_pattern", []):
        forced.setdefault("negative_pattern", []).append(match)
    return forced


def _build_per_shot_matches(
    catalog: Catalog,
    base_intent: Intent,
    *,
    allow_drafts: bool,
    brand_boost_terms,
    config: Config | None = None,
) -> list[dict]:
    """Run a fresh search per shot, tinting intent with the role hint."""

    out: list[dict] = []
    for role, hint in shot_role_hints():
        tinted = Intent(
            raw_brief=f"{base_intent.raw_brief}\n[shot role: {role}] {hint}",
            subject=base_intent.subject,
            audience=base_intent.audience,
            mood=[*base_intent.mood],
            style_hints=[*base_intent.style_hints, role, hint],
            avoid=list(base_intent.avoid),
            format_hints=list(base_intent.format_hints),
        )
        out.append(
            search(
                catalog,
                tinted,
                "storyboard",
                allow_drafts=allow_drafts,
                brand_boost_terms=brand_boost_terms,
                per_type_limit=4,
                config=config,
            )
        )
    return out


def card_to_card_dict(card: PromptCard) -> dict[str, Any]:
    """Serialize a :class:`PromptCard` to a plain dict suitable for JSON output."""

    return to_dict(card)


_CAMPAIGN_BLUEPRINT = [
    {"role": "hero_static", "mode": "static_image"},
    {"role": "hero_video", "mode": "image_to_video"},
    {"role": "thumbnail", "mode": "static_image"},
    {"role": "social_crop", "mode": "static_image"},
    {"role": "storyboard", "mode": "storyboard"},
]


def generate_campaign(
    brief_text: str,
    *,
    image_target: str | None = None,
    video_target: str | None = None,
    adapters_dir: str | Path = "examples/adapters",
    catalog_dir: str | Path = "catalog",
    allow_drafts: bool = True,
    risk_level: str = "safe",
    brand_profile: BrandProfile | str | Path | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, list[PromptCard]]:
    """Generate a coordinated campaign pack from one brief.

    Returns a mapping ``{role: [PromptCard]}`` covering the standard campaign
    asset set: hero static, matching hero video, thumbnail, social crop, and
    a storyboard. Image and video targets may be different adapters.
    """

    adapters = load_adapters(adapters_dir)
    image_adapter = resolve_adapter(adapters, image_target)
    video_adapter = resolve_adapter(adapters, video_target)

    out: dict[str, list[PromptCard]] = {}
    for entry in _CAMPAIGN_BLUEPRINT:
        if should_cancel and should_cancel():
            break
        adapter = image_adapter if entry["mode"] in {"static_image", "image_editing"} else video_adapter
        if not adapter.supports_mode(entry["mode"]):
            continue
        cards = generate_cards(
            brief_text,
            mode=entry["mode"],
            target_model=adapter.model_id,
            n=1,
            adapters_dir=adapters_dir,
            catalog_dir=catalog_dir,
            allow_drafts=allow_drafts,
            risk_level=risk_level,
            brand_profile=brand_profile,
            should_cancel=should_cancel,
        )
        out[entry["role"]] = cards
    return out
