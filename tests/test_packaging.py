"""Tests de `build/package.py` — leitura de versão e geração do zip portátil."""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest


def _load_package_module() -> object:
    """Carrega `build/package.py` como módulo (build/ não é pacote)."""
    package_path = Path(__file__).resolve().parent.parent / "build" / "package.py"
    spec = importlib.util.spec_from_file_location("build_package", package_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_package"] = module
    spec.loader.exec_module(module)
    return module


package = _load_package_module()


def test_read_version_pyproject_do_repo() -> None:
    repo = Path(__file__).resolve().parent.parent
    version = package.read_version(repo / "pyproject.toml")
    assert isinstance(version, str) and version  # ex: "0.1.0"


def test_read_version_sem_campo_lanca(tmp_path: Path) -> None:
    p = tmp_path / "pyproject.toml"
    p.write_text("[project]\nname = 'x'\n")
    with pytest.raises(ValueError, match="project.version"):
        package.read_version(p)


def test_zip_name_formato() -> None:
    assert package.zip_name("0.1.0") == "kuatia-portable-v0.1.0.zip"


def test_build_zip_dist_inexistente(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        package.build_zip(tmp_path / "naoexiste", tmp_path / "out.zip", "0.1.0")


def test_build_zip_contem_conteudo_de_dist_e_readme(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist" / "kuatia"
    dist_dir.mkdir(parents=True)
    (dist_dir / "kuatia.exe").write_bytes(b"MZ\x90\x00fake")
    (dist_dir / "lib").mkdir()
    (dist_dir / "lib" / "openvino.dll").write_bytes(b"\x00" * 16)

    out = tmp_path / "kuatia-portable-v0.1.0.zip"
    result = package.build_zip(dist_dir, out, "0.1.0")
    assert result == out
    assert out.exists()

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "kuatia/kuatia.exe" in names
        assert "kuatia/lib/openvino.dll" in names
        assert "kuatia/README.txt" in names
        readme = zf.read("kuatia/README.txt").decode("utf-8")
        assert "Kuatia 0.1.0" in readme
        assert "winget install Gyan.FFmpeg" in readme


def test_main_retorna_0_em_zip_pequeno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Smoke do main: zip pequeno → exit 0."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname = 'x'\nversion = '0.1.0'\n")
    dist = repo / "dist" / "kuatia"
    dist.mkdir(parents=True)
    (dist / "kuatia.exe").write_bytes(b"x")

    rc = package.main([str(repo)])
    assert rc == 0
    out = repo / "dist" / "kuatia-portable-v0.1.0.zip"
    assert out.exists()


def test_readme_template_render() -> None:
    """README inclui versão e instrução de instalar ffmpeg."""
    rendered = package.README_TEMPLATE.format(version="1.2.3")
    assert "Kuatia 1.2.3" in rendered
    assert "ffmpeg" in rendered.lower()
    assert "%LOCALAPPDATA%" in rendered
