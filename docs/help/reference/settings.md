# Settings reference

Every tunable lives in `Config` (`prompt_genius/core/config.py`) and is
persisted to the user's config file (see
[file locations](file-locations.html)).

## `paths`

| Key | Default (source) | Default (bundled) | Purpose |
|-----|-----------------|-------------------|---------|
| `adapters_dir` | `examples/adapters` | bundled MEIPASS | Where adapter JSONs live. |
| `catalog_dir` | `catalog` | bundled MEIPASS | Curated catalog items. |
| `schemas_dir` | `schemas` | bundled MEIPASS | JSON schemas for validation. |
| `templates_dir` | `templates` | bundled MEIPASS | Sample brand / brief / card templates. |
| `history_dir` | `data/history` | `~/Library/Application Support/PromptGenius/history` | Saved cards. |
| `feedback_path` | `data/feedback.jsonl` | user-data dir | Feedback log. |
| `usage_path` | `data/usage.jsonl` | user-data dir | Usage events for quality scoring. |
| `versions_path` | `data/versions.jsonl` | user-data dir | Save-version log. |

## `llm`

| Key | Default | Purpose |
|-----|---------|---------|
| `backend` | `heuristic` | `heuristic` / `claude` / `codex` / `mlx` / `auto`. |
| `effort` | `low` | Reasoning effort tier. |
| `claude_model` | `opus` | Alias or model id. Empty = CLI default. |
| `claude_lean_flags` | `true` | Strip MCP / tools / slash. ~40% faster. |
| `codex_model` | `""` | Empty = CLI default. |
| `codex_lean_flags` | `true` | `--ephemeral --ignore-user-config …` |
| `timeout_seconds` | `180.0` | Per-subprocess hard cap. |
| `mlx_model` | `mlx-community/Llama-3.2-3B-Instruct-4bit` | HF model id. |
| `mlx_max_tokens` / `mlx_temperature` | `800` / `0.2` | MLX gen knobs. |
| `hf_token`, `hf_cache_dir` | `""` | HuggingFace creds + cache override. |

## `embeddings`

| Key | Default | Purpose |
|-----|---------|---------|
| `backend` | `dense` | `tfidf` / `bm25` / `dense` / `hybrid`. |
| `prefer_dense` | `true` | Legacy; honoured when backend == `tfidf`. |
| `model_name` | `all-MiniLM-L6-v2` | sentence-transformers model. |
| `cache_dir` | `.cache/embeddings` | Where dense vectors are cached. |
| `mmr_diversity` | `0.4` | 0 = pure relevance, 1 = pure diversity. |
| `per_type_limit` | `5` | Max items per catalog type returned. |
| `bm25_k1` / `bm25_b` | `1.5` / `0.75` | BM25 tuning. |
| `hybrid_rrf_k` | `60` | Reciprocal-rank-fusion k. |
| `prewarm_on_launch` | `true` | Warm the dense model on GUI startup. |

## `retrieval` (weights)

| Key | Default | Effect |
|-----|---------|--------|
| `tag_weight` | `3.0` | Boost for catalog tag matches. |
| `text_weight` | `2.0` | Boost for body-text matches. |
| `compatible_with_weight` | `1.0` | Boost for `compatible_with` graph hits. |
| `avoid_with_penalty` | `5.0` | Penalty for `avoid_with` graph hits. |
| `intent_avoid_penalty` | `5.0` | Penalty for intent.avoid token matches. |
| `cosine_weight` | `4.0` | Dense cosine similarity scale. |
| `brand_boost_weight` | `2.0` | Brand-token boost scale. |

## `video`

Defaults for video modes — apply when the adapter doesn't override.

| Key | Default |
|-----|---------|
| `single_shot_duration_seconds` | `6.0` |
| `storyboard_total_duration_seconds` | `15.0` |
| `keyframe_total_duration_seconds` | `6.0` |
| `default_shot_count` | `4` |
| `default_keyframe_count` | `3` |
| `default_aspect_ratio` | `16:9` |
| `default_camera_motion` | `slow push-in` |
| `default_subject_motion` | `subtle` |
| `default_pacing` | `calm` |
| `default_continuity` | `("preserve_subject",)` |
| `artifact_avoidance` | `("no warping", "no flicker", "no fake text", "no morphing")` |

## `quality` (weights)

Per-card score = weighted sum of curator review, positive feedback rate,
save / reuse / export rates, minus negative-rate penalty; decayed by
`half_life_days`.

## `gui`

| Key | Default | Purpose |
|-----|---------|---------|
| `theme` | `system` | `system` / `light` / `dark`. |
| `default_mode` | `static_image` | Initial Mode selection. |
| `default_target` | `generic` | Initial Target selection. |
| `default_n` | `5` | Initial # cards. |
| `default_risk` | `safe` | Initial Risk selection. |
| `brand_profile_path` | `""` | Currently-active profile path. |
| `allow_drafts` | `true` | Include catalog items with `status=draft`. |
| `show_advanced_settings` | `false` | Hide retrieval/quality/video knobs by default. |
