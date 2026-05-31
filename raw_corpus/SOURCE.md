# Reference corpus source

The CSVs in this directory are downloaded from [youmind.com](https://youmind.com) /
[YouMind OpenLab](https://github.com/YouMind-OpenLab), a public, free, open-source
prompt library curated by the YouMind community.

| File prefix | YouMind repo |
|---|---|
| `nano-banana-pro-prompts-*` | [awesome-nano-banana-pro-prompts](https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts) |
| `seedance-2-0-prompts-*` | [seedance-2-prompts-search-skill](https://github.com/YouMind-OpenLab/seedance-2-prompts-search-skill) |
| `grok-imagine-prompts-*` | YouMind OpenLab community library |

Prompt Genius uses these CSVs as a reference corpus for vocab mining, BM25
retrieval, and exemplar lookup. The catalog is derived from them, not a copy
of them. Original attribution stays with the YouMind authors via the
`author` and `sourceLink` columns of each row.

To refresh: download the latest CSVs from the YouMind repos above and drop
them in this directory. The app's File > Ingest CSV prompts dialog detects
the schema and merges only new rows.
