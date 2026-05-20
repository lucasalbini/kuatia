"""Helpers de seleção de arquivo e detecção de duração.

Funções puras testáveis sem mexer em Qt — mantém o `main_window.py` focado
em widgets e estado da UI.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("kuatia")

SUPPORTED_EXTENSIONS = frozenset({".mp4", ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm"})

# Filtro do QFileDialog (formato Qt: "Texto (*.ext1 *.ext2)").
FILE_DIALOG_FILTER = "Áudio/Vídeo ({patterns});;Todos os arquivos (*.*)".format(
    patterns=" ".join(sorted(f"*{ext}" for ext in SUPPORTED_EXTENSIONS))
)


def is_supported(path: Path) -> bool:
    """Verifica se a extensão de `path` está em `SUPPORTED_EXTENSIONS` (case-insensitive)."""
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def all_supported(paths: list[Path]) -> bool:
    """`True` se todos os paths têm extensão suportada e a lista não é vazia."""
    return bool(paths) and all(is_supported(p) for p in paths)


def get_audio_duration(path: Path) -> float | None:
    """Tenta extrair a duração em segundos via `ffprobe`. Retorna `None` em falha.

    Não levanta — o caller decide se mostra a duração ou um placeholder.
    """
    if shutil.which("ffprobe") is None:
        log.debug("ffprobe não está no PATH; pulando detecção de duração de %s", path.name)
        return None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, check=True, text=True, timeout=10)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        log.debug("ffprobe falhou em %s: %s", path.name, exc)
        return None

    raw = result.stdout.strip()
    if not raw or raw.lower() == "n/a":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def format_duration_short(seconds: float | None) -> str:
    """Duração curta pra UI: `1h 23m`, `5m 32s`, `42s`, ou `--:--` se `None`."""
    if seconds is None or seconds < 0:
        return "--:--"
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"
