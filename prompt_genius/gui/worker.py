"""Background workers wrapping :mod:`prompt_genius.core` long-running calls.

All workers are pure consumers of the core API. Nothing in this module reaches
back into the GUI layer.
"""

from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import QObject, QThread, Signal
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PySide6 is not installed. Install the GUI extra: pip install -e \".[gui]\""
    ) from exc

from prompt_genius.core.brief_parsers import make_parser_from_config
from prompt_genius.core.config import Config
from prompt_genius.core.generate import card_to_card_dict, generate_cards


class MlxDownloadWorker(QThread):
    """Downloads an MLX model from Hugging Face on a background thread."""

    finished_ok = Signal(str)   # local path
    finished_err = Signal(str)  # error message

    def __init__(self, parent, model_name: str, hf_token: str | None) -> None:
        super().__init__(parent)
        self._model_name = model_name
        self._hf_token = hf_token

    def run(self) -> None:
        try:
            from prompt_genius.core.llm_local import download_mlx_model
        except ImportError as exc:
            self.finished_err.emit(
                "mlx-lm / huggingface_hub not installed. Run: pip install -e \".[mlx]\""
            )
            return
        try:
            path = download_mlx_model(self._model_name, hf_token=self._hf_token)
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(f"{type(exc).__name__}: {exc}")
            return
        if path:
            self.finished_ok.emit(path)
        else:
            self.finished_err.emit(
                "Download returned no path. Check the model name and HF token."
            )


class IndexPrewarmWorker(QThread):
    """Loads + warms the catalog (incl. dense embeddings model) at app launch."""

    ready = Signal(dict)        # {"items": N, "elapsed": s, "backend": str}
    failed = Signal(str)

    def __init__(self, parent: QObject | None, config: Config) -> None:
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        import time
        try:
            from prompt_genius.core.generate import get_or_load_catalog

            cfg = self._config
            t = time.time()
            catalog = get_or_load_catalog(
                cfg.paths.catalog_dir,
                backend=cfg.embeddings.backend,
                prefer_dense=cfg.embeddings.prefer_dense,
                model_name=cfg.embeddings.model_name,
                cache_dir=cfg.embeddings.cache_dir,
                bm25_k1=cfg.embeddings.bm25_k1,
                bm25_b=cfg.embeddings.bm25_b,
                rrf_k=cfg.embeddings.hybrid_rrf_k,
            )
            self.ready.emit({
                "items": len(catalog.items),
                "elapsed": time.time() - t,
                "backend": cfg.embeddings.backend,
            })
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class GenerateWorker(QThread):
    card_ready = Signal(dict)        # streams one card at a time
    cards_ready = Signal(list)       # fires once when generation is complete
    failed = Signal(str)
    tick = Signal(int)               # seconds elapsed since start (~1Hz)

    def __init__(self, parent: QObject | None, params: dict[str, Any], config: Config) -> None:
        super().__init__(parent)
        self._params = params
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:  # noqa: D401 — QThread API
        import threading
        import time

        def on_card(card) -> None:
            if self._cancelled:
                return
            self.card_ready.emit(card_to_card_dict(card))

        # Heartbeat — emit elapsed seconds so the UI shows a live counter
        # while we wait on subprocess LLM calls.
        started = time.time()
        ticker_stop = threading.Event()

        def _ticker() -> None:
            while not ticker_stop.wait(1.0):
                if self._cancelled:
                    return
                self.tick.emit(int(time.time() - started))

        ticker_thread = threading.Thread(target=_ticker, daemon=True)
        ticker_thread.start()

        try:
            cfg = self._config
            cards = generate_cards(
                self._params["brief"],
                mode=self._params["mode"],
                target_model=self._params.get("target") or None,
                n=int(self._params.get("n", cfg.gui.default_n)),
                adapters_dir=self._params.get("adapters_dir", cfg.paths.adapters_dir),
                catalog_dir=self._params.get("catalog_dir", cfg.paths.catalog_dir),
                allow_drafts=bool(self._params.get("allow_drafts", cfg.gui.allow_drafts)),
                risk_level=self._params.get("risk", cfg.gui.default_risk),
                brand_profile=self._params.get("brand_profile") or None,
                prefer_dense_embeddings=cfg.embeddings.prefer_dense,
                embeddings_model=cfg.embeddings.model_name,
                embeddings_cache_dir=cfg.embeddings.cache_dir,
                brief_parser=make_parser_from_config(cfg.llm),
                corpus_dir=self._params.get("corpus_dir", "raw_corpus"),
                usage_ledger=cfg.paths.usage_path,
                config=cfg,
                card_callback=on_card,
                should_cancel=lambda: self._cancelled,
            )
            if self._cancelled:
                return
            self.cards_ready.emit([card_to_card_dict(c) for c in cards])
        except Exception as exc:  # noqa: BLE001 — surface to UI
            if self._cancelled:
                return
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            ticker_stop.set()
