"""Thread-safe in-process trace of the last LLM calls.

Lets the GUI show "what was actually fed to the backend" without changing the
proposer's call signature or adding return values everywhere. The proposer
pushes one :class:`LlmCall` per subprocess; the GUI reads the latest batch.

Trace is per-process and not persisted — the window of interest is "what just
happened" while debugging a single generation.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass(slots=True)
class LlmCall:
    """One subprocess LLM call: the prompt sent and the raw output returned."""

    backend: str                       # "claude" / "codex" / "heuristic" / ...
    binary: str                        # the resolved CLI binary used
    args: tuple[str, ...]              # extra CLI args (model, --effort, ...)
    direction: str                     # creative-direction tilt for this call
    prompt: str                        # the full prompt string fed via stdin / argv
    output: str                        # raw stdout returned by the LLM
    returncode: int                    # subprocess return code (0 = ok)
    elapsed_seconds: float             # wall-clock latency
    started_at: float = field(default_factory=time.time)


_LOCK = threading.Lock()
_RING: Deque[LlmCall] = deque(maxlen=16)


def reset() -> None:
    """Drop all captured calls. Call before a new generation."""

    with _LOCK:
        _RING.clear()


def record(call: LlmCall) -> None:
    """Append one call to the ring buffer (thread-safe)."""

    with _LOCK:
        _RING.append(call)


def recent() -> list[LlmCall]:
    """Snapshot of the ring buffer, most-recent last."""

    with _LOCK:
        return list(_RING)
