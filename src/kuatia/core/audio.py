"""Decodificação de áudio para Whisper via ffmpeg.

Usa subprocess + ffmpeg porque librosa.load não lê mp4 nativamente e
o pipeline via audioread é frágil no Windows.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from kuatia.core.errors import AudioLoadError

SAMPLE_RATE = 16_000

log = logging.getLogger("kuatia")


def load_audio(path: Path) -> np.ndarray:
    """Decodifica áudio para float32 mono 16 kHz via ffmpeg.

    Lança `AudioLoadError` se ffmpeg não estiver no PATH, o arquivo não
    existir, ou a decodificação retornar áudio vazio/falhar.
    """
    if shutil.which("ffmpeg") is None:
        raise AudioLoadError(
            "ffmpeg não encontrado no PATH. Instale com `winget install Gyan.FFmpeg` "
            "no Windows ou `sudo apt install ffmpeg` no Linux."
        )

    if not path.exists():
        raise AudioLoadError(f"Arquivo não encontrado: {path}")

    size_mb = path.stat().st_size / (1024 * 1024)
    log.info("ffmpeg: decodificando %r (%.1f MB)", path.name, size_mb)
    started = time.perf_counter()

    cmd = [
        "ffmpeg",
        "-nostdin",
        "-i",
        str(path),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-loglevel",
        "error",
        "-",
    ]
    log.debug("ffmpeg cmd: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise AudioLoadError(f"ffmpeg falhou ao decodificar {path}: {stderr}") from exc

    audio = np.frombuffer(result.stdout, dtype=np.float32)
    if audio.size == 0:
        raise AudioLoadError(f"ffmpeg não extraiu áudio de {path} (vazio).")

    elapsed = time.perf_counter() - started
    duration_min = audio.size / SAMPLE_RATE / 60
    log.info(
        "audio: %.1f min, %d Hz, %d samples (decodificado em %.1fs)",
        duration_min,
        SAMPLE_RATE,
        audio.size,
        elapsed,
    )
    return audio
