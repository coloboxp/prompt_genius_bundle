# Create and use a brand profile

A brand profile teaches the engine which words to prefer, which to avoid,
and how to score the result. Five minutes start to finish.

## 1. Open the manager

In the left panel, next to **Brand**, click **Manage…**. The Brand Profiles
dialog opens. It lists every profile in your per-user store
(`~/Library/Application Support/PromptGenius/brands/`).

> On a fresh install the list is empty. Click **New…** to start.

## 2. Fill the fields

Each field accepts comma- or newline-separated tags. The fields are tagged
verbatim onto the engine's retrieval intent, so write them the way you'd
want them to surface in the prompt:

| Field | Role |
|-------|------|
| **Name** | Display label in the picker. |
| **Tone** | Brand voice descriptors (`trustworthy`, `playful`, `premium`). |
| **Visual style** | Style cues (`modern`, `editorial`, `minimal`). |
| **Color palette** | Brand colors as words or hex (`deep blue`, `#f5a623`). |
| **Prefer** | Phrases that should appear in generated prompts. |
| **Avoid** | Phrases that must NOT appear — added to the negative prompt. |
| **Video rules** | Motion guidance (`slow stable motion`, `avoid flicker`). |

`id` is derived from the name; it stays stable across renames so cards
already saved keep linking to the right profile.

## 3. Save

Click **Save changes** (<kbd>⌘</kbd>+<kbd>S</kbd>). The dialog notices
unsaved edits and prompts you if you switch profiles without saving.

## 4. Make it the active profile

Select the profile in the list and click **Use selected**. The dialog
closes and the **Brand** label in the main window updates. To turn brand
guidance off entirely, click the **✕** button next to the brand label or
choose **Use (none)** in the manager.

## 5. Generate and score

Generate as usual. The right panel shows a **brand-fit** score (0–1) for the
selected card — a quick heuristic that counts how many of your *prefer*
tokens made it into the compiled prompt minus the *avoid* tokens that
slipped through.

## What this is, and what it isn't

Brand profiles are a soft pull, not a hard filter. The LLM is given them as
intent but can still produce off-brand wording — that's what the avoid list
and the negative prompt are for. For hard rules (no logos, no on-screen
text), keep them in the *Avoid* field so they go into the negative prompt.
