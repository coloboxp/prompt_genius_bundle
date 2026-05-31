"""Verify the core stays GUI-agnostic.

A Qt (PySide6) GUI must be able to import from ``prompt_genius.core`` and
wire it to widgets without changing any core code. Uses AST analysis to avoid
matching docstring or comment text that *describes* the rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_FORBIDDEN_IMPORTS = {"typer", "argparse", "click"}
_FORBIDDEN_ATTRIBUTES = {
    ("sys", "stdin"),
    ("sys", "stdout"),
    ("os", "environ"),
}
_FORBIDDEN_BUILTIN_CALLS = {"print", "input"}


@pytest.fixture()
def core_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / "prompt_genius" / "core").rglob("*.py"))


# resources.py is platform-conventions lookup — XDG / APPDATA / Library paths
# are inherently env-driven. It's still pure: no stdin/stdout, no print, no CLI.
_ENV_OK_FILES: frozenset[str] = frozenset({"resources.py"})


def test_core_has_no_cli_imports_or_io(core_files: list[Path]) -> None:
    offenders: list[str] = []
    for path in core_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for issue in _scan(tree, path.name):
            if path.name in _ENV_OK_FILES and "os.environ" in issue:
                continue
            offenders.append(issue)
    assert not offenders, "Core must stay GUI-agnostic:\n" + "\n".join(offenders)


def _scan(tree: ast.AST, filename: str) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _FORBIDDEN_IMPORTS:
                    out.append(f"{filename}:{node.lineno}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _FORBIDDEN_IMPORTS:
                out.append(f"{filename}:{node.lineno}: forbidden import from {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_BUILTIN_CALLS:
                out.append(f"{filename}:{node.lineno}: forbidden call {node.func.id}()")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            pair = (node.value.id, node.attr)
            if pair in _FORBIDDEN_ATTRIBUTES:
                out.append(
                    f"{filename}:{node.lineno}: forbidden attribute {pair[0]}.{pair[1]}"
                )
    return out
