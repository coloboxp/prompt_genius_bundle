"""Image + prompt + comments → refined prompt.

The designer points at a generated image, pastes the prompt that produced it,
and writes what's wrong. A vision-capable LLM (via ``claude -p`` or
``codex exec`` subprocess) reads the image, then proposes both a granular
delta and a complete rewritten prompt.

No Anthropic / OpenAI SDK dependency — uses the same subprocess pattern as the
brief parser and card proposer. The CLI is told to read the image file from
disk via its built-in file-reading tool.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from prompt_genius.core.brief_parsers import _safe_load_json
from prompt_genius.runtime.cli_resolver import cli_env, resolve_cli_binary


@dataclass(slots=True)
class RefineDelta:
    action: str        # add | remove | change | tighten | replace
    target: str        # lighting | composition | camera | mood | negative | other
    text: str


@dataclass(slots=True)
class RefineResult:
    whole: str                            # complete rewritten prompt
    delta: list[RefineDelta] = field(default_factory=list)
    rationale: str = ""
    raw: str = ""                         # raw model response, kept for debugging
    backend: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "whole": self.whole,
            "delta": [asdict(d) for d in self.delta],
            "rationale": self.rationale,
            "backend": self.backend,
        }


_SYSTEM_PROMPT = """You are a senior creative-prompt critic helping a designer
refine a prompt for a generative-AI image or video model.

You will be given:
  - ORIGINAL_PROMPT: the prompt the designer used.
  - COMMENTS: what the designer says is wrong with the result.
  - IMAGE_PATH: a local file path to the resulting image. Use your file-reading
    tool to actually look at the image before proposing changes.

Produce JSON only, no prose, no fences:

{
  "delta": [
    {"action": "add|remove|change|tighten|replace",
     "target": "lighting|composition|camera|mood|color|subject|negative|other",
     "text": "what to add / what to remove / what to change to"}
  ],
  "whole": "a complete rewritten prompt that addresses the comments while keeping what was already working",
  "rationale": "one or two sentences on the creative direction of the fix"
}

Rules:
  - The "whole" prompt must respect the original creative intent — fix the
    issues, don't pivot the concept.
  - Honor every comment in COMMENTS. If a comment is vague, interpret
    generously but stay inside the designer's brief.
  - Keep the prompt model-neutral unless the original prompt used a specific
    model's grammar (Midjourney --no, Seedance shot-timing, etc).
  - If you cannot read the image, say so in "rationale" and proceed using
    ORIGINAL_PROMPT + COMMENTS only.
"""


def _build_user_payload(image_path: Path, original_prompt: str, comments: str) -> str:
    return (
        f"IMAGE_PATH: {image_path}\n\n"
        f"ORIGINAL_PROMPT:\n{original_prompt.strip()}\n\n"
        f"COMMENTS:\n{comments.strip()}\n\n"
        "Look at the image, then return only the JSON object specified above."
    )


def _save_image_source(image_source: bytes | str | Path) -> tuple[Path, bool]:
    """Normalize the image source to a Path on disk.

    Returns ``(path, created_temp)``. When ``created_temp`` is True the caller
    owns cleanup. Bytes are written to a tempfile.
    """

    if isinstance(image_source, (str, Path)):
        path = Path(image_source).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")
        return path, False
    if isinstance(image_source, (bytes, bytearray)):
        fd, name = tempfile.mkstemp(prefix="pg_refine_", suffix=".png")
        with open(fd, "wb") as handle:
            handle.write(bytes(image_source))
        return Path(name), True
    raise TypeError(f"Unsupported image source type: {type(image_source).__name__}")


def _run_claude(
    image_path: Path, payload: str, timeout_seconds: float, binary: str = "claude"
) -> tuple[int, str, str]:
    resolved = resolve_cli_binary(binary)
    if not resolved:
        return 127, "", f"{binary} CLI not found"
    cmd = [
        resolved,
        "-p",
        "--add-dir", str(image_path.parent),     # allow the file dir
        "--allowedTools", "Read",                # let it open the image
        "--system-prompt", _SYSTEM_PROMPT,
        payload,
    ]
    try:
        result = subprocess.run(                  # noqa: S603 — explicit binary
            cmd, capture_output=True, text=True, check=False, timeout=timeout_seconds,
            env=cli_env(),
        )
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", "timed out"
    return result.returncode, result.stdout, result.stderr


def _run_codex(
    image_path: Path, payload: str, timeout_seconds: float, binary: str = "codex"
) -> tuple[int, str, str]:
    resolved = resolve_cli_binary(binary)
    if not resolved:
        return 127, "", f"{binary} CLI not found"
    full = _SYSTEM_PROMPT + "\n\n" + payload
    cmd = [resolved, "exec", full]
    try:
        result = subprocess.run(                  # noqa: S603
            cmd, capture_output=True, text=True, check=False, timeout=timeout_seconds,
            env=cli_env(),
        )
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", "timed out"
    return result.returncode, result.stdout, result.stderr


_RUNNERS = {
    "claude": _run_claude,
    "codex": _run_codex,
}


def refine_prompt(
    image_source: bytes | str | Path | None,
    original_prompt: str,
    comments: str,
    *,
    backend: str = "claude",
    timeout_seconds: float = 180.0,
    claude_binary: str = "claude",
    codex_binary: str = "codex",
) -> RefineResult:
    """Critique an image+prompt with the LLM and return a refined prompt."""

    if not original_prompt.strip():
        raise ValueError("original_prompt is required")
    if not comments.strip():
        raise ValueError("comments is required")

    runner = _RUNNERS.get(backend)
    if runner is None:
        raise ValueError(f"Unsupported backend: {backend!r}. Use one of {sorted(_RUNNERS)}")

    image_path: Path | None = None
    created_temp = False
    try:
        if image_source is not None:
            image_path, created_temp = _save_image_source(image_source)
        # When no image was supplied the LLM still runs against prompt+comments.
        effective_path = image_path or Path("<no_image_provided>")
        payload = _build_user_payload(effective_path, original_prompt, comments)
        binary = claude_binary if backend == "claude" else codex_binary
        rc, stdout, stderr = runner(effective_path, payload, timeout_seconds, binary)
        if rc != 0:
            raise RuntimeError(
                f"{backend} exited {rc}. stderr (tail): {stderr.strip()[-400:]}"
            )

        data = _safe_load_json(stdout)
        if not isinstance(data, dict):
            return RefineResult(
                whole=original_prompt,
                rationale=(
                    f"{backend} did not return parseable JSON. "
                    "Showing the original prompt unchanged."
                ),
                raw=stdout,
                backend=backend,
            )

        delta = []
        for entry in data.get("delta") or []:
            if not isinstance(entry, dict):
                continue
            delta.append(
                RefineDelta(
                    action=str(entry.get("action") or "change"),
                    target=str(entry.get("target") or "other"),
                    text=str(entry.get("text") or "").strip(),
                )
            )

        whole = str(data.get("whole") or "").strip() or original_prompt
        rationale = str(data.get("rationale") or "").strip()
        return RefineResult(
            whole=whole, delta=delta, rationale=rationale, raw=stdout, backend=backend,
        )
    finally:
        if created_temp and image_path is not None:
            try:
                image_path.unlink()
            except OSError:
                pass
