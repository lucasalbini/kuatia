"""Export multi-formato e abertura de pasta no SO — extraído pra ser testável.

Centraliza a lógica de aplicar `core.writers` baseado em quais formatos
o usuário marcou, e de abrir a pasta no explorer nativo.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

from kuatia.core.transcriber import Segment
from kuatia.core.writers import DocxMeta, write_docx, write_srt, write_txt, write_vtt

log = logging.getLogger("kuatia")

WRITER_BY_FORMAT = {
    "txt": write_txt,
    "srt": write_srt,
    "vtt": write_vtt,
    # docx tratado à parte porque recebe `meta`.
}


def export_outputs(
    segments: list[Segment],
    base_path: Path,
    formats: Mapping[str, bool],
    docx_meta: DocxMeta | None = None,
) -> list[Path]:
    """Chama os writers selecionados em `formats` e retorna paths gerados.

    `base_path` é o caminho-base sem extensão (ex: `/out/audiencia`); cada
    writer concatena seu sufixo. Apenas formatos com valor `True` são gerados.
    """
    out: list[Path] = []
    for fmt, writer in WRITER_BY_FORMAT.items():
        if not formats.get(fmt, False):
            continue
        target = base_path.with_suffix(f".{fmt}")
        writer(segments, target)
        out.append(target)
        log.info("export: %s", target)

    if formats.get("docx", False):
        target = base_path.with_suffix(".docx")
        write_docx(segments, target, meta=docx_meta)
        out.append(target)
        log.info("export: %s", target)

    return out


def open_in_file_manager(path: Path) -> bool:
    """Abre `path` (pasta) no explorer nativo. Retorna `True` se conseguiu disparar.

    - Windows: `os.startfile`
    - macOS: `open`
    - Linux/outros: `xdg-open`
    """
    if not path.exists():
        log.warning("open_in_file_manager: %s não existe", path)
        return False
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except OSError as exc:
        log.warning("open_in_file_manager: falhou em %s: %s", path, exc)
        return False


def selected_formats(checks: Mapping[str, bool]) -> list[str]:
    """Lista dos formatos com `True`. Útil em logs."""
    return [fmt for fmt, checked in checks.items() if checked]


def at_least_one_selected(checks: Iterable[tuple[str, bool]] | Mapping[str, bool]) -> bool:
    """Verifica se pelo menos um formato está marcado."""
    if isinstance(checks, Mapping):
        return any(checks.values())
    return any(v for _, v in checks)
