"""Entry point CLI do kuatia.

Orquestra `core/audio` → `core/model_manager` → `core/transcriber` → `core/writers`.
A lógica de domínio fica nos módulos do core; aqui só ficam argparse, logging
e tradução de exceptions em exit codes.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from kuatia.core.audio import load_audio
from kuatia.core.errors import AudioLoadError, ModelNotFoundError, TranscriptionError
from kuatia.core.model_manager import available_models, download_and_convert
from kuatia.core.transcriber import Transcriber
from kuatia.core.writers import write_srt, write_txt

log = logging.getLogger("kuatia")


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for noisy in ("transformers", "optimum", "urllib3", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    model_choices = [m.name for m in available_models()]
    parser = argparse.ArgumentParser(description="Transcreve áudio/vídeo com Whisper + OpenVINO.")
    parser.add_argument("input", type=Path, help="Arquivo de áudio ou vídeo (mp4, mp3, wav, ...).")
    parser.add_argument(
        "--model",
        default="large-v3",
        choices=model_choices,
        help=(
            "Nome curto do modelo (default: large-v3). Baixa do HF Hub e converte pra "
            "OpenVINO IR no 1º run; cacheado depois disso."
        ),
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=None,
        help=(
            "Diretório de um modelo OpenVINO IR pré-convertido (sobrepõe --model). "
            "Útil pra modelo INT8 customizado ou local fora do cache."
        ),
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

    try:
        audio = load_audio(args.input)
        model_dir = args.model_dir or download_and_convert(args.model)
        transcriber = Transcriber()
        transcriber.load_model(model_dir, args.device)
        segments = transcriber.transcribe(audio, language=args.language, task=args.task)
    except (AudioLoadError, ModelNotFoundError, TranscriptionError) as exc:
        sys.exit(str(exc))

    out_dir = args.output_dir or args.input.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / args.input.stem
    txt_path = base.with_suffix(".txt")
    srt_path = base.with_suffix(".srt")

    write_txt(segments, txt_path)
    write_srt(segments, srt_path)

    log.info("saída: %s", txt_path)
    log.info("saída: %s", srt_path)
    log.info("tempo total: %.1fs", time.perf_counter() - wall_started)


if __name__ == "__main__":
    main()
