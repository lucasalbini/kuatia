"""Transcreve um arquivo de áudio/vídeo usando Whisper + OpenVINO.

Pré-requisitos:
- ffmpeg disponível no PATH (para decodificar mp4/mp3/etc).
- Modelo já convertido para OpenVINO IR (rode `kuatia-convert` antes).

Exemplo:
    uv run kuatia-transcribe "audiencia.mp4" --device GPU --language portuguese
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from optimum.intel.openvino import OVModelForSpeechSeq2Seq
from transformers import AutoProcessor, pipeline

SAMPLE_RATE = 16_000

log = logging.getLogger("kuatia")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Silencia libs ruidosas em DEBUG (transformers, optimum).
    for noisy in ("transformers", "optimum", "urllib3", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        sys.exit(
            "ffmpeg não encontrado no PATH. Instale com `winget install Gyan.FFmpeg` "
            "no Windows ou `sudo apt install ffmpeg` no Linux."
        )


def load_audio(path: Path) -> np.ndarray:
    """Decodifica áudio para float32 mono 16 kHz via ffmpeg."""
    _ensure_ffmpeg()
    if not path.exists():
        sys.exit(f"Arquivo não encontrado: {path}")

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
    result = subprocess.run(cmd, capture_output=True, check=True)
    audio = np.frombuffer(result.stdout, dtype=np.float32)
    if audio.size == 0:
        sys.exit(f"ffmpeg não extraiu áudio de {path} (vazio).")

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


def _format_timestamp(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - (h * 3600 + m * 60)
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _iter_valid_chunks(chunks: list[dict[str, Any]]) -> list[tuple[float, float, str]]:
    """Filtra chunks vazios/sem início e completa fins faltantes."""
    valid: list[tuple[float, float, str]] = []
    for chunk in chunks:
        start_ts, end_ts = chunk["timestamp"]
        if start_ts is None:
            continue
        if end_ts is None:
            end_ts = start_ts + 1.0
        text = (chunk.get("text") or "").strip()
        if not text:
            continue
        valid.append((float(start_ts), float(end_ts), text))
    return valid


def write_txt_with_timestamps(chunks: list[tuple[float, float, str]], output_path: Path) -> None:
    lines = [
        f"[{_format_timestamp(start)} --> {_format_timestamp(end)}] {text}"
        for start, end, text in chunks
    ]
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_srt(chunks: list[tuple[float, float, str]], output_path: Path) -> None:
    lines: list[str] = []
    for idx, (start, end, text) in enumerate(chunks, start=1):
        lines.append(str(idx))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(text)
        lines.append("")
    output_path.write_text("\n".join(lines), encoding="utf-8")


def build_pipeline(model_dir: Path, device: str) -> Any:
    if not model_dir.exists():
        sys.exit(
            f"Modelo não encontrado em {model_dir}. Rode `kuatia-convert` antes."
        )
    log.info("modelo: carregando %s no device=%s", model_dir.name, device)
    started = time.perf_counter()
    model = OVModelForSpeechSeq2Seq.from_pretrained(
        model_dir,
        device=device,
        ov_config={"PERFORMANCE_HINT": "LATENCY"},
    )
    processor = AutoProcessor.from_pretrained(model_dir)
    pipe = pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        chunk_length_s=30,
        return_timestamps=True,
    )
    log.info("modelo: pronto em %.1fs", time.perf_counter() - started)
    return pipe


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcreve áudio/vídeo com Whisper + OpenVINO.")
    parser.add_argument("input", type=Path, help="Arquivo de áudio ou vídeo (mp4, mp3, wav, ...).")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("models/whisper-large-v3-ov"),
        help="Diretório do modelo OpenVINO IR (gerado por kuatia-convert).",
    )
    parser.add_argument(
        "--device",
        default="GPU",
        choices=["CPU", "GPU", "NPU", "AUTO"],
        help="Device OpenVINO para inferência (default: GPU = iGPU Intel Arc).",
    )
    parser.add_argument(
        "--language",
        default="portuguese",
        help="Idioma do áudio (default: portuguese). Use 'auto' para detectar.",
    )
    parser.add_argument(
        "--task",
        default="transcribe",
        choices=["transcribe", "translate"],
        help="transcribe = mesmo idioma; translate = traduz para inglês.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Diretório de saída para .txt e .srt (default: mesmo diretório do input).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Habilita logs DEBUG (comando do ffmpeg, detalhes internos).",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)
    wall_started = time.perf_counter()

    audio = load_audio(args.input)
    duration_sec = audio.size / SAMPLE_RATE

    pipe = build_pipeline(args.model_dir, args.device)

    generate_kwargs: dict[str, Any] = {"task": args.task}
    if args.language != "auto":
        generate_kwargs["language"] = args.language

    log.info(
        "transcrição: iniciando (task=%s, lang=%s)",
        args.task,
        args.language,
    )
    started = time.perf_counter()
    result = pipe(audio, generate_kwargs=generate_kwargs)
    elapsed = time.perf_counter() - started

    raw_chunks = result.get("chunks") or []
    chunks = _iter_valid_chunks(raw_chunks)
    realtime = duration_sec / elapsed if elapsed > 0 else 0.0
    log.info(
        "transcrição: %d chunks (de %d) em %.1fs (%.2fx realtime)",
        len(chunks),
        len(raw_chunks),
        elapsed,
        realtime,
    )

    out_dir = args.output_dir or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / args.input.stem
    txt_path = base.with_suffix(".txt")
    srt_path = base.with_suffix(".srt")

    write_txt_with_timestamps(chunks, txt_path)
    write_srt(chunks, srt_path)

    log.info("saída: %s", txt_path)
    log.info("saída: %s", srt_path)
    log.info("tempo total: %.1fs", time.perf_counter() - wall_started)


if __name__ == "__main__":
    main()
