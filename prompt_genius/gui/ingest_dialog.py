"""File → Ingest CSV… dialog.

Pick one or more CSV datasets, see the delta (new / duplicate / invalid) for
each, then confirm to write the deduplicated new rows into ``raw_corpus/``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from prompt_genius.core.ingest import (
    IngestPlan,
    apply_plan,
    plan_ingest,
    write_stub_adapter_if_missing,
)


class IngestDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        raw_corpus_dir: Path,
        adapters_dir: Path,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ingest CSV prompts")
        self.resize(900, 560)
        self._raw_corpus_dir = raw_corpus_dir
        self._adapters_dir = adapters_dir
        self._plans: list[IngestPlan] = []
        self._files: list[Path] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Top: file row
        top = QHBoxLayout()
        self.summary_label = QLabel(
            "Pick one or more CSV files. Prompt Genius detects each file's "
            "schema and shows the delta against the current corpus before "
            "writing anything."
        )
        self.summary_label.setWordWrap(True)
        top.addWidget(self.summary_label, stretch=1)
        pick_btn = QPushButton("Pick CSV files…")
        pick_btn.clicked.connect(self._pick_files)
        top.addWidget(pick_btn)
        layout.addLayout(top)

        # Preview table
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(
            ["File", "Model id", "Rows in CSV", "New", "Duplicates"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents,
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table, stretch=1)

        # Options
        self.auto_adapter_check = QCheckBox(
            "Auto-create a stub adapter when a new model id appears"
        )
        self.auto_adapter_check.setChecked(True)
        layout.addWidget(self.auto_adapter_check)

        self.warnings_label = QLabel("")
        self.warnings_label.setStyleSheet("color: #c0392b;")
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Ingest")
        buttons.accepted.connect(self._on_apply)
        buttons.rejected.connect(self.reject)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(buttons)

    # ----------------------------------------------------- handlers

    def _pick_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pick prompt CSVs", "", "CSV (*.csv)",
        )
        if not files:
            return
        self._files = [Path(f) for f in files]
        self._refresh_plans()

    def _refresh_plans(self) -> None:
        self._plans = []
        warnings: list[str] = []
        self.table.setRowCount(0)
        for path in self._files:
            try:
                plan = plan_ingest(path, self._raw_corpus_dir)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"{path.name}: {exc}")
                continue
            self._plans.append(plan)
            if plan.fmt.missing_required:
                warnings.append(
                    f"{path.name}: missing columns {plan.fmt.missing_required} "
                    f"(detected {plan.fmt.detected_columns})"
                )
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(path.name))
            self.table.setItem(row, 1, QTableWidgetItem(plan.fmt.model_id))
            self.table.setItem(row, 2, QTableWidgetItem(str(plan.total_input)))
            new_item = QTableWidgetItem(str(len(plan.new_rows)))
            new_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, new_item)
            dup_item = QTableWidgetItem(str(plan.duplicate_rows))
            dup_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 4, dup_item)
        self.warnings_label.setText("\n".join(warnings))

    def _on_apply(self) -> None:
        if not self._plans:
            QMessageBox.information(self, "Ingest", "Pick at least one CSV first.")
            return
        applied: list[str] = []
        skipped: list[str] = []
        for plan in self._plans:
            if plan.fmt.missing_required:
                skipped.append(plan.fmt.path.name)
                continue
            if not plan.new_rows:
                skipped.append(f"{plan.fmt.path.name} (no new rows)")
                continue
            written = apply_plan(plan, self._raw_corpus_dir)
            applied.append(f"{plan.fmt.path.name} → {written.name if written else '?'} "
                           f"(+{len(plan.new_rows)} rows)")
            if self.auto_adapter_check.isChecked():
                adapter_path = write_stub_adapter_if_missing(
                    plan.fmt.model_id, self._adapters_dir,
                )
                if adapter_path:
                    applied.append(f"  ↳ stub adapter created: {adapter_path.name}")
        message = ["Ingest complete:", ""] + applied
        if skipped:
            message += ["", "Skipped:"] + skipped
        message += [
            "",
            "Caches were invalidated — the vocab and embeddings index will rebuild "
            "on the next generation.",
        ]
        QMessageBox.information(self, "Ingest", "\n".join(message))
        self.accept()
