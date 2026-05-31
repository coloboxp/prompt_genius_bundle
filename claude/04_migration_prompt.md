# Claude CLI task: migration plan

Create a safe migration plan from the raw CSV corpus in `raw_corpus/` to the normalized Prompt Genius catalog under `catalog/`.

## Output

Create `audit/migration_plan.md` with:

1. Current source structure (two CSVs in `raw_corpus/`, columns `id,title,description,content,sourceLink,sourcePublishedAt,author,sourceMedia[,sourceReferenceImages,sourceVideos]`).
2. Proposed target structure (`catalog/styles/`, `catalog/camera/`, `catalog/lighting/`, `catalog/composition/`, `catalog/motion/`, `catalog/shots/`, `catalog/negative/`, `catalog/tasks/`).
3. Mapping from CSV row → catalog item type, per source file:
   - Nano Banana Pro → `style_pattern`, `camera_pattern`, `lighting_pattern`, `composition_pattern`, `negative_pattern`, `task_template`, `prompt_example`.
   - Seedance 2.0 → `motion_pattern`, `shot_pattern`, `transition_pattern`, `negative_pattern`, `task_template`, `prompt_example`.
4. Fields that can be migrated automatically: `id` → `source.csv_id`, `sourceLink` → `source.url`, `author.name` → `source.author`, CSV file → `source.file`, `title` → `name`.
5. Fields that require manual review: `content` decomposition into pattern parts; Chinese → English translation; quality_score assignment; `applies_to` / `not_recommended_for`.
6. High-risk migrations: long multi-shot Seedance prompts (risk: losing shot structure), Nano Banana Pro rows that mix multiple style families (risk: over-broad pattern), rows whose `content` contains another tool's syntax (risk: leaking unsupported settings into our adapters).
7. Suggested first batch: ~100 NBP items + ~50 Seedance items hand-picked from highest-confidence rows from `audit/`.
8. Rollback plan: catalog lives in Git; rollback = `git revert`. Source CSVs are never modified.
9. Validation plan: `scripts/validate_catalog.py catalog/` must pass before merge; `scripts/find_duplicates.py catalog/` report reviewed.
10. Review checklist (per batch): provenance present, no invented settings, draft vs active set deliberately, language handled, fragments present for the relevant target model.

## Rules

- Do not modify or delete the source CSVs.
- Do not rename source files.
- Keep `raw_corpus/` separate from `catalog/`.
- Make migration incremental and reviewable (one PR per ≤50 items).
- Prefer 100 to 300 high-quality active items before scaling further.
