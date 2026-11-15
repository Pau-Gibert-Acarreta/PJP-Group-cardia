# Cardia: puesta en marcha completa en Windows.
#   powershell -ExecutionPolicy Bypass -File setup.ps1 [opciones]     (o doble clic en setup.cmd)
# Instala uv si falta y ejecuta scripts/bootstrap.py, que hace el resto. Opciones: --help
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'Instalando uv (gestor de Python de Astral)...'
    powershell -ExecutionPolicy ByPass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host 'No se ha podido instalar uv. Instalalo desde https://docs.astral.sh/uv/ y vuelve a ejecutar.'
        exit 1
    }
}

$env:PYTHONUTF8 = '1'
uv run --no-project --python 3.11 scripts/bootstrap.py @args
exit $LASTEXITCODE
