# TODO

## Packaging

- After the next clean build, inspect `dist/PromptGenius.app` for unrelated
  native packages and add PyInstaller excludes only for anything that still
  leaks in through hooks.
- Add a packaged-app smoke test that launches a copied `.app` from a temporary
  directory, waits for the main window, and verifies bundled catalog/adapters
  resolve after relocation.

## LLM CLI Integration

- Add a small Preferences action that shows the resolved `claude` and `codex`
  paths, so users can see exactly what the GUI will execute.
