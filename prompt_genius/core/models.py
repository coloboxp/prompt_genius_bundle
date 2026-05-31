"""Pure data types used across the Prompt Genius core.

Every type here is a stdlib ``@dataclass``. No I/O, no formatting, no UI logic.
A GUI consumes these directly; the CLI does too.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Intent:
    """Structured representation of a user brief."""

    raw_brief: str
    subject: str | None = None
    audience: str | None = None
    mood: list[str] = field(default_factory=list)
    style_hints: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    format_hints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CatalogItem:
    """In-memory representation of a normalized catalog item."""

    id: str
    type: str
    category: str
    name: str
    description: str
    applies_to: list[str]
    not_recommended_for: list[str]
    prompt_fragments: dict[str, str]
    parameters: dict[str, Any]
    compatible_with: list[str]
    avoid_with: list[str]
    tags: list[str]
    quality_score: float
    status: str
    version: str
    notes: str | None = None
    source: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogItem":
        return cls(
            id=data["id"],
            type=data["type"],
            category=data["category"],
            name=data["name"],
            description=data["description"],
            applies_to=list(data.get("applies_to") or []),
            not_recommended_for=list(data.get("not_recommended_for") or []),
            prompt_fragments=dict(data.get("prompt_fragments") or {}),
            parameters=dict(data.get("parameters") or {}),
            compatible_with=list(data.get("compatible_with") or []),
            avoid_with=list(data.get("avoid_with") or []),
            tags=list(data.get("tags") or []),
            quality_score=float(data.get("quality_score", 0.0)),
            status=data.get("status", "draft"),
            version=str(data.get("version", "0.1")),
            notes=data.get("notes"),
            source=data.get("source"),
        )


@dataclass(slots=True)
class Match:
    """A catalog item that matched the user intent, with a score."""

    item: CatalogItem
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructuredPrompt:
    """Model-neutral creative object produced by the assembler.

    For storyboard / keyframe modes the GUI/CLI receives a ``list[StructuredPrompt]``
    rather than a single instance; this dataclass also carries optional
    ``shot_number`` / ``frame_role`` fields for that case.
    """

    mode: str
    target_model: str
    creative_intent: dict[str, Any]
    selected_patterns: list[str]
    why_this_works: str
    negative_fragments: list[str]
    visual_parameters: dict[str, Any] | None = None
    video_parameters: dict[str, Any] | None = None
    shot_number: int | None = None
    duration_seconds: float | None = None
    frame_role: str | None = None


@dataclass(slots=True)
class Warning:
    """Non-fatal warning attached to a compiled prompt or card."""

    code: str
    message: str


@dataclass(slots=True)
class CompiledPrompt:
    """Text + parameters produced by compiling a StructuredPrompt for an adapter."""

    text: str
    negative_text: str
    parameters: dict[str, Any]
    warnings: list[Warning] = field(default_factory=list)


@dataclass(slots=True)
class PromptCard:
    """Top-level object returned by ``generate_cards``."""

    id: str
    title: str
    mode: str
    target_model: str
    structured: StructuredPrompt | list[StructuredPrompt]
    compiled: CompiledPrompt | list[CompiledPrompt]
    why_this_works: str
    selected_patterns: list[str]
    risk_level: str
    warnings: list[Warning]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return _dataclass_to_dict(self)


@dataclass(slots=True)
class ValidationError:
    """One validation problem against a JSON schema."""

    path: str
    message: str


def _dataclass_to_dict(value: Any) -> Any:
    """Convert dataclasses (including nested lists/dicts) to plain JSON-friendly dicts.

    ``warnings`` is dropped from any dataclass output: warnings are diagnostic
    (adapter-stub notices, dropped-param hints) and meaningless to the model
    that ultimately consumes the JSON. Programmatic callers that need them
    must read the dataclass field directly.
    """

    if hasattr(value, "__dataclass_fields__"):
        result = {key: _dataclass_to_dict(val) for key, val in asdict(value).items()}
        result.pop("warnings", None)
        return result
    if isinstance(value, list):
        return [_dataclass_to_dict(v) for v in value]
    if isinstance(value, dict):
        return {key: _dataclass_to_dict(val) for key, val in value.items()}
    return value


def to_dict(value: Any) -> Any:
    """Public helper to convert any core dataclass tree to a JSON-friendly dict."""

    return _dataclass_to_dict(value)
