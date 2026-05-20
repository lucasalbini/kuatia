# Kuatia — instruções para o Claude

## Visão
Ferramenta de transcrição local de áudio/vídeo usando OpenAI Whisper acelerado por OpenVINO em hardware Intel Core Ultra (iGPU Arc + NPU AI Boost). 100% offline.

Fase atual: **CLI funcional**. Próxima fase: **GUI portátil para Windows** (PySide6 + PyInstaller) com drag-and-drop, progress bar, seleção de device e export `.txt`/`.srt`/`.docx`. Roadmap completo em `docs/adr/0001-stack-inicial.md` e nas issues abertas.

## Como rodar
Alvo é **Windows nativo** (PowerShell), não WSL — passthrough de iGPU/NPU Intel em WSL não é confiável. Setup completo no `README.md`.

Comandos canônicos:
```powershell
uv sync                                                     # instala deps
uv run kuatia-convert --out models\whisper-large-v3-ov      # converte modelo (1x)
uv run kuatia-transcribe "arquivo.mp4"                      # transcreve
uv run kuatia-transcribe "arquivo.mp4" --verbose            # logs DEBUG
```

## Estrutura
```
src/kuatia/
├── cli.py              # entry point CLI (entry: kuatia-transcribe)
├── convert_model.py    # one-shot: HF → OpenVINO IR (entry: kuatia-convert)
└── core/               # API pura reutilizável (CLI + futura GUI)
    ├── audio.py        # load_audio via ffmpeg
    ├── errors.py       # AudioLoadError, ModelNotFoundError, TranscriptionError
    ├── transcriber.py  # Transcriber, Segment
    └── writers.py      # write_txt, write_srt, write_vtt
docs/adr/               # ADRs
tests/                  # pytest
models/                 # gitignored, modelos OV vão aqui
```

## Git workflow (override local)
- **Posso (Claude) revisar e mergear PRs automatizadas em `dev` neste projeto.** Override do default global (no global, só Lucas mergeia).
- Critérios obrigatórios antes do merge: CI verde, self-review com `/review` aplicado, sem comentários abertos pendentes, sem mudança fora do escopo da issue.
- **Squash merge** na entrada da `dev` (mantém histórico limpo). Mensagem do squash usa o título da PR.
- Continua valendo: merge `dev → prod` é manual do Lucas. Nunca mergeio em `prod`.

## Convenções específicas
- **Sem async.** É script CLI síncrono CPU/GPU-bound; o default global de `async em todo I/O` não se aplica aqui.
- **`subprocess` + `ffmpeg` para decodificar áudio**, não `librosa.load` direto — librosa não lê mp4 nativamente e o pipeline via audioread é frágil no Windows.
- **Device default é `GPU`** (iGPU Arc). NPU exige modelo int8 separado por causa da restrição de shape estática.
- **Modelo é parâmetro**, não hardcoded. Default `openai/whisper-large-v3` por ser o melhor em PT-BR.
- **Logging via módulo `logging`** com logger `"kuatia"`. Nada de `print()` no código de produção.

## Modelos LLM / serviços externos
Nenhum em runtime. Único acesso externo é o download inicial do modelo do HuggingFace Hub (passo de setup, não de uso).

## Variáveis de ambiente
- `HF_HOME` (opcional) — cache do HuggingFace. Default: `~/.cache/huggingface`.
- Nada mais. Não há `.env`.

## Notas
- Pipeline usa `transformers.pipeline("automatic-speech-recognition", ...)` com `chunk_length_s=30` para áudios longos. NÃO usa `openvino-genai.WhisperPipeline` (API menos estável entre versões).
- Output salva sempre `.txt` (uma linha por fala, com timestamps `[HH:MM:SS,mmm --> HH:MM:SS,mmm] texto`) e `.srt` (legenda padrão) no mesmo diretório do input.
- Flag `--verbose` ativa logs DEBUG (comando do ffmpeg, detalhes internos).
