"""core/refine.py — argument validation + safe error path.

The actual CLI calls are integration-only; this module's tests cover only the
pure-Python plumbing (invalid args, missing CLI fallback, type coercion).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from prompt_genius.core.refine import (
    RefineDelta,
    RefineResult,
    refine_prompt,
)


def test_blank_prompt_raises() -> None:
    with pytest.raises(ValueError):
        refine_prompt(None, "", "fix it", backend="claude")


def test_blank_comments_raises() -> None:
    with pytest.raises(ValueError):
        refine_prompt(None, "hero image", "", backend="claude")


def test_unknown_backend_raises() -> None:
    with pytest.raises(ValueError):
        refine_prompt(None, "hero image", "looks off", backend="invented")


def test_missing_image_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        refine_prompt(
            "/tmp/this/does/not/exist.png",
            "hero image", "looks off", backend="claude",
        )


def test_refine_result_serializes() -> None:
    res = RefineResult(
        whole="new prompt",
        delta=[RefineDelta(action="add", target="lighting", text="warmer golden hour")],
        rationale="warmer mood",
        backend="claude",
    )
    out = res.to_dict()
    assert out["whole"] == "new prompt"
    assert out["delta"][0]["action"] == "add"
    assert out["rationale"] == "warmer mood"
    assert out["backend"] == "claude"


@pytest.mark.skipif(
    shutil.which("claude") is None, reason="claude CLI not on PATH",
)
def test_runs_against_claude_when_available(tmp_path: Path) -> None:
    # Minimal end-to-end: tiny 1x1 PNG so the CLI has a real file.
    image = tmp_path / "tiny.png"
    image.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
        b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05"
        b"\xfe\x02\xfe\xa3*\x9eY\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    result = refine_prompt(
        image, "a tiny test pixel", "make it pop more", backend="claude",
        timeout_seconds=60.0,
    )
    assert isinstance(result, RefineResult)
    assert result.whole  # some refined text returned
