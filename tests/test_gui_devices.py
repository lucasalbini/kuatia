"""Tests do `gui/devices.py` — mocka `openvino.Core` pra simular hardware."""

from __future__ import annotations

import pytest

from kuatia.gui import devices
from kuatia.gui.devices import default_device, detect_devices, device_label


def _patch_raw(monkeypatch: pytest.MonkeyPatch, raw_devices: list[str]) -> None:
    monkeypatch.setattr(devices, "_raw_available_devices", lambda: raw_devices)


def test_detect_devices_apenas_cpu_adiciona_auto(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_raw(monkeypatch, ["CPU"])
    assert detect_devices() == ["CPU", "AUTO"]


def test_detect_devices_cpu_gpu_npu(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_raw(monkeypatch, ["CPU", "GPU", "NPU"])
    assert detect_devices() == ["CPU", "GPU", "NPU", "AUTO"]


def test_detect_devices_multi_gpu_colapsa_para_um(monkeypatch: pytest.MonkeyPatch) -> None:
    """`GPU.0` + `GPU.1` → único `GPU` (OpenVINO aceita o alias)."""
    _patch_raw(monkeypatch, ["CPU", "GPU.0", "GPU.1", "NPU"])
    assert detect_devices() == ["CPU", "GPU", "NPU", "AUTO"]


def test_detect_devices_falha_no_core_fallback_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `Core` ou erro: garante ao menos CPU + AUTO."""
    _patch_raw(monkeypatch, [])
    assert detect_devices() == ["CPU", "AUTO"]


def test_detect_devices_auto_ja_presente_nao_duplica(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_raw(monkeypatch, ["CPU", "AUTO"])
    assert detect_devices() == ["CPU", "AUTO"]


def test_default_device_prefere_gpu() -> None:
    assert default_device(["CPU", "GPU", "AUTO"]) == "GPU"


def test_default_device_sem_gpu_usa_cpu() -> None:
    assert default_device(["CPU", "AUTO"]) == "CPU"


def test_device_label_npu_ganha_aviso() -> None:
    assert device_label("NPU") == "NPU (requer modelo INT8)"


def test_device_label_demais_passam_inalterados() -> None:
    assert device_label("CPU") == "CPU"
    assert device_label("GPU") == "GPU"
    assert device_label("AUTO") == "AUTO"
