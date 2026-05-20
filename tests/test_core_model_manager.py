"""Tests do `core/model_manager.py` — mocka HF/optimum, não baixa em CI."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from kuatia.core import model_manager
from kuatia.core.model_manager import (
    ModelInfo,
    available_models,
    cache_dir,
    download_and_convert,
    get_model_info,
    is_model_ready,
    model_dir,
)


def test_available_models_nao_vazio() -> None:
    models = available_models()
    assert models, "deve ter ao menos um modelo suportado"
    assert all(isinstance(m, ModelInfo) for m in models)
    assert {m.name for m in models} >= {"large-v3", "medium", "small"}


def test_get_model_info_conhecido() -> None:
    info = get_model_info("large-v3")
    assert info.hf_id == "openai/whisper-large-v3"
    assert info.size_mb > 0


def test_get_model_info_desconhecido() -> None:
    with pytest.raises(ValueError, match="Modelo desconhecido"):
        get_model_info("nao-existe")


def test_cache_dir_linux(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.core.model_manager.sys.platform", "linux")
    monkeypatch.setattr("kuatia.core.model_manager.Path.home", lambda: tmp_path)
    assert cache_dir() == tmp_path / ".cache" / "kuatia" / "models"


def test_cache_dir_windows_com_localappdata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("kuatia.core.model_manager.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    assert cache_dir() == tmp_path / "AppData" / "Local" / "kuatia" / "models"


def test_cache_dir_windows_sem_localappdata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Sem `LOCALAPPDATA` no Windows, cai no fallback `~/.cache`."""
    monkeypatch.setattr("kuatia.core.model_manager.sys.platform", "win32")
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr("kuatia.core.model_manager.Path.home", lambda: tmp_path)
    assert cache_dir() == tmp_path / ".cache" / "kuatia" / "models"


def test_model_dir_resolve(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)
    assert model_dir("large-v3") == tmp_path / "large-v3"


def test_model_dir_nome_invalido() -> None:
    with pytest.raises(ValueError, match="Modelo desconhecido"):
        model_dir("nao-existe")


def test_is_model_ready_false_quando_dir_nao_existe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)
    assert is_model_ready("large-v3") is False


def test_is_model_ready_true_quando_sentinel_existe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)
    target = tmp_path / "large-v3"
    target.mkdir()
    (target / "openvino_encoder_model.xml").write_text("<xml />")
    assert is_model_ready("large-v3") is True


def test_download_and_convert_pula_se_ja_pronto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Modelo já cacheado: não chama convert, callback em 1.0."""
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)
    target = tmp_path / "large-v3"
    target.mkdir()
    (target / "openvino_encoder_model.xml").write_text("<xml />")

    fake_convert = MagicMock()
    monkeypatch.setattr("kuatia.convert_model.convert", fake_convert)

    progress: list[float] = []
    result = download_and_convert("large-v3", on_progress=progress.append)

    assert result == target
    fake_convert.assert_not_called()
    assert progress == [1.0]


def test_download_and_convert_chama_convert_e_callbacks(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Modelo ausente: chama convert(hf_id, target, int8=False), callbacks 0→1."""
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)

    def fake_convert(hf_id: str, output_dir: Path, int8: bool) -> None:
        # Simula que convert cria o sentinela.
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "openvino_encoder_model.xml").write_text("<xml />")
        # Validações dos args passados
        assert hf_id == "openai/whisper-large-v3"
        assert output_dir == tmp_path / "large-v3"
        assert int8 is False

    monkeypatch.setattr("kuatia.convert_model.convert", fake_convert)

    progress: list[float] = []
    result = download_and_convert("large-v3", on_progress=progress.append)

    assert result == tmp_path / "large-v3"
    assert (result / "openvino_encoder_model.xml").exists()
    assert progress == [0.0, 1.0]


def test_download_and_convert_sem_callback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`on_progress=None` não quebra o fluxo."""
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)
    target = tmp_path / "medium"
    target.mkdir()
    (target / "openvino_encoder_model.xml").write_text("<xml />")

    monkeypatch.setattr("kuatia.convert_model.convert", MagicMock())

    result = download_and_convert("medium")
    assert result == target


def test_download_and_convert_modelo_desconhecido() -> None:
    with pytest.raises(ValueError, match="Modelo desconhecido"):
        download_and_convert("inexistente")


def test_download_and_convert_propaga_falha_do_convert(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Se convert lança, o erro propaga (CLI decide como tratar)."""
    monkeypatch.setattr("kuatia.core.model_manager.cache_dir", lambda: tmp_path)

    def bad_convert(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("rede caiu")

    monkeypatch.setattr("kuatia.convert_model.convert", bad_convert)

    with pytest.raises(RuntimeError, match="rede caiu"):
        download_and_convert("small")


def test_module_publica_ready_sentinel() -> None:
    """Confere que o nome do sentinela está consistente entre is_model_ready e docs."""
    assert model_manager._READY_SENTINEL == "openvino_encoder_model.xml"
