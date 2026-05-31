# Manage brand profiles

CRUD for the brand profile store. Profiles live in
`~/Library/Application Support/PromptGenius/brands/` and survive app
updates.

## Open the manager

Left panel → **Manage…** (next to **Brand**).

## Actions

| Button | What it does |
|--------|--------------|
| **New…** | Asks for a name, writes a fresh profile JSON. |
| **Duplicate** | Clones the selected profile under a new name. |
| **Delete** | Removes the file from disk. Cannot be undone. |
| **Save changes** (<kbd>⌘</kbd>+<kbd>S</kbd>) | Writes form edits back to the JSON. |
| **Use (none)** | Clears the active profile and closes the dialog. |
| **Use selected** | Sets the selected profile active and closes. |

Switching profiles or closing with unsaved edits prompts to save / discard
/ cancel.

## Field semantics

All tag-list fields (Tone, Visual style, Color palette, Prefer, Avoid,
Video rules) accept comma- or newline-separated tokens. Tokens are matched
case-insensitively against the compiled prompt for the brand-fit score and
fed verbatim into the engine's retrieval intent.

`id` is a slug of the name when the profile is first created. It does
**not** change when you rename — cards already in history keep linking to
the right profile.

## Where they're used

- **Generate** — adds *prefer* / *avoid* to the retrieval intent so matching
  catalog patterns get boosted (and conflicting ones penalised).
- **Compile** — `avoid` tokens go into the model's negative prompt.
- **Brand-fit score** — surface metric on each card.

## Editing files directly

The profile files are plain JSON in the same format as
`templates/brand-profile-template.json`. Editing them on disk while the
app is running is safe; the manager re-reads on selection. You'll need to
re-pick the active profile if you renamed its file.
