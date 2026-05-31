"""Brand profile manager dialog.

CRUD over the per-user brand profile store (``user_brands_dir()``). Each
profile is a JSON file matching :class:`BrandProfile`. Returns the selected
profile path on accept, or ``""`` if the user picked the (none) row.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from prompt_genius.core.brand import BrandProfile, load_brand_profile
from prompt_genius.core.resources import user_brands_dir


_TAG_FIELDS: list[tuple[str, str, str]] = [
    # (attribute, label, tooltip)
    ("tone", "Tone", "Brand tone descriptors — e.g. trustworthy, premium, playful. Comma- or newline-separated."),
    ("visual_style", "Visual style", "Visual style cues — e.g. modern, minimal, editorial. Comma- or newline-separated."),
    ("color_palette", "Color palette", "Brand colors as words or hex — e.g. deep blue, white, #f5a623."),
    ("prefer", "Prefer", "Phrases that should appear / be amplified in generated prompts."),
    ("avoid", "Avoid", "Phrases that must NOT appear — added to the negative prompt."),
    ("video_rules", "Video rules", "Motion guidance — e.g. slow stable motion, avoid flicker, preserve product."),
]


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"brand-{uuid.uuid4().hex[:6]}"


def _parse_tags(text: str) -> list[str]:
    """Split a tag editor blob on commas + newlines, trim, drop empties."""

    out: list[str] = []
    for chunk in re.split(r"[,\n]", text):
        token = chunk.strip()
        if token and token not in out:
            out.append(token)
    return out


def _format_tags(values: list[str]) -> str:
    return "\n".join(values)


class BrandManagerDialog(QDialog):
    """List + edit + new/duplicate/delete brand profiles."""

    def __init__(self, parent: QWidget | None, *, current_path: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle("Brand profiles")
        self.resize(820, 560)

        self._dir = user_brands_dir()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._current: BrandProfile | None = None
        self._current_path: Path | None = None
        # Per-profile editor widget cache for the currently-shown profile.
        self._editors: dict[str, QPlainTextEdit] = {}
        self._dirty = False

        self._selected_path: str = current_path  # filled on accept

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)

        # --- left: list + actions ---
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_layout.addWidget(QLabel("<b>Profiles</b>"))
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setToolTip(
            f"Brand profiles in {self._dir}.\n(none) generates without brand boosts."
        )
        self.list.currentItemChanged.connect(self._on_select)
        left_layout.addWidget(self.list, stretch=1)

        row = QHBoxLayout()
        new_btn = QPushButton("New…")
        new_btn.setToolTip("Create a new empty brand profile.")
        new_btn.clicked.connect(self._on_new)
        dup_btn = QPushButton("Duplicate")
        dup_btn.setToolTip("Clone the selected profile under a new name.")
        dup_btn.clicked.connect(self._on_duplicate)
        del_btn = QPushButton("Delete")
        del_btn.setToolTip("Delete the selected profile from disk. Can't be undone.")
        del_btn.clicked.connect(self._on_delete)
        for btn in (new_btn, dup_btn, del_btn):
            row.addWidget(btn)
        left_layout.addLayout(row)

        splitter.addWidget(left)

        # --- right: editor ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(8)

        self.title_label = QLabel("<i>Pick a profile on the left, or click New…</i>")
        right_layout.addWidget(self.title_label)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Internal display name")
        self.name_edit.setToolTip("Human-readable name shown in the picker.")
        self.name_edit.textChanged.connect(self._mark_dirty)
        form.addRow("Name", self.name_edit)

        self.id_label = QLabel("—")
        self.id_label.setStyleSheet("color: gray;")
        self.id_label.setToolTip("Stable identifier derived from the name; persists across renames.")
        form.addRow("id", self.id_label)

        right_layout.addLayout(form)

        for attr, label, tooltip in _TAG_FIELDS:
            section = QLabel(f"<b>{label}</b>")
            section.setToolTip(tooltip)
            right_layout.addWidget(section)
            editor = QPlainTextEdit()
            editor.setPlaceholderText(
                f"One per line, or comma-separated.\n{tooltip}"
            )
            editor.setToolTip(tooltip)
            editor.setMaximumHeight(72)
            editor.textChanged.connect(self._mark_dirty)
            self._editors[attr] = editor
            right_layout.addWidget(editor)

        right_layout.addStretch(1)
        splitter.addWidget(right)
        splitter.setSizes([240, 580])
        root.addWidget(splitter, stretch=1)

        # --- buttons ---
        save_btn = QPushButton("Save changes")
        save_btn.setToolTip("Write edits to disk. ⌘S")
        save_btn.setShortcut("Ctrl+S")
        save_btn.clicked.connect(self._on_save_current)

        none_btn = QPushButton("Use (none)")
        none_btn.setToolTip("Close and clear the active brand profile for generation.")
        none_btn.clicked.connect(self._on_use_none)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Use selected")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setToolTip(
            "Close and use the selected profile for generation."
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(save_btn)
        bottom.addWidget(none_btn)
        bottom.addStretch(1)
        bottom.addWidget(buttons)
        root.addLayout(bottom)

        self._reload_list(prefer_path=current_path)

    # ------------------------------------------------------------------ data

    def _reload_list(self, *, prefer_path: str = "") -> None:
        self.list.blockSignals(True)
        self.list.clear()
        files = sorted(self._dir.glob("*.json"))
        preferred_row = 0
        for index, path in enumerate(files):
            try:
                profile = load_brand_profile(path)
                label = f"{profile.name}  ·  {path.name}"
            except (OSError, ValueError, KeyError):
                label = f"(unreadable) {path.name}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.list.addItem(item)
            if prefer_path and Path(prefer_path) == path:
                preferred_row = index
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(preferred_row)
        else:
            self._show_blank()

    def _show_blank(self) -> None:
        self._current = None
        self._current_path = None
        self.title_label.setText("<i>No profiles yet — click <b>New…</b> to create one.</i>")
        self.name_edit.blockSignals(True)
        self.name_edit.clear()
        self.name_edit.blockSignals(False)
        self.id_label.setText("—")
        for editor in self._editors.values():
            editor.blockSignals(True)
            editor.clear()
            editor.blockSignals(False)
        self._dirty = False

    def _on_select(self, current: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if not self._maybe_save_pending():
            # Re-select the previous row if the user cancelled.
            return
        if current is None:
            self._show_blank()
            return
        path = Path(current.data(Qt.ItemDataRole.UserRole))
        try:
            profile = load_brand_profile(path)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Brand", f"Couldn't read {path.name}: {exc}")
            return
        self._current = profile
        self._current_path = path
        self.title_label.setText(f"<b>{profile.name}</b>  <span style='color:gray'>· {path.name}</span>")
        self.name_edit.blockSignals(True)
        self.name_edit.setText(profile.name)
        self.name_edit.blockSignals(False)
        self.id_label.setText(profile.id)
        for attr, editor in self._editors.items():
            editor.blockSignals(True)
            editor.setPlainText(_format_tags(getattr(profile, attr, []) or []))
            editor.blockSignals(False)
        self._dirty = False

    def _mark_dirty(self) -> None:
        if self._current is not None:
            self._dirty = True

    def _collect_profile_from_form(self) -> BrandProfile:
        name = self.name_edit.text().strip() or "Untitled brand"
        ident = self._current.id if self._current else _slugify(name)
        kwargs = {attr: _parse_tags(self._editors[attr].toPlainText()) for attr, _, _ in _TAG_FIELDS}
        return BrandProfile(
            id=ident,
            name=name,
            tone=kwargs["tone"],
            visual_style=kwargs["visual_style"],
            color_palette=kwargs["color_palette"],
            prefer=kwargs["prefer"],
            avoid=kwargs["avoid"],
            video_rules=kwargs["video_rules"],
            status="active",
            version="1.0",
        )

    def _profile_to_dict(self, profile: BrandProfile) -> dict:
        return {
            "id": profile.id,
            "name": profile.name,
            "tone": profile.tone,
            "visual_style": profile.visual_style,
            "color_palette": profile.color_palette,
            "prefer": profile.prefer,
            "avoid": profile.avoid,
            "video_rules": profile.video_rules,
            "status": profile.status,
            "version": profile.version,
        }

    def _maybe_save_pending(self) -> bool:
        """If there are unsaved edits, ask before discarding. Return False = cancel."""

        if not self._dirty or self._current is None or self._current_path is None:
            return True
        result = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes to {self._current.name}?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if result == QMessageBox.StandardButton.Save:
            self._on_save_current()
        elif result == QMessageBox.StandardButton.Cancel:
            return False
        self._dirty = False
        return True

    # --------------------------------------------------------------- actions

    def _on_new(self) -> None:
        if not self._maybe_save_pending():
            return
        name, ok = QInputDialog.getText(self, "New brand profile", "Name:")
        if not ok or not name.strip():
            return
        slug = _slugify(name.strip())
        path = self._dir / f"{slug}.json"
        if path.exists():
            QMessageBox.warning(self, "Brand", f"{path.name} already exists.")
            return
        profile = BrandProfile(id=slug, name=name.strip(), status="active", version="1.0")
        path.write_text(json.dumps(self._profile_to_dict(profile), indent=2) + "\n", encoding="utf-8")
        self._reload_list(prefer_path=str(path))

    def _on_duplicate(self) -> None:
        if self._current is None or self._current_path is None:
            QMessageBox.information(self, "Brand", "Pick a profile to duplicate first.")
            return
        if not self._maybe_save_pending():
            return
        new_name, ok = QInputDialog.getText(
            self, "Duplicate brand profile", "New name:",
            text=f"{self._current.name} (copy)",
        )
        if not ok or not new_name.strip():
            return
        slug = _slugify(new_name.strip())
        target = self._dir / f"{slug}.json"
        if target.exists():
            QMessageBox.warning(self, "Brand", f"{target.name} already exists.")
            return
        clone = BrandProfile(
            id=slug, name=new_name.strip(),
            tone=list(self._current.tone),
            visual_style=list(self._current.visual_style),
            color_palette=list(self._current.color_palette),
            prefer=list(self._current.prefer),
            avoid=list(self._current.avoid),
            video_rules=list(self._current.video_rules),
            status="active", version="1.0",
        )
        target.write_text(json.dumps(self._profile_to_dict(clone), indent=2) + "\n", encoding="utf-8")
        self._reload_list(prefer_path=str(target))

    def _on_delete(self) -> None:
        if self._current is None or self._current_path is None:
            return
        result = QMessageBox.question(
            self,
            "Delete brand profile",
            f"Delete {self._current.name} ({self._current_path.name})? This can't be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        try:
            self._current_path.unlink()
        except OSError as exc:
            QMessageBox.warning(self, "Brand", f"Couldn't delete: {exc}")
            return
        self._dirty = False
        self._reload_list()

    def _on_save_current(self) -> None:
        if self._current is None or self._current_path is None:
            return
        profile = self._collect_profile_from_form()
        try:
            self._current_path.write_text(
                json.dumps(self._profile_to_dict(profile), indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.warning(self, "Brand", f"Couldn't save: {exc}")
            return
        self._current = profile
        self._dirty = False
        self.title_label.setText(
            f"<b>{profile.name}</b>  <span style='color:gray'>· {self._current_path.name}</span>",
        )
        # Update list label after rename.
        row = self.list.currentRow()
        if row >= 0:
            item = self.list.item(row)
            item.setText(f"{profile.name}  ·  {self._current_path.name}")

    # ------------------------------------------------------------- accept

    def _on_accept(self) -> None:
        if not self._maybe_save_pending():
            return
        if self._current_path is None:
            self._selected_path = ""
        else:
            self._selected_path = str(self._current_path)
        self.accept()

    def _on_use_none(self) -> None:
        if not self._maybe_save_pending():
            return
        self._selected_path = ""
        self.accept()

    # ---------------------------------------------------------- public api

    def selected_path(self) -> str:
        return self._selected_path
