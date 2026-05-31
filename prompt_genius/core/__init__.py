"""Public core API for Prompt Genius.

This package is the only surface a GUI (Qt/PySide6, web, etc.) should depend on.
Nothing in this package may import from ``prompt_genius.cli`` or touch
``sys.stdin`` / ``sys.stdout`` / ``print`` / ``argparse`` / ``typer``.
"""

from prompt_genius.core.adapters import (
    Adapter,
    list_adapters,
    load_adapters,
    resolve_adapter,
)
from prompt_genius.core.assembler import assemble
from prompt_genius.core.brand import (
    BrandProfile,
    apply_brand,
    brand_fit_score,
    load_brand_profile,
)
from prompt_genius.core.brief import parse_brief
from prompt_genius.core.brief_parsers import (
    BriefParser,
    ClaudeCliBriefParser,
    CodexCliBriefParser,
    HeuristicBriefParser,
    make_parser,
)
from prompt_genius.core.retrieval import Retriever
from prompt_genius.core.catalog import Catalog, load_catalog, search
from prompt_genius.core.compiler import compile_prompt
from prompt_genius.core.convert import static_to_video
from prompt_genius.core.export import export_card, list_exporters
from prompt_genius.core.generate import (
    generate_cards,
    generate_campaign,
    get_or_load_catalog,
    invalidate_catalog_cache,
)
from prompt_genius.core.models import (
    CompiledPrompt,
    Intent,
    Match,
    PromptCard,
    StructuredPrompt,
    ValidationError,
    Warning,
)
from prompt_genius.core.quality import recompute_quality_scores
from prompt_genius.core.refine import RefineDelta, RefineResult, refine_prompt
from prompt_genius.core.storage import save_card, save_feedback
from prompt_genius.core.validator import validate_card
from prompt_genius.core.versioning import diff_cards, save_version

__all__ = [
    "Adapter",
    "BrandProfile",
    "Catalog",
    "CompiledPrompt",
    "Intent",
    "Match",
    "PromptCard",
    "StructuredPrompt",
    "ValidationError",
    "Warning",
    "apply_brand",
    "assemble",
    "brand_fit_score",
    "compile_prompt",
    "diff_cards",
    "export_card",
    "generate_campaign",
    "generate_cards",
    "list_adapters",
    "list_exporters",
    "load_adapters",
    "load_brand_profile",
    "load_catalog",
    "parse_brief",
    "recompute_quality_scores",
    "refine_prompt",
    "RefineDelta",
    "RefineResult",
    "resolve_adapter",
    "save_card",
    "save_feedback",
    "save_version",
    "search",
    "static_to_video",
    "validate_card",
]
