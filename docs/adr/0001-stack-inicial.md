# ADR-0001: Stack inicial — Kuatia

- **Status:** Proposto
- **Data:** 2026-05-20
- **Última atualização:** 2026-05-20 (criação)
- **Autor:** Lucas Albini

## 1. Contexto e Problema

Lucas Albini precisa de uma ferramenta para transcrever áudios e vídeos longos (audiências, entrevistas, reuniões) com qualidade alta em PT-BR, **100% offline**, rodando em notebook Intel Core Ultra 7 155U (iGPU Arc + NPU AI Boost). Soluções SaaS (Otter, Rev, AssemblyAI) saem por dois motivos: custo recorrente e privacidade dos áudios.

O projeto começou como `whisper-local`, um CLI pequeno que orquestra OpenAI Whisper acelerado por OpenVINO. O CLI funciona, mas a meta agora é embrulhar em ferramenta de uso geral: **GUI portátil para Windows**, que pessoas não-dev possam baixar, descompactar e usar. Este ADR registra a stack escolhida para o caminho do CLI até essa ferramenta portátil.

### Requisitos Funcionais

- **RF01** — Transcrever arquivos locais de áudio/vídeo nos containers comuns (mp4, mp3, wav, m4a, flac, ogg, webm).
- **RF02** — Exportar pelo menos `.txt` com timestamps embarcados, `.srt` (legenda) e `.docx` (texto formatado).
- **RF03** — GUI Windows com drag-and-drop de arquivo, progress bar, log em tempo real, seleção de device.
- **RF04** — Suportar múltiplos tamanhos de modelo Whisper (`large-v3`, `medium`, `small`) escolhidos pelo usuário.
- **RF05** — Detectar e listar devices OpenVINO disponíveis (CPU/GPU/NPU) e permitir seleção.
- **RF06** — Idiomas: PT-BR (foco), inglês, auto-detect; modo `transcribe` e `translate` (para inglês).
- **RF07** — Modelo baixado no primeiro uso (não bundlado no `.zip` portátil); cache em `%LOCALAPPDATA%`.

### Requisitos Não-Funcionais

- **RNF01** — 100% offline em runtime. Único acesso externo permitido: download do modelo na primeira execução.
- **RNF02** — Performance: ≥4x realtime no iGPU Arc com `large-v3` (1 hora de áudio em menos de 15 minutos).
- **RNF03** — Distribuição: `.zip` portátil < 500 MB sem modelo, descompacta e roda sem instalador.
- **RNF04** — Tempo de carga do modelo na iGPU < 20 s.
- **RNF05** — GUI não pode travar durante transcrição (worker thread + sinais).
- **RNF06** — Cobertura de testes: ≥ 80% em PR para `dev`, ≥ 90% em merge `dev → prod`.
- **RNF07** — Sem licença paga em runtime; deps MIT/Apache/BSD/LGPL apenas.

## 2. Drivers de Decisão

1. **Privacidade** — áudios de audiência nunca podem sair da máquina. Anula opções SaaS e qualquer telemetria default.
2. **Performance no hardware Intel** — a justificativa do hardware do Lucas é justamente acelerar Whisper na iGPU/NPU. Qualquer stack que ignore o silício é desperdício.
3. **Portabilidade** — usuário final deve precisar de zero conhecimento: baixar, descompactar, abrir.
4. **Manutenibilidade single-dev** — Lucas mantém o projeto sozinho. Ferramentas e patterns devem ser reversíveis e bem documentados.
5. **Qualidade em PT-BR** — modelo escolhido tem que ser o estado da arte open-source em português brasileiro.
6. **Custo de bundle** — Whisper-large-v3 + OpenVINO + torch já são GBs de dependência. Cada escolha de lib precisa pesar isso.

## 3. Arquitetura Proposta

### 3.1 Visão Geral

```
+--------------------------------------+
|         GUI (PySide6 / Qt6)          |
|  drag-drop | progress | log | export |
+------------------+-------------------+
                   |
            QThread worker
                   |
                   v
+--------------------------------------+
|          Core (src/kuatia/core)      |
|  - audio.py        (ffmpeg loader)   |
|  - transcriber.py  (Whisper + OV)    |
|  - writers.py      (.txt/.srt/.docx) |
|  - model_manager.py (download/cache) |
+------------------+-------------------+
                   |
        +----------+----------+
        |                     |
        v                     v
+----------------+   +-------------------+
| ffmpeg (PATH)  |   |   OpenVINO IR     |
| subprocess     |   |   iGPU / NPU / CPU|
+----------------+   +-------------------+
                              ^
                              |
                     +-----------------+
                     | HF Hub (1x DL)  |
                     +-----------------+
```

### 3.2 Conceitos centrais

- **Modelo OV IR** — representação OpenVINO do Whisper, par de arquivos `openvino_model.xml` + `openvino_model.bin`. Gerado uma vez por `kuatia-convert` a partir do checkpoint HuggingFace.
- **Device** — backend OpenVINO. `GPU` = iGPU Intel Arc (default). `NPU` = AI Boost (exige modelo INT8). `CPU` = fallback. `AUTO` = OpenVINO escolhe.
- **Segment** — dataclass `(start: float, end: float, text: str)` representando uma fala. É o tipo canônico entre core e writers.
- **Worker thread** — `QThread` (ou `QRunnable`) que executa transcrição sem travar a UI. Comunica via signals `progress`, `log`, `finished`, `error`.
- **Cache do modelo** — diretório `%LOCALAPPDATA%\kuatia\models\<nome>\` com os arquivos OV IR. Carregado uma vez por sessão, reutilizado entre jobs (singleton `Transcriber`).

### 3.3 Fluxo de Dados — exemplo concreto

Caso: usuário arrasta `audiencia.mp4` (12 min, 80 MB) na janela.

1. **GUI** dispara worker passando `Path("audiencia.mp4")`, `device="GPU"`, `language="portuguese"`.
2. **Worker** chama `core.audio.load_audio(path)` →
   - subprocess `ffmpeg -i audiencia.mp4 -f f32le -ac 1 -ar 16000 -` (~2 s)
   - retorna `ndarray float32 (11_520_000,)` (mono 16 kHz)
3. **Worker** chama `core.transcriber.Transcriber.get_or_load(model_dir, device)` →
   - Se primeiro uso na sessão: `OVModelForSpeechSeq2Seq.from_pretrained(...)` (~15 s)
   - Senão: reutiliza singleton em memória
4. **Worker** chama `transcriber.transcribe(audio, language, task, on_progress=signal_emit)` →
   - `pipeline(...)(audio, chunk_length_s=30, return_timestamps=True)`
   - Emite `progress(i/total)` a cada chunk processado
   - Retorna `list[Segment]` (ex.: 47 segments)
5. **Worker** emite `finished(segments)`.
6. **GUI** (main thread) chama `writers.write_txt(segments, "audiencia.txt")`, `write_srt(...)`, `write_docx(...)` conforme checkboxes marcadas.

**Saídas geradas:**

```
audiencia.txt:
[00:00:01,200 --> 00:00:04,800] Boa tarde, Excelência.
[00:00:04,801 --> 00:00:09,400] Pode iniciar o depoimento.
...

audiencia.srt:
1
00:00:01,200 --> 00:00:04,800
Boa tarde, Excelência.
...

audiencia.docx:
[cabeçalho com nome, duração, modelo usado]
[tabela: timestamp | texto]
```

Tempo total esperado: ~3 min em iGPU Arc para esses 12 min de áudio.

### 3.4 Singleton de modelo

`Transcriber` mantém o modelo carregado em memória entre transcrições. Mudar de device força recarga. GUI exibe estado "modelo carregado / não carregado" no canto. Liberar memória explicitamente é fora de escopo do MVP (Python garbage collector resolve no fechamento).

## 4. Decisões Técnicas

### 4.1 Modelo de ASR — Whisper `large-v3`

**Decisão:** modelo default `openai/whisper-large-v3`, com `medium` e `small` como alternativas selecionáveis na GUI.

**Justificativa:** dos modelos open-source MIT, `large-v3` é o estado da arte em PT-BR (treinado em > 5M h, com viés explícito pra languages-other-than-english). Tradeoffs de tamanho/velocidade são deixados pro usuário escolher na UI.

**Alternativas:**

| Opção | Prós | Contras |
|---|---|---|
| **Whisper large-v3** | Melhor PT-BR open-source; MIT | 3 GB; mais lento |
| Whisper medium | 4x mais rápido | Qualidade significativamente pior em PT-BR |
| Whisper.cpp | C++, otimizado | Sem aceleração oficial NPU/iGPU Intel |
| Seamless M4T (Meta) | Multilíngue, multitask | Licença CC-BY-NC; qualidade PT-BR inferior |
| Distil-Whisper | Compacto, rápido | Treinado só em inglês |

**Notas:** `medium` e `small` ficam como opções secundárias na GUI (RF04) — não no MVP CLI.

### 4.2 Inferência — OpenVINO + optimum-intel

**Decisão:** `openvino` + `openvino-tokenizers` + `optimum-intel` para conversão HF → OV IR e inferência.

**Justificativa:** única stack com suporte oficial e estável para iGPU Arc e NPU AI Boost. `optimum.intel` dá API alto nível compatível com `transformers.pipeline`, evitando reimplementar I/O do Whisper.

**Alternativas:**

| Opção | Prós | Contras |
|---|---|---|
| **OpenVINO + optimum-intel** | Suporte oficial Intel; API HF | Versões acopladas (`openvino` ↔ `optimum` ↔ `transformers`); breaking changes |
| onnxruntime | Multiplataforma | Sem suporte NPU Intel; iGPU exige config manual |
| openvino-genai | API mais moderna pra LLMs | API instável entre 2024.X; falta abstração pipeline-style |
| torch direto | Mais simples | Sem aceleração iGPU/NPU; só CPU |

**Notas:** NPU exige modelo quantizado INT8 (restrição de shape estática). `kuatia-convert --int8` gera essa variante separada.

### 4.3 Interface gráfica — PySide6 (Qt6)

**Decisão:** PySide6 (LGPL) para a GUI desktop.

**Justificativa:** drag-and-drop, progress bar, threading e signals/slots são primitivos maduros do Qt; renderização nativa no Windows; LGPL permite distribuição com bundle. Casa com workflow de worker thread (RNF05).

**Alternativas:**

| Opção | Prós | Contras |
|---|---|---|
| **PySide6** | Maduro, nativo, threading sólido | ~80 MB no bundle |
| Tkinter + customtkinter | Leve, vem com Python | Threading manual; menos polido; drag-drop limitado |
| Web local (FastAPI + browser) | UI flexível, dev rápido | Depende de browser instalado; sensação não-nativa |
| Flet | Visual moderno (Flutter) | Menos maduro; comunidade pequena; bundle pesado |

### 4.4 Empacotamento portátil — PyInstaller `--onedir --windowed`

**Decisão:** PyInstaller modo `onedir`, sem modelo bundlado. Download na primeira execução.

**Justificativa:** `onedir` evita o cold-start lento do `onefile` (que descomprime tudo em `%TEMP%` cada vez); `--windowed` esconde o console no Windows. Bundlar o modelo (3 GB) inflaria o `.zip` para 5+ GB e violaria RNF03.

**Alternativas:**

| Opção | Prós | Contras |
|---|---|---|
| **PyInstaller `--onedir`** | Maduro; configurável; cold-start rápido | Precisa cuidar de hidden imports (optimum, openvino_tokenizers) |
| PyInstaller `--onefile` | 1 único `.exe` | Cold-start lento; extrai em %TEMP% toda execução |
| Nuitka | Binário menor; obfusca | OpenVINO/torch causam crashes; comunidade menor |
| Briefcase (BeeWare) | Multiplataforma | Overhead; menos usado em produção |

**Notas:** torch (~800 MB) é a dep mais pesada. Issue futura: avaliar wheel `torch` CPU-only se viável (Whisper só precisa de torch como dep transitiva do `transformers`).

### 4.5 Runtime — Python 3.12 + uv

**Decisão:** Python 3.12 fixo (`requires-python = ">=3.12,<3.13"`), gerenciado por `uv`. Dev dependencies via PEP 735 `[dependency-groups]`.

**Justificativa:** `openvino-tokenizers` ainda não publica wheels estáveis para 3.13 (em 2026-05). `uv` é o gerenciador Python mais rápido (Rust), com CI integrado e suporte nativo a PEP 735.

**Alternativas:**

| Opção | Prós | Contras |
|---|---|---|
| **Python 3.12 + uv** | Wheels estáveis; gerenciador rápido | Bloqueia 3.13 |
| Python 3.11 | Maior cobertura de wheels antigas | Sem improvements de 3.12 |
| Poetry | Maduro | Lento; menos integração com pipx/CI |
| Conda | Binários pré-compilados | Overhead; ruim pra distribuir end-user |

### 4.6 Decode de áudio — ffmpeg via subprocess

**Decisão:** `subprocess.run(["ffmpeg", ...])` para decodificar qualquer container → float32 mono 16 kHz.

**Justificativa:** `librosa.load` via `audioread` é frágil no Windows (especialmente com mp4); `soundfile` não lê containers de vídeo. ffmpeg é gold standard.

**Alternativas:**

| Opção | Prós | Contras |
|---|---|---|
| **subprocess + ffmpeg** | Robusto, lê tudo | Dep externa no PATH |
| librosa + audioread | Pure Python | Frágil no Windows; mp4 instável |
| pydub | API simples | Wrapper sobre ffmpeg, não simplifica |
| moviepy | Multimídia completa | Pesado, dep transitiva enorme |

**Notas:** ffmpeg não é bundlado no `.zip` portátil. README instrui `winget install Gyan.FFmpeg`. Issue futura: avaliar bundlar ffmpeg-essentials junto.

### 4.7 Qualidade de código — ruff + mypy --strict + pytest + detect-secrets

**Decisão:** stack moderna padrão. `pre-commit` obrigatório local; CI bloqueia merge.

**Justificativa:** `ruff` substitui `black + isort + flake8` com 1 ferramenta, 100x mais rápida. `mypy --strict` força tipagem completa. `detect-secrets` evita vazamento de credenciais.

**Alternativas:** descartadas — black+isort+flake8+pyright também funciona mas é mais lento e mais peças. Não há razão objetiva.

### 4.8 Branches e CI — trunk-based `dev` + `prod`

**Decisão:** feature branches saem de `dev`, voltam por PR squash. `dev → prod` por merge manual quando estável. CI roda em todo PR e push para `dev`/`prod`.

**Justificativa:** padrão do Lucas em outros projetos (definido no CLAUDE.md global). Trunk-based reduz overhead de release branch e merge hell.

**Alternativas:** GitFlow descartado por complexidade desnecessária pra single-dev.

## 5. Infraestrutura

Não há infraestrutura server-side. CI roda no **GitHub Actions** (`.github/workflows/ci.yml`):

- Runner: `ubuntu-latest` (testa core sem GUI nem inferência iGPU)
- Steps: install uv → install ffmpeg → `uv sync` → ruff check + format → mypy → pytest com coverage
- Gate adicional: na branch `prod`, coverage total ≥ 90% (lê `coverage.xml`)

Distribuição final é um `.zip` gerado por PyInstaller em runner Windows (a configurar como job opcional/release-only — issue #11).

## 6. Estrutura do Projeto

```
kuatia/
├── pyproject.toml                 # deps + scripts CLI
├── .pre-commit-config.yaml        # hooks locais
├── .github/workflows/ci.yml       # CI
├── CLAUDE.md                      # instruções pro Claude (este projeto)
├── README.md                      # user-facing
├── LICENSE                        # MIT
│
├── docs/adr/                      # Architecture Decision Records
│   └── 0001-stack-inicial.md      # este ADR
│
├── src/kuatia/
│   ├── __init__.py
│   ├── core/                      # API pura, sem UI/CLI [issue #1]
│   │   ├── audio.py
│   │   ├── transcriber.py
│   │   ├── writers.py
│   │   └── model_manager.py
│   ├── gui/                       # GUI PySide6 [issues #5-#10]
│   │   ├── main_window.py
│   │   ├── worker.py
│   │   └── widgets/
│   ├── cli.py                     # entry point CLI (ex-transcribe.py após refactor)
│   ├── convert_model.py           # existing — exporta HF → OV IR
│   └── transcribe.py              # existing — vai ser refactorado em core + cli
│
├── tests/
│   ├── __init__.py
│   ├── test_smoke.py              # bootstrap
│   ├── test_core_audio.py         # [issue #3]
│   ├── test_core_transcriber.py   # [issue #3]
│   └── test_writers.py            # [issue #3]
│
├── build/                         # scripts de empacotamento [issue #11]
│   ├── build.ps1
│   └── kuatia.spec
│
└── models/                        # gitignored, modelos OV locais
```

## 7. Segurança

App **single-user, local, sem auth**. Modelo de ameaça é correspondentemente simples — mas há vetores reais:

| Vetor | Descrição | Mitigação |
|---|---|---|
| Modelo malicioso | HF Hub comprometido entrega modelo adulterado | Pinar `revision` específica nos defaults; logar SHA256 do `.bin` baixado |
| Arquivo de áudio malicioso | ffmpeg parser bug explorado | ffmpeg em subprocess (isolamento de processo); só flags fixas (`-i <file> -f f32le -ac 1 -ar 16000 -`), nada do usuário |
| Path traversal | Usuário arrasta arquivo com nome construído | Saída sempre em `Path(input).parent / Path(input).stem`, sem manipulação de string |
| Vulns em deps antigas | torch/transformers com CVE | Dependabot ativado; revisão trimestral |
| Secrets no repo | API key, .env commitado | `detect-secrets` no pre-commit |
| Telemetria oculta | optimum/transformers fazendo "phone home" | Variável `HF_HUB_OFFLINE=1` após download inicial; revisar comportamento na issue #10 |

**Sem dados sensíveis em trânsito** após o setup inicial — todo processamento é local.

## 8. Estratégia de Evolução

### Fase MVP — 4-6 semanas (estado atual → entrega)

Objetivo: ferramenta portátil que o Lucas (e amigos) usam de verdade.

- ✅ CLI funcional (entregue)
- ✅ ADR-0001 (este)
- ✅ Setup de qualidade (pre-commit, CI, tests, branches)
- ⏳ Refactor core (issue #1)
- ⏳ Writer `.docx` (issue #2)
- ⏳ Tests do core (issue #3)
- ⏳ Model manager (issue #4)
- ⏳ GUI MVP (issues #5-#10)
- ⏳ Empacotamento `.zip` portátil (issues #11-#13)

**Critério de sucesso:** baixar o `.zip` em VM Windows limpa, descompactar, abrir, baixar modelo na 1ª execução, transcrever um áudio de 5 min e ter os 3 outputs (`.txt`, `.srt`, `.docx`) corretos no disco.

### Fase Beta — depois do MVP

Objetivo: usável por não-devs (jornalistas, advogados, pesquisadores).

- Edição inline de chunks antes de exportar
- `.docx` polido (formatação, header com metadados, hyperlinks de timestamp)
- Auto-detect de device + benchmark inicial sugerindo o melhor
- Tema escuro, i18n PT/EN, atalhos de teclado
- Manual de uso (`docs/manual.md`)

**Critério de sucesso:** 3 usuários externos testando sem suporte ativo do Lucas.

### Fase Produto — futuro distante

- Diarização (quem falou — D2)
- Streaming de microfone (transcrição ao vivo)
- Glossário customizado (jargão de domínio)
- Batch multi-arquivo
- Instalador `.msi` assinado (D4)
- Telemetria opt-in (D5)

**Critério de sucesso:** distribuição em listas de transcrição forensic / jornalismo.

## 9. Estimativa de Custos

Projeto pessoal, sem custos recorrentes. Hardware (notebook Core Ultra) já existente. CI no plano gratuito do GitHub Actions. Custos potenciais futuros (todos em **D**ecisões em **a**berto): code signing (~U$ 200/ano), domínio `kuatia.app` (opcional, ~U$ 20/ano).

## 10. Riscos e Mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|---|---|---|---|
| OpenVINO / optimum quebram compat entre versões | Alto | Médio | Pinar versões mínimas no `pyproject`; smoke test em CI; dependabot em PR de bump |
| Driver Intel iGPU/NPU desatualizado quebra inferência | Médio | Baixo | Documentado no README; fallback automático para CPU se device escolhido falhar |
| Modelo `large-v3` alucina em silêncio prolongado | Médio | Médio | Alertar usuário no README; oferecer `medium` na GUI; futura issue: VAD pré-segmentação |
| Bundle PyInstaller cresce > 1 GB | Alto | Médio | Avaliar `torch-cpu` wheel; exclude libs Qt não usadas; relatório de tamanho em CI |
| HF Hub indisponível no 1º run (offline, censura, falha) | Alto | Baixo | Permitir apontar pasta local manualmente; instruções de download alternativo |
| Worker thread Qt crasha sem limpar UI | Médio | Médio | Exception handler global no worker; UI volta a estado inicial; log para arquivo |
| ffmpeg não está no PATH na máquina do usuário | Alto | Alto | Detecção no boot da GUI; banner instrutivo com link `winget`; futura: bundlar ffmpeg-essentials |
| Whisper / OpenVINO mudam licença | Alto | Muito baixo | MIT/Apache são irrevogáveis nas versões já lançadas; ADR-NNN se fork for necessário |
| Tradução `translate` piora qualidade em PT | Baixo | Médio | UI deixa claro que `translate` é PT→EN, não cross-lingual STT |

## 11. Decisões em Aberto

| # | Decisão | Opções | Prazo |
|---|---|---|---|
| D1 | Suporte a Apple Silicon / Linux | core.ml (mac) / cuda (linux) / desligado | Pós-MVP |
| D2 | Diarização (identificar quem falou) | pyannote-audio (GPL!) vs alternativa MIT vs externo | Fase Beta |
| D3 | Coverage gate 80% no PR para `dev` | desligado até issue #3 / ativar com diff-cover / threshold absoluto | Quando issue #3 entregar |
| D4 | Code signing do executável | comprar certificado EV (~$200/ano) vs distribuir não-assinado | Fase Produto |
| D5 | Telemetria opt-in (device, modelo, duração) | nenhuma / opt-in via flag / opt-in com prompt no 1º run | Fase Produto |
| D6 | Bundlar ffmpeg-essentials no `.zip` portátil | bundlar (~80 MB) / instruir `winget` (atual) | Após smoke test em VM limpa (issue #13) |

## 12. Glossário

- **ASR** — Automatic Speech Recognition. O que Whisper faz.
- **Whisper** — modelo de ASR da OpenAI (open source, MIT).
- **OpenVINO** — toolkit da Intel para inferência otimizada em CPU/GPU/NPU.
- **OV IR** — OpenVINO Intermediate Representation. Par `xml + bin` que descreve o modelo otimizado.
- **iGPU** — GPU integrada à CPU. No Core Ultra é a Intel Arc.
- **NPU** — Neural Processing Unit. No Core Ultra é o "AI Boost".
- **optimum-intel** — biblioteca da HuggingFace que adapta modelos `transformers` para OpenVINO.
- **PySide6** — bindings oficiais de Qt6 para Python, licença LGPL.
- **uv** — gerenciador de ambiente Python da Astral, escrito em Rust.
- **PyInstaller** — empacota aplicação Python + deps em um diretório standalone executável.
- **Hatchling** — backend de build padrão usado pelo `pyproject.toml` deste projeto.
- **Segment** — nome interno do trecho transcrito (`start, end, text`); tipo canônico passado entre core e writers.
- **PEP 735** — proposta que padroniza `[dependency-groups]` no `pyproject.toml`. Usado aqui pro grupo `dev`.

## 13. Referências

- Whisper paper — https://arxiv.org/abs/2212.04356
- OpenVINO docs — https://docs.openvino.ai/2024/index.html
- optimum-intel — https://huggingface.co/docs/optimum/intel/index
- PySide6 — https://doc.qt.io/qtforpython-6/
- Intel Core Ultra NPU — https://www.intel.com/content/www/us/en/products/docs/processors/core-ultra/ai-pc.html
- uv — https://docs.astral.sh/uv/
- PEP 735 (Dependency Groups) — https://peps.python.org/pep-0735/
- PyInstaller — https://pyinstaller.org/en/stable/
- Conventional Commits — https://www.conventionalcommits.org/

## 14. Estado da Implementação

### 14.1 Entregue ✅

- CLI `kuatia-transcribe` e `kuatia-convert` em `src/kuatia/transcribe.py` e `src/kuatia/convert_model.py`
- Output `.txt` com timestamps embarcados (`[HH:MM:SS,mmm --> HH:MM:SS,mmm] texto`) e `.srt`
- Logging via módulo `logging` com flag `--verbose` (DEBUG)
- Setup base: `pyproject.toml` (`kuatia`), `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `tests/test_smoke.py`, branches `dev` e `prod`

### 14.2 Pendente dentro deste ADR

- Refactor do core em `src/kuatia/core/` (issue #1)
- Writer `.docx` (issue #2)
- Tests do core com coverage ≥ 80% (issue #3)
- Model manager com download na 1ª execução (issue #4)
- GUI PySide6 completa (issues #5-#10)
- Empacotamento `.zip` portátil via PyInstaller (issues #11-#13)

### 14.3 Fora de escopo deste ADR

- Diarização (D2 — Fase Beta)
- Telemetria (D5 — Fase Produto)
- Suporte Apple Silicon / Linux (D1 — Pós-MVP)
- Code signing (D4 — Fase Produto)

Esses itens, quando endereçados, ganham ADRs próprios que complementam ou supersedam este.

### 14.4 Critérios de calibração

- **Quando issue #1 entregar:** revisar §4.2 (API do core) e atualizar §3.4 (singleton de modelo).
- **Quando issue #11 entregar:** medir bundle final e atualizar §10 (risco "Bundle > 1 GB").
- **Quando GUI MVP entregar (issue #10):** validar RNF02 (4x realtime) e RNF05 (não trava UI) em VM Windows limpa.
- **Evitar:** estender este ADR para cobrir Fase Beta ou Produto. Decisões dessas fases devem virar ADRs novos.
