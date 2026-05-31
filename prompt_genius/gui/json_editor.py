"""Editable structured-JSON tree for prompt cards.

Built on the canonical PySide6 model/view pattern:
  * ``QStandardItemModel`` holds the key / value tree.
  * ``QTreeView`` renders it.
  * ``JsonValueDelegate`` swaps the editor per-row based on value type and
    on a per-key vocabulary harvested from the catalog (e.g. ``camera_motion``
    cells get a combo of every camera-motion value any catalog item uses).

When the user edits a cell, the tree's data is reassembled into a dict and the
``card_changed`` signal fires with the new card dict so the host window can
re-render the compiled prompt.
"""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHeaderView,
    QLineEdit,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

# Custom Qt roles for storing per-item metadata that the delegate consults.
_KEY_PATH_ROLE = Qt.ItemDataRole.UserRole + 1
_VALUE_TYPE_ROLE = Qt.ItemDataRole.UserRole + 2


def build_catalog_vocab(catalog) -> dict[str, list[str]]:
    """Harvest per-key value sets from every catalog item's ``parameters``."""

    raw: dict[str, set[str]] = {}
    for item in catalog.items.values():
        for key, value in (item.parameters or {}).items():
            if isinstance(value, str) and value.strip():
                raw.setdefault(key, set()).add(value.strip())
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, str) and v.strip():
                        raw.setdefault(key, set()).add(v.strip())
    return {key: sorted(values) for key, values in raw.items() if len(values) > 1}


def build_full_vocab(
    catalog,
    corpus_dir: str | None = "raw_corpus",
    *,
    per_category_cap: int = 40,
) -> dict[str, list[str]]:
    """Catalog vocab + corpus-mined vocab merged, sorted by corpus frequency."""

    catalog_vocab = build_catalog_vocab(catalog) if catalog is not None else {}
    if not corpus_dir:
        return catalog_vocab
    try:
        from prompt_genius.core.vocab import load_or_build_vocab, merge_vocab_lists

        corpus_vocab = load_or_build_vocab(corpus_dir)
        return merge_vocab_lists(catalog_vocab, corpus_vocab, per_category_cap=per_category_cap)
    except Exception:  # noqa: BLE001 — corpus is optional
        return catalog_vocab


# Default vocabularies for adapter-level params (fallback when catalog is thin).
_FALLBACK_VOCAB: dict[str, list[str]] = {
    "aspect_ratio": ["1:1", "4:5", "3:2", "16:9", "9:16", "21:9"],
    "camera_motion": [
        "static", "slow push-in", "slow pull-back", "dolly left",
        "dolly right", "orbit", "handheld",
    ],
    "subject_motion": ["none", "subtle", "medium", "dynamic"],
    "pacing": ["calm", "medium", "fast", "dramatic"],
    "lens": ["24mm", "35mm", "50mm", "85mm", "macro"],
    "depth_of_field": ["very shallow", "shallow", "medium", "deep"],
    "framing": ["close-up", "portrait", "medium", "wide", "environmental"],
    "lighting": [
        "soft studio", "natural window", "golden hour",
        "dramatic low-key", "overcast",
    ],
    "shadow_style": ["soft", "clean soft shadows", "hard", "high-contrast"],
    "contrast": ["low", "medium-low", "medium", "high"],
    "transition": ["match_cut", "fade", "camera_move"],
}


class JsonValueDelegate(QStyledItemDelegate):
    """Picks an editor per cell based on the value type and the key vocab."""

    def __init__(self, vocab: dict[str, list[str]], parent=None) -> None:
        super().__init__(parent)
        self._vocab = dict(vocab)
        # Layer the fallbacks underneath so adapter-level params always get a combo.
        for key, values in _FALLBACK_VOCAB.items():
            self._vocab.setdefault(key, values)

    # -------------------------------------------------------- editor lifecycle

    def createEditor(  # noqa: N802 — Qt API
        self,
        parent: QWidget,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> QWidget:
        key = self._leaf_key(index)
        value_type = index.data(_VALUE_TYPE_ROLE) or "str"

        if value_type == "bool":
            combo = QComboBox(parent)
            combo.addItems(["true", "false"])
            return combo
        if value_type == "int":
            spin = QSpinBox(parent)
            spin.setRange(-1_000_000, 1_000_000)
            return spin
        if value_type == "float":
            spin = QDoubleSpinBox(parent)
            spin.setRange(-1_000_000.0, 1_000_000.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.05)
            return spin
        if key and key in self._vocab:
            combo = QComboBox(parent)
            combo.setEditable(True)  # let designers add a fresh value
            combo.addItems(self._vocab[key])
            return combo
        return QLineEdit(parent)

    def setEditorData(  # noqa: N802 — Qt API
        self, editor: QWidget, index: QModelIndex,
    ) -> None:
        raw_value = index.model().data(index, Qt.ItemDataRole.EditRole)
        value_type = index.data(_VALUE_TYPE_ROLE) or "str"
        if isinstance(editor, QSpinBox):
            editor.setValue(_as_int(raw_value))
        elif isinstance(editor, QDoubleSpinBox):
            editor.setValue(_as_float(raw_value))
        elif isinstance(editor, QComboBox):
            text = "true" if raw_value is True else ("false" if raw_value is False else str(raw_value))
            idx = editor.findText(text)
            if idx >= 0:
                editor.setCurrentIndex(idx)
            else:
                editor.setEditText(text)
        elif isinstance(editor, QLineEdit):
            editor.setText("" if raw_value is None else str(raw_value))

    def setModelData(  # noqa: N802 — Qt API
        self, editor: QWidget, model, index: QModelIndex,
    ) -> None:
        value_type = index.data(_VALUE_TYPE_ROLE) or "str"
        if isinstance(editor, QSpinBox):
            new = editor.value()
        elif isinstance(editor, QDoubleSpinBox):
            new = editor.value()
        elif isinstance(editor, QComboBox):
            text = editor.currentText()
            if value_type == "bool":
                new = text.lower() == "true"
            else:
                new = text
        else:
            new = editor.text()
        model.setData(index, new, Qt.ItemDataRole.EditRole)

    # --------------------------------------------------------------- helpers

    def _leaf_key(self, index: QModelIndex) -> str | None:
        # column 0 = key, column 1 = value
        key_index = index.sibling(index.row(), 0)
        return key_index.data() if key_index.isValid() else None


class JsonTreeModel(QStandardItemModel):
    """Two-column key/value tree built from any JSON-like dict/list/scalar tree."""

    structure_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHorizontalHeaderLabels(["Field", "Value"])
        self.itemChanged.connect(self._on_item_changed)

    def populate(self, data: Any) -> None:
        self.removeRows(0, self.rowCount())
        root = self.invisibleRootItem()
        if isinstance(data, dict):
            for key, value in data.items():
                root.appendRow(self._make_row(str(key), value))
        elif isinstance(data, list):
            for index, value in enumerate(data):
                root.appendRow(self._make_row(f"[{index}]", value))
        else:
            root.appendRow(self._make_row("value", data))

    def to_dict(self) -> Any:
        return self._collect(self.invisibleRootItem())

    # -------------------------------------------------------------- internals

    def _make_row(self, key: str, value: Any) -> list[QStandardItem]:
        key_item = QStandardItem(key)
        key_item.setEditable(False)
        key_item.setData(_value_type(value), _VALUE_TYPE_ROLE)

        if isinstance(value, dict):
            value_item = QStandardItem("{…}")
            value_item.setEditable(False)
            for k, v in value.items():
                key_item.appendRow(self._make_row(str(k), v))
        elif isinstance(value, list):
            value_item = QStandardItem(f"[{len(value)}]")
            value_item.setEditable(False)
            for index, v in enumerate(value):
                key_item.appendRow(self._make_row(f"[{index}]", v))
        else:
            value_item = QStandardItem()
            value_item.setData(value, Qt.ItemDataRole.EditRole)
            value_item.setData(_value_type(value), _VALUE_TYPE_ROLE)
            value_item.setEditable(True)
        return [key_item, value_item]

    def _collect(self, parent: QStandardItem) -> Any:
        # Pure leaf: dict if first child looks like dict; list if [N] keys; else scalar.
        if parent.rowCount() == 0:
            return None
        first_key = parent.child(0, 0).text()
        is_list = first_key.startswith("[") and first_key.endswith("]")
        if is_list:
            out_list: list[Any] = []
            for row in range(parent.rowCount()):
                key_child = parent.child(row, 0)
                value_child = parent.child(row, 1)
                if key_child.hasChildren():
                    out_list.append(self._collect(key_child))
                else:
                    out_list.append(value_child.data(Qt.ItemDataRole.EditRole))
            return out_list
        out_dict: dict[str, Any] = {}
        for row in range(parent.rowCount()):
            key_child = parent.child(row, 0)
            value_child = parent.child(row, 1)
            key = key_child.text()
            if key_child.hasChildren():
                out_dict[key] = self._collect(key_child)
            else:
                out_dict[key] = value_child.data(Qt.ItemDataRole.EditRole)
        return out_dict

    def _on_item_changed(self, _item: QStandardItem) -> None:
        self.structure_changed.emit()


class StructuredCardEditor(QWidget):
    """Right-panel widget: structured editable tree + raw-JSON view.

    Emits :pyattr:`card_changed` whenever the user edits a value. The host
    window should re-run the compiler with the new ``structured`` field.
    """

    card_changed = Signal(dict)

    def __init__(self, catalog=None, parent=None) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._card: dict | None = None
        self._suspend_emit = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs, stretch=1)

        # --- Structured tab ---
        self.tree_view = QTreeView(self)
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setEditTriggers(
            QTreeView.EditTrigger.DoubleClicked
            | QTreeView.EditTrigger.SelectedClicked
            | QTreeView.EditTrigger.EditKeyPressed
        )
        self.tree_view.setUniformRowHeights(True)
        self.tree_view.setHeaderHidden(False)
        self.model = JsonTreeModel(self)
        self.tree_view.setModel(self.model)
        self.tree_view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._delegate = JsonValueDelegate(
            build_full_vocab(catalog) if catalog is not None else {},
            self,
        )
        self.tree_view.setItemDelegateForColumn(1, self._delegate)
        self.model.structure_changed.connect(self._on_model_edited)
        self.tabs.addTab(self.tree_view, "Structured")

        # --- Raw JSON tab ---
        self.raw_view = QTextEdit(self)
        self.raw_view.setReadOnly(True)
        mono = self.raw_view.font()
        mono.setFamily("Menlo")
        self.raw_view.setFont(mono)
        self.tabs.addTab(self.raw_view, "Raw JSON")

    # --------------------------------------------------------- public API

    def set_catalog(self, catalog) -> None:
        self._catalog = catalog
        self._delegate = JsonValueDelegate(
            build_full_vocab(catalog) if catalog is not None else {},
            self,
        )
        self.tree_view.setItemDelegateForColumn(1, self._delegate)

    def set_card(self, card: dict | None) -> None:
        self._card = card
        self._suspend_emit = True
        try:
            if card is None:
                self.model.removeRows(0, self.model.rowCount())
                self.raw_view.clear()
                return
            # Show only the editable structured/parameters payload, not the whole card.
            payload = card.get("structured", card)
            self.model.populate(payload)
            self.tree_view.expandToDepth(1)
            self._refresh_raw_view()
        finally:
            self._suspend_emit = False

    def current_card(self) -> dict | None:
        if self._card is None:
            return None
        edited = self.model.to_dict()
        new_card = dict(self._card)
        if "structured" in new_card:
            new_card["structured"] = edited
        else:
            new_card.update(edited if isinstance(edited, dict) else {})
        return new_card

    # ------------------------------------------------------------- internals

    def _on_model_edited(self) -> None:
        if self._suspend_emit:
            return
        card = self.current_card()
        if card is not None:
            self._refresh_raw_view()
            self.card_changed.emit(card)

    def _refresh_raw_view(self) -> None:
        if self._card is None:
            self.raw_view.clear()
            return
        try:
            text = json.dumps(self.current_card(), indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            text = json.dumps(self._card, indent=2, ensure_ascii=False)
        self.raw_view.setPlainText(text)


# --------------------------------------------------------------- value typing


def _value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, dict):
        return "dict"
    if isinstance(value, list):
        return "list"
    if value is None:
        return "null"
    return "str"


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
