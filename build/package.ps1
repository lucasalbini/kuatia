# Empacotamento do dist\kuatia\ em zip portátil versionado.
#
# Uso:
#   pwsh build\package.ps1
#
# Pré-requisito: dist\kuatia\ existe (rodar pwsh build\build.ps1 antes).
#
# Saída: dist\kuatia-portable-v<X.Y.Z>.zip
#
# Versão e lógica de zip ficam em build\package.py (Python, testável).

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $RepoRoot

if (-not (Test-Path "$RepoRoot\dist\kuatia\kuatia.exe")) {
    throw "dist\kuatia\kuatia.exe não existe — rode pwsh build\build.ps1 primeiro."
}

Write-Host "==> Empacotando dist\kuatia\ em .zip portátil..."
& uv run python "$RepoRoot\build\package.py" "$RepoRoot"
if ($LASTEXITCODE -ne 0) { throw "package.py falhou (exit $LASTEXITCODE)" }

Get-ChildItem "$RepoRoot\dist\kuatia-portable-v*.zip" | ForEach-Object {
    Write-Host "    $($_.FullName) ($([math]::Round($_.Length / 1MB, 1)) MB)"
}
