# Empacota o LiveCapture num exe portatil (PyInstaller).
#
#   .\build_livecapture.ps1
#
# Resultado:
#   dist\LiveCapture\LiveCapture.exe      -> interface grafica (abra este)
#   dist\LiveCapture\LiveCapture-cli.exe  -> modo console (--monitor / --lctool)
#   LiveCapture-portatil.zip              -> pacote pronto p/ enviar
$ErrorActionPreference = "Continue"
$proj = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $proj

$py = "$proj\.venv-livecapture\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Output "Ambiente .venv-livecapture nao encontrado."
    exit 1
}

Write-Output ""
Write-Output " [1/4] preparando o ffmpeg portatil..."
New-Item -ItemType Directory -Force -Path "$proj\build_bin" | Out-Null
if (Test-Path "$proj\build_bin\ffmpeg.exe") {
    # quem chamou ja preparou o ffmpeg (a CI baixa antes de rodar o script)
    Write-Output "          usando o build_bin\ffmpeg.exe que ja esta aqui"
} else {
    $ff = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
    if (-not $ff) {
        $ff = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" `
                -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
                Select-Object -First 1).FullName
    }
    if (-not ($ff -and (Test-Path $ff))) {
        Write-Output "ffmpeg do sistema nao encontrado. Instale com: winget install Gyan.FFmpeg"
        exit 1
    }
    Copy-Item $ff "$proj\build_bin\ffmpeg.exe" -Force
}
Write-Output ("          ffmpeg {0:N1} MB" -f ((Get-Item "$proj\build_bin\ffmpeg.exe").Length / 1MB))

Write-Output ""
Write-Output " [2/4] limpando builds anteriores..."
Remove-Item "$proj\build", "$proj\dist" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$proj\LiveCapture-portatil.zip" -Force -ErrorAction SilentlyContinue

Write-Output ""
Write-Output " [3/4] rodando o PyInstaller (demora um pouco)..."
& $py -m PyInstaller --noconfirm --clean livecapture.spec *> "$proj\build_pyinstaller.log"
if ($LASTEXITCODE -ne 0) {
    Write-Output "PyInstaller falhou (exit $LASTEXITCODE). Veja build_pyinstaller.log"
    Get-Content "$proj\build_pyinstaller.log" -Tail 30
    exit 1
}
Remove-Item "$proj\build" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$proj\build_pyinstaller.log" -Force -ErrorAction SilentlyContinue

Write-Output ""
Write-Output " [4/4] gerando o zip..."
Compress-Archive -Path "$proj\dist\LiveCapture" -DestinationPath "$proj\LiveCapture-portatil.zip" -CompressionLevel Optimal

$distMB = [math]::Round((Get-ChildItem "$proj\dist\LiveCapture" -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 0)
$zipMB = [math]::Round((Get-Item "$proj\LiveCapture-portatil.zip").Length / 1MB, 1)
Write-Output ""
Write-Output "=============================================="
Write-Output " PRONTO"
Write-Output "=============================================="
Write-Output "  interface    : $proj\dist\LiveCapture\LiveCapture.exe   (abra este)"
Write-Output "  modo console : $proj\dist\LiveCapture\LiveCapture-cli.exe"
Write-Output "  pasta dist   : $distMB MB"
Write-Output "  zip p/ enviar: $proj\LiveCapture-portatil.zip  ($zipMB MB)"
