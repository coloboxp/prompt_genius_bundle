"""dmgbuild settings for PromptGenius-<version>.dmg.

Layout: 660×420 window, splash.png as backdrop, PromptGenius.app on the
left, Applications shortcut on the right, hidden top toolbar.

Run via packaging/build_dmg.sh — it picks up version/output paths from env.
"""

from __future__ import annotations

import os
from pathlib import Path


# --------------------------------------------------------------- paths --
# dmgbuild evaluates this file via exec(), so __file__ isn't defined.
# build_dmg.sh sets PG_ROOT before invoking dmgbuild; fall back to cwd
# (also the repo root in normal builds).
_ROOT = Path(os.environ.get("PG_ROOT", os.getcwd())).resolve()
_APP = Path(os.environ.get("PG_APP", _ROOT / "dist" / "PromptGenius.app"))
_BACKGROUND = Path(os.environ.get("PG_DMG_BG", _ROOT / "packaging" / "dmg_background.png"))
_ICON = _ROOT / "packaging" / "PromptGenius.icns"


# --------------------------------------------------------- dmgbuild keys --

# What goes inside the disk image. dmgbuild's "files" puts items at the
# root of the volume; "symlinks" adds an alias to /Applications so the
# user can drag from one to the other.
filename = os.environ.get("PG_DMG_OUTPUT", str(_ROOT / "dist" / "PromptGenius.dmg"))
volume_name = "🦊 Prompt Genius"
format = "UDZO"           # zlib-compressed; broadest compatibility.
size = None               # auto-size from contents.

files = [str(_APP)]
symlinks = {"Applications": "/Applications"}

# Volume icon (the icon Finder shows when the .dmg is mounted).
if _ICON.exists():
    icon = str(_ICON)

# Background image. If the rendered backdrop isn't available we fall back
# to no background — the layout still works, just visually plain.
if _BACKGROUND.exists():
    background = str(_BACKGROUND)

# Window geometry — tuned to a 660×420 backdrop. Coordinates are pixel
# offsets from the top-left of the *window*, not the screen.
window_rect = ((200, 200), (660, 420))
icon_size = 128
text_size = 13

icon_locations = {
    "PromptGenius.app": (160, 210),
    "Applications":      (500, 210),
}

# Hide the Finder window decorations that would distract from the drag-
# to-install motion.
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False

# Default view = icon view (the layout above only makes sense in icons).
default_view = "icon-view"
include_icon_view_settings = "auto"
include_list_view_settings = "auto"

# Open the window automatically when the user double-clicks the DMG.
auto_open = True
