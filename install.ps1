# Windows PowerShell 5.1 / PowerShell 7
# .\install.ps1 -Demo
# .\install.ps1 -Lan -Port 3000
param([switch]$Demo,[switch]$Lan,[int]$Port=8080,[string]$Source='0',[switch]$InstallOnly)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.15 -m venv .venv }
    else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.15 is required.' }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $python -c "import sys; sys.exit(sys.version_info[:2] != (3, 15))"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.15 is required. Rename or remove the old .venv and rerun.' }
& $python -m pip install --only-binary=:all: -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($InstallOnly) { return }
$arguments = @('pyWCam.py','--port',"$Port",'--source',$Source)
if ($Demo) { $arguments += '--demo' }
if ($Lan) { $arguments += '--lan' }
& $python @arguments
exit $LASTEXITCODE
