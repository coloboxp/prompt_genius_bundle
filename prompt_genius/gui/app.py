"""Three-panel PySide6 GUI for Prompt Genius.

Left: brief + mode + target + brand + fine-tune.
Middle: prompt cards + history.
Right: rendered prompt + JSON + feedback + brand-fit + export.

All long-running work runs on a QThread worker; cancel + reactive UI throughout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QAction, QKeySequence, QPalette, QColor, QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QButtonGroup,
        QCheckBox,
        QComboBox,
        QDialog,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMenu,
        QMessageBox,
        QPlainTextEdit,
        QPushButton,
        QRadioButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QSplashScreen,
        QSplitter,
        QStatusBar,
        QTabWidget,
        QTextEdit,
        QToolBar,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PySide6 is not installed. Install the GUI extra: pip install -e \".[gui]\""
    ) from exc

from prompt_genius.core.adapters import list_adapters, load_adapters
from prompt_genius.core.brand import brand_fit_score, load_brand_profile
from prompt_genius.core.config import Config, ConfigSaveError, load_or_init, default_config_path
from prompt_genius.core.export import export_card
from prompt_genius.core.storage import save_card, save_feedback
from prompt_genius.core.usage import record_usage
from prompt_genius.core.versioning import save_version

from prompt_genius.core.adapters import resolve_adapter
from prompt_genius.core.catalog import load_catalog
from prompt_genius.core.compiler import compile_prompt
from prompt_genius.core.models import StructuredPrompt, to_dict as _model_to_dict
from prompt_genius.gui.ingest_dialog import IngestDialog
from prompt_genius.gui.json_editor import StructuredCardEditor, build_full_vocab
from prompt_genius.gui.refine_dialog import RefineDialog
from prompt_genius.gui.settings_dialog import SettingsDialog
from prompt_genius.gui.worker import GenerateWorker, IndexPrewarmWorker

_MODES = [
    "static_image",
    "image_editing",
    "text_to_video",
    "image_to_video",
    "storyboard",
    "keyframe",
]
_MODE_LABELS = {
    "static_image": "Static image",
    "image_editing": "Image edit",
    "text_to_video": "Text → video",
    "image_to_video": "Image → video",
    "storyboard": "Storyboard (scene-by-scene)",
    "keyframe": "Keyframes (start / mid / end)",
}
_MODE_EXAMPLES: dict[str, str] = {
    "static_image": (
        "Editorial portrait of a 60-year-old jazz pianist mid-performance — "
        "backlit, deep blue stage haze, warm bokeh, Leica grain, hands in focus."
    ),
    "image_editing": (
        "Restore this 1960s wedding photo to gallery-grade print quality. "
        "Repair the torn upper-left corner, deepen the blacks, keep skin tones "
        "honest. No over-smoothing or face reconstruction."
    ),
    "text_to_video": (
        "6-second seamless loop: one slow drop of water hitting an espresso "
        "crema, top-down macro, golden rim light, crema swirls then settles. "
        "Cinematic, no text, no chrome."
    ),
    "image_to_video": (
        "Animate this poster into a 4-second loop: subtle parallax on the "
        "foreground figure, slow drift on the background neon, gentle film "
        "grain. Preserve typography exactly."
    ),
    "storyboard": (
        "12-second product spot for noise-cancelling headphones. Open on a "
        "chaotic Tokyo subway, hands lift headphones to ears, world goes "
        "silent and color-graded teal, close on the product against black."
    ),
    "keyframe": (
        "3-frame ad for a hybrid road bike: start with the bike against a "
        "city skyline at dawn, mid push-in on the carbon dropouts, end on "
        "the rider's silhouette cresting a hill against orange sky."
    ),
}
_RATINGS = [
    "good", "bad", "too_generic", "off_brand", "wrong_style",
    "motion_too_fast", "motion_too_boring", "video_likely_unstable",
]
_RATING_LABELS = {
    "good": "👍 good",
    "bad": "👎 bad",
    "too_generic": "too generic",
    "off_brand": "off brand",
    "wrong_style": "wrong style",
    "motion_too_fast": "motion too fast",
    "motion_too_boring": "motion too boring",
    "video_likely_unstable": "video likely unstable",
}


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        config: Config | None = None,
        adapters_dir: Path | None = None,
        catalog_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("🦊 Prompt Genius")
        self.resize(1480, 900)

        self._config = config or load_or_init()
        # Resolve from config if not explicitly overridden
        self._adapters_dir = adapters_dir or Path(self._config.paths.adapters_dir)
        self._catalog_dir = catalog_dir or Path(self._config.paths.catalog_dir)

        self._cards: list[dict[str, Any]] = []
        self._worker: GenerateWorker | None = None

        self.setStatusBar(QStatusBar(self))
        self._build_menu_and_toolbar()
        self._build_central()
        self._apply_theme()
        self._load_history_into_panel()
        self._prewarm_worker: IndexPrewarmWorker | None = None
        QTimer.singleShot(0, self._first_run_check)

        # Build the prewarm worker now so main() can connect to its signals
        # before kicking it off; actually start it on the next event-loop tick.
        if getattr(self._config.embeddings, "prewarm_on_launch", True):
            self._prewarm_worker = IndexPrewarmWorker(self, self._config)
            backend = self._config.embeddings.backend
            self.statusBar().showMessage(
                f"Warming {backend} retrieval index… "
                "(Generate is available while this runs)",
                0,
            )
            self._prewarm_worker.ready.connect(self._on_prewarm_ready)
            self._prewarm_worker.failed.connect(self._on_prewarm_failed)
            QTimer.singleShot(50, self._prewarm_worker.start)

    def _on_prewarm_ready(self, stats: dict) -> None:
        self.statusBar().showMessage(
            f"Retrieval ready: {stats['backend']} · {stats['items']} catalog items "
            f"({stats['elapsed']:.1f}s)",
            10_000,
        )

    def _on_prewarm_failed(self, msg: str) -> None:
        self.statusBar().showMessage(f"Retrieval prewarm failed: {msg}", 12_000)

    def _on_rebuild_indexes(self) -> None:
        """Pre-warm catalog/corpus/vocab caches on a background thread."""

        from PySide6.QtCore import QThread, Signal
        from PySide6.QtWidgets import QProgressDialog

        class _Worker(QThread):
            done = Signal(dict)
            failed = Signal(str)

            def __init__(self, parent, cfg) -> None:
                super().__init__(parent)
                self._cfg = cfg

            def run(self) -> None:
                try:
                    import time
                    from prompt_genius.core.catalog import load_catalog
                    from prompt_genius.core.corpus import load_or_build_corpus_index
                    from prompt_genius.core.vocab import load_or_build_vocab

                    timings: dict[str, float] = {}
                    t = time.time()
                    catalog = load_catalog(
                        self._cfg.paths.catalog_dir,
                        backend=self._cfg.embeddings.backend,
                        model_name=self._cfg.embeddings.model_name,
                        cache_dir=self._cfg.embeddings.cache_dir,
                    )
                    timings["catalog"] = time.time() - t
                    t = time.time()
                    corpus = load_or_build_corpus_index("raw_corpus", rebuild=True)
                    timings["corpus"] = time.time() - t
                    t = time.time()
                    vocab = load_or_build_vocab("raw_corpus", rebuild=True)
                    timings["vocab"] = time.time() - t
                    self.done.emit({
                        "timings": timings,
                        "catalog_items": len(catalog.items),
                        "corpus_rows": len(corpus),
                        "vocab_categories": len(vocab.by_category),
                    })
                except Exception as exc:  # noqa: BLE001
                    self.failed.emit(f"{type(exc).__name__}: {exc}")

        progress = QProgressDialog(
            "Rebuilding catalog embeddings, corpus BM25, and vocab caches…",
            "Hide", 0, 0, self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        worker = _Worker(self, self._config)
        self._index_worker = worker

        def on_done(stats: dict) -> None:
            progress.close()
            self._cached_vocab = None
            self._cached_catalog = None
            t = stats["timings"]
            QMessageBox.information(
                self, "Indexes rebuilt",
                f"Catalog: {stats['catalog_items']} items in {t['catalog']:.1f}s\n"
                f"Corpus: {stats['corpus_rows']} rows in {t['corpus']:.1f}s\n"
                f"Vocab: {stats['vocab_categories']} categories in {t['vocab']:.1f}s",
            )

        def on_err(msg: str) -> None:
            progress.close()
            QMessageBox.critical(self, "Rebuild failed", msg)

        worker.done.connect(on_done)
        worker.failed.connect(on_err)
        progress.canceled.connect(lambda: progress.close())  # detach; worker keeps running
        worker.start()
        progress.show()

    def _on_ingest_csv(self) -> None:
        """Open the CSV ingest dialog. Refreshes adapters + clears cached vocab on close."""

        raw_corpus_dir = Path("raw_corpus")
        dialog = IngestDialog(
            self, raw_corpus_dir=raw_corpus_dir, adapters_dir=self._adapters_dir,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Vocab was reset by ingest; force a rebuild on the next combo lookup.
            self._cached_vocab = None
            self._cached_catalog = None
            self._refresh_adapters()
            self.statusBar().showMessage(
                "Corpus updated — vocabulary and embeddings will rebuild on next generate.", 8000,
            )

    def _on_refine_from_feedback(self) -> None:
        """Open the image-critique dialog; pre-fill with the currently selected card."""

        original_prompt = ""
        row = self.cards_list.currentRow()
        if 0 <= row < len(self._cards):
            card = self._cards[row]
            compiled = card.get("compiled")
            if isinstance(compiled, list):
                original_prompt = (compiled[0] or {}).get("text", "") if compiled else ""
            elif isinstance(compiled, dict):
                original_prompt = compiled.get("text", "")
        default_backend = (
            self._config.llm.backend if self._config.llm.backend in {"claude", "codex"} else "claude"
        )
        dialog = RefineDialog(
            self, original_prompt=original_prompt, default_backend=default_backend,
        )
        dialog.applied_new_card.connect(self._on_refined_apply_new)
        dialog.replaced_current.connect(self._on_refined_replace_current)
        dialog.exec()

    def _on_refined_apply_new(self, refined_prompt: str) -> None:
        """Push the refined prompt back into the brief and queue a regenerate."""

        self.brief_edit.setPlainText(refined_prompt)
        self.statusBar().showMessage(
            "Refined prompt loaded into the brief — hit Generate to materialize it.", 8000,
        )

    def _on_refined_replace_current(self, refined_prompt: str) -> None:
        """Overwrite the selected card's compiled text with the refined prompt."""

        row = self.cards_list.currentRow()
        if not (0 <= row < len(self._cards)):
            self._on_refined_apply_new(refined_prompt)
            return
        card = self._cards[row]
        compiled = card.get("compiled")
        if isinstance(compiled, list) and compiled:
            compiled[0]["text"] = refined_prompt
        elif isinstance(compiled, dict):
            compiled["text"] = refined_prompt
        else:
            card["compiled"] = {"text": refined_prompt, "negative_text": "", "parameters": {}, "warnings": []}
        self._cards[row] = card
        self.prompt_view.setPlainText(self._render_card(card))
        self.card_editor.set_card(card)
        self.statusBar().showMessage("Card updated with the refined prompt.", 8000)

    def _safe_save_config(self) -> bool:
        try:
            self._config.save(default_config_path())
            return True
        except ConfigSaveError as exc:
            QMessageBox.warning(
                self,
                "Couldn't save settings",
                f"{exc}\n\nYour changes will only apply to this session.",
            )
            return False

    def _first_run_check(self) -> None:
        """Show a friendly setup hint when the catalog or adapters directory is empty."""

        problems: list[str] = []
        if not self._adapters_dir.exists() or not any(self._adapters_dir.glob("*_adapter.json")):
            problems.append(
                f"No adapters found in {self._adapters_dir}.\n"
                "Adapters describe how to compile prompts for each target model."
            )
        catalog_count = (
            sum(1 for _ in self._catalog_dir.rglob("*.json")) if self._catalog_dir.exists() else 0
        )
        if catalog_count == 0:
            problems.append(
                f"Catalog at {self._catalog_dir} is empty.\n"
                "Run `python scripts/seed_catalog.py catalog/` to populate it."
            )
        if not problems:
            return
        QMessageBox.warning(
            self,
            "First-run setup needed",
            "Prompt Genius can't generate yet:\n\n" + "\n\n".join(problems)
            + "\n\nOpen Settings (⌘,) → Paths to point at the right directories.",
        )

    # ------------------------------------------------------------------- chrome

    def _build_menu_and_toolbar(self) -> None:
        # ---- menu ----
        # On macOS Qt promotes this to the system menubar at the top of the
        # screen. About / Settings / Quit are tagged with their MenuRole so
        # they auto-migrate into the "🦊 Prompt Genius" application menu in
        # the macOS convention (App → About / Preferences… / Quit).
        menubar = self.menuBar()
        menubar.setNativeMenuBar(True)

        # ---- Application-menu actions (macOS) — added to a menu but the
        # MenuRole tags below tell Qt to move them into the App menu.
        about_action = QAction("About 🦊 Prompt Genius", self)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        about_action.triggered.connect(self._show_about)

        settings_action = QAction("Preferences…", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        settings_action.setToolTip("Open application preferences (⌘,)")
        settings_action.triggered.connect(self._on_settings)

        quit_action = QAction("Quit 🦊 Prompt Genius", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)

        # ---- File ----
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New brief", self)
        new_action.setShortcut(QKeySequence.New)
        new_action.setToolTip("Clear the brief (⌘N)")
        new_action.triggered.connect(self._on_new_brief)
        file_menu.addAction(new_action)

        save_action = QAction("&Save selected card", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setToolTip(
            "Save the selected card as a standalone JSON in history/ (⌘S). "
            "Different from Save version, which appends a row to a revision log."
        )
        save_action.triggered.connect(self._on_save_card)
        file_menu.addAction(save_action)

        export_action = QAction("&Export selected…", self)
        export_action.setShortcut("Ctrl+E")
        export_action.setToolTip("Export the selected card to .md / .txt / .json (⌘E)")
        export_action.triggered.connect(self._on_export)
        file_menu.addAction(export_action)

        file_menu.addSeparator()
        ingest_action = QAction("&Ingest CSV prompts…", self)
        ingest_action.setShortcut("Ctrl+I")
        ingest_action.setToolTip(
            "Pick prompt CSVs to merge into the corpus. Detects schema, shows "
            "delta vs the current corpus, then writes only new rows (⌘I)."
        )
        ingest_action.triggered.connect(self._on_ingest_csv)
        file_menu.addAction(ingest_action)

        # File → Quit (Qt will migrate to App menu on macOS via QuitRole).
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        # ---- Edit ----
        # Preferences gets added here but lands in the App menu on macOS.
        edit_menu = menubar.addMenu("&Edit")
        edit_menu.addAction(settings_action)

        # ---- View ----
        view_menu = menubar.addMenu("&View")
        for label, key in [("System theme", "system"), ("Light", "light"), ("Dark", "dark")]:
            act = QAction(label, self, checkable=True)
            act.setData(key)
            act.triggered.connect(self._on_theme_change)
            act.setToolTip(f"Switch the UI to the {label.lower()} palette.")
            if self._config.gui.theme == key:
                act.setChecked(True)
            view_menu.addAction(act)

        # ---- Run ----
        run_menu = menubar.addMenu("&Run")
        gen_action = QAction("&Generate", self)
        gen_action.setShortcut("Ctrl+Return")
        gen_action.setToolTip("Generate prompt cards from the current brief (⌘↩)")
        gen_action.triggered.connect(self._on_generate)
        run_menu.addAction(gen_action)
        cancel_action = QAction("Cancel", self)
        cancel_action.setShortcut("Esc")
        cancel_action.setToolTip("Cancel the running generation (Esc)")
        cancel_action.triggered.connect(self._on_cancel)
        run_menu.addAction(cancel_action)

        # ---- Tools ----
        tools_menu = menubar.addMenu("&Tools")
        refine_action = QAction("&Refine from feedback…", self)
        refine_action.setShortcut("Ctrl+R")
        refine_action.setToolTip(
            "Open the image-critique dialog: paste a description of the generated "
            "image and get a refined prompt back (⌘R)."
        )
        refine_action.triggered.connect(self._on_refine_from_feedback)
        tools_menu.addAction(refine_action)

        tools_menu.addSeparator()
        last_prompt_action = QAction("Show &last LLM prompts…", self)
        last_prompt_action.setShortcut("Ctrl+L")
        last_prompt_action.setToolTip(
            "Inspect the exact prompt(s) fed to claude / codex in the most "
            "recent generation, plus their raw output. Useful to debug why "
            "the LLM produced what it did (⌘L)."
        )
        last_prompt_action.triggered.connect(self._show_last_llm_prompts)
        tools_menu.addAction(last_prompt_action)

        tools_menu.addSeparator()
        rebuild_action = QAction("Rebuild &indexes…", self)
        rebuild_action.setToolTip(
            "Pre-build catalog embeddings, corpus BM25, and vocab caches. "
            "Not required (Generate builds lazily) but useful after a big ingest."
        )
        rebuild_action.triggered.connect(self._on_rebuild_indexes)
        tools_menu.addAction(rebuild_action)

        # ---- Help ----
        help_menu = menubar.addMenu("&Help")
        docs_action = QAction("🦊 Prompt Genius Help", self)
        docs_action.setShortcut("Ctrl+?")
        docs_action.setMenuRole(QAction.MenuRole.ApplicationSpecificRole)
        docs_action.setToolTip(
            "Open the full documentation (tutorials, how-to guides, reference, "
            "explanation). Uses macOS Help Viewer when bundled, in-app browser "
            "in source mode (⌘?)."
        )
        docs_action.triggered.connect(self._show_help)
        help_menu.addAction(docs_action)
        help_menu.addSeparator()
        shortcuts_action = QAction("Keyboard shortcuts", self)
        shortcuts_action.setToolTip("Show the keyboard shortcut cheat sheet.")
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)
        # About is also added to Help so it shows in non-macOS menubars.
        help_menu.addAction(about_action)

        # ---- toolbar ----
        toolbar = QToolBar("main", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        toolbar.addAction(gen_action)
        toolbar.addAction(cancel_action)
        toolbar.addSeparator()
        toolbar.addAction(save_action)
        toolbar.addAction(export_action)
        toolbar.addSeparator()
        toolbar.addAction(refine_action)
        toolbar.addSeparator()
        toolbar.addAction(settings_action)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_middle())
        splitter.addWidget(self._build_right())
        # Initial pixel sizes give the right panel real room for the structured editor.
        splitter.setSizes([380, 460, 640])
        splitter.setHandleWidth(6)
        splitter.setChildrenCollapsible(False)
        self.setCentralWidget(splitter)

    # --------------------------------------------------------------------- left

    def _build_left(self) -> QWidget:
        scroll = QScrollArea(self); scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        brief_header = QHBoxLayout()
        brief_header.setSpacing(8)
        brief_header.addWidget(_section("Brief"))
        brief_header.addStretch(1)
        try_example_btn = QPushButton("Try an example")
        try_example_btn.setToolTip("Fill the brief with an example for the current mode")
        try_example_btn.clicked.connect(self._insert_example_brief)
        brief_header.addWidget(try_example_btn)
        layout.addLayout(brief_header)

        self.brief_edit = QPlainTextEdit()
        self._update_brief_placeholder(self._config.gui.default_mode)
        self.brief_edit.setMinimumHeight(140)
        self.brief_edit.setToolTip(
            "Describe the image or video you want — what, who, mood, lighting, "
            "constraints. Be specific; the engine pulls catalog items that match "
            "the words you use. Hints from the panels below are appended automatically."
        )
        layout.addWidget(self.brief_edit)

        # Inputs
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.mode_combo = QComboBox()
        for mode_id in _MODES:
            self.mode_combo.addItem(_MODE_LABELS.get(mode_id, mode_id), userData=mode_id)
        self._select_mode(self._config.gui.default_mode)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        self.mode_combo.setToolTip(
            "What kind of asset to design: a still image, a short video, a multi-shot "
            "storyboard, or explicit start/mid/end keyframes."
        )
        form.addRow("Mode", self.mode_combo)

        self.target_combo = QComboBox()
        self.target_combo.setToolTip(
            "Which model the prompt is compiled for. Each adapter knows the "
            "model's parameter syntax, negative-prompt convention, and any "
            "quirks (aspect ratio, max length). 'generic' = model-agnostic."
        )
        self._refresh_adapters()
        form.addRow("Target", self.target_combo)

        self.n_spin = QSpinBox(); self.n_spin.setRange(1, 12); self.n_spin.setValue(self._config.gui.default_n)
        self.n_spin.setToolTip(
            "How many distinct prompt cards to generate from this brief. "
            "Each card explores a different creative direction."
        )
        form.addRow("# cards", self.n_spin)

        self.risk_combo = QComboBox(); self.risk_combo.addItems(["safe", "creative", "experimental"])
        self.risk_combo.setCurrentText(self._config.gui.default_risk)
        self.risk_combo.setToolTip(
            "How far from the brief the engine should wander. "
            "safe = stays close · creative = adds tasteful liberties · "
            "experimental = bigger swings, lower hit rate."
        )
        form.addRow("Risk", self.risk_combo)

        self.brand_label = QLabel(self._brand_label_text())
        self.brand_label.setToolTip(
            self._config.gui.brand_profile_path
            or "No brand profile active. Click Manage… to create one."
        )
        brand_btn = QPushButton("Manage…")
        brand_btn.setToolTip(
            "Open the brand profile manager — create, edit, duplicate, and "
            "pick the active brand. Profiles are stored per-user and persist "
            "across app updates."
        )
        brand_btn.clicked.connect(self._open_brand_manager)
        brand_clear_btn = QPushButton("✕")
        brand_clear_btn.setFixedWidth(28)
        brand_clear_btn.setToolTip("Clear active brand profile (keep files on disk).")
        brand_clear_btn.clicked.connect(self._clear_brand_profile)
        brand_row = _row(self.brand_label, brand_btn, brand_clear_btn)
        form.addRow("Brand", brand_row)

        self.allow_drafts_check = QCheckBox("Allow draft catalog items")
        self.allow_drafts_check.setChecked(self._config.gui.allow_drafts)
        self.allow_drafts_check.setToolTip(
            "Include catalog items marked status=draft. Drafts are unverified "
            "patterns — useful for exploration, riskier for production output."
        )
        form.addRow(self.allow_drafts_check)

        layout.addLayout(form)

        # Fine-tune hints — appended to the brief as inline guidance.
        ft_header = _section("Hints (appended to your brief)")
        ft_header.setToolTip(
            "These values are added to the brief as guidance — the engine "
            "treats them as part of your request. To edit the structured "
            "fields of an already-generated card, right-click it."
        )
        layout.addWidget(ft_header)
        self.finetune_tabs = QTabWidget()
        self.finetune_tabs.addTab(self._build_finetune_image_tab(), "Image")
        self.finetune_tabs.addTab(self._build_finetune_video_tab(), "Video")
        layout.addWidget(self.finetune_tabs)

        # Action buttons
        self.generate_btn = QPushButton("Generate (⌘↩)")
        self.generate_btn.setToolTip(
            "Generate prompt cards from the current brief, mode, target, and "
            "hints. Cards stream into the middle panel as the LLM responds."
        )
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)

        self.cancel_btn = QPushButton("Cancel (Esc)")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip(
            "Cancel the running generation. Cards already streamed in stay."
        )
        self.cancel_btn.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel_btn)

        layout.addStretch(1)
        scroll.setWidget(container)
        return scroll

    def _vocab(self) -> dict[str, list[str]]:
        if getattr(self, "_cached_vocab", None) is None:
            catalog = self._catalog_for_editor()
            self._cached_vocab = build_full_vocab(catalog) if catalog else {}
        return self._cached_vocab

    def _editable_combo(self, vocab_key: str, fallback: list[str]) -> QComboBox:
        """Editable combo box populated from the merged catalog+corpus vocab."""

        values = self._vocab().get(vocab_key) or fallback
        combo = QComboBox()
        combo.setEditable(True)
        combo.addItem("")  # first row = no hint
        seen: set[str] = set()
        for value in values:
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            combo.addItem(value)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMaxVisibleItems(20)
        return combo

    def _build_finetune_image_tab(self) -> QWidget:
        widget, form = _form()
        self.aspect_combo = self._editable_combo(
            "aspect_ratio", ["1:1", "4:5", "3:2", "16:9", "9:16", "21:9"],
        )
        self.aspect_combo.setToolTip(
            "Target aspect ratio. Type a custom value if your model accepts it."
        )
        form.addRow("Aspect ratio", self.aspect_combo)
        self.lens_combo = self._editable_combo(
            "lens", ["24mm", "35mm", "50mm", "85mm", "macro"],
        )
        self.lens_combo.setToolTip(
            f"Lens / focal length hint. {len(self._vocab().get('lens') or [])} "
            "values mined from the corpus; type your own to add."
        )
        form.addRow("Lens hint", self.lens_combo)
        self.lighting_combo = self._editable_combo(
            "lighting",
            ["soft studio", "natural window", "golden hour", "dramatic low-key", "overcast"],
        )
        self.lighting_combo.setToolTip(
            "Lighting setup / quality hint. Drives mood as much as the subject does."
        )
        form.addRow("Lighting hint", self.lighting_combo)
        self.realism_combo = self._editable_combo(
            "style", ["photorealistic", "semi-realistic", "stylized", "illustration"],
        )
        self.realism_combo.setToolTip(
            "Stylistic register. photorealistic ↔ illustration; pick or type custom."
        )
        form.addRow("Style / realism", self.realism_combo)
        self.mood_combo = self._editable_combo("mood", ["calm", "premium", "playful"])
        self.mood_combo.setToolTip("Emotional register of the result.")
        form.addRow("Mood", self.mood_combo)
        self.color_combo = self._editable_combo(
            "color_palette", ["warm tones", "cool tones", "monochrome"],
        )
        self.color_combo.setToolTip(
            "Color treatment hint. Combine with brand profile for stronger pull."
        )
        form.addRow("Color palette", self.color_combo)
        self.framing_combo = self._editable_combo(
            "framing", ["close-up", "medium shot", "wide shot"],
        )
        self.framing_combo.setToolTip("Composition / shot size hint.")
        form.addRow("Framing", self.framing_combo)
        return widget

    def _build_finetune_video_tab(self) -> QWidget:
        widget, form = _form()
        self.duration_spin = QSpinBox(); self.duration_spin.setRange(0, 60); self.duration_spin.setValue(0)
        self.duration_spin.setSuffix("s   (0 = adapter default)")
        self.duration_spin.setToolTip(
            "Override the target clip duration in seconds. 0 means use the "
            "target model's adapter default (often 6 or 8s)."
        )
        form.addRow("Duration", self.duration_spin)
        self.shotcount_spin = QSpinBox(); self.shotcount_spin.setRange(0, 12); self.shotcount_spin.setValue(0)
        self.shotcount_spin.setSuffix("   (0 = adapter default)")
        self.shotcount_spin.setToolTip(
            "Storyboard mode only — number of distinct shots to plan. "
            "0 = let the adapter decide."
        )
        form.addRow("Shot count (storyboard)", self.shotcount_spin)
        self.camera_motion_combo = self._editable_combo(
            "camera_motion",
            ["static", "slow push-in", "slow pull-back", "dolly left",
             "dolly right", "orbit", "handheld"],
        )
        self.camera_motion_combo.setToolTip(
            "How the camera itself moves. Strong effect on temporal stability — "
            "slow + simple motion = fewer artifacts."
        )
        form.addRow("Camera motion", self.camera_motion_combo)
        self.subject_motion_combo = self._editable_combo(
            "subject_motion", ["none", "subtle", "medium", "dynamic"],
        )
        self.subject_motion_combo.setToolTip(
            "How much the subject moves within the frame. Higher = harder to "
            "keep identity stable on most video models."
        )
        form.addRow("Subject motion", self.subject_motion_combo)
        self.pacing_combo = self._editable_combo(
            "pacing", ["calm", "medium", "fast", "dramatic"],
        )
        self.pacing_combo.setToolTip(
            "Editorial pacing hint. Combines with camera/subject motion to shape rhythm."
        )
        form.addRow("Pacing", self.pacing_combo)
        return widget

    # ------------------------------------------------------------------ middle

    def _build_middle(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 14, 12, 14)
        layout.setSpacing(10)

        self.tabs = QTabWidget()
        # Cards tab
        cards_widget = QWidget(); cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(0, 8, 0, 0)
        cards_layout.setSpacing(8)
        cards_layout.addWidget(_section("Prompt cards"))
        self.cards_list = QListWidget()
        self.cards_list.setToolTip(
            "Generated prompt cards for the current brief. Click a card to "
            "preview / edit it on the right. Right-click for regenerate, "
            "more-like-this, export, copy variants, or discard."
        )
        self.cards_list.setSpacing(4)
        self.cards_list.setWordWrap(True)
        self.cards_list.setUniformItemSizes(False)
        self.cards_list.setStyleSheet(
            "QListWidget { border: 1px solid rgba(127,127,127,0.20); border-radius: 4px; }"
            "QListWidget::item { padding: 12px 14px; border-bottom: 1px solid rgba(127,127,127,0.20); }"
            "QListWidget::item:selected { background-color: rgba(91,141,239,0.25); color: inherit; }"
        )
        self.cards_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cards_list.customContextMenuRequested.connect(self._on_card_context_menu)
        self.cards_list.currentRowChanged.connect(self._on_select_card)
        cards_layout.addWidget(self.cards_list)
        self.tabs.addTab(cards_widget, "Cards")

        # History tab
        history_widget = QWidget(); history_layout = QVBoxLayout(history_widget)
        history_layout.setContentsMargins(0, 0, 0, 0)
        history_layout.addWidget(_section("History"))
        self.history_list = QListWidget()
        self.history_list.setToolTip(
            "Saved cards from past sessions. Double-click to pull one back into "
            "the Cards panel. Stored as JSON in history/."
        )
        self.history_list.itemActivated.connect(self._on_history_open)
        history_layout.addWidget(self.history_list)
        history_refresh = QPushButton("Reload history")
        history_refresh.setToolTip("Re-scan history/ for any cards saved outside this session.")
        history_refresh.clicked.connect(self._load_history_into_panel)
        history_layout.addWidget(history_refresh)
        self.tabs.addTab(history_widget, "History")

        layout.addWidget(self.tabs)
        return container

    # ------------------------------------------------------------------- right

    def _build_right(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(_section("Compiled prompt"))
        self.prompt_view = QTextEdit(); self.prompt_view.setReadOnly(True)
        self.prompt_view.setToolTip(
            "Final compiled prompt text — the exact string to feed the model. "
            "Read-only; edit the structured fields below to change it."
        )
        self.prompt_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.prompt_view, stretch=2)

        # Why + brand-fit summary
        info_row = QHBoxLayout()
        self.why_label = QLabel(""); self.why_label.setWordWrap(True)
        self.why_label.setStyleSheet("color: gray;")
        self.why_label.setToolTip("Short rationale the engine attached to this card.")
        info_row.addWidget(self.why_label, stretch=4)
        self.brandfit_label = QLabel("brand-fit: —")
        self.brandfit_label.setStyleSheet("font-weight: bold;")
        self.brandfit_label.setToolTip(
            "Heuristic 0–1 score: how many brand 'prefer' tokens appear in the "
            "compiled prompt minus 'avoid' tokens that slipped through. — = no "
            "active brand profile."
        )
        info_row.addWidget(self.brandfit_label, stretch=1, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(info_row)

        layout.addWidget(_section("Editable structure"))
        self.card_editor = StructuredCardEditor()
        self.card_editor.setToolTip(
            "Structured fields the engine used. Edit any value to recompile "
            "the prompt text above. Right-click a row for vocab suggestions."
        )
        self.card_editor.card_changed.connect(self._on_card_edited)
        layout.addWidget(self.card_editor, stretch=3)

        # Action row: copy variants / save version / feedback
        actions = QHBoxLayout()

        copy_text_btn = QPushButton("Copy text")
        copy_text_btn.setToolTip(
            "Copy just the compiled prompt text to the clipboard — the string "
            "you paste into the model. No JSON, no warnings."
        )
        copy_text_btn.clicked.connect(self._on_copy_text)
        actions.addWidget(copy_text_btn)

        copy_json_btn = QPushButton("Copy JSON")
        copy_json_btn.setToolTip(
            "Copy the structured card as JSON — useful when the model accepts "
            "a JSON payload, or for storing the full structured response."
        )
        copy_json_btn.clicked.connect(self._on_copy_json)
        actions.addWidget(copy_json_btn)

        copy_toon_btn = QPushButton("Copy TOON")
        copy_toon_btn.setToolTip(
            "Copy the card as TOON (Token-Oriented Object Notation) — a compact "
            "JSON alternative that saves 30–60% tokens when feeding structured "
            "context to LLMs. Falls back to JSON if the TOON package isn't installed."
        )
        copy_toon_btn.clicked.connect(self._on_copy_toon)
        actions.addWidget(copy_toon_btn)

        version_btn = QPushButton("Save version")
        version_btn.setToolTip(
            "Append the current card to versions.jsonl — a revision log of one "
            "evolving card across edits. Different from Save (⌘S), which writes "
            "a standalone card JSON to history/."
        )
        version_btn.clicked.connect(self._on_snapshot)
        actions.addWidget(version_btn)

        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addWidget(_section("Feedback"))
        feedback_row = QHBoxLayout()
        self.rating_combo = QComboBox()
        for rating_id in _RATINGS:
            self.rating_combo.addItem(_RATING_LABELS.get(rating_id, rating_id), userData=rating_id)
        self.rating_combo.setToolTip(
            "Rate the selected card — feedback is logged to feedback.jsonl and "
            "shapes quality scores for the patterns this card used."
        )
        feedback_row.addWidget(self.rating_combo, stretch=1)
        self.note_edit = QPlainTextEdit(); self.note_edit.setPlaceholderText("Note (optional)")
        self.note_edit.setToolTip("Optional free-text note attached to this feedback.")
        self.note_edit.setMaximumHeight(60)
        feedback_row.addWidget(self.note_edit, stretch=3)
        feedback_btn = QPushButton("Send")
        feedback_btn.setToolTip("Write the rating + note to feedback.jsonl.")
        feedback_btn.clicked.connect(self._on_feedback)
        feedback_row.addWidget(feedback_btn)
        layout.addLayout(feedback_row)

        return container

    # ----------------------------------------------------------------- actions

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt API
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        if self._prewarm_worker and self._prewarm_worker.isRunning():
            self._prewarm_worker.wait(2000)
        event.accept()

    def _on_settings(self) -> None:
        dialog = SettingsDialog(self, self._config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._config = load_or_init()
            self._adapters_dir = Path(self._config.paths.adapters_dir)
            self._catalog_dir = Path(self._config.paths.catalog_dir)
            self._refresh_adapters()
            self.allow_drafts_check.setChecked(self._config.gui.allow_drafts)
            self.n_spin.setValue(self._config.gui.default_n)
            self.risk_combo.setCurrentText(self._config.gui.default_risk)
            self.brand_label.setText(self._brand_label_text())
            self.brand_label.setToolTip(self._config.gui.brand_profile_path or "")
            self._apply_theme()
            self._load_history_into_panel()
            self.statusBar().showMessage("Settings saved.", 6000)

    def _on_new_brief(self) -> None:
        self.brief_edit.clear()
        self.brief_edit.setFocus()

    def _on_theme_change(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QAction):
            return
        for action in self.menuBar().actions():
            menu = action.menu()
            if not menu:
                continue
            for sub in menu.actions():
                if sub.data() in {"system", "light", "dark"}:
                    sub.setChecked(sub is sender)
        self._config.gui.theme = sender.data() or "system"
        self._safe_save_config()
        self._apply_theme()

    def _on_generate(self) -> None:
        if self._worker and self._worker.isRunning():
            self.statusBar().showMessage(
                "Already generating — cancel the current run first.", 4000,
            )
            return
        brief = self.brief_edit.toPlainText().strip()
        if not brief:
            QMessageBox.information(self, "Brief required", "Please enter a brief.")
            return
        # Warn if the configured LLM backend isn't installed — silently falling
        # back to heuristic would confuse the user.
        from prompt_genius.gui.settings_dialog import _confirm_backend_available
        if not _confirm_backend_available(self, self._config.llm.backend):
            return

        target = self.target_combo.currentData()
        # apply fine-tune hints by appending to the brief — keeps assembler simple
        hint_pieces = []
        if self.aspect_combo.currentText():
            hint_pieces.append(self.aspect_combo.currentText())
        for combo in (
            self.lens_combo, self.lighting_combo, self.realism_combo,
            self.mood_combo, self.color_combo, self.framing_combo,
            self.camera_motion_combo, self.subject_motion_combo, self.pacing_combo,
        ):
            text = combo.currentText().strip()
            if text:
                hint_pieces.append(text)
        if self.duration_spin.value() > 0:
            hint_pieces.append(f"{self.duration_spin.value()}s")
        brief_with_hints = brief
        if hint_pieces:
            brief_with_hints = brief + "\n[hints] " + ", ".join(hint_pieces)

        params = {
            "brief": brief_with_hints,
            "mode": self._current_mode(),
            "target": target,
            "n": self.n_spin.value(),
            "risk": self.risk_combo.currentText(),
            "brand_profile": self._config.gui.brand_profile_path or None,
            "adapters_dir": self._adapters_dir,
            "catalog_dir": self._catalog_dir,
            "allow_drafts": self.allow_drafts_check.isChecked(),
        }
        self.generate_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        # Reset the cards panel before streaming begins.
        self._cards = []
        self.cards_list.clear()
        # Drop captured LLM prompts from prior runs so the trace viewer only
        # shows what's relevant to this generation.
        try:
            from prompt_genius.core import llm_trace
            llm_trace.reset()
        except ImportError:
            pass
        self._stream_count = 0
        self._target_n = int(params["n"])
        self.statusBar().showMessage(f"Generating 0 / {self._target_n}…")
        self._worker = GenerateWorker(self, params, self._config)
        self._worker.card_ready.connect(self._on_card_streamed)
        self._worker.cards_ready.connect(self._on_cards_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.tick.connect(self._on_generate_tick)
        self._worker.start()

    def _on_generate_tick(self, elapsed: int) -> None:
        """Update status bar with live elapsed counter while the LLM thinks."""

        backend = self._config.llm.backend if self._config.llm.backend != "heuristic" else "heuristic"
        suffix = f" — asking {backend}" if backend != "heuristic" else ""
        n_so_far = len(self._cards)
        self.statusBar().showMessage(
            f"Generating {n_so_far} / {self._target_n}  ·  {elapsed}s elapsed{suffix}",
            0,
        )

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
            self.statusBar().showMessage("Cancelling…")

    def _on_card_streamed(self, card: dict[str, Any]) -> None:
        """Append a single card as soon as the engine emits it."""

        self._cards.append(card)
        self._stream_count += 1
        index = len(self._cards)
        title = card.get("title", "(untitled)")
        compiled = card.get("compiled") or {}
        if isinstance(compiled, list):
            preview = (compiled[0] or {}).get("text", "") if compiled else ""
        else:
            preview = compiled.get("text", "")
        preview = " ".join(preview.split())[:96]
        target = card.get("target_model", "")
        risk = card.get("risk_level", "")
        label = f"{index}. {title}\n{preview}\n  · {target}  · risk: {risk}"
        item = QListWidgetItem(label)
        item.setToolTip(card.get("why_this_works", ""))
        self.cards_list.addItem(item)
        if index == 1:
            self.cards_list.setCurrentRow(0)
        target_n = int(getattr(self, "_target_n", index))
        self.statusBar().showMessage(f"Generated {index} / {target_n}…")

    def _on_cards_ready(self, cards: list[dict[str, Any]]) -> None:
        # The list was streamed in via _on_card_streamed; this only finalizes.
        # Fallback: if no streaming happened, render the batch the engine returned.
        if not self._cards and cards:
            for card in cards:
                self._on_card_streamed(card)
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.tabs.setCurrentIndex(0)
        final_count = len(self._cards)
        self.statusBar().showMessage(f"Generated {final_count} cards.", 8000)

    def _on_failed(self, message: str) -> None:
        self.generate_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.statusBar().clearMessage()
        # Strip the leading "ExceptionName: " for a friendlier read.
        cleaned = message.split(": ", 1)[-1] if ":" in message else message
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Couldn't finish generating")
        box.setText("Generation didn't complete.")
        box.setInformativeText(cleaned)
        box.setDetailedText(message)  # the full ExceptionName for devs
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def _show_last_llm_prompts(self) -> None:
        from prompt_genius.gui.llm_trace_dialog import LlmTraceDialog
        LlmTraceDialog(self).exec()

    def _show_help(self) -> None:
        from prompt_genius.gui.help_viewer import open_help
        open_help(self)

    def _show_about(self) -> None:
        from prompt_genius import __version__
        QMessageBox.about(
            self,
            "About 🦊 Prompt Genius",
            f"<h3>🦊 Prompt Genius</h3>"
            f"<p>Internal creative prompt workbench for static images and video.</p>"
            f"<p>Version <b>{__version__}</b></p>"
            f"<p>Backends: heuristic · claude · codex · mlx · sentence-transformers</p>"
            f"<p style='color:gray; font-size:11px;'>"
            f"Bundled splash art: gift from the cave 🦊</p>",
        )

    def _show_shortcuts(self) -> None:
        QMessageBox.information(
            self,
            "Keyboard shortcuts",
            "<table cellspacing=8>"
            "<tr><td><b>⌘N</b></td><td>New brief</td></tr>"
            "<tr><td><b>⌘↩</b></td><td>Generate</td></tr>"
            "<tr><td><b>Esc</b></td><td>Cancel generation</td></tr>"
            "<tr><td><b>⌘S</b></td><td>Save selected card</td></tr>"
            "<tr><td><b>⌘E</b></td><td>Export selected card</td></tr>"
            "<tr><td><b>⌘,</b></td><td>Open Settings</td></tr>"
            "<tr><td colspan=2 style='padding-top:10px;'>"
            "Right-click a card for: Regenerate · More like this · Discard"
            "</td></tr>"
            "</table>",
        )

    def _on_select_card(self, row: int) -> None:
        if row < 0 or row >= len(self._cards):
            self.prompt_view.clear()
            self.card_editor.set_card(None)
            self.brandfit_label.setText("brand-fit: —"); self.why_label.setText("")
            return
        card = self._cards[row]
        self.prompt_view.setPlainText(self._render_card(card))
        # Keep the editor's catalog in sync (its delegate vocab depends on it).
        self.card_editor.set_catalog(self._catalog_for_editor())
        self.card_editor.set_card(card)
        self.why_label.setText(card.get("why_this_works", ""))
        brand_path = self._config.gui.brand_profile_path
        if brand_path:
            try:
                brand = load_brand_profile(brand_path)
                score = brand_fit_score(card, brand)
                self.brandfit_label.setText(f"brand-fit: {score:.2f}")
            except (OSError, ValueError, KeyError):
                self.brandfit_label.setText("brand-fit: ?")
        else:
            self.brandfit_label.setText("brand-fit: —")
        # record reuse usage signal
        try:
            record_usage(
                card.get("selected_patterns") or [],
                event="selected",
                card_id=card.get("id"),
                ledger_path=self._config.paths.usage_path,
            )
        except OSError:
            pass

    def _catalog_for_editor(self):
        """Return the in-process warm catalog (or load+cache it once)."""

        if getattr(self, "_cached_catalog", None) is None:
            try:
                from prompt_genius.core.generate import get_or_load_catalog
                cfg = self._config.embeddings
                self._cached_catalog = get_or_load_catalog(
                    self._catalog_dir,
                    backend=cfg.backend,
                    prefer_dense=cfg.prefer_dense,
                    model_name=cfg.model_name,
                    cache_dir=cfg.cache_dir,
                    bm25_k1=cfg.bm25_k1,
                    bm25_b=cfg.bm25_b,
                    rrf_k=cfg.hybrid_rrf_k,
                )
            except Exception:  # noqa: BLE001
                self._cached_catalog = None
        return self._cached_catalog

    def _on_card_edited(self, new_card: dict[str, Any]) -> None:
        """Recompile the prompt text from the edited structured fields."""

        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            return
        # Persist edits back into the in-memory card list.
        self._cards[row] = new_card
        # Attempt a live recompile so the prompt text reflects the edit.
        try:
            adapters = load_adapters(self._adapters_dir)
            adapter = resolve_adapter(adapters, new_card.get("target_model"))
            catalog = self._catalog_for_editor()
            if catalog is None:
                return
            structured_dicts = new_card.get("structured")
            if isinstance(structured_dicts, list):
                compiled = [
                    _model_to_dict(compile_prompt(_structured_from_dict(s, adapter.model_id), adapter, catalog))
                    for s in structured_dicts
                ]
            else:
                compiled = _model_to_dict(
                    compile_prompt(
                        _structured_from_dict(structured_dicts or {}, adapter.model_id),
                        adapter, catalog,
                    )
                )
            new_card["compiled"] = compiled
        except Exception as exc:  # noqa: BLE001
            self.statusBar().showMessage(f"Live recompile failed: {exc}", 6000)
            return
        self.prompt_view.setPlainText(self._render_card(new_card))
        self.statusBar().showMessage("Recompiled from your edits.", 6000)

    def _on_copy_text(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            return
        QApplication.clipboard().setText(self._render_card(self._cards[row]))
        self.statusBar().showMessage("Copied prompt text.", 6000)

    def _on_copy_json(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            return
        payload = json.dumps(self._cards[row], indent=2, ensure_ascii=False)
        QApplication.clipboard().setText(payload)
        self.statusBar().showMessage("Copied card JSON.", 6000)

    def _on_copy_toon(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            return
        card = self._cards[row]
        try:
            from toon import encode as toon_encode
        except ImportError:
            payload = json.dumps(card, indent=2, ensure_ascii=False)
            QApplication.clipboard().setText(payload)
            self.statusBar().showMessage(
                "TOON package not installed — copied JSON instead. "
                "Install with: pip install python-toon",
                8000,
            )
            return
        try:
            payload = toon_encode(card)
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps(card, indent=2, ensure_ascii=False)
            QApplication.clipboard().setText(payload)
            self.statusBar().showMessage(f"TOON encode failed ({exc}); copied JSON.", 8000)
            return
        QApplication.clipboard().setText(payload)
        self.statusBar().showMessage("Copied card as TOON.", 6000)

    def _on_save_card(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            QMessageBox.information(self, "Save", "Select a card first.")
            return
        card = self._cards[row]
        path = save_card(card, self._config.paths.history_dir)
        record_usage(
            card.get("selected_patterns") or [],
            event="saved",
            card_id=card.get("id"),
            ledger_path=self._config.paths.usage_path,
        )
        self._load_history_into_panel()
        self.statusBar().showMessage(f"Saved to {path}.", 8000)

    def _on_snapshot(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            return
        card = self._cards[row]
        path = save_version(card, self._config.paths.versions_path, change_summary="GUI snapshot")
        self.statusBar().showMessage(f"Snapshot → {path}.", 3500)

    def _on_export(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            QMessageBox.information(self, "Export", "Select a card first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export card",
            "card.md",
            "Markdown (*.md);;Plain text (*.txt);;JSON (*.json)",
        )
        if not path:
            return
        if path.endswith(".json"):
            fmt = "json"
        elif path.endswith(".md"):
            fmt = "markdown"
        else:
            fmt = "plain"
        _suffix, text = export_card(self._cards[row], fmt)
        Path(path).write_text(text, encoding="utf-8")
        card = self._cards[row]
        try:
            record_usage(
                card.get("selected_patterns") or [],
                event="exported",
                card_id=card.get("id"),
                ledger_path=self._config.paths.usage_path,
            )
        except OSError:
            pass
        self.statusBar().showMessage(f"Exported → {path}.", 8000)

    def _on_feedback(self) -> None:
        row = self.cards_list.currentRow()
        if row < 0 or row >= len(self._cards):
            QMessageBox.information(self, "Feedback", "Select a card first.")
            return
        card = self._cards[row]
        save_feedback(
            {
                "card_id": card.get("id"),
                "rating": self.rating_combo.currentText(),
                "note": self.note_edit.toPlainText(),
            },
            self._config.paths.feedback_path,
        )
        self.statusBar().showMessage("Feedback saved.", 6000)
        self.note_edit.clear()

    def _on_card_context_menu(self, position) -> None:
        row = self.cards_list.indexAt(position).row()
        if row < 0 or row >= len(self._cards):
            return
        card = self._cards[row]
        menu = QMenu(self)
        regen = menu.addAction("Regenerate this card")
        more_like = menu.addAction("More like this")
        menu.addSeparator()
        copy_text_act = menu.addAction("Copy text")
        copy_json_act = menu.addAction("Copy JSON")
        copy_toon_act = menu.addAction("Copy TOON")
        export_act = menu.addAction("Export…")
        menu.addSeparator()
        discard = menu.addAction("Discard card")
        chosen = menu.exec(self.cards_list.viewport().mapToGlobal(position))
        if chosen is None:
            return
        if chosen == copy_text_act:
            self.cards_list.setCurrentRow(row); self._on_copy_text()
        elif chosen == copy_json_act:
            self.cards_list.setCurrentRow(row); self._on_copy_json()
        elif chosen == copy_toon_act:
            self.cards_list.setCurrentRow(row); self._on_copy_toon()
        elif chosen == export_act:
            self.cards_list.setCurrentRow(row)
            self._on_export()
        elif chosen == discard:
            self._cards.pop(row)
            self.cards_list.takeItem(row)
        elif chosen == regen:
            # Re-run with same brief + mode, n=1, append the result.
            self._regenerate_one(card)
        elif chosen == more_like:
            self._more_like_this(card)

    def _regenerate_one(self, card: dict[str, Any]) -> None:
        self.brief_edit.setPlainText(self.brief_edit.toPlainText())  # keep
        self.n_spin.setValue(1)
        self.statusBar().showMessage("Regenerating one variant…", 6000)
        self._on_generate()

    def _more_like_this(self, card: dict[str, Any]) -> None:
        seed = card.get("why_this_works", "") or card.get("title", "")
        new_brief = (
            self.brief_edit.toPlainText().strip() +
            f"\n[more like] {seed[:200]}"
        )
        self.brief_edit.setPlainText(new_brief)
        self.n_spin.setValue(3)
        self.statusBar().showMessage("Generating 3 variants in the same direction…", 6000)
        self._on_generate()

    def _on_mode_changed(self, _index: int) -> None:
        mode = self._current_mode()
        self._update_brief_placeholder(mode)
        if mode in {"static_image", "image_editing"}:
            self.finetune_tabs.setCurrentIndex(0)
        else:
            self.finetune_tabs.setCurrentIndex(1)

    def _current_mode(self) -> str:
        data = self.mode_combo.currentData()
        return data or _MODES[0]

    def _select_mode(self, mode_id: str) -> None:
        for index in range(self.mode_combo.count()):
            if self.mode_combo.itemData(index) == mode_id:
                self.mode_combo.setCurrentIndex(index)
                return

    def _update_brief_placeholder(self, mode: str) -> None:
        example = _MODE_EXAMPLES.get(mode, "Describe what you want.")
        self.brief_edit.setPlaceholderText(
            f"Describe what you want.\n\nFor {_MODE_LABELS.get(mode, mode)}, e.g.:\n{example}"
        )

    def _insert_example_brief(self) -> None:
        mode = self._current_mode()
        example = _MODE_EXAMPLES.get(mode, "")
        if example:
            self.brief_edit.setPlainText(example)
            self.brief_edit.setFocus()

    def _on_history_open(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if not path.exists():
            return
        try:
            card = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if card not in self._cards:
            self._cards.insert(0, card)
            self.cards_list.insertItem(
                0,
                QListWidgetItem(f"(history)  {card.get('title', '(untitled)')}"),
            )
            self.cards_list.setCurrentRow(0)
            self.tabs.setCurrentIndex(0)

    # ----------------------------------------------------------------- helpers

    def _refresh_adapters(self) -> None:
        try:
            rows = list_adapters(load_adapters(self._adapters_dir))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Adapters", str(exc))
            return
        previous = self.target_combo.currentData() if self.target_combo.count() else None
        self.target_combo.clear()
        target_pref = self._config.gui.default_target or "generic"
        chosen_index = 0
        for index, row in enumerate(rows):
            label = f"{row['model_id']} — {row['adapter_status']}"
            self.target_combo.addItem(label, userData=row["model_id"])
            if row["model_id"] == (previous or target_pref):
                chosen_index = index
        self.target_combo.setCurrentIndex(chosen_index)

    def _open_brand_manager(self) -> None:
        from prompt_genius.gui.brand_dialog import BrandManagerDialog
        dialog = BrandManagerDialog(self, current_path=self._config.gui.brand_profile_path or "")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        path = dialog.selected_path()
        self._config.gui.brand_profile_path = path
        self._safe_save_config()
        self.brand_label.setText(self._brand_label_text())
        self.brand_label.setToolTip(
            path or "No brand profile active. Click Manage… to create one."
        )

    def _clear_brand_profile(self) -> None:
        self._config.gui.brand_profile_path = ""
        self._safe_save_config()
        self.brand_label.setText(self._brand_label_text())
        self.brand_label.setToolTip("")

    def _brand_label_text(self) -> str:
        path = self._config.gui.brand_profile_path
        return Path(path).name if path else "(none)"

    def _render_card(self, card: dict[str, Any]) -> str:
        compiled = card.get("compiled")
        if isinstance(compiled, list):
            return "\n\n".join(
                f"shot {i+1}:\n{(c or {}).get('text', '')}" + (
                    f"\n\n{(c or {}).get('negative_text', '')}"
                    if (c or {}).get("negative_text") else ""
                )
                for i, c in enumerate(compiled)
            )
        text = ((compiled or {}).get("text") or "")
        neg = ((compiled or {}).get("negative_text") or "")
        return text + (f"\n\n{neg}" if neg else "")

    def _load_history_into_panel(self) -> None:
        if not hasattr(self, "history_list"):
            return
        self.history_list.clear()
        history_dir = Path(self._config.paths.history_dir)
        if not history_dir.exists():
            return
        for path in sorted(history_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            label = f"{data.get('title', path.name)}  ·  {data.get('mode')} · {data.get('target_model')}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self.history_list.addItem(item)

    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        theme = self._config.gui.theme
        if theme == "light":
            app.setPalette(_light_palette())
        elif theme == "dark":
            app.setPalette(_dark_palette())
        else:
            app.setPalette(QApplication.style().standardPalette())


# --------------------------------------------------------------------- helpers

def _section(label: str) -> QLabel:
    widget = QLabel(f"<b>{label}</b>")
    widget.setStyleSheet("margin-top: 4px;")
    return widget


def _row(*items: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    for item in items:
        layout.addWidget(item)
    return container


def _form() -> tuple[QWidget, QFormLayout]:
    widget = QWidget()
    form = QFormLayout(widget)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    return widget, form


def _structured_from_dict(data: dict, target: str) -> StructuredPrompt:
    return StructuredPrompt(
        mode=data.get("mode", "static_image"),
        target_model=target,
        creative_intent=dict(data.get("creative_intent") or {}),
        selected_patterns=list(data.get("selected_patterns") or []),
        why_this_works=data.get("why_this_works", ""),
        negative_fragments=list(data.get("negative_fragments") or []),
        visual_parameters=data.get("visual_parameters"),
        video_parameters=data.get("video_parameters"),
        shot_number=data.get("shot_number"),
        duration_seconds=data.get("duration_seconds"),
        frame_role=data.get("frame_role"),
    )


def _light_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#fafafa"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#111111"))
    return palette


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1f1f23"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#26262c"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#eaeaea"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#eaeaea"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2c2c33"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#eaeaea"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3a6ea5"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return palette


def _load_splash_pixmap() -> QPixmap | None:
    """Find the bundled splash image; fall back to repo-root splash.png."""

    try:
        from importlib.resources import files
        path = files("prompt_genius.gui.assets") / "splash.png"
        pm = QPixmap(str(path))
        if not pm.isNull():
            return pm
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        pass
    # Fallbacks: repo-root splash.png next to cwd, or package source tree.
    for candidate in (Path("splash.png"), Path(__file__).resolve().parent / "assets" / "splash.png"):
        if candidate.exists():
            pm = QPixmap(str(candidate))
            if not pm.isNull():
                return pm
    return None


def _make_splash(app: QApplication) -> "QSplashScreen | None":
    pm = _load_splash_pixmap()
    if pm is None:
        return None
    # Pick a sensible on-screen size relative to the primary screen.
    screen = app.primaryScreen()
    if screen is not None:
        max_side = min(560, int(screen.availableGeometry().height() * 0.55))
    else:
        max_side = 520
    scaled = pm.scaled(
        max_side, max_side,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    splash = QSplashScreen(scaled, Qt.WindowType.WindowStaysOnTopHint)
    splash.setMask(scaled.mask())
    return splash


def _splash_msg(splash: "QSplashScreen | None", text: str) -> None:
    if splash is None:
        return
    splash.showMessage(
        text,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        Qt.GlobalColor.white,
    )
    QApplication.processEvents()


def _preimport_native_libs() -> None:
    """Initialize torch + sentence_transformers on the MAIN thread once.

    PyInstaller-bundled torch on macOS aborts with
    ``generic_type: cannot initialize type "GradBucket"`` when its C
    extension is first imported from a QThread instead of the main thread —
    the duplicate pybind11 type registration is triggered because Shiboken's
    lazy-import path re-enters the C module init from the worker. Loading
    here, before any QThread starts, guarantees a single initialization.
    """

    try:
        import torch  # noqa: F401
    except ImportError:
        return
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        pass


def main() -> int:
    _preimport_native_libs()

    # Make sure menus go to the macOS system menubar at the top of the screen
    # (the Qt default flips to in-window when this attribute is True).
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, False)

    app = QApplication(sys.argv)
    app.setApplicationName("🦊 Prompt Genius")
    app.setApplicationDisplayName("🦊 Prompt Genius")

    splash = _make_splash(app)
    if splash is not None:
        splash.show()
        _splash_msg(splash, "Starting Prompt Genius…")
        QApplication.processEvents()

    _splash_msg(splash, "Loading config + catalog…")
    window = MainWindow()

    backend = window._config.embeddings.backend
    _splash_msg(splash, f"Warming {backend} retrieval index…")

    def _finish() -> None:
        window.show()
        window.raise_()
        window.activateWindow()
        if splash is not None:
            splash.finish(window)

    if window._prewarm_worker is not None:
        worker = window._prewarm_worker

        def _on_ready(_stats):
            _finish()

        def _on_err(_msg):
            _finish()

        worker.ready.connect(_on_ready)
        worker.failed.connect(_on_err)

        # Safety net: never leave the splash up indefinitely.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(15_000, _finish)
    else:
        _finish()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
