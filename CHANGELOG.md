# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto usa [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [Não lançado]

Nada por enquanto.

## [0.1.0] — 2026-05-21

Primeiro release. MVP funcional cobrindo CLI + GUI + empacotamento portátil.

### Adicionado

#### Core API (`kuatia.core`)
- `audio.load_audio(path)` — decode via ffmpeg pra `float32 mono 16 kHz`.
- `transcriber.Transcriber` — `load_model` idempotente + `transcribe` com
  callbacks `on_progress` / `on_log` pra integração com UI.
- `transcriber.Segment(start, end, text)` — dataclass tipada.
- `writers` — `write_txt`, `write_srt`, `write_vtt`, `write_docx` (com cabeçalho
  de metadados em parágrafos com timestamp em bold).
- `model_manager` — cache cross-platform (`%LOCALAPPDATA%\kuatia\models\` no
  Windows, `~/.cache/kuatia/models/` no resto), download via HuggingFace Hub,
  conversão pra OpenVINO IR.
- `errors` — exceptions tipadas: `AudioLoadError`, `ModelNotFoundError`,
  `TranscriptionError`.

#### CLI (`kuatia-transcribe`)
- Default: `large-v3` + GPU + português + saída `.txt` + `.srt`.
- Flags: `--model {large-v3,medium,small}`, `--device {CPU,GPU,NPU,AUTO}`,
  `--language`, `--task {transcribe,translate}`, `--model-dir` (override),
  `--output-dir`, `--verbose`.
- `kuatia-convert` — exporta modelo HF pra OpenVINO IR (suporta `--int8` pra NPU).

#### GUI (`kuatia-gui`)
- Visual **Fluent Design** (Microsoft Win11) via PySide6-Fluent-Widgets.
- Tema **auto** (segue claro/escuro do Windows).
- **Drag-and-drop** com validação visual (borda muda de cor para accept/reject).
- Extensões suportadas: `.mp4`, `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.webm`.
- Botão "Procurar…" com `QFileDialog` filtrado.
- Detecção automática de devices OpenVINO; NPU rotulado com "(requer modelo INT8)".
- **Worker thread Qt** — transcrição não bloqueia UI. Cancelamento por flag.
- Progress bar + log streamando linha-a-linha do core.
- Checkboxes pros formatos de saída (`.txt`/`.srt`/`.vtt`/`.docx`).
- Botão "Abrir pasta de saída" cross-platform (`os.startfile`, `xdg-open`, `open`).
- **Diálogo de 1ª execução**: oferece baixar modelo, pular, ou apontar pasta com
  modelo OpenVINO IR existente.
- Detecção de duração via `ffprobe` (gracioso se ausente).

#### Empacotamento
- PyInstaller `--onedir --windowed` em `build/kuatia.spec`.
- Script `build/build.ps1` (PowerShell): limpa + uv sync + pyinstaller.
- Script `build/package.ps1` + `build/package.py` (Python testável):
  empacota `dist/kuatia/` em `kuatia-portable-v<X.Y.Z>.zip` com README dentro.
- Versão lida do `pyproject.toml`, não hardcoded.

#### Documentação
- README com screenshots (light + dark), badges, install, quick start, FAQ.
- `CONTRIBUTING.md`, `CHANGELOG.md`, templates de issue/PR.
- `docs/adr/0001-stack-inicial.md` — registro da escolha de stack.
- `docs/release-checklist.md` — smoke E2E em VM Windows limpa.

#### CI / qualidade
- GitHub Actions: ruff (lint + format), mypy strict em `src/`, pytest.
- Coverage gate: ≥ 80% em `src/kuatia/core/` (PR pra `dev`).
- Coverage gate ≥ 90% pra merge `dev → prod` (job separado).
- 178 testes verdes, ~98% cobertura no core.

### Notas

- **Licença GPLv3** — exigida pela dependência `PySide6-Fluent-Widgets`.
- **Lazy import de `optimum`/`transformers`** — boot da GUI ~1s em vez de ~17s.
- **WSL não é suportado em runtime** — passthrough de iGPU/NPU Intel via WSL
  não é estável. Usar Windows nativo.

[Não lançado]: https://github.com/lucasalbini/kuatia/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lucasalbini/kuatia/releases/tag/v0.1.0
