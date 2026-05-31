# Why TOON

TOON = Token-Oriented Object Notation. A compact, human-readable
alternative to JSON aimed at LLM contexts.

## The problem

LLMs charge per token. JSON is verbose for the things you typically send
an LLM as context — quoted keys, repeated structure, `[`, `]`, `{`, `}`
all eat tokens. A modest 5KB card uses ~1500 tokens in JSON.

## What TOON does

YAML-like indentation for nesting, CSV-like tabular shorthand for arrays
of records. Same card in TOON:

```toon
mode: static_image
target_model: generic
selected_patterns[3]: lens-50mm,light-low-key,grain-leica
structured:
  creative_intent:
    subject: pianist
    mood[2]: contemplative,nostalgic
compiled:
  text: "Editorial portrait of a 60-year-old jazz pianist..."
  parameters:
    aspect_ratio: 3:2
    negative_prompt: no_warping,no_morphing
```

Round-trip with JSON is lossless. Token reduction is typically 30–60%
depending on shape — arrays of records (the most common LLM context
shape) compress the most.

## When to use it

- **You're feeding the card to another LLM** as context (e.g. a
  meta-prompt: "given these 5 cards, pick the best one"). TOON. Always.
- **You're piping the card to a downstream service** — JSON. Universal,
  standard, your service speaks it.
- **You're storing the card on disk** — JSON. TOON's compactness doesn't
  matter at rest; JSON tooling is everywhere.

## What it isn't

TOON is *not* a schema language. It's a serialisation format. Validate
your data with JSON Schema or a dataclass; encode for transport with
TOON.

## Installation

Bundled `.app` ships `python-toon` automatically. In source mode:

```
pip install python-toon
```

The **Copy TOON** button falls back to JSON (with a status-bar notice) if
the package isn't found.

## Further reading

- [TOON format spec & implementations](https://github.com/toon-format)
- The `python-toon` package (import name: `toon`) on PyPI.
