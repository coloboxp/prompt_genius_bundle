#!/usr/bin/env python3
"""Convert ``docs/help/`` (Markdown source) into ``PromptGenius.help/`` —
a fully-formed Apple Help Book ready to ship in the .app's Resources/.

Bundle structure produced::

    packaging/build/PromptGenius.help/
        Contents/
            Info.plist
            Resources/
                English.lproj/
                    index.html              # table of contents
                    tutorials/*.html
                    how-to/*.html
                    reference/*.html
                    explanation/*.html
                    css/help.css
                    Help.helpindex          # built by Apple's hiutil

Registered in Info.plist of the main .app via:
    CFBundleHelpBookFolder  = PromptGenius.help
    CFBundleHelpBookName    = com.innovatrics.promptgenius.help
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import markdown as _md
except ImportError:
    print(
        "FATAL: the `markdown` package is required to build the Help Book.\n"
        "Install with: pip install markdown",
        file=sys.stderr,
    )
    sys.exit(2)


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "help"
OUT_ROOT = ROOT / "packaging" / "build" / "PromptGenius.help"
RES = OUT_ROOT / "Contents" / "Resources"
LPROJ = RES / "English.lproj"

BOOK_NAME = "🦊 Prompt Genius Help"
BOOK_ID = "com.innovatrics.promptgenius.help"

SECTION_LABELS = {
    "tutorials": "Tutorials",
    "how-to": "How-to guides",
    "reference": "Reference",
    "explanation": "Explanation",
}


# --------------------------------------------------------- markdown → HTML --

_MD = _md.Markdown(
    extensions=["extra", "toc", "sane_lists", "tables", "fenced_code"],
    output_format="html5",
)


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title} — {book_name}</title>
<meta name="AppleTitle" content="{title}">
<meta name="AppleIcon" content="../shared/icon.png">
<meta name="description" content="{description}">
<link rel="stylesheet" href="{css_href}">
</head>
<body>
<main>
<header class="bread"><a href="{home_href}">{book_name}</a> &rsaquo; {section_label}</header>
<a name="{anchor}"></a>
{body}
<footer class="nav">
<span>{section_label}</span>
<a href="{home_href}">&larr; Back to index</a>
</footer>
</main>
</body>
</html>
"""

INDEX_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{book_name}</title>
<meta name="AppleTitle" content="{book_name}">
<link rel="stylesheet" href="css/help.css">
</head>
<body>
<main>
<h1>{book_name}</h1>
<p class="lede">Internal documentation for the Prompt Genius workbench. Organised
as <a href="https://diataxis.fr/">Diátaxis</a> — pick by the kind of need
you have right now.</p>

<div class="diataxis-grid">
{sections_html}
</div>

<hr>
<p style="color:var(--muted); font-size:12px">
Press <kbd>⌘?</kbd> any time to reopen this help. Search uses the macOS Help Viewer index.
</p>
</main>
</body>
</html>
"""


def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return base or "page"


def _extract_title(markdown_source: str, fallback: str) -> str:
    for line in markdown_source.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _extract_description(markdown_source: str) -> str:
    # First non-empty paragraph after the H1 — short summary for meta tags.
    after_h1 = False
    for line in markdown_source.splitlines():
        if line.startswith("# "):
            after_h1 = True
            continue
        if after_h1 and line.strip():
            text = re.sub(r"[*_`>]+", "", line).strip()
            return text[:160]
    return ""


def _render_page(
    *,
    md_path: Path,
    section: str,
    title: str,
    description: str,
    anchor: str,
    output: Path,
) -> None:
    body = _MD.reset().convert(md_path.read_text(encoding="utf-8"))
    html = PAGE_TEMPLATE.format(
        title=title,
        description=description.replace('"', "'"),
        book_name=BOOK_NAME,
        section_label=SECTION_LABELS.get(section, section.title()),
        css_href="../css/help.css",
        home_href="../index.html",
        anchor=anchor,
        body=body,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")


def _build_index(pages_by_section: dict[str, list[tuple[str, str, str]]]) -> str:
    """Render the per-section card grid for the help home page."""

    cards: list[str] = []
    blurbs = {
        "tutorials": "Learning-oriented — work through these end-to-end the first time you use a feature.",
        "how-to": "Task-oriented — short recipes you can follow when you already know what you want.",
        "reference": "Information-oriented — schemas, settings, shortcuts, file locations.",
        "explanation": "Understanding-oriented — the why behind the design, for deeper questions.",
    }
    for section, label in SECTION_LABELS.items():
        items = sorted(pages_by_section.get(section, []), key=lambda x: x[2])
        if not items:
            continue
        rows = "\n".join(
            f'<li><a href="{section}/{slug}.html">{title}</a></li>'
            for slug, title, _ in items
        )
        cards.append(
            f'<div class="card">'
            f'<h3>{label}</h3>'
            f'<p>{blurbs.get(section, "")}</p>'
            f'<ul>{rows}</ul>'
            f'</div>'
        )
    return "\n".join(cards)


# ------------------------------------------------------------- bundle bits --

INFO_PLIST = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleIdentifier</key>
    <string>{BOOK_ID}</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>{BOOK_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>BNDL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>HPDBookAccessPath</key>
    <string>index.html</string>
    <key>HPDBookIconPath</key>
    <string>shared/icon.png</string>
    <key>HPDBookIndexPath</key>
    <string>Help.helpindex</string>
    <key>HPDBookTitle</key>
    <string>{BOOK_NAME}</string>
    <key>HPDBookType</key>
    <string>3</string>
</dict>
</plist>
"""


def _run_hiutil(lproj: Path) -> bool:
    """Build the Apple Help Viewer search index next to the HTML pages."""

    hiutil = shutil.which("hiutil")
    if hiutil is None:
        print("WARN: `hiutil` not found — skipping Help.helpindex generation.")
        print("      Search will be limited but the Help Book is still usable.")
        return False
    index_path = lproj / "Help.helpindex"
    cmd = [hiutil, "-Cf", str(index_path), str(lproj)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"WARN: hiutil failed: {res.stderr.strip() or res.stdout.strip()}")
        return False
    return True


# --------------------------------------------------------------- build flow --

def build() -> Path:
    if not DOCS.is_dir():
        print(f"FATAL: missing docs source at {DOCS}", file=sys.stderr)
        sys.exit(2)

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    LPROJ.mkdir(parents=True)

    # Copy CSS into Resources/English.lproj/css/.
    css_target = LPROJ / "css"
    css_target.mkdir(parents=True, exist_ok=True)
    shutil.copy(DOCS / "_assets" / "help.css", css_target / "help.css")

    pages_by_section: dict[str, list[tuple[str, str, str]]] = {}
    total = 0
    for section in SECTION_LABELS:
        src_dir = DOCS / section
        if not src_dir.is_dir():
            continue
        for md_path in sorted(src_dir.glob("*.md")):
            slug = _slug(md_path.stem)
            md_source = md_path.read_text(encoding="utf-8")
            title = _extract_title(md_source, fallback=md_path.stem.replace("-", " ").title())
            description = _extract_description(md_source)
            html_path = LPROJ / section / f"{slug}.html"
            _render_page(
                md_path=md_path,
                section=section,
                title=title,
                description=description,
                anchor=slug,
                output=html_path,
            )
            pages_by_section.setdefault(section, []).append((slug, title, md_path.stem))
            total += 1

    # Top-level index.html.
    sections_html = _build_index(pages_by_section)
    index_path = LPROJ / "index.html"
    index_path.write_text(
        INDEX_TEMPLATE.format(book_name=BOOK_NAME, sections_html=sections_html),
        encoding="utf-8",
    )

    # Info.plist for the .help bundle itself.
    (OUT_ROOT / "Contents").mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "Contents" / "Info.plist").write_text(INFO_PLIST, encoding="utf-8")

    # Apple search index.
    _run_hiutil(LPROJ)

    print(f"[help] built {total} pages → {OUT_ROOT}")
    return OUT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the PromptGenius.help bundle.")
    parser.parse_args()
    build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
