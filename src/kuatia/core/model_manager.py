"""Descoberta, download e conversão de modelos Whisper para OpenVINO IR.

Fluxo no 1º run da GUI: `available_models()` lista o que o app suporta,
`is_model_ready(name)` checa o cache local, e `download_and_convert(name)`
baixa do HF Hub + exporta para OpenVINO IR — registrando no cache pra
os runs seguintes.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("kuatia")

ProgressCallback = Callable[[float], None]

# Arquivo sentinela: se existe no diretório do modelo, considera-se pronto.
_READY_SENTINEL = "openvino_encoder_model.xml"


@dataclass(frozen=True)
class ModelInfo:
    """Metadados de um modelo suportado pelo Kuatia."""

    name: str  # nome curto: "large-v3", "medium", "small"
    hf_id: str  # id no HuggingFace: "openai/whisper-large-v3"
    size_mb: int  # tamanho aproximado em MB do snapshot HF


_MODELS: tuple[ModelInfo, ...] = (
    ModelInfo(name="large-v3", hf_id="openai/whisper-large-v3", size_mb=3000),
    ModelInfo(name="medium", hf_id="openai/whisper-medium", size_mb=1500),
    ModelInfo(name="small", hf_id="openai/whisper-small", size_mb=500),
)


def available_models() -> list[ModelInfo]:
    """Modelos suportados, na ordem de preferência (melhor qualidade primeiro)."""
    return list(_MODELS)


def get_model_info(name: str) -> ModelInfo:
    """Lookup por nome curto. Lança `ValueError` se desconhecido."""
    for info in _MODELS:
        if info.name == name:
            return info
    valid = ", ".join(m.name for m in _MODELS)
    raise ValueError(f"Modelo desconhecido: {name!r}. Suportados: {valid}.")


def cache_dir() -> Path:
    """Diretório de cache dos modelos OpenVINO IR.

    Windows: `%LOCALAPPDATA%/kuatia/models`. Demais: `~/.cache/kuatia/models`.
    """
    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            return Path(local_app) / "kuatia" / "models"
    return Path.home() / ".cache" / "kuatia" / "models"


def model_dir(name: str) -> Path:
    """Caminho onde o modelo `name` é (ou será) cacheado."""
    get_model_info(name)  # valida nome antes
    return cache_dir() / name


def is_model_ready(name: str) -> bool:
    """`True` se o modelo já foi baixado e convertido localmente."""
    target = model_dir(name)
    return (target / _READY_SENTINEL).exists()


def download_and_convert(
    name: str,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Baixa do HF Hub e converte para OpenVINO IR, se ainda não estiver pronto.

    Idempotente: se `is_model_ready(name)` é `True`, retorna o path sem refazer.

    `on_progress` recebe `0.0` no início e `1.0` no fim. Granularidade
    intermediária fica como TODO — `optimum.from_pretrained(export=True)`
    bloqueia até finalizar e a barra do HF Hub vai pra stderr.
    """
    info = get_model_info(name)
    target = model_dir(name)

    if is_model_ready(name):
        log.info("model_manager: %s já pronto em %s", name, target)
        if on_progress is not None:
            on_progress(1.0)
        return target

    log.info(
        "model_manager: baixando + convertendo %s (~%d MB) -> %s",
        info.hf_id,
        info.size_mb,
        target,
    )
    if on_progress is not None:
        on_progress(0.0)

    # Import lazy: convert_model carrega optimum/transformers (caros).
    from kuatia.convert_model import convert

    target.mkdir(parents=True, exist_ok=True)
    convert(info.hf_id, target, int8=False)

    if on_progress is not None:
        on_progress(1.0)
    log.info("model_manager: %s pronto", name)
    return target
