"""Converte um modelo Whisper do HuggingFace para o formato OpenVINO IR.

Esse passo é único por modelo. Depois de rodar, o diretório de saída pode ser
carregado direto pelo `kuatia-transcribe` em qualquer device suportado (CPU/GPU/NPU).

Exemplo:
    uv run kuatia-convert --model openai/whisper-large-v3 --out models/whisper-large-v3-ov
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from optimum.intel.openvino import OVModelForSpeechSeq2Seq
from transformers import AutoProcessor


def convert(model_id: str, output_dir: Path, int8: bool) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        print(f"[skip] {output_dir} já existe e não está vazio.", file=sys.stderr)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    load_kwargs: dict[str, object] = {"export": True, "compile": False}
    if int8:
        from optimum.intel import OVWeightQuantizationConfig

        load_kwargs["quantization_config"] = OVWeightQuantizationConfig(bits=8)

    print(f"Baixando e convertendo {model_id} -> {output_dir} ...")
    model = OVModelForSpeechSeq2Seq.from_pretrained(model_id, **load_kwargs)
    model.save_pretrained(output_dir)

    processor = AutoProcessor.from_pretrained(model_id)  # type: ignore[no-untyped-call]
    processor.save_pretrained(output_dir)

    print(f"Pronto. Modelo OpenVINO salvo em: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta Whisper para OpenVINO IR.")
    parser.add_argument(
        "--model",
        default="openai/whisper-large-v3",
        help="ID do modelo no HuggingFace (default: openai/whisper-large-v3).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("models/whisper-large-v3-ov"),
        help="Diretório de saída para o modelo OpenVINO IR.",
    )
    parser.add_argument(
        "--int8",
        action="store_true",
        help="Quantiza pesos para int8 (menos RAM, perda mínima de qualidade, exigido pela NPU).",
    )
    args = parser.parse_args()

    convert(args.model, args.out, args.int8)


if __name__ == "__main__":
    main()
