# prompt_genius.core — Public API contract

This is the surface a GUI (Qt, web, anything) should depend on. The CLI is one consumer; it is not privileged.

## Rules

- Pure functions only. No `print`, no `input`, no `sys.stdin`/`stdout`, no `typer`/`argparse`/`click`, no `os.environ`.
- Every function returns either a dataclass from `models.py` or a plain `dict`/`list` tree.
- Paths and config come in as arguments, never read from the environment.
- Long-running calls accept `should_cancel: Callable[[], bool] | None = None` where it makes sense.

These rules are enforced by `tests/test_qt_readiness.py` (AST scan).

## Public surface

```python
from prompt_genius.core import (
    # Top-level facade — the main thing a GUI calls.
    generate_cards,

    # Building blocks (call directly if you want lower-level control).
    parse_brief,
    load_catalog, search,
    load_adapters, resolve_adapter, list_adapters,
    assemble, compile_prompt,
    validate_card,
    save_card, save_feedback,

    # Dataclasses.
    Intent, Match, StructuredPrompt, CompiledPrompt, PromptCard,
    Warning, ValidationError,
    Adapter, Catalog,
)
```

## Top-level facade

```python
generate_cards(
    brief_text: str,
    *,
    mode: str,                       # static_image | image_editing | text_to_video |
                                     # image_to_video | storyboard | keyframe
    target_model: str | None = None, # adapter id; None = "generic"
    n: int = 5,
    adapters_dir: str | Path = "examples/adapters",
    catalog_dir: str | Path = "catalog",
    allow_drafts: bool = True,
    risk_level: str = "safe",
    should_cancel: Callable[[], bool] | None = None,
) -> list[PromptCard]
```

A `PromptCard.structured` field is either a single `StructuredPrompt` (for single-shot modes) or a `list[StructuredPrompt]` (for `storyboard` / `keyframe`). The same applies to `compiled`.

## Wiring example (PySide6 sketch, not shipped)

```python
from PySide6.QtCore import QThread, Signal
from prompt_genius.core import generate_cards

class GenerateWorker(QThread):
    finished_cards = Signal(list)

    def __init__(self, brief, mode, target, n):
        super().__init__()
        self._args = (brief, mode, target, n)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        brief, mode, target, n = self._args
        cards = generate_cards(
            brief,
            mode=mode,
            target_model=target,
            n=n,
            should_cancel=lambda: self._cancel,
        )
        self.finished_cards.emit(cards)
```

## What you must not import in core

| Why blocked | What |
|---|---|
| CLI plumbing | `typer`, `argparse`, `click` |
| Terminal I/O | `print`, `input`, `sys.stdin`, `sys.stdout` |
| Implicit config | `os.environ` |

If you need any of those, add it in `prompt_genius/cli/` (or a future `prompt_genius/gui/`), not here.
