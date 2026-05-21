# Contribuindo com o Kuatia

Obrigado pelo interesse! Issues e PRs são bem-vindas. Este doc cobre o
workflow básico — pra detalhes de arquitetura, ver o
[README](README.md) e os [ADRs](docs/adr/).

## Antes de abrir issue ou PR

- **Procure issues existentes** primeiro — pode ser que já esteja sendo
  trabalhado.
- **Toda tarefa começa por issue.** Se você quer mexer em algo sem issue,
  abra uma primeiro descrevendo o que pretende fazer.
- **Tamanho-alvo de issue:** algo que um dev sênior resolve em ~2h. Maior?
  Quebra em sub-issues.

## Setup de desenvolvimento

```powershell
git clone https://github.com/lucasalbini/kuatia.git
cd kuatia
uv sync           # instala todas as deps (inclui dev tools)
uv run pytest     # tudo verde antes de começar a mexer
```

## Workflow de PR

1. **Fork** o repo (ou crie branch direto se tem write access).
2. **Branch a partir de `dev`** com naming `<type>/<issue>-<slug>`:
   - `feat/42-rate-limit`
   - `fix/57-token-refresh`
   - `docs/13-readme-update`
   - Tipos: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `perf`
3. **Escreva testes.** PR sem teste é rejeitada — mesmo solo, mesmo MVP.
4. **Roda tudo verde local:**
   ```powershell
   uv run ruff check src tests build
   uv run ruff format --check src tests build
   uv run mypy src/
   uv run pytest --cov=src/kuatia/core
   ```
5. **Commit** com [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   feat: adicionar export pra .vtt
   fix: tratar áudio vazio sem crashar
   refactor: extrair writers em módulo separado
   ```
6. **Abre PR contra `dev`** (nunca contra `prod`). Linka a issue com `Closes #N`.
7. **CI verde + self-review** (`/review`) antes de pedir merge.

## Critérios de aceite de uma PR

- ✅ CI verde (lint, types, tests, coverage gate)
- ✅ Testes cobrindo o caso novo (regressão pra bug fix)
- ✅ Disciplina de escopo — não refatora fora da issue, não troca de versão de dep sem motivo
- ✅ Descrição da PR explica o **porquê** (3-6 bullets)
- ✅ Sem segredos (`.env`, tokens) no commit

## Tipos de mudança

| Tipo | Quando usar |
|---|---|
| `feat` | Funcionalidade nova exposta ao usuário |
| `fix` | Correção de bug; **comece pelo teste de regressão** |
| `refactor` | Mudança interna sem alteração de comportamento |
| `perf` | Otimização (inclua medições no PR) |
| `test` | Adicionar/melhorar testes |
| `docs` | README, ADR, comentários |
| `chore` | Setup, CI, deps, build |

## Estilo de código

- **Python idiomático**: type hints estritos (mypy `strict`), pathlib em vez de `os.path`, dataclasses pra estados.
- **Sem comentários redundantes**: comente quando o "porquê" não é óbvio do código.
- **Naming claro**: `transcribe_audio` vez de `do_it`. Identificadores em inglês quando público; comentários e mensagens em pt-BR.
- **Funções pequenas e coesas.** Se cresceu pra >50 linhas, provavelmente cabe dividir.

## Testes

- **Comportamento, não implementação.** Refactor interno não deve quebrar teste.
- **Nome descreve o caso:** `test_write_docx_sem_meta_usa_placeholder`, não `test_docx2`.
- **Um conceito por teste.** Vários asserts cobrindo o mesmo conceito é OK; vários conceitos pulam pra novo teste.
- **Mock no boundary**, não no detalhe: tests do worker mockam `_build_pipeline`, não cada classe do `optimum`/`transformers`.

## Coverage

- PR para `dev`: ≥ 80% em código novo.
- Merge `dev → prod`: ≥ 90% total (CI bloqueia).

## Reportar bugs

Use o [template de bug report](.github/ISSUE_TEMPLATE/bug_report.md). Inclua:
- Versão do Kuatia (zip portátil ou commit SHA)
- Windows version (`winver`)
- Hardware (modelo do processador Intel)
- Driver Intel Graphics / NPU versions
- Passos pra reproduzir
- Log da pasta `%LOCALAPPDATA%\kuatia\` se houver

## Propor features

Use o [template de feature request](.github/ISSUE_TEMPLATE/feature_request.md).
Antes de implementar mudança grande, abra uma issue de **discussão** primeiro
pra alinhar abordagem.

## Conduta

Trate todos com respeito. Pra reportar problemas, contato direto com
[Lucas Albini](mailto:lucasalbini@gmail.com).
