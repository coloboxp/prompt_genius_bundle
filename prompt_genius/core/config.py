"""Single source of truth for every tunable knob in Prompt Genius.

Every magic number that previously lived inline in assembler / catalog / quality
is exposed here. Function defaults still use these values via ``Config.default()``
so existing call sites keep working, but a GUI / CLI can override anything by
passing a mutated :class:`Config` instance.

Persisted to ``~/.prompt-genius/config.json`` by default; the GUI's Settings
dialog reads / writes that file.
"""

from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------- paths --

class ConfigSaveError(RuntimeError):
    """Raised when the config file cannot be written (read-only FS, perms, etc)."""


def _default_path(name: str, *, writable: bool = False) -> str:
    """Resolve a default Config path against the bundled / source-tree layout."""

    from prompt_genius.core.resources import (
        resource_path, user_data_dir, is_bundled,
    )
    if writable:
        if is_bundled():
            return str(user_data_dir() / name)
        return str(Path("data") / name) if name else "data"
    return str(resource_path(name)) if name else str(resource_path("."))


@dataclass(slots=True)
class PathsConfig:
    adapters_dir: str = field(default_factory=lambda: _default_path("examples/adapters"))
    catalog_dir: str = field(default_factory=lambda: _default_path("catalog"))
    schemas_dir: str = field(default_factory=lambda: _default_path("schemas"))
    templates_dir: str = field(default_factory=lambda: _default_path("templates"))
    history_dir: str = field(default_factory=lambda: _default_path("history", writable=True))
    feedback_path: str = field(default_factory=lambda: _default_path("feedback.jsonl", writable=True))
    usage_path: str = field(default_factory=lambda: _default_path("usage.jsonl", writable=True))
    versions_path: str = field(default_factory=lambda: _default_path("versions.jsonl", writable=True))


# ----------------------------------------------------------------------- llm --

@dataclass(slots=True)
class LlmConfig:
    """Brief-parser LLM backend selection + tunables."""

    backend: str = "heuristic"          # heuristic | claude | codex | mlx | auto
    effort: str = "low"                 # low | medium | high | xhigh | max
    claude_model: str = "opus"          # alias (sonnet / opus / haiku) or full id; "" = claude default
    claude_binary: str = "claude"
    claude_args: tuple[str, ...] = ("-p",)
    claude_lean_flags: bool = True      # ~40% faster per call by skipping MCP, tools,
                                        # slash commands, session persistence, and
                                        # dynamic system prompt sections. Turn off only
                                        # if your proposer prompt needs claude's tools.
    codex_binary: str = "codex"
    codex_args: tuple[str, ...] = ("exec",)
    codex_lean_flags: bool = True       # --ephemeral --ignore-user-config --ignore-rules --skip-git-repo-check
                                        # + -c model_reasoning_effort=<effort>. ~10% faster, more variance-resilient.
    codex_model: str = ""               # "" = codex default. Override with e.g. "gpt-5" or "gpt-4o"
    timeout_seconds: float = 180.0      # bumped to absorb LLM tail latency
    # MLX local backend
    mlx_model: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"
    mlx_max_tokens: int = 800
    mlx_temperature: float = 0.2
    hf_token: str = ""
    hf_cache_dir: str = ""


# ---------------------------------------------------------------- embeddings --

@dataclass(slots=True)
class EmbeddingsConfig:
    backend: str = "dense"             # tfidf | bm25 | dense | hybrid
    prefer_dense: bool = True          # legacy; honored when backend == "tfidf"
    model_name: str = "all-MiniLM-L6-v2"
    cache_dir: str = ".cache/embeddings"
    mmr_diversity: float = 0.4
    per_type_limit: int = 5
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    hybrid_rrf_k: int = 60
    prewarm_on_launch: bool = True     # load + warm dense model on GUI startup


# ------------------------------------------------------------------ retrieval

@dataclass(slots=True)
class RetrievalWeights:
    tag_weight: float = 3.0
    text_weight: float = 2.0
    compatible_with_weight: float = 1.0
    avoid_with_penalty: float = 5.0
    intent_avoid_penalty: float = 5.0
    cosine_weight: float = 4.0
    brand_boost_weight: float = 2.0


# -------------------------------------------------------------------- video --

@dataclass(slots=True)
class VideoDefaults:
    single_shot_duration_seconds: float = 6.0
    storyboard_total_duration_seconds: float = 15.0
    keyframe_total_duration_seconds: float = 6.0
    default_shot_count: int = 4
    default_keyframe_count: int = 3
    default_aspect_ratio: str = "16:9"
    default_camera_motion: str = "slow push-in"
    default_subject_motion: str = "subtle"
    default_pacing: str = "calm"
    default_continuity: tuple[str, ...] = ("preserve_subject",)
    artifact_avoidance: tuple[str, ...] = (
        "no warping",
        "no flicker",
        "no fake text",
        "no morphing",
    )


# ------------------------------------------------------------------- quality

@dataclass(slots=True)
class QualityWeights:
    curator_weight: float = 0.45
    positive_rate_weight: float = 0.20
    save_rate_weight: float = 0.10
    reuse_rate_weight: float = 0.10
    export_rate_weight: float = 0.05
    negative_rate_penalty: float = 0.20
    half_life_days: float = 90.0


# ------------------------------------------------------------------- gui ----

@dataclass(slots=True)
class GuiConfig:
    theme: str = "system"               # system | light | dark
    default_mode: str = "static_image"
    default_target: str = "generic"
    default_n: int = 5
    default_risk: str = "safe"
    brand_profile_path: str = ""
    allow_drafts: bool = True
    show_advanced_settings: bool = False  # hides retrieval/quality/video weight knobs by default


# ---------------------------------------------------------------- top-level --

@dataclass(slots=True)
class Config:
    paths: PathsConfig = field(default_factory=PathsConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    embeddings: EmbeddingsConfig = field(default_factory=EmbeddingsConfig)
    retrieval: RetrievalWeights = field(default_factory=RetrievalWeights)
    video: VideoDefaults = field(default_factory=VideoDefaults)
    quality: QualityWeights = field(default_factory=QualityWeights)
    gui: GuiConfig = field(default_factory=GuiConfig)
    version: int = 1

    @classmethod
    def default(cls) -> "Config":
        return cls()

    def to_dict(self) -> dict[str, Any]:
        return _to_jsonable(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        return _from_jsonable(cls, data)

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            # GUI/CLI callers should catch this and surface a friendly message.
            raise ConfigSaveError(f"Could not write {target}: {exc}") from exc
        return target

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        target = Path(path)
        if not target.exists():
            return cls.default()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
            return cls.from_dict(data)
        except (json.JSONDecodeError, OSError, TypeError, KeyError, ValueError):
            # Back up the malformed file so the user can recover hand-edits.
            try:
                backup = target.with_suffix(target.suffix + ".bak")
                target.replace(backup)
            except OSError:
                pass
            return cls.default()


def default_config_path() -> Path:
    """Location of the persisted user config.

    Source-tree runs use ``~/.prompt-genius/config.json`` (git-friendly).
    Bundled .app runs use the platform user-data dir so source and bundled
    deployments don't collide and stale relative paths from source-mode
    configs don't leak into the bundled app's resource lookup.
    """

    from prompt_genius.core.resources import user_config_path
    return user_config_path()


def load_or_init(path: str | Path | None = None) -> Config:
    """Load config from ``path`` (or default), creating it on first use."""

    target = Path(path) if path else default_config_path()
    if target.exists():
        return Config.load(target)
    cfg = Config.default()
    cfg.save(target)
    return cfg


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, list):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_jsonable(v) for k, v in value.items()}
    return value


def _from_jsonable(cls: type, data: Any) -> Any:
    if not is_dataclass(cls):
        return data
    kwargs: dict[str, Any] = {}
    for field_def in fields(cls):
        name = field_def.name
        if name not in data:
            continue
        raw = data[name]
        child = _CHILDREN_BY_FIELD.get((cls.__name__, name))
        if child is not None and isinstance(raw, dict):
            kwargs[name] = _from_jsonable(child, raw)
            continue
        default_value = _field_default_value(field_def)
        if isinstance(default_value, tuple) and isinstance(raw, list):
            kwargs[name] = tuple(raw)
        else:
            kwargs[name] = raw
    return cls(**kwargs)


def _field_default_value(field_def) -> Any:
    if field_def.default is not MISSING:
        return field_def.default
    if field_def.default_factory is not MISSING:  # type: ignore[misc]
        try:
            return field_def.default_factory()  # type: ignore[misc]
        except TypeError:
            return None
    return None


_CHILDREN_BY_FIELD: dict[tuple[str, str], type] = {
    ("Config", "paths"): PathsConfig,
    ("Config", "llm"): LlmConfig,
    ("Config", "embeddings"): EmbeddingsConfig,
    ("Config", "retrieval"): RetrievalWeights,
    ("Config", "video"): VideoDefaults,
    ("Config", "quality"): QualityWeights,
    ("Config", "gui"): GuiConfig,
}
