"""Settings dialog. Binds every :class:`Config` field to a control.

Tabs: General · LLM · Embeddings · Paths · Advanced (retrieval + quality + video).
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from prompt_genius.gui.worker import MlxDownloadWorker

from prompt_genius.core.config import (
    Config,
    EmbeddingsConfig,
    GuiConfig,
    LlmConfig,
    PathsConfig,
    QualityWeights,
    RetrievalWeights,
    VideoDefaults,
    default_config_path,
)


_LLM_BACKENDS = ["heuristic", "claude", "codex", "mlx", "auto"]
_LLM_EFFORTS = ["low", "medium", "high"]
_THEMES = ["system", "light", "dark"]
_MODES = [
    "static_image",
    "image_editing",
    "text_to_video",
    "image_to_video",
    "storyboard",
    "keyframe",
]


class SettingsDialog(QDialog):
    def __init__(self, parent: QWidget | None, config: Config) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prompt Genius — Settings")
        self.resize(720, 620)
        self._config = config
        self._widgets: dict[str, dict[str, Any]] = {}

        layout = QVBoxLayout(self)

        tabs = QTabWidget(self)
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_llm_tab(), "LLM")
        tabs.addTab(self._build_embeddings_tab(), "Retrieval")
        tabs.addTab(self._build_paths_tab(), "Paths")
        if config.gui.show_advanced_settings:
            tabs.addTab(self._build_advanced_tab(), "⚙ Advanced (developer)")
        layout.addWidget(tabs, stretch=1)

        info = QLabel(
            f"Settings file: {default_config_path()}"
        )
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Reset
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Save,
            parent=self,
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Reset).clicked.connect(self._on_reset)
        layout.addWidget(buttons)

    # --------------------------------------------------------------------- tabs

    def _build_general_tab(self) -> QWidget:
        widget, form = self._form()
        gui = self._config.gui

        theme = QComboBox(); theme.addItems(_THEMES); theme.setCurrentText(gui.theme)
        form.addRow("Theme", theme)

        mode = QComboBox(); mode.addItems(_MODES); mode.setCurrentText(gui.default_mode)
        form.addRow("Default mode", mode)

        target = QLineEdit(gui.default_target)
        form.addRow("Default target adapter", target)

        n_spin = QSpinBox(); n_spin.setRange(1, 12); n_spin.setValue(gui.default_n)
        form.addRow("Default # cards", n_spin)

        risk = QComboBox(); risk.addItems(["safe", "creative", "experimental"]); risk.setCurrentText(gui.default_risk)
        form.addRow("Default risk", risk)

        brand_edit = QLineEdit(gui.brand_profile_path)
        brand_btn = QPushButton("Pick…")
        brand_btn.clicked.connect(lambda: _pick_file(self, brand_edit))
        brand_row = self._row(brand_edit, brand_btn)
        form.addRow("Brand profile", brand_row)

        allow = QCheckBox("Allow draft catalog items by default"); allow.setChecked(gui.allow_drafts)
        allow.setToolTip(
            "Draft items are seeded but unreviewed. Turn off once your team has "
            "promoted the patterns it trusts to 'active'."
        )
        form.addRow(allow)

        show_adv = QCheckBox(
            "Show advanced settings tab (retrieval / quality / video weights)"
        )
        show_adv.setChecked(gui.show_advanced_settings)
        show_adv.setToolTip(
            "These knobs let a developer tune the retrieval and scoring formulas. "
            "Reopen Settings after toggling to see the Advanced tab."
        )
        form.addRow(show_adv)

        self._widgets["gui"] = {
            "theme": theme,
            "default_mode": mode,
            "default_target": target,
            "default_n": n_spin,
            "default_risk": risk,
            "brand_profile_path": brand_edit,
            "allow_drafts": allow,
            "show_advanced_settings": show_adv,
        }
        return widget

    def _build_llm_tab(self) -> QWidget:
        widget, form = self._form()
        llm = self._config.llm

        backend = QComboBox(); backend.addItems(_LLM_BACKENDS); backend.setCurrentText(llm.backend)
        form.addRow("Backend", backend)

        effort = QComboBox(); effort.addItems(_LLM_EFFORTS); effort.setCurrentText(llm.effort)
        form.addRow("Effort", effort)

        claude_binary = QLineEdit(llm.claude_binary)
        form.addRow("`claude` binary", claude_binary)
        claude_args = QLineEdit(" ".join(llm.claude_args))
        form.addRow("`claude` args", claude_args)

        codex_binary = QLineEdit(llm.codex_binary)
        form.addRow("`codex` binary", codex_binary)
        codex_args = QLineEdit(" ".join(llm.codex_args))
        form.addRow("`codex` args", codex_args)

        timeout = QDoubleSpinBox(); timeout.setRange(1.0, 600.0); timeout.setValue(llm.timeout_seconds)
        form.addRow("CLI timeout (s)", timeout)

        form.addRow(QLabel("<b>MLX local model (Apple Silicon)</b>"))
        mlx_model = QLineEdit(llm.mlx_model)
        form.addRow("MLX model", mlx_model)

        mlx_tokens = QSpinBox(); mlx_tokens.setRange(64, 8192); mlx_tokens.setValue(llm.mlx_max_tokens)
        form.addRow("MLX max tokens", mlx_tokens)

        mlx_temp = QDoubleSpinBox(); mlx_temp.setRange(0.0, 2.0); mlx_temp.setSingleStep(0.05); mlx_temp.setValue(llm.mlx_temperature)
        form.addRow("MLX temperature", mlx_temp)

        hf_token = QLineEdit(llm.hf_token); hf_token.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Hugging Face token", hf_token)

        hf_cache = QLineEdit(llm.hf_cache_dir)
        hf_cache_btn = QPushButton("Pick…")
        hf_cache_btn.clicked.connect(lambda: _pick_dir(self, hf_cache))
        form.addRow("HF cache dir", self._row(hf_cache, hf_cache_btn))

        download_btn = QPushButton("Download MLX model now")
        download_btn.clicked.connect(self._on_download_mlx)
        form.addRow(download_btn)

        self._widgets["llm"] = {
            "backend": backend,
            "effort": effort,
            "claude_binary": claude_binary,
            "claude_args": claude_args,
            "codex_binary": codex_binary,
            "codex_args": codex_args,
            "timeout_seconds": timeout,
            "mlx_model": mlx_model,
            "mlx_max_tokens": mlx_tokens,
            "mlx_temperature": mlx_temp,
            "hf_token": hf_token,
            "hf_cache_dir": hf_cache,
        }
        return widget

    def _build_embeddings_tab(self) -> QWidget:
        widget, form = self._form()
        emb = self._config.embeddings

        backend = QComboBox()
        backend.addItem("Keyword TF-IDF (fastest)", userData="tfidf")
        backend.addItem("Keyword BM25 (better lexical match)", userData="bm25")
        backend.addItem("Semantic — sentence-transformers (best quality)", userData="dense")
        backend.addItem("Hybrid — BM25 + semantic (recommended)", userData="hybrid")
        for index in range(backend.count()):
            if backend.itemData(index) == emb.backend:
                backend.setCurrentIndex(index)
                break
        backend.setToolTip(
            "How catalog patterns are matched to your brief. "
            "Hybrid usually wins; dense needs sentence-transformers installed."
        )
        form.addRow("How to find patterns", backend)

        model = QLineEdit(emb.model_name)
        model.setToolTip("Hugging Face model used for semantic search — only when 'semantic' or 'hybrid' is active.")
        form.addRow("Semantic model", model)

        cache = QLineEdit(emb.cache_dir)
        cache_btn = QPushButton("Pick…")
        cache_btn.clicked.connect(lambda: _pick_dir(self, cache))
        form.addRow("Embeddings cache folder", self._row(cache, cache_btn))

        mmr = QDoubleSpinBox(); mmr.setRange(0.0, 1.0); mmr.setSingleStep(0.05); mmr.setValue(emb.mmr_diversity)
        mmr.setToolTip("How different the returned cards should be from each other. "
                       "0 = very similar, 1 = maximally varied.")
        form.addRow("Variety between results", mmr)

        per_type = QSpinBox(); per_type.setRange(1, 50); per_type.setValue(emb.per_type_limit)
        per_type.setToolTip("How many candidates per pattern type the retriever considers before ranking.")
        form.addRow("Candidates per pattern type", per_type)

        # Tuning knobs — hidden in plain sight, but renamed.
        k1 = QDoubleSpinBox(); k1.setRange(0.0, 5.0); k1.setSingleStep(0.1); k1.setValue(emb.bm25_k1)
        k1.setToolTip("BM25 k1 — how sharply repeated terms boost the score.")
        form.addRow("Keyword match strength", k1)

        b = QDoubleSpinBox(); b.setRange(0.0, 1.0); b.setSingleStep(0.05); b.setValue(emb.bm25_b)
        b.setToolTip("BM25 b — how much long descriptions are penalized vs short ones.")
        form.addRow("Length normalization", b)

        rrf = QSpinBox(); rrf.setRange(1, 1000); rrf.setValue(emb.hybrid_rrf_k)
        rrf.setToolTip("Hybrid RRF k — how forgiving Reciprocal Rank Fusion is to disagreement.")
        form.addRow("Hybrid blend constant", rrf)

        # 'prefer_dense' kept for backward compatibility but hidden from the UI.
        prefer = QCheckBox(); prefer.setChecked(emb.prefer_dense); prefer.setVisible(False)

        self._widgets["embeddings"] = {
            "backend": backend,
            "prefer_dense": prefer,
            "model_name": model,
            "cache_dir": cache,
            "mmr_diversity": mmr,
            "per_type_limit": per_type,
            "bm25_k1": k1,
            "bm25_b": b,
            "hybrid_rrf_k": rrf,
        }
        return widget

    def _build_paths_tab(self) -> QWidget:
        widget, form = self._form()
        paths = self._config.paths
        self._widgets["paths"] = {}
        for fld in fields(paths):
            current = getattr(paths, fld.name)
            edit = QLineEdit(str(current))
            btn = QPushButton("Pick…")
            btn.clicked.connect(lambda _checked=False, e=edit, name=fld.name: _pick_path(self, e, name))
            form.addRow(fld.name.replace("_", " "), self._row(edit, btn))
            self._widgets["paths"][fld.name] = edit
        return widget

    def _build_advanced_tab(self) -> QWidget:
        widget = QWidget(self)
        outer = QVBoxLayout(widget)

        outer.addWidget(QLabel("<b>Retrieval weights</b>"))
        retr_widget, retr_form = self._form()
        outer.addWidget(retr_widget)
        self._bind_dataclass(self._config.retrieval, retr_form, "retrieval")

        outer.addWidget(QLabel("<b>Quality weights</b>"))
        q_widget, q_form = self._form()
        outer.addWidget(q_widget)
        self._bind_dataclass(self._config.quality, q_form, "quality")

        outer.addWidget(QLabel("<b>Video defaults</b>"))
        v_widget, v_form = self._form()
        outer.addWidget(v_widget)
        self._bind_dataclass(self._config.video, v_form, "video")

        outer.addStretch(1)
        return widget

    # ---------------------------------------------------------- save / actions

    def _on_save(self) -> None:
        try:
            new_config = self._collect_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid value", str(exc))
            return
        # Friendly missing-CLI guard before persisting.
        if not _confirm_backend_available(self, new_config.llm.backend):
            return
        try:
            new_config.save(default_config_path())
        except Exception as exc:  # noqa: BLE001 — surface to user
            QMessageBox.critical(
                self,
                "Couldn't save settings",
                f"{exc}\n\nYour changes will only apply to this session.",
            )
            return
        self._config = new_config
        self.accept()

    def _on_reset(self) -> None:
        result = QMessageBox.question(
            self,
            "Reset settings",
            "Reset all settings to defaults? This cannot be undone.",
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        self._config = Config.default()
        self._config.save(default_config_path())
        self.accept()

    def _on_download_mlx(self) -> None:
        llm = self._collect_section(self._config.llm, "llm")
        try:
            import importlib
            importlib.import_module("huggingface_hub")
        except ImportError:
            QMessageBox.warning(
                self,
                "MLX download unavailable",
                "Install the MLX extra to download models:\n\n"
                "    pip install -e \".[mlx]\"",
            )
            return

        progress = QProgressDialog(
            f"Downloading {llm.mlx_model} from Hugging Face…\n"
            "This can take several minutes the first time.",
            "Cancel",
            0,
            0,
            self,
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)

        worker = MlxDownloadWorker(self, llm.mlx_model, llm.hf_token or None)

        def on_ok(path: str) -> None:
            progress.close()
            QMessageBox.information(self, "Model ready", f"Model files at:\n{path}")

        def on_err(message: str) -> None:
            progress.close()
            QMessageBox.critical(self, "MLX download failed", message)

        def on_cancel() -> None:
            # huggingface_hub doesn't support clean cancel, but we can detach.
            worker.requestInterruption()
            progress.close()

        worker.finished_ok.connect(on_ok)
        worker.finished_err.connect(on_err)
        progress.canceled.connect(on_cancel)
        worker.start()
        progress.show()

    def _collect_config(self) -> Config:
        return Config(
            paths=self._collect_section(self._config.paths, "paths"),
            llm=self._collect_section(self._config.llm, "llm"),
            embeddings=self._collect_section(self._config.embeddings, "embeddings"),
            retrieval=self._collect_section(self._config.retrieval, "retrieval"),
            video=self._collect_section(self._config.video, "video"),
            quality=self._collect_section(self._config.quality, "quality"),
            gui=self._collect_section(self._config.gui, "gui"),
            version=self._config.version,
        )

    def _collect_section(self, original, section: str):
        widgets = self._widgets.get(section, {})
        if not is_dataclass(original):
            return original
        kwargs: dict[str, Any] = {}
        for fld in fields(original):
            widget = widgets.get(fld.name)
            if widget is None:
                kwargs[fld.name] = getattr(original, fld.name)
                continue
            current = getattr(original, fld.name)
            kwargs[fld.name] = _read_widget(widget, current, fld.name)
        return type(original)(**kwargs)

    def _bind_dataclass(self, instance, form, section: str) -> None:
        self._widgets.setdefault(section, {})
        for fld in fields(instance):
            value = getattr(instance, fld.name)
            widget = _make_widget_for(value)
            form.addRow(fld.name.replace("_", " "), widget)
            self._widgets[section][fld.name] = widget

    # ------------------------------------------------------------------ utils

    @staticmethod
    def _form() -> tuple[QWidget, QFormLayout]:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        return widget, form

    @staticmethod
    def _row(*items: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        for item in items:
            layout.addWidget(item)
        return container


# ----------------------------------------------------------------- widget helpers

def _make_widget_for(value: Any) -> QWidget:
    if isinstance(value, bool):
        widget = QCheckBox()
        widget.setChecked(value)
        return widget
    if isinstance(value, int):
        widget = QSpinBox()
        widget.setRange(-10_000, 10_000)
        widget.setValue(value)
        return widget
    if isinstance(value, float):
        widget = QDoubleSpinBox()
        widget.setRange(-10_000.0, 10_000.0)
        widget.setDecimals(3)
        widget.setSingleStep(0.05)
        widget.setValue(value)
        return widget
    if isinstance(value, (list, tuple)):
        return QLineEdit(", ".join(str(v) for v in value))
    return QLineEdit("" if value is None else str(value))


def _read_widget(widget: QWidget, current: Any, name: str) -> Any:
    if isinstance(widget, QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QSpinBox):
        return widget.value()
    if isinstance(widget, QDoubleSpinBox):
        return widget.value()
    if isinstance(widget, QComboBox):
        data = widget.currentData()
        if data is not None:
            return data
        return widget.currentText()
    if isinstance(widget, QLineEdit):
        text = widget.text()
        if isinstance(current, tuple):
            return tuple(part.strip() for part in text.split(",") if part.strip())
        if isinstance(current, list):
            return [part.strip() for part in text.split(",") if part.strip()]
        # special-case args fields that store tuple of CLI args separated by spaces
        if name.endswith("_args"):
            return tuple(text.split())
        return text
    return current


def _pick_file(parent: QWidget, edit: QLineEdit) -> None:
    path, _ = QFileDialog.getOpenFileName(parent, "Pick file", edit.text() or "")
    if path:
        edit.setText(path)


def _pick_dir(parent: QWidget, edit: QLineEdit) -> None:
    path = QFileDialog.getExistingDirectory(parent, "Pick directory", edit.text() or "")
    if path:
        edit.setText(path)


def _pick_path(parent: QWidget, edit: QLineEdit, name: str) -> None:
    """Choose file or directory based on field name."""

    if name.endswith("_path") or "feedback" in name or "usage" in name or "versions" in name:
        path, _ = QFileDialog.getSaveFileName(parent, "Pick file", edit.text() or "")
    else:
        path = QFileDialog.getExistingDirectory(parent, "Pick directory", edit.text() or "")
    if path:
        edit.setText(path)


# --------------------------------------------------------- missing-CLI dialog


def _confirm_backend_available(parent: QWidget, backend: str) -> bool:
    """When the user picks an LLM backend that isn't installed, offer to open
    the install instructions. Returns True to proceed with save, False to stay
    in the dialog so they can change the backend.
    """

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    from prompt_genius.core.cli_check import backend_meta, is_backend_installed

    if is_backend_installed(backend):
        return True
    meta = backend_meta(backend)
    if not meta:
        return True  # unknown backend id; let it through silently
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(f"{meta['display_name']} not installed")
    box.setText(
        f"You picked <b>{meta['display_name']}</b> as the LLM backend, "
        f"but it isn't installed on this machine."
    )
    box.setInformativeText(
        f"Install with:\n\n    {meta['install_command']}\n\n"
        f"Or open the install instructions in your browser."
    )
    open_btn = box.addButton("Open install page", QMessageBox.ButtonRole.ActionRole)
    keep_btn = box.addButton("Keep this setting anyway", QMessageBox.ButtonRole.AcceptRole)
    pick_btn = box.addButton("Pick a different backend", QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(open_btn)
    box.exec()
    if box.clickedButton() is open_btn:
        QDesktopServices.openUrl(QUrl(meta["install_url"]))
        return False
    if box.clickedButton() is pick_btn:
        return False
    return True   # "Keep anyway" — they accept the fallback
