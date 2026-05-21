"""Empacotamento do `dist/kuatia/` em `kuatia-portable-v<X.Y.Z>.zip`.

Chamado pelo `build/package.ps1` (Windows). Lógica em Python pra:
1. Ser testável sem precisar do PowerShell.
2. Multiplataforma (mesmo que o uso primário seja Windows).

Lê a versão do `pyproject.toml` — não hardcoded. Inclui um README dentro
do zip com instruções de descompactar + rodar.
"""

from __future__ import annotations

import sys
import tomllib
import zipfile
from pathlib import Path

README_TEMPLATE = """# Kuatia {version} — distribuição portátil

Ferramenta de transcrição local de áudio/vídeo usando Whisper + OpenVINO em
hardware Intel Core Ultra (iGPU Arc + NPU AI Boost). Roda 100% offline.

## Como usar

1. Descompacte este arquivo em qualquer pasta.
2. Garanta que `ffmpeg` está no PATH do Windows. Instale com:
   ```powershell
   winget install Gyan.FFmpeg
   ```
3. Rode `kuatia.exe`.
4. No 1º uso, o app vai oferecer baixar o modelo Whisper (~3 GB). O
   download acontece uma vez; runs seguintes usam o cache local
   (`%LOCALAPPDATA%\\kuatia\\models`).

## Modelos suportados

- `large-v3` (default, ~3 GB) — melhor qualidade
- `medium` (~1,5 GB) — mais rápido
- `small` (~500 MB) — mais leve

Pra trocar de modelo: combo "Modelo" na janela principal.

## NPU INT8 (avançado)

O NPU exige modelo quantizado em INT8. Use `kuatia-convert` (vem junto)
ou converta com Optimum/OpenVINO Toolkit e aponte via "Apontar modelo
manualmente" no diálogo do 1º run.
"""


def read_version(pyproject_path: Path) -> str:
    """Lê `project.version` do `pyproject.toml`. Lança `ValueError` se ausente."""
    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)
    try:
        return str(data["project"]["version"])
    except KeyError as exc:
        raise ValueError(f"Não achei project.version em {pyproject_path}") from exc


def zip_name(version: str) -> str:
    return f"kuatia-portable-v{version}.zip"


def build_zip(
    dist_dir: Path,
    output_zip: Path,
    version: str,
) -> Path:
    """Empacota `dist_dir` em `output_zip`, anexando um README com instruções.

    Lança `FileNotFoundError` se `dist_dir` não existir.
    """
    if not dist_dir.is_dir():
        raise FileNotFoundError(f"Diretório esperado não encontrado: {dist_dir}")

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    readme_text = README_TEMPLATE.format(version=version)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(dist_dir.rglob("*")):
            if path.is_dir():
                continue
            arcname = Path("kuatia") / path.relative_to(dist_dir)
            zf.write(path, arcname=str(arcname))
        zf.writestr("kuatia/README.txt", readme_text)

    return output_zip


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    repo_root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent.parent

    pyproject = repo_root / "pyproject.toml"
    version = read_version(pyproject)

    dist_dir = repo_root / "dist" / "kuatia"
    output_zip = repo_root / "dist" / zip_name(version)

    print(f"==> Empacotando {dist_dir} → {output_zip}")
    build_zip(dist_dir, output_zip, version)

    size_mb = output_zip.stat().st_size / (1024 * 1024)
    print(f"==> OK ({size_mb:.1f} MB)")
    if size_mb >= 500:
        print("AVISO: zip > 500 MB (RNF03 pede < 500 MB sem modelo).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
