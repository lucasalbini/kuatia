# Release checklist — smoke E2E em VM Windows limpa

Critério final pra cada release MVP: rodar o `.zip` portátil em uma máquina Windows 11
sem dev tools instalados, validando o fluxo completo da perspectiva do usuário final.
Pega regressões de hidden imports do PyInstaller, deps externas esquecidas (ffmpeg,
drivers Intel), e bugs de empacotamento que não aparecem em dev.

## Pré-requisitos do ambiente

- **Hospedeiro**: pode ser Hyper-V, VMware Workstation, VirtualBox, ou laptop físico
  com Windows 11 recém-instalado.
- **Guest**: Windows 11 atualizado, sem Python, sem Visual Studio, sem Git pré-instalado
  além do que vem com o Windows.
- **Sem internet só durante a transcrição**: o app pode (e deve) baixar o modelo na
  1ª execução; a transcrição em si tem que rodar 100% offline (RNF02 do ADR-0001).
- **Hardware**: idealmente um Intel Core Ultra (iGPU Arc + NPU) pra validar GPU/NPU.
  Sem Arc, o teste cobre só `--device CPU`.

## Artefato a testar

Antes de começar, garanta que existe um zip versionado:

```powershell
pwsh build\build.ps1     # gera dist\kuatia\kuatia.exe
pwsh build\package.ps1   # gera dist\kuatia-portable-v<X.Y.Z>.zip
```

Copie o `.zip` pra dentro da VM via pasta compartilhada, OneDrive, ou drag-and-drop
da hypervisor — não rode `git clone` lá dentro: o sentido é simular usuário final.

## Roteiro

Marque cada item ao executar e cole abaixo (`### Execução em <data>`) ao final.

### 0. Preparação da VM

- [ ] Windows 11 (Pro ou Home) atualizado via Windows Update.
- [ ] Logado com conta local ou Microsoft.
- [ ] Confirmar que **não existe** `python` no PATH (`where python` deve falhar).
- [ ] Confirmar que **não existe** `ffmpeg` no PATH (vai instalar logo abaixo).

### 1. Instalar pré-requisitos do usuário final

- [ ] Abrir `PowerShell` (não-admin, conta de usuário comum).
- [ ] Instalar `ffmpeg`:
      ```powershell
      winget install Gyan.FFmpeg
      ```
- [ ] Fechar e reabrir o PowerShell pra refresh do PATH.
- [ ] Validar:
      ```powershell
      ffmpeg -version
      ffprobe -version
      ```
      Espera-se output com versão; se falhar, ver troubleshooting do README.

### 2. Instalar drivers (se for testar GPU/NPU)

- [ ] **Intel Graphics Driver** atualizado via Windows Update ou Intel Driver Assistant
      (pra usar `--device GPU` ou `AUTO`).
- [ ] **Intel NPU Driver** instalado manualmente (pra usar `--device NPU` com modelo INT8).
- [ ] Reiniciar a VM se algum driver pediu.

### 3. Descompactar o app

- [ ] Copiar `kuatia-portable-v<X.Y.Z>.zip` pra `C:\Users\<voce>\Desktop\` (ou outro lugar).
- [ ] Botão direito → "Extrair tudo…" → escolher destino (ex: `C:\Users\<voce>\kuatia\`).
- [ ] Conferir que o destino tem `kuatia.exe` + diretório `_internal\` (ou similar do PyInstaller)
      + `README.txt`.

### 4. Smoke da GUI

- [ ] Duplo-clique em `kuatia.exe`.
- [ ] Janela "Kuatia — Transcrição local" abre sem erro/popup.
- [ ] Dialog "Baixar modelo large-v3?" aparece (já que o cache é limpo na VM).
- [ ] Cancelar com **X** → janela continua aberta, botão Transcrever desabilitado
      (estado "modelo não carregado").
- [ ] Reabrir o app (fechar e dar duplo-clique de novo) → dialog reaparece (não há
      `_manual_model_dir` persistido — esperado per AC #11 limitação).
- [ ] Clicar **Baixar agora** → progress bar aparece, log streama mensagens, botão
      Transcrever desabilitado durante.
- [ ] Aguardar o download (~3 GB; tempo depende da conexão e do tier — 10-30 min em
      conexão residencial).
- [ ] Ao terminar: progress bar some, botão Transcrever volta a habilitar.

### 5. Transcrição end-to-end (CPU)

- [ ] Trocar device pra **CPU** no combo (sempre disponível, baseline).
- [ ] Arrastar um arquivo de teste de 1 min (`.mp4` ou `.mp3`) pra dentro da janela.
- [ ] Área de drop mostra o nome do arquivo + duração (`1m 00s` ou similar).
- [ ] Marcar `.txt`, `.srt`, `.docx`.
- [ ] Clicar **Transcrever**.
- [ ] Botão vira "Cancelar", progress bar visível.
- [ ] Log do `transcribe` aparece (carregando modelo, iniciando, % de progresso).
- [ ] Ao terminar: log mostra "Transcrição concluída: N segments." + paths dos 3
      arquivos. Botão "Abrir pasta de saída…" aparece.
- [ ] Confirmar em `C:\Users\<voce>\Desktop\` (ou pasta do input) que os 3 arquivos
      existem com bytes > 0:
      - `<nome>.txt` com timestamps `[HH:MM:SS,mmm --> HH:MM:SS,mmm] texto`.
      - `<nome>.srt` legível em qualquer player (VLC + load subtitle).
      - `<nome>.docx` abrindo no Word/LibreOffice com cabeçalho + parágrafos.
- [ ] Clicar **Abrir pasta de saída…** → Explorer abre no diretório certo.

### 6. Transcrição GPU (se Arc disponível)

- [ ] Trocar device pra **GPU**, mesmo áudio.
- [ ] Reportar tempo gasto vs CPU (esperado ~3x mais rápido com Arc).

### 7. Transcrição NPU (se NPU disponível)

- [ ] Precisa de modelo INT8: rodar a partir da árvore com `uv` (não vem no zip).
  Alternativa: "Apontar modelo manualmente" pra uma pasta com OV INT8 que você converteu
  separadamente.
- [ ] Transcrever áudio curto; reportar funcionamento (ou bug).

### 8. Cancelamento

- [ ] Iniciar transcrição de áudio longo (5+ min).
- [ ] Clicar **Cancelar** mid-transcrição.
- [ ] Log mostra "cancelada"; botão volta a "Transcrever"; progress bar some.
- [ ] **Limitação esperada**: cancelar mid-inferência não interrompe o pipeline na hora
      — só segura o emit do `finished`. Tudo bem se o áudio terminou de processar e o
      resultado foi descartado.

### 9. Caminhos de erro

- [ ] Arrastar um arquivo `.txt` (não suportado): borda fica vermelha, drop rejeitado.
- [ ] Apagar manualmente o `openvino_encoder_model.xml` do cache, reabrir o app:
      dialog do 1º run reaparece.
- [ ] Renomear a pasta do modelo: clicar Transcrever → mensagem amigável "modelo não pronto".

### 10. Reabrir após sucesso

- [ ] Fechar o app.
- [ ] Reabrir → dialog do 1º run **não** aparece (cache persiste).
- [ ] Transcrever novamente, mais rápido (modelo já carregado em cache + reload do
      OpenVINO).

## Critério de "pronto"

- Todos os itens 0-5 verdes.
- Itens 6-7 verdes se tiver hardware Intel; senão marcar `N/A`.
- Itens 8-10 verdes.

Se **qualquer item falhar**, **abrir issue nova** com label `bug` e detalhes (log + screenshot
+ passos). **Não consertar nesta PR** — o objetivo é fotografar a release, não esconder bugs.

## Evidência

Cole abaixo um bloco a cada execução do checklist:

```
### Execução em YYYY-MM-DD por <quem>
- Versão testada: kuatia-portable-vX.Y.Z.zip
- VM: Windows 11 Pro 23H2, Intel Core Ultra 7 155U (ou outro)
- Drivers: Intel Graphics XX.X, NPU Driver XX.X
- Resultado:
  - Itens 0-5: OK
  - Item 6 GPU: OK (tempo X.Xs)
  - Item 7 NPU: pendente (sem modelo INT8 na máquina)
  - Itens 8-10: OK
- Issues abertas: #N (descrição curta), #M (...), …
- Screenshot/video: <link interno>
```
