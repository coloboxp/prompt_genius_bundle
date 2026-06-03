"""LLM-driven card proposer.

The retrieval layer surfaces:
    - Catalog patterns (reusable, model-neutral building blocks).
    - Raw-corpus exemplars (real prompts that designers wrote and that worked
      well enough to ship).

This module asks the LLM to combine both: pick a handful of catalog patterns,
propose concrete parameter values inspired by the exemplars, and write a one-
liner "why this works". The output is then validated against the chosen
adapter's parameter whitelist — the LLM cannot inject unsupported fields.

Subprocess backends (``claude -p``, ``codex exec``, MLX local) share the same
prompt template. When no backend is available or the call fails, the deterministic
:class:`HeuristicProposer` falls back to the existing assembler logic.
"""

from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from prompt_genius.core.adapters import Adapter
from prompt_genius.core.assembler import assemble
from prompt_genius.core.brief_parsers import _safe_load_json
from prompt_genius.runtime.cli_resolver import cli_env, resolve_cli_binary
from prompt_genius.core.catalog import Catalog
from prompt_genius.core.corpus import CorpusRow
from prompt_genius.core.models import Intent, Match, StructuredPrompt


_SYSTEM_PROMPT = """You are a senior creative-prompt curator helping a designer
build prompts for a generative-AI model. You will receive:
  (1) the user's brief (parsed intent).
  (2) the chosen target model's adapter — its supported parameters and prompt style.
  (3) a shortlist of CATALOG patterns retrieved from our internal library.
  (4) a shortlist of EXEMPLAR prompts from the public corpus that scored highest
      for this brief.

Your job: produce {n_cards} **diverse, imaginative** proposal objects. The catalog
patterns and exemplars are INSPIRATION, not constraints. Riff freely — invent
fresh phrasings, propose unexpected lens / lighting / motion choices, lean into
the mood. The only hard rules are:

  HARD RULES
  - Stay inside the brief: subject + mood + format hints must be respected.
  - Honor every term in `brief.avoid` — never produce them, even creatively.
  - For parameters: only use keys listed in ADAPTER.supported_parameters. Any
    other parameter key will be dropped. Values can be inventive.
  - Pick 3–6 pattern_ids from CATALOG that anchor the card; you may also add
    your own fresh phrases via `additional_fragments`.

Diversity matters — each of the {n_cards} proposals should explore a meaningfully
different direction (different style family, different mood vector, different
composition or camera idea). Don't return five variations of the same card.

Return ONLY JSON, no prose, no fences:
{{"proposals": [
   {{"selected_pattern_ids": [...],
     "additional_fragments": ["fresh phrase 1", "fresh phrase 2"],
     "additional_negatives": ["thing to avoid"],
     "parameters": {{...adapter-whitelisted only...}},
     "why_this_works": "one sentence on the creative direction" }},
   ...
]}}
"""


@dataclass(slots=True)
class ProposedCard:
    selected_pattern_ids: list[str]
    parameters: dict[str, Any]
    why_this_works: str
    additional_fragments: list[str] = field(default_factory=list)
    additional_negatives: list[str] = field(default_factory=list)
    exemplar_ids: list[str] = field(default_factory=list)


class CardProposer(Protocol):
    def propose(
        self,
        *,
        intent: Intent,
        adapter: Adapter,
        catalog: Catalog,
        matches: dict[str, list[Match]],
        exemplars: list[CorpusRow],
        n: int,
        mode: str,
        on_proposal: Callable[[ProposedCard], None] | None = None,
    ) -> list[ProposedCard]: ...


# Direction tilts that nudge each parallel LLM call toward a different creative
# angle so we don't get five lookalikes when fanning out.
_DIRECTIONS: tuple[str, ...] = (
    "lean into the brief's primary mood",
    "explore an alternative lighting + color direction",
    "explore an alternative composition / camera angle",
    "explore a more editorial / cinematic interpretation",
    "explore a quieter, more minimal interpretation",
    "explore a bolder, more graphic interpretation",
    "explore a more documentary / candid interpretation",
    "explore a more stylized / illustrated interpretation",
)


def _direction_for(index: int) -> str:
    return _DIRECTIONS[index % len(_DIRECTIONS)]


# ------------------------------------------------------------ heuristic fallback

@dataclass(slots=True)
class HeuristicProposer:
    """Falls back to the deterministic Python assembler."""

    def propose(
        self, *, intent, adapter, catalog, matches, exemplars, n, mode,
        on_proposal: Callable[[ProposedCard], None] | None = None,
    ) -> list[ProposedCard]:
        proposed: list[ProposedCard] = []
        for offset in range(n):
            rotated = {
                t: ms[offset % len(ms):] + ms[: offset % len(ms)]
                for t, ms in matches.items() if ms
            }
            for t, ms in matches.items():
                rotated.setdefault(t, ms)
            structured = assemble(intent, rotated, adapter, mode)
            if isinstance(structured, list):
                first = structured[0]
            else:
                first = structured
            params: dict[str, Any] = {}
            params.update(first.visual_parameters or {})
            params.update(first.video_parameters or {})
            card = ProposedCard(
                selected_pattern_ids=list(first.selected_patterns),
                parameters={k: v for k, v in params.items() if k in adapter.supported_parameters()},
                why_this_works=first.why_this_works,
                exemplar_ids=[ex.id for ex in exemplars[:2]],
            )
            proposed.append(card)
            if on_proposal is not None:
                try:
                    on_proposal(card)
                except Exception:  # noqa: BLE001
                    pass
        return proposed


# ------------------------------------------------------------- CLI subprocess

@dataclass(slots=True)
class _CliProposer:
    binary: str
    args: tuple[str, ...]
    timeout_seconds: float = 90.0
    max_parallel: int = 5
    prompt_as_arg: bool = False        # False = pipe via stdin (claude), True = append as positional (codex)
    fallback: CardProposer = field(default_factory=HeuristicProposer)

    def _run(self, full_prompt: str, *, direction: str = "") -> str | None:
        from prompt_genius.core import llm_trace
        import time as _time

        resolved = resolve_cli_binary(self.binary)
        if not resolved:
            return None
        if self.prompt_as_arg:
            cmd = [resolved, *self.args, full_prompt]
            stdin_input = None
        else:
            cmd = [resolved, *self.args]
            stdin_input = full_prompt
        t0 = _time.perf_counter()
        rc = -1
        stdout = ""
        try:
            result = subprocess.run(  # noqa: S603 — binary explicitly looked up
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
                env=cli_env(),
            )
            rc = result.returncode
            stdout = result.stdout
        except (subprocess.TimeoutExpired, OSError):
            return None
        finally:
            llm_trace.record(llm_trace.LlmCall(
                backend=self.binary.rsplit("/", 1)[-1],
                binary=resolved or self.binary,
                args=tuple(self.args),
                direction=direction,
                prompt=full_prompt,
                output=stdout,
                returncode=rc,
                elapsed_seconds=_time.perf_counter() - t0,
            ))
        if rc != 0:
            return None
        return stdout

    def _propose_one(
        self,
        *,
        intent, adapter, catalog, matches, exemplars, mode, direction: str,
    ) -> list[ProposedCard]:
        """Ask the LLM for ONE proposal, tilted toward ``direction``."""

        payload = _build_prompt(
            intent, adapter, catalog, matches, exemplars,
            n=1, mode=mode, direction=direction,
        )
        text = self._run(payload, direction=direction)
        if not text:
            return []
        data = _safe_load_json(text)
        if not isinstance(data, dict):
            return []
        return _validate_proposals(
            data, adapter=adapter, catalog=catalog, exemplars=exemplars,
            fallback=lambda: [],
        )

    def propose(
        self,
        *,
        intent, adapter, catalog, matches, exemplars, n, mode,
        on_proposal: Callable[[ProposedCard], None] | None = None,
    ) -> list[ProposedCard]:
        """Fan out N parallel single-card LLM calls; stream each as it lands."""

        if not resolve_cli_binary(self.binary):
            return self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
                on_proposal=on_proposal,
            )

        # Submit N parallel subprocesses, each requesting one card with a
        # different creative-direction tilt to keep variety.
        workers = min(max(self.max_parallel, 1), n)
        results: list[ProposedCard] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    self._propose_one,
                    intent=intent, adapter=adapter, catalog=catalog,
                    matches=matches, exemplars=exemplars, mode=mode,
                    direction=_direction_for(i),
                )
                for i in range(n)
            ]
            for future in as_completed(futures):
                try:
                    chunk = future.result()
                except Exception:  # noqa: BLE001
                    chunk = []
                for card in chunk:
                    results.append(card)
                    if on_proposal is not None:
                        try:
                            on_proposal(card)
                        except Exception:  # noqa: BLE001
                            pass

        # If every parallel call failed, fall back to the deterministic path.
        if not results:
            return self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
                on_proposal=on_proposal,
            )
        return results


@dataclass(slots=True)
class ClaudeCliProposer(_CliProposer):
    binary: str = "claude"
    args: tuple[str, ...] = ("-p",)


@dataclass(slots=True)
class CodexCliProposer(_CliProposer):
    binary: str = "codex"
    args: tuple[str, ...] = ("exec",)
    prompt_as_arg: bool = True


# ---------------------------------------------------------------------- MLX

@dataclass(slots=True)
class MlxProposer:
    model_name: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"
    max_tokens: int = 1200
    temperature: float = 0.3
    hf_token: str | None = None
    fallback: CardProposer = field(default_factory=HeuristicProposer)
    _model: Any = None
    _tokenizer: Any = None

    def _load(self) -> bool:
        if self._model is not None:
            return True
        try:
            from mlx_lm import load  # type: ignore
            from prompt_genius.core.llm_local import ensure_huggingface_login
        except ImportError:
            return False
        ensure_huggingface_login(self.hf_token)
        try:
            self._model, self._tokenizer = load(self.model_name)
        except Exception:  # pragma: no cover
            return False
        return True

    def propose(
        self, *, intent, adapter, catalog, matches, exemplars, n, mode,
        on_proposal: Callable[[ProposedCard], None] | None = None,
    ) -> list[ProposedCard]:
        if not self._load():
            return self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
                on_proposal=on_proposal,
            )
        try:
            from mlx_lm import generate  # type: ignore
        except ImportError:
            return self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
                on_proposal=on_proposal,
            )

        payload = _build_prompt(intent, adapter, catalog, matches, exemplars, n=n, mode=mode)
        try:
            text = generate(
                self._model, self._tokenizer,
                prompt=payload, max_tokens=self.max_tokens, temp=self.temperature, verbose=False,
            )
        except Exception:
            return self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
            )
        data = _safe_load_json(text or "")
        if not isinstance(data, dict):
            return self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
            )
        return _validate_proposals(
            data, adapter=adapter, catalog=catalog, exemplars=exemplars,
            fallback=lambda: self.fallback.propose(
                intent=intent, adapter=adapter, catalog=catalog,
                matches=matches, exemplars=exemplars, n=n, mode=mode,
            ),
        )


# ------------------------------------------------------------------- factory

def make_proposer_from_config(llm) -> CardProposer:
    """Pick a proposer backend mirroring the brief-parser config."""

    if llm.backend == "claude":
        args = list(llm.claude_args)
        if llm.effort and "--effort" not in args:
            args += ["--effort", llm.effort]
        if getattr(llm, "claude_model", "") and "--model" not in args:
            args += ["--model", llm.claude_model]
        if getattr(llm, "claude_lean_flags", True):
            args += [
                "--strict-mcp-config",
                "--tools", "",
                "--disable-slash-commands",
                "--no-session-persistence",
                "--exclude-dynamic-system-prompt-sections",
            ]
        return ClaudeCliProposer(
            binary=llm.claude_binary, args=tuple(args),
            timeout_seconds=llm.timeout_seconds,
        )
    if llm.backend == "codex":
        args = list(llm.codex_args)
        if getattr(llm, "codex_lean_flags", True):
            args += [
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
            ]
            if llm.effort:
                args += ["-c", f"model_reasoning_effort={llm.effort}"]
        if getattr(llm, "codex_model", "") and "--model" not in args and "-m" not in args:
            args += ["--model", llm.codex_model]
        return CodexCliProposer(
            binary=llm.codex_binary, args=tuple(args),
            timeout_seconds=llm.timeout_seconds,
        )
    if llm.backend == "mlx":
        return MlxProposer(
            model_name=llm.mlx_model,
            max_tokens=max(llm.mlx_max_tokens, 1200),
            temperature=llm.mlx_temperature,
            hf_token=llm.hf_token or None,
        )
    if llm.backend == "auto":
        if resolve_cli_binary(llm.claude_binary):
            return ClaudeCliProposer(
                binary=llm.claude_binary, args=tuple(llm.claude_args),
                timeout_seconds=llm.timeout_seconds,
            )
        if resolve_cli_binary(llm.codex_binary):
            return CodexCliProposer(
                binary=llm.codex_binary, args=tuple(llm.codex_args),
                timeout_seconds=llm.timeout_seconds,
            )
    return HeuristicProposer()


# ------------------------------------------------------------ prompt builder

def _build_prompt(
    intent: Intent,
    adapter: Adapter,
    catalog: Catalog,
    matches: dict[str, list[Match]],
    exemplars: list[CorpusRow],
    *,
    n: int,
    mode: str,
    direction: str | None = None,
) -> str:
    pattern_blocks: list[dict[str, Any]] = []
    for bucket in matches.values():
        for match in bucket:
            item = match.item
            pattern_blocks.append(
                {
                    "id": item.id,
                    "type": item.type,
                    "name": item.name,
                    "description": item.description,
                    "tags": item.tags,
                    "generic_fragment": item.prompt_fragments.get("generic", ""),
                    "parameters": item.parameters,
                }
            )
    pattern_blocks = pattern_blocks[:30]

    exemplar_blocks = [
        {
            "id": ex.id,
            "title": ex.title,
            "description": ex.description,
            "content_excerpt": ex.content[:600],
        }
        for ex in exemplars[:6]
    ]

    user_payload = {
        "brief": {
            "raw": intent.raw_brief,
            "subject": intent.subject,
            "audience": intent.audience,
            "mood": intent.mood,
            "style_hints": intent.style_hints,
            "avoid": intent.avoid,
            "format_hints": intent.format_hints,
        },
        "mode": mode,
        "adapter": {
            "model_id": adapter.model_id,
            "display_name": adapter.display_name,
            "prompt_style": adapter.prompt_style,
            "supported_parameters": sorted(adapter.supported_parameters()),
        },
        "catalog_shortlist": pattern_blocks,
        "exemplars": exemplar_blocks,
        "n_cards": n,
    }
    if direction:
        user_payload["creative_direction_for_this_call"] = direction
    return _SYSTEM_PROMPT.format(n_cards=n) + "\n\n" + json.dumps(user_payload, ensure_ascii=False)


# ------------------------------------------------------------ validation


def _validate_proposals(
    data: dict[str, Any],
    *,
    adapter: Adapter,
    catalog: Catalog,
    exemplars: list[CorpusRow],
    fallback,
) -> list[ProposedCard]:
    raw = data.get("proposals")
    if not isinstance(raw, list) or not raw:
        return fallback()

    allowed_params = adapter.supported_parameters()
    out: list[ProposedCard] = []
    exemplar_ids = [ex.id for ex in exemplars]
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        ids = entry.get("selected_pattern_ids") or []
        if not isinstance(ids, list):
            continue
        kept_ids = [pid for pid in ids if isinstance(pid, str) and pid in catalog.items]
        if not kept_ids:
            continue
        params = entry.get("parameters") or {}
        if not isinstance(params, dict):
            params = {}
        safe_params = {k: v for k, v in params.items() if k in allowed_params}
        why = str(entry.get("why_this_works") or "").strip() or "LLM-proposed combination"
        additional_fragments = _as_str_list(entry.get("additional_fragments"))
        additional_negatives = _as_str_list(entry.get("additional_negatives"))
        out.append(
            ProposedCard(
                selected_pattern_ids=kept_ids,
                parameters=safe_params,
                why_this_works=why,
                additional_fragments=additional_fragments,
                additional_negatives=additional_negatives,
                exemplar_ids=exemplar_ids[:3],
            )
        )
    return out or fallback()


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for entry in value:
        if entry is None:
            continue
        text = str(entry).strip()
        if text:
            out.append(text)
    return out
