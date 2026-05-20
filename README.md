# Kuatia

> *kuatia* (tupi): papel, escrita, desenho — o que se registra.

Transcrição local de áudio e vídeo com [Whisper](https://github.com/openai/whisper) (OpenAI, open-source, MIT) acelerada por [OpenVINO](https://docs.openvino.ai/) no hardware Intel Core Ultra (iGPU Arc + NPU AI Boost).

Tudo roda 100% offline. Nenhuma chamada a API externa em runtime.

## Hardware-alvo

Esse projeto foi pensado para Intel Core Ultra (Meteor Lake / Lunar Lake) no Windows nativo. WSL2 não tem passthrough estável para a iGPU/NPU Intel — use PowerShell, não Ubuntu.

| Device | O que é | Quando usar |
|---|---|---|
| `GPU` | Intel Arc iGPU | **Default**. Bom balanço, suporta FP16 e INT8, modelo dinâmico. |
| `NPU` | Intel AI Boost | Mais eficiente em energia, **exige INT8** e tem limitações de shape estática. |
| `CPU` | Os 12 cores do Ultra | Fallback se driver de GPU não carregar. |
| `AUTO` | OpenVINO escolhe | Útil pra testar rápido. |

## Pré-requisitos no Windows

Abra o **PowerShell** (não o WSL) e instale:

```powershell
# Gerenciador de versões Python + uv
winget install --id=astral-sh.uv -e

# ffmpeg (obrigatório para ler mp4/mp3)
winget install --id=Gyan.FFmpeg -e

# Drivers Intel atualizados (Windows Update já tende a ter, mas confirmar):
# - Intel Graphics Driver: https://www.intel.com/content/www/us/en/download-center/home.html
# - Intel NPU Driver:      https://www.intel.com/content/www/us/en/download/794734/intel-npu-driver-windows.html
```

Confirme que ficou tudo no PATH (pode precisar reabrir o PowerShell):

```powershell
uv --version
ffmpeg -version
```

## Setup do projeto

A pasta do projeto está no WSL em `\\wsl.localhost\Ubuntu\home\lucasalbini\personal\kuatia`. Você pode trabalhar direto por esse caminho UNC ou copiar para `C:\` (mais rápido no I/O):

```powershell
# Opção A: trabalhar in-place no caminho do WSL
cd \\wsl.localhost\Ubuntu\home\lucasalbini\personal\kuatia

# Opção B: copiar pra Windows (recomendado para performance)
robocopy \\wsl.localhost\Ubuntu\home\lucasalbini\personal\kuatia C:\dev\kuatia /E
cd C:\dev\kuatia
```

Crie o venv e instale as deps:

```powershell
uv sync
```

## Passo 1 — converter o modelo (uma vez só)

Baixa `openai/whisper-large-v3` do HuggingFace (~3 GB) e exporta para o formato OpenVINO IR.

```powershell
# Para GPU/CPU (FP16, melhor qualidade)
uv run kuatia-convert --model openai/whisper-large-v3 --out models\whisper-large-v3-ov

# Para NPU (INT8, obrigatório)
uv run kuatia-convert --model openai/whisper-large-v3 --out models\whisper-large-v3-ov-int8 --int8
```

O modelo fica em `models\whisper-large-v3-ov\`. Esse passo demora alguns minutos no primeiro download.

## Passo 2 — transcrever

```powershell
# Default: iGPU Intel Arc, idioma português
uv run kuatia-transcribe "audiencia.mp4"

# Logs detalhados (DEBUG)
uv run kuatia-transcribe "audiencia.mp4" --verbose

# Forçar NPU (precisa do modelo int8)
uv run kuatia-transcribe "audiencia.mp4" `
    --device NPU `
    --model-dir models\whisper-large-v3-ov-int8

# Detecção automática de idioma
uv run kuatia-transcribe "audio.mp3" --language auto

# Traduzir para inglês ao invés de transcrever
uv run kuatia-transcribe "audio.mp3" --task translate
```

A saída fica no mesmo diretório do input (salvo `--output-dir`):
- `<nome>.txt` — uma linha por fala, no formato `[HH:MM:SS,mmm --> HH:MM:SS,mmm] texto`
- `<nome>.srt` — legenda padrão com timestamps

## Performance esperada (Core Ultra 7 155U, large-v3)

Valores aproximados para 1 hora de áudio:

| Device | Modelo | Tempo | Notas |
|---|---|---|---|
| CPU | FP16 | ~50-70 min | Lento, usa só CPU |
| iGPU (Arc) | FP16 | ~8-12 min | Default recomendado |
| NPU | INT8 | ~6-10 min | Menor consumo de energia |

## Roadmap

A fase atual é CLI. A próxima entrega é uma **GUI portátil para Windows** com drag-and-drop de arquivo, progress bar, seleção de device e export direto para `.txt`, `.srt` e `.docx`. Veja `docs/adr/0001-stack-inicial.md` e as issues abertas no repositório para o desenho completo.

## Troubleshooting

**`Cannot find OpenCL device`** ao usar `--device GPU`: driver Intel Graphics desatualizado. Atualize via Windows Update ou Intel Driver Assistant.

**`NPU plugin not found`** ao usar `--device NPU`: instale o Intel NPU Driver (link nos pré-requisitos) e reinicie.

**`ffmpeg não encontrado`**: o PATH não pegou o `winget install`. Feche e reabra o PowerShell, ou rode `refreshenv` se tiver Chocolatey.

**Transcrição com lacunas/repetições**: large-v3 é melhor em PT-BR mas pode alucinar em trechos de silêncio. Não há fix simples; corte silêncios longos antes ou use `--language portuguese` explicitamente.

## Estrutura

```
.
├── pyproject.toml              # deps gerenciadas por uv
├── src/kuatia/
│   ├── cli.py                  # entry point CLI (kuatia-transcribe)
│   ├── convert_model.py        # exporta Whisper → OpenVINO IR
│   └── core/                   # API pura reutilizável (CLI + futura GUI)
│       ├── audio.py            # load_audio via ffmpeg
│       ├── errors.py           # exceptions tipadas
│       ├── transcriber.py      # Transcriber, Segment
│       └── writers.py          # write_txt, write_srt, write_vtt
├── docs/adr/                   # Architecture Decision Records
├── tests/                      # pytest
├── models/                     # gitignored, modelos convertidos
└── README.md
```

## Licença

MIT — veja `LICENSE`.
