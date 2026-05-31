# Claude CLI task: normalize first catalog batch

Use the audit results in `audit/` to normalize a first active catalog batch from `raw_corpus/`.

## Goal

Create 100 to 300 high-quality catalog items from the two source CSVs (`raw_corpus/nano-banana-pro-prompts-20260324.csv` and `raw_corpus/seedance-2-0-prompts-20260324.csv`).

Target split for the first batch:

- ~60% derived from Nano Banana Pro rows → static image / image editing patterns
- ~40% derived from Seedance 2.0 rows → text-to-video, image-to-video, motion, and shot patterns

## Instructions

1. Read `audit/proposed_taxonomy.md` and `schemas/catalog-item.schema.json`.
2. Select the strongest source rows (high-quality `content`, clear structure, non-duplicate, English or translatable).
3. For each selected row, decompose `content` into reusable patterns: style, camera, lighting, composition, motion, shot, negative.
4. Preserve provenance: copy the source `id`, `sourceLink`, `author.name`, and CSV file name into the catalog item under `source.csv_id`, `source.url`, `source.author`, `source.file`.
5. Add tags drawn from `title` and `description`.
6. Add `applies_to` and `not_recommended_for` based on the **mode**, not the source model. The catalog item should be reusable across any adapter that supports that mode:
   - Patterns derived from Nano Banana Pro rows usually fit `[static_image, image_editing]` — also reusable by Firefly / ChatGPT image / Midjourney adapters.
   - Patterns derived from Seedance rows usually fit `[text_to_video, image_to_video, storyboard]` — also reusable by Runway / Kling / Sora / Veo adapters.
7. Add `compatible_with` and `avoid_with`.
8. Add `prompt_fragments`:
   - **Always include `generic`** as a model-neutral instruction. This is the default the system will use.
   - Only add a per-adapter fragment (`nano_banana_pro`, `seedance_2_0`, `firefly`, `chatgpt_image`, `runway`, `midjourney`, …) when the model truly needs different phrasing or grammar (e.g. Seedance shot-timing `（0-Xs）`, Midjourney `--ar`/`--no` flags). Never paraphrase `generic` into per-model fragments — that bakes in unverified bias.
9. For Chinese-language Seedance prompts, always store an English translation in `prompt_fragments.generic`. Keep the original Chinese under `prompt_fragments.seedance_2_0` only if it materially differs from a literal translation.
10. Set `status` to `draft` unless the item is clearly ready.
11. Run `scripts/validate_catalog.py catalog/` after writing.

## Output

Create:

- `catalog/styles/`
- `catalog/camera/`
- `catalog/lighting/`
- `catalog/composition/`
- `catalog/motion/`
- `catalog/shots/`
- `catalog/negative/`
- `catalog/tasks/`
- `catalog/normalization_report.md`

## Rules

- Do not normalize low-quality duplicates.
- Do not overwrite the source CSVs.
- Do not invent unsupported settings for Nano Banana Pro or Seedance.
- If unsure, mark the item as `draft` and add `notes`.
- Keep source attribution on every item.
