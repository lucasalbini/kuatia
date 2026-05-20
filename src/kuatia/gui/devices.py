"""Detecção de devices OpenVINO disponíveis pra popular o dropdown da GUI.

Encapsulado num módulo pra ser testável sem rodar a GUI e pra isolar a
dependência de `openvino.Core` — em CI Linux a lista virá só com `CPU`.
"""

from __future__ import annotations

import logging

log = logging.getLogger("kuatia")

NPU_LABEL_SUFFIX = " (requer modelo INT8)"


def detect_devices() -> list[str]:
    """Devices OpenVINO disponíveis, normalizados, com `AUTO` e `CPU` garantidos.

    Multi-GPU (`GPU.0`, `GPU.1`) é colapsado pra `GPU` — o OpenVINO aceita o
    alias e simplifica a UI. Em caso de erro ao consultar o `Core`, cai
    pro mínimo viável `['CPU', 'AUTO']`.
    """
    raw = _raw_available_devices()
    seen: list[str] = []
    for dev in raw:
        # Normaliza GPU.0/GPU.1 → GPU; mantém outros tal qual.
        normalized = dev.split(".", 1)[0] if dev.startswith("GPU") else dev
        if normalized not in seen:
            seen.append(normalized)
    if "CPU" not in seen:
        seen.append("CPU")
    if "AUTO" not in seen:
        seen.append("AUTO")
    return seen


def _raw_available_devices() -> list[str]:
    """Consulta `openvino.Core().available_devices`. Lista vazia em falha."""
    try:
        from openvino import Core

        return list(Core().available_devices)
    except Exception as exc:  # pragma: no cover — só em ambientes muito quebrados
        log.warning("openvino.Core().available_devices falhou: %s", exc)
        return []


def default_device(devices: list[str]) -> str:
    """GPU se presente, senão CPU (sempre presente, conforme `detect_devices`)."""
    if "GPU" in devices:
        return "GPU"
    return "CPU"


def device_label(device: str) -> str:
    """Texto exibido no dropdown — anota NPU com requisito de INT8."""
    if device == "NPU":
        return f"NPU{NPU_LABEL_SUFFIX}"
    return device
