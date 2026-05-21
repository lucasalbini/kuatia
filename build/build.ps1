# Build PyInstaller do Kuatia GUI (Windows).
#
# Uso (no PowerShell, raiz do repo):
#   pwsh build\build.ps1
#
# Pré-requisitos:
#   - uv instalado (https://docs.astral.sh/uv/)
#   - Python 3.12 disponível (uv baixa se faltar)
#
# Saída esperada: dist\kuatia\kuatia.exe
#
# Lê a versão do pyproject.toml apenas pra logar — o nome do output
# fica fixo em `kuatia.exe` (versionamento entra no .zip, em package.ps1).

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

Write-Host "==> Limpando build/ e dist/ antigos..."
Remove-Item -Recurse -Force "$RepoRoot\build\kuatia" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$RepoRoot\dist" -ErrorAction SilentlyContinue

Write-Host "==> Instalando deps (uv sync)..."
& uv sync
if ($LASTEXITCODE -ne 0) { throw "uv sync falhou" }

Write-Host "==> Rodando PyInstaller..."
& uv run pyinstaller "$RepoRoot\build\kuatia.spec" --noconfirm --distpath "$RepoRoot\dist" --workpath "$RepoRoot\build\pyinstaller-work"
if ($LASTEXITCODE -ne 0) { throw "pyinstaller falhou" }

$ExePath = Join-Path $RepoRoot "dist\kuatia\kuatia.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build falhou: $ExePath não foi gerado"
}

$Size = (Get-Item $ExePath).Length / 1MB
$DistSize = (Get-ChildItem -Recurse "$RepoRoot\dist\kuatia" | Measure-Object -Property Length -Sum).Sum / 1MB

Write-Host ""
Write-Host "==> Build OK"
Write-Host "    exe: $ExePath ($([math]::Round($Size, 1)) MB)"
Write-Host "    dist\kuatia\ total: $([math]::Round($DistSize, 1)) MB"
Write-Host ""
Write-Host "Próximo passo: rodar pwsh build\package.ps1 pra gerar o .zip portátil."
