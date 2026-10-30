"""
Ponto de entrada do LiveCapture.exe.

1. Copia os arquivos do app para %LOCALAPPDATA%\\LiveCapture\\app.
2. Garante Python + ambiente virtual + dependencias + ffmpeg (bootstrap).
3. Abre a interface grafica usando o Python do ambiente virtual.

Flags:
    --check   so verifica o ambiente e sai
    --setup   instala/atualiza o ambiente e sai
"""
import os
import subprocess
import sys

import bootstrap as B


def bundled_dir():
    """Pasta onde estao os arquivos do app (extraidos pelo PyInstaller ou o repo)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def main():
    src = bundled_dir()
    B.install_payload(src)

    if "--check" in sys.argv:
        for k, v in B.status().items():
            print(f"{k}: {'OK' if v else 'FALTA'}")
        return 0
    if "--setup" in sys.argv:
        B.ensure_ready()
        print("Pronto.")
        return 0

    py = B.ensure_ready()
    gui = os.path.join(B.app_dir(), "livecapture_gui.py")
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")   # abre sem console extra
    runner = pyw if os.path.exists(pyw) else py
    return subprocess.call([runner, gui])


if __name__ == "__main__":
    sys.exit(main())
