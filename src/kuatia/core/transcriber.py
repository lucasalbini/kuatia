"""Wrapper sobre Whisper + OpenVINO com estado mantido entre chamadas.

A classe `Transcriber` separa carregamento de modelo (caro, idempotente)
de transcrição (chamável N vezes). Callbacks `on_progress` / `on_log`
permitem que a GUI receba eventos sem depender do logger global.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from optimum.intel.openvino import OVModelForSpeechSeq2Seq
from transformers import AutoProcessor, pipeline

from kuatia.core.audio import SAMPLE_RATE
from kuatia.core.errors import ModelNotFoundError, TranscriptionError

log = logging.getLogger("kuatia")

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[float], None]


@dataclass(frozen=True)
class Segment:
    """Trecho transcrito com timestamps em segundos."""

    start: float
    end: float
    text: str


def _chunks_to_segments(chunks: list[dict[str, Any]]) -> list[Segment]:
    """Filtra chunks vazios/sem início e completa fins faltantes."""
    valid: list[Segment] = []
    for chunk in chunks:
        start_ts, end_ts = chunk["timestamp"]
        if start_ts is None:
            continue
        if end_ts is None:
            end_ts = start_ts + 1.0
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        valid.append(Segment(float(start_ts), float(end_ts), text))
    return valid


class Transcriber:
    """Carrega modelo Whisper + OpenVINO e transcreve áudios.

    `load_model` é idempotente: chamadas subsequentes com (model_dir, device)
    idênticos reutilizam o pipeline já carregado.
    """

    def __init__(self) -> None:
        self._pipeline: Any | None = None
        self._loaded: tuple[Path, str] | None = None

    def load_model(self, model_dir: Path, device: str) -> None:
        if self._loaded == (model_dir, device):
            return
        if not model_dir.exists():
            raise ModelNotFoundError(
                f"Modelo não encontrado em {model_dir}. Rode `kuatia-convert` antes."
            )

        log.info("modelo: carregando %s no device=%s", model_dir.name, device)
        started = time.perf_counter()
        model = OVModelForSpeechSeq2Seq.from_pretrained(
            model_dir,
            device=device,
            ov_config={"PERFORMANCE_HINT": "LATENCY"},
        )
        processor = AutoProcessor.from_pretrained(model_dir)  # type: ignore[no-untyped-call]
        self._pipeline = pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            chunk_length_s=30,
            return_timestamps=True,
        )
        self._loaded = (model_dir, device)
        log.info("modelo: pronto em %.1fs", time.perf_counter() - started)

    def transcribe(
        self,
        audio: np.ndarray,
        language: str = "portuguese",
        task: str = "transcribe",
        on_progress: ProgressCallback | None = None,
        on_log: LogCallback | None = None,
    ) -> list[Segment]:
        if self._pipeline is None:
            raise TranscriptionError("Modelo não carregado. Chame load_model() antes.")

        def emit(msg: str) -> None:
            log.info(msg)
            if on_log is not None:
                on_log(msg)

        generate_kwargs: dict[str, Any] = {"task": task}
        if language != "auto":
            generate_kwargs["language"] = language

        emit(f"transcrição: iniciando (task={task}, lang={language})")
        if on_progress is not None:
            on_progress(0.0)

        started = time.perf_counter()
        try:
            result = self._pipeline(audio, generate_kwargs=generate_kwargs)
        except Exception as exc:
            raise TranscriptionError(f"Falha na transcrição: {exc}") from exc
        elapsed = time.perf_counter() - started

        raw_chunks = result.get("chunks") or []
        segments = _chunks_to_segments(raw_chunks)

        duration_sec = audio.size / SAMPLE_RATE
        realtime = duration_sec / elapsed if elapsed > 0 else 0.0
        emit(
            f"transcrição: {len(segments)} segments (de {len(raw_chunks)} chunks) "
            f"em {elapsed:.1f}s ({realtime:.2f}x realtime)"
        )
        if on_progress is not None:
            on_progress(1.0)

        return segments
