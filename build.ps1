$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Invoke-Step {
    param([string]$Label, [scriptblock]$Command)
    Write-Host "== $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed with exit code $LASTEXITCODE" }
}

if (-not (Test-Path .venv\Scripts\python.exe)) {
    Invoke-Step 'create .venv' { py -3.12 -m venv .venv }
}
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'

Invoke-Step 'install' { & $python -m pip install -e ".[dev,build]" }
Invoke-Step 'tests' { & $python -m pytest tests }

foreach ($dir in 'build', 'dist') {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}
Invoke-Step 'pyinstaller' { & $python -m PyInstaller --noconfirm tiff2png.spec }

if (-not (Test-Path dist\tiff2png.exe)) { throw 'dist\tiff2png.exe was not produced' }
Write-Host "Built $(Join-Path $PSScriptRoot 'dist\tiff2png.exe')"
