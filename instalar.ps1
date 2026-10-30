# Instalador do LiveCapture.
# Cria o ambiente, baixa as dependencias (Python, pacotes e ffmpeg) e cria um atalho.
# Uso:  powershell -ExecutionPolicy Bypass -File instalar.ps1
$ErrorActionPreference = "Stop"
$proj = $PSScriptRoot

Write-Host "== Instalador LiveCapture =="

function Find-Py {
    foreach ($c in @("py", "python", "python3")) {
        $p = Get-Command $c -ErrorAction SilentlyContinue
        if ($p) { return $p.Source }
    }
    return $null
}

$py = Find-Py
if (-not $py) {
    Write-Host "Python nao encontrado. Baixando o uv para obter um Python 3.13..."
    $bin = Join-Path $env:LOCALAPPDATA "LiveCapture\bin"
    New-Item -ItemType Directory -Force -Path $bin | Out-Null
    $uv = Join-Path $bin "uv.exe"
    if (-not (Test-Path $uv)) {
        $zip = Join-Path $env:TEMP "uv.zip"
        Invoke-WebRequest -Uri "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip
        Expand-Archive -Path $zip -DestinationPath $bin -Force
    }
    & $uv python install 3.13
    $py = & $uv python find 3.13
}

Write-Host "Usando Python: $py"
& $py (Join-Path $proj "bootstrap.py") --setup

# Atalho na Area de Trabalho (aponta para o exe se existir, senao para o app)
$root = Join-Path $env:LOCALAPPDATA "LiveCapture"
$exe = Join-Path $proj "dist\LiveCapture.exe"
if (Test-Path $exe) {
    $target = $exe; $arguments = ""
} else {
    $target = Join-Path $root "venv\Scripts\pythonw.exe"
    $arguments = '"' + (Join-Path $root "app\livecapture_gui.py") + '"'
}

$lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "LiveCapture.lnk"
$shell = New-Object -ComObject WScript.Shell
$sc = $shell.CreateShortcut($lnk)
$sc.TargetPath = $target
$sc.Arguments = $arguments
$sc.WorkingDirectory = $root
$sc.IconLocation = "$target,0"
$sc.Save()

Write-Host ""
Write-Host "Instalado! Atalho criado em $lnk"
Write-Host "Pasta de dados: $root"
