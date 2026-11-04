# -*- mode: python ; coding: utf-8 -*-
#
# Receita do empacotado do LiveCapture (PyInstaller).
# Gera dois executáveis numa mesma pasta:
#   LiveCapture.exe      -> interface gráfica (sem console)
#   LiveCapture-cli.exe  -> modo console: --monitor (sem interface) e --lctool
#                           (os subprocessos do streamlink/yt-dlp saem daqui)
#
# O streamlink e o yt-dlp vão EMBUTIDOS como módulos; o ffmpeg vai na pasta
# bin/ do pacote. Nada de Python precisa estar instalado na máquina.

from PyInstaller.utils.hooks import collect_all
import faster_whisper
import os

datas = [("build_bin", "bin")]
binaries = []
hiddenimports = ["streamlink_cli"]

# assets do faster-whisper (modelo de voz/atividade em onnx tem que ir junto)
_fwp = os.path.dirname(faster_whisper.__file__)
datas.append((os.path.join(_fwp, "assets"), os.path.join("faster_whisper", "assets")))

for pkg in ("streamlink", "yt_dlp", "faster_whisper"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["livecapture_gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["torch", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_gui = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="LiveCapture",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
exe_cli = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="LiveCapture-cli",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
coll = COLLECT(
    exe_gui,
    exe_cli,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="LiveCapture",
)
