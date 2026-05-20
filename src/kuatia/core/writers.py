"""Escritores de output: `.txt`, `.srt`, `.vtt`.

Recebem `Iterable[Segment]` para serem reutilizáveis por CLI e GUI sem
acoplamento ao pipeline de transcrição.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from kuatia.core.transcriber import Segment


def _format_timestamp(seconds: float) -> str:
    """Formato SRT: HH:MM:SS,mmm (vírgula nos milissegundos)."""
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - (h * 3600 + m * 60)
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _format_timestamp_vtt(seconds: float) -> str:
    """Formato WebVTT: HH:MM:SS.mmm (ponto nos milissegundos)."""
    return _format_timestamp(seconds).replace(",", ".")


def write_txt(segments: Iterable[Segment], output_path: Path) -> None:
    """Uma linha por segment, com timestamps `[start --> end] texto`."""
    lines = [
        f"[{_format_timestamp(s.start)} --> {_format_timestamp(s.end)}] {s.text}" for s in segments
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_srt(segments: Iterable[Segment], output_path: Path) -> None:
    """SubRip — formato `.srt` padrão."""
    lines: list[str] = []
    for idx, s in enumerate(segments, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_timestamp(s.start)} --> {_format_timestamp(s.end)}")
        lines.append(s.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_vtt(segments: Iterable[Segment], output_path: Path) -> None:
    """WebVTT — formato `.vtt` para players HTML5."""
    lines: list[str] = ["WEBVTT", ""]
    for s in segments:
        lines.append(f"{_format_timestamp_vtt(s.start)} --> {_format_timestamp_vtt(s.end)}")
        lines.append(s.text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")
