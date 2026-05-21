# PyInstaller spec do Kuatia GUI.
#
# Como rodar: `pwsh build/build.ps1` (preferido) ou diretamente
# `uv run pyinstaller build/kuatia.spec --noconfirm`.
#
# Foco: `--onedir --windowed` no Windows. Hidden imports listados pra
# cobrir o que `optimum`/`openvino`/`transformers` carregam dinamicamente.
# `collect_*` traz datas e submódulos automaticamente — sem isso o exe
# crasha na hora de carregar o modelo no 1º run.

# ruff: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent
ENTRY_SCRIPT = str(PROJECT_ROOT / "src" / "kuatia" / "gui" / "app.py")

HIDDEN_IMPORTS = [
    # OpenVINO + optimum
    "openvino",
    "openvino.runtime",
    "openvino_tokenizers",
    "optimum",
    "optimum.intel",
    "optimum.intel.openvino",
    # transformers (Whisper carrega via nome dinâmico)
    "transformers",
    "transformers.models.whisper",
    "transformers.models.whisper.modeling_whisper",
    "transformers.models.whisper.tokenization_whisper",
    "transformers.models.whisper.feature_extraction_whisper",
    # HF Hub
    "huggingface_hub",
    # Áudio
    "soundfile",
    "librosa",
    # PySide6
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Fluent UI
    "qfluentwidgets",
    "qframelesswindow",
    # python-docx
    "docx",
    "docx.oxml",
]

# Submódulos dinâmicos (transformers carrega `models.<arch>` por reflection).
HIDDEN_IMPORTS += collect_submodules("transformers.models.whisper")
HIDDEN_IMPORTS += collect_submodules("optimum.intel")
HIDDEN_IMPORTS += collect_submodules("qfluentwidgets")
HIDDEN_IMPORTS += collect_submodules("qframelesswindow")

DATAS = []
DATAS += collect_data_files("openvino")
DATAS += collect_data_files("openvino_tokenizers")
DATAS += collect_data_files("optimum")
DATAS += collect_data_files("transformers", include_py_files=False)
DATAS += collect_data_files("huggingface_hub")
DATAS += collect_data_files("librosa")
# qfluentwidgets traz fontes, ícones, .qss — todos como data files.
DATAS += collect_data_files("qfluentwidgets")
DATAS += collect_data_files("qframelesswindow")

ICON_PATH = PROJECT_ROOT / "build" / "kuatia.ico"
icon = str(ICON_PATH) if ICON_PATH.exists() else None

block_cipher = None

a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=DATAS,
    hiddenimports=HIDDEN_IMPORTS,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # Reduz tamanho — não usamos esses no runtime.
        "matplotlib",
        "scipy.misc",
        "tkinter",
        "pytest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    # transformers e optimum usam `inspect.getsource()` nos decorators de doc
    # (@add_start_docstrings, etc). Sem os .py originais (só bytecode no PYZ),
    # `inspect.getsource` lança OSError no import. Mantemos .py + .pyc desses
    # pacotes pra os decorators acharem o source.
    module_collection_mode={
        "transformers": "pyz+py",
        "optimum": "pyz+py",
    },
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="kuatia",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # --windowed
    icon=icon,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="kuatia",
)
