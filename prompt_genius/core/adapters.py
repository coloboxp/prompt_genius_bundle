"""Adapter loading and resolution.

Adapters describe how to compile a model-neutral StructuredPrompt for a specific
target model. They live as JSON files. Adding a new adapter must never require
a code change in this package — only a new JSON file in the adapter directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Adapter:
    """One target-model adapter loaded from JSON."""

    model_id: str
    display_name: str
    supports: dict[str, bool]
    parameters: dict[str, dict[str, Any]]
    prompt_style: str
    unsupported_fields_behavior: str
    negative_prompt_behavior: str | None = None
    adapter_status: str = "stub_unverified"
    language: str | None = None
    notes: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Adapter":
        return cls(
            model_id=data["model_id"],
            display_name=data.get("display_name", data["model_id"]),
            supports=dict(data.get("supports") or {}),
            parameters=dict(data.get("parameters") or {}),
            prompt_style=data.get("prompt_style", "structured_natural_language"),
            unsupported_fields_behavior=data.get("unsupported_fields_behavior", "drop"),
            negative_prompt_behavior=data.get("negative_prompt_behavior"),
            adapter_status=data.get("adapter_status", "stub_unverified"),
            language=data.get("language"),
            notes=data.get("notes"),
            raw=data,
        )

    def supports_mode(self, mode: str) -> bool:
        return bool(self.supports.get(mode, False))

    def supported_parameters(self) -> set[str]:
        return {name for name, spec in self.parameters.items() if spec.get("supported")}

    def parameter_syntax(self, name: str) -> str | None:
        spec = self.parameters.get(name)
        if not spec:
            return None
        return spec.get("syntax")


def load_adapters(adapter_dir: str | Path) -> dict[str, Adapter]:
    """Load all ``*_adapter.json`` files from ``adapter_dir``.

    Returns a mapping of ``model_id`` to :class:`Adapter`. Raises ``ValueError``
    if any required adapter (``generic``) is missing.
    """

    root = Path(adapter_dir)
    if not root.exists():
        raise FileNotFoundError(f"Adapter directory does not exist: {root}")

    adapters: dict[str, Adapter] = {}
    for path in sorted(root.glob("*_adapter.json")):
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        adapter = Adapter.from_dict(data)
        if adapter.model_id in adapters:
            raise ValueError(f"Duplicate adapter model_id: {adapter.model_id}")
        adapters[adapter.model_id] = adapter

    if "generic" not in adapters:
        raise ValueError(
            "A 'generic' adapter is required as the default. "
            "Expected examples/adapters/generic_adapter.json."
        )
    return adapters


def list_adapters(adapters: dict[str, Adapter]) -> list[dict[str, Any]]:
    """Return adapter summaries suitable for GUI tables or CLI output."""

    summaries: list[dict[str, Any]] = []
    for model_id, adapter in sorted(adapters.items()):
        modes = sorted(name for name, ok in adapter.supports.items() if ok)
        summaries.append(
            {
                "model_id": model_id,
                "display_name": adapter.display_name,
                "adapter_status": adapter.adapter_status,
                "modes": modes,
                "prompt_style": adapter.prompt_style,
            }
        )
    return summaries


def resolve_adapter(adapters: dict[str, Adapter], model_id: str | None) -> Adapter:
    """Resolve an adapter id to an :class:`Adapter`.

    ``None`` resolves to the ``generic`` adapter. Unknown ids raise ``KeyError``.
    """

    key = model_id or "generic"
    if key not in adapters:
        raise KeyError(f"Unknown target model: {model_id!r}. Known: {sorted(adapters)}")
    return adapters[key]
