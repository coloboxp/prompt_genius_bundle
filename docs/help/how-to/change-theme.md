# Switch theme

**View → System theme / Light / Dark.**

- **System** follows the macOS appearance — flips with Dark Mode.
- **Light** and **Dark** override regardless of macOS setting.

The choice persists across launches (stored in the per-user config at
`~/Library/Application Support/PromptGenius/config.json`).

## What changes

Only the Qt palette: window/base/text/button colors. The help book and the
splash art use their own contrast-aware styling.

## When system theme misbehaves

Qt's *System* palette doesn't always update live when you flip macOS
appearance. If it lags, switch to Light then back to System; or restart
the app.
