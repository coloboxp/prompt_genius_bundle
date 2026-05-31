"""Pluggable brief parsers.

Default = heuristic (stdlib). When a coding-agent CLI is available on PATH the
LLM-backed parsers shell out to it:

- :class:`ClaudeCliBriefParser` invokes ``claude -p`` (Claude CLI, print mode).
- :class:`CodexCliBriefParser` invokes ``codex exec`` (OpenAI Codex CLI).

Both run as subprocesses, reuse the host's existing auth, need no Python SDK
install, and require no API key. JSON-only output is requested in the system
prompt; if parsing fails the parser falls back to the heuristic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Protocol

from prompt_genius.core.brief import parse_brief as heuristic_parse_brief
from prompt_genius.core.models import Intent

_SYSTEM_PROMPT = (
    "You convert a creative brief from a designer into a strict JSON object "
    "for a prompt-engineering workbench. Return ONLY JSON with these keys "
    "(no prose, no markdown fences, no commentary):\n"
    '{"subject": string|null,\n'
    ' "audience": string|null,\n'
    ' "mood": string[],\n'
    ' "style_hints": string[],\n'
    ' "avoid": string[],\n'
    ' "format_hints": string[]}\n\n'
    "User brief follows.\n"
)


class BriefParser(Protocol):
    def parse(self, brief_text: str) -> Intent: ...


@dataclass(slots=True)
class HeuristicBriefParser:
    """Wraps the stdlib heuristic parser as a :class:`BriefParser`."""

    def parse(self, brief_text: str) -> Intent:
        return heuristic_parse_brief(brief_text)


@dataclass(slots=True)
class _CliParserBase:
    """Common subprocess + fallback machinery for CLI-backed parsers."""

    binary: str
    args: tuple[str, ...]
    fallback: BriefParser | None = None
    timeout_seconds: float = 60.0
    prompt_as_arg: bool = False

    def _run(self, full_prompt: str) -> str | None:
        if not shutil.which(self.binary):
            return None
        try:
            if self.prompt_as_arg:
                cmd = [self.binary, *self.args, full_prompt]
                stdin_input = None
            else:
                cmd = [self.binary, *self.args]
                stdin_input = full_prompt
            result = subprocess.run(  # noqa: S603 — explicit binary lookup above
                cmd,
                input=stdin_input,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if result.returncode != 0:
            return None
        return result.stdout

    def parse(self, brief_text: str) -> Intent:
        full = _SYSTEM_PROMPT + "\n" + brief_text
        payload = self._run(full)
        if payload is None:
            return (self.fallback or HeuristicBriefParser()).parse(brief_text)
        data = _safe_load_json(payload)
        if not isinstance(data, dict):
            return (self.fallback or HeuristicBriefParser()).parse(brief_text)
        return _intent_from_data(brief_text, data)


@dataclass(slots=True)
class ClaudeCliBriefParser(_CliParserBase):
    """Uses ``claude -p`` (Claude CLI, print mode). Reads brief from stdin."""

    binary: str = "claude"
    args: tuple[str, ...] = ("-p",)


@dataclass(slots=True)
class CodexCliBriefParser(_CliParserBase):
    """Uses ``codex exec`` (OpenAI Codex CLI). Passes brief as positional arg."""

    binary: str = "codex"
    args: tuple[str, ...] = ("exec",)
    prompt_as_arg: bool = True


def _intent_from_data(brief_text: str, data: dict) -> Intent:
    return Intent(
        raw_brief=brief_text,
        subject=_as_optional_str(data.get("subject")),
        audience=_as_optional_str(data.get("audience")),
        mood=_as_str_list(data.get("mood")),
        style_hints=_as_str_list(data.get("style_hints")),
        avoid=_as_str_list(data.get("avoid")),
        format_hints=_as_str_list(data.get("format_hints")),
    )


def _safe_load_json(payload: str) -> object:
    payload = (payload or "").strip()
    if payload.startswith("```"):
        payload = payload.strip("`").strip()
        if payload.startswith("json"):
            payload = payload[len("json"):].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(payload[start:end + 1])
            except json.JSONDecodeError:
                pass
        return None


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_str_list(value: object) -> list[str]:
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


def make_parser_from_config(config_llm) -> BriefParser:
    """Convenience: build a parser from a ``LlmConfig`` dataclass."""

    claude_args = list(config_llm.claude_args)
    if config_llm.effort and "--effort" not in claude_args:
        claude_args += ["--effort", config_llm.effort]
    claude_model = getattr(config_llm, "claude_model", "")
    if claude_model and "--model" not in claude_args:
        claude_args += ["--model", claude_model]
    if getattr(config_llm, "claude_lean_flags", True):
        claude_args += [
            "--strict-mcp-config",
            "--tools", "",
            "--disable-slash-commands",
            "--no-session-persistence",
            "--exclude-dynamic-system-prompt-sections",
        ]
    codex_args = list(config_llm.codex_args)
    if getattr(config_llm, "codex_lean_flags", True):
        codex_args += [
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
        ]
        if config_llm.effort:
            codex_args += ["-c", f"model_reasoning_effort={config_llm.effort}"]
    codex_model = getattr(config_llm, "codex_model", "")
    if codex_model and "--model" not in codex_args and "-m" not in codex_args:
        codex_args += ["--model", codex_model]
    return make_parser(
        backend=config_llm.backend,
        mlx_model=config_llm.mlx_model,
        mlx_max_tokens=config_llm.mlx_max_tokens,
        mlx_temperature=config_llm.mlx_temperature,
        hf_token=config_llm.hf_token or None,
        claude_binary=config_llm.claude_binary,
        claude_args=tuple(claude_args),
        codex_binary=config_llm.codex_binary,
        codex_args=tuple(codex_args),
        timeout_seconds=config_llm.timeout_seconds,
    )


def make_parser(
    *,
    backend: str = "auto",
    mlx_model: str | None = None,
    mlx_max_tokens: int | None = None,
    mlx_temperature: float | None = None,
    hf_token: str | None = None,
    claude_binary: str | None = None,
    claude_args: tuple[str, ...] | None = None,
    codex_binary: str | None = None,
    codex_args: tuple[str, ...] | None = None,
    timeout_seconds: float | None = None,
) -> BriefParser:
    """Factory: pick a brief-parser backend by name.

    ``backend`` values:
        - ``"auto"``  → claude > codex > heuristic (whichever is on PATH).
        - ``"claude"``    → :class:`ClaudeCliBriefParser`
        - ``"codex"``     → :class:`CodexCliBriefParser`
        - ``"mlx"``       → MLX local backend (requires ``mlx-lm``)
        - ``"heuristic"`` → :class:`HeuristicBriefParser`
    """

    heuristic = HeuristicBriefParser()

    def _claude() -> BriefParser:
        return ClaudeCliBriefParser(
            binary=claude_binary or "claude",
            args=claude_args or ("-p",),
            fallback=heuristic,
            timeout_seconds=timeout_seconds or 60.0,
        )

    def _codex() -> BriefParser:
        return CodexCliBriefParser(
            binary=codex_binary or "codex",
            args=codex_args or ("exec",),
            fallback=heuristic,
            timeout_seconds=timeout_seconds or 60.0,
        )

    def _mlx() -> BriefParser:
        from prompt_genius.core.llm_local import MlxBriefParser  # local import to keep optional

        return MlxBriefParser(
            model_name=mlx_model or "mlx-community/Llama-3.2-3B-Instruct-4bit",
            max_tokens=mlx_max_tokens or 800,
            temperature=mlx_temperature if mlx_temperature is not None else 0.2,
            hf_token=hf_token or None,
            fallback=heuristic,
        )

    if backend == "heuristic":
        return heuristic
    if backend == "claude":
        return _claude()
    if backend == "codex":
        return _codex()
    if backend == "mlx":
        return _mlx()
    if backend != "auto":
        raise ValueError(f"Unknown brief parser backend: {backend!r}")
    if shutil.which("claude"):
        return _claude()
    if shutil.which("codex"):
        return _codex()
    return heuristic
