# Gera o LiveCapture.exe (leve: baixa as dependencias na 1a execucao).
# Uso:  powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = "Stop"
$proj = $PSScriptRoot
$buildVenv = Join-Path $proj ".venv-build"
$vpy = Join-Path $buildVenv "Scripts\python.exe"

function Test-GoodVenv($exe) {
    if (-not (Test-Path $exe)) { return $false }
    $v = & $exe -c "import sys;m=sys.version_info;print(m[1] in (11,12,13))" 2>$null
    return ($v.Trim() -eq "True")
}

if (-not (Test-GoodVenv $vpy)) {
    if (Test-Path $buildVenv) { Remove-Item -Recurse -Force $buildVenv }
    Write-Host "Localizando um Python 3.11-3.13..."
    $base = (& python (Join-Path $proj "bootstrap.py") --base-python 2>$null | Select-Object -Last 1)
    if (-not $base) { $base = (Get-Command python).Source }
    Write-Host "Python base: $base"
    & $base -m venv $buildVenv
}

Write-Host "Instalando PyInstaller..."
& $vpy -m pip install --upgrade pip pyinstaller | Out-Null

Push-Location $proj
try {
    & $vpy -m PyInstaller --noconfirm --clean --onefile --console --name LiveCapture `
        --add-data "$proj\livecapture_gui.py;." --add-data "$proj\requirements.txt;." `
        --distpath "$proj\dist" --workpath "$proj\build" --specpath "$proj\build" `
        "$proj\launcher.py"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou (codigo $LASTEXITCODE)" }
    Write-Host ""
    Write-Host "OK -> $proj\dist\LiveCapture.exe"
} finally {
    Pop-Location
}
