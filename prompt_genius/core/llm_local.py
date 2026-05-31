"""On-device LLM brief parser via mlx-lm (Apple Silicon).

Optional. Requires::

    pip install -e ".[mlx]"        # or: pip install mlx-lm huggingface_hub

Downloads the chosen model from Hugging Face on first use (honoring an HF token
if provided). Falls back to the heuristic parser when MLX or the model cannot
be loaded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prompt_genius.core.brief_parsers import (
    BriefParser,
    HeuristicBriefParser,
    _SYSTEM_PROMPT,
    _intent_from_data,
    _safe_load_json,
)
from prompt_genius.core.models import Intent


def ensure_huggingface_login(hf_token: str | None) -> None:
    """Authenticate with Hugging Face for the current process if a token is set."""

    if not hf_token:
        return
    try:
        from huggingface_hub import login  # type: ignore
    except ImportError:
        return
    try:
        login(token=hf_token, add_to_git_credential=False)
    except Exception:  # pragma: no cover — network/perm failures
        pass


@dataclass(slots=True)
class MlxBriefParser:
    """Parses briefs via a locally-loaded MLX language model."""

    model_name: str = "mlx-community/Llama-3.2-3B-Instruct-4bit"
    max_tokens: int = 800
    temperature: float = 0.2
    hf_token: str | None = None
    fallback: BriefParser | None = None
    _model: Any = None
    _tokenizer: Any = None

    def _load(self) -> bool:
        if self._model is not None:
            return True
        try:
            from mlx_lm import load  # type: ignore
        except ImportError:
            return False
        ensure_huggingface_login(self.hf_token)
        try:
            self._model, self._tokenizer = load(self.model_name)
        except Exception:  # pragma: no cover — disk / network failures
            return False
        return True

    def _fallback(self, brief_text: str) -> Intent:
        return (self.fallback or HeuristicBriefParser()).parse(brief_text)

    def parse(self, brief_text: str) -> Intent:
        if not self._load():
            return self._fallback(brief_text)
        try:
            from mlx_lm import generate  # type: ignore
        except ImportError:
            return self._fallback(brief_text)

        prompt = _SYSTEM_PROMPT + "\n" + brief_text + "\n\nJSON:\n"
        try:
            output = generate(
                self._model,
                self._tokenizer,
                prompt=prompt,
                max_tokens=self.max_tokens,
                temp=self.temperature,
                verbose=False,
            )
        except Exception:  # pragma: no cover — runtime model failure
            return self._fallback(brief_text)

        text = (output or "").strip()
        data = _safe_load_json(text)
        if not isinstance(data, dict):
            return self._fallback(brief_text)
        return _intent_from_data(brief_text, data)


def download_mlx_model(model_name: str, hf_token: str | None = None) -> str:
    """Eagerly fetch ``model_name`` from Hugging Face. Returns local path or ``""``."""

    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except ImportError:
        return ""
    ensure_huggingface_login(hf_token)
    try:
        return snapshot_download(repo_id=model_name, token=hf_token or None)
    except Exception:  # pragma: no cover
        return ""
