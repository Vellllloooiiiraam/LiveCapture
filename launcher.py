"""
Ponto de entrada do LiveCapture.exe.

1. Copia os arquivos do app para %LOCALAPPDATA%\\LiveCapture\\app.
2. Garante Python + ambiente virtual + dependencias + ffmpeg (bootstrap).
   Na primeira execucao mostra uma janela de progresso (sem console preto).
3. Abre a interface grafica usando o Python do ambiente virtual.

Os clipes e o ocorrencias.csv ficam em Videos\\LiveCapture (LIVECAPTURE_HOME).

Flags:
    --check   so verifica o ambiente e sai
    --setup   instala/atualiza o ambiente e sai
"""
import os
import queue
import subprocess
import sys
import threading

import bootstrap as B

try:
    import tkinter as tk
    from tkinter import messagebox
except ImportError:                     # ambiente sem tk (nao deveria ocorrer)
    tk = None


def bundled_dir():
    """Arquivos empacotados dentro do exe (extraidos pelo PyInstaller)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def sidecar_dir():
    """Pasta ao lado do exe (onde ficam ffmpeg.exe/ffprobe.exe do ZIP)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _clean_child_env(env):
    """Remove variaveis que o PyInstaller injeta e que quebram o Python do venv.

    O exe congela o Tcl/Tk e exporta TCL_LIBRARY/TK_LIBRARY apontando para o
    Tcl dele; o python do venv herda isso, o tkinter dele acha o Tcl errado e
    o programa fecha com erro de versao do Tcl. Removemos essas variaveis (e as
    _PYI_*, alem do PATH) para o filho usar o proprio ambiente.
    """
    for key in list(env):
        up = key.upper()
        if up.startswith("_PYI") or up in ("_MEIPASS2", "TCL_LIBRARY", "TK_LIBRARY", "TCL", "TK"):
            env.pop(key, None)
    meipass = getattr(sys, "_MEIPASS", "")
    if meipass:
        mp = os.path.abspath(meipass)
        parts = [p for p in env.get("PATH", "").split(os.pathsep)
                 if p and os.path.abspath(p) != mp]
        env["PATH"] = os.pathsep.join(parts)
    return env


def install_sidecar_ffmpeg():
    if getattr(sys, "frozen", False):
        B.install_bundled_ffmpeg(sidecar_dir())


def needs_setup():
    s = B.status()
    return not (s["venv"] and s["deps"] and s["ffmpeg"])


def launch(py):
    gui = os.path.join(B.app_dir(), "livecapture_gui.py")
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")   # abre a GUI sem console
    runner = pyw if os.path.exists(pyw) else py

    env = _clean_child_env(os.environ.copy())
    # O ffmpeg recem-instalado pode nao estar no PATH deste processo: passa adiante.
    ff = B.find_ffmpeg()
    if ff:
        env["PATH"] = os.path.dirname(ff) + os.pathsep + env.get("PATH", "")
    data = B.data_dir()                       # clipes/ e ocorrencias.csv ficam aqui
    os.makedirs(data, exist_ok=True)
    env["LIVECAPTURE_HOME"] = data

    return subprocess.call([runner, gui], env=env, cwd=data, **B._no_window())


def setup_with_progress():
    """Roda o bootstrap mostrando o andamento numa janelinha."""
    if tk is None:
        return {"py": B.ensure_ready()}
    q = queue.Queue()
    orig_log = B.log

    def log(msg):
        orig_log(msg)
        q.put(msg)

    B.log = log                                   # captura as mensagens do bootstrap
    root = tk.Tk()
    root.title("LiveCapture - preparando")
    root.geometry("460x170")
    root.resizable(False, False)
    tk.Label(root, text="Preparando o LiveCapture (primeira execucao).",
             font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16, pady=(16, 2))
    tk.Label(root, justify="left", wraplength=420,
             text="Baixa Python, dependencias e ffmpeg. Pode demorar alguns minutos."
             ).pack(anchor="w", padx=16)
    status = tk.Label(root, text="Iniciando...", justify="left", wraplength=420,
                      fg="#333333")
    status.pack(anchor="w", padx=16, pady=(10, 0))
    done = {"ok": False, "err": None, "py": None}

    def worker():
        try:
            install_sidecar_ffmpeg()
            done["py"] = B.ensure_ready()
            done["ok"] = True
        except Exception as e:                    # mostra o erro em vez de sumir
            done["err"] = e

    threading.Thread(target=worker, daemon=True).start()

    def poll():
        while not q.empty():
            status.config(text=q.get())
        if done["ok"] or done["err"]:
            root.after(400, root.destroy)
        else:
            root.after(200, poll)

    root.after(200, poll)
    root.mainloop()
    return done


def _error(err):
    if tk is not None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("LiveCapture", f"Falha ao preparar o ambiente:\n\n{err}")
        root.destroy()
    print(f"Erro: {err}", file=sys.stderr)


def main():
    B.install_payload(bundled_dir())

    if "--check" in sys.argv:
        install_sidecar_ffmpeg()
        for k, v in B.status().items():
            print(f"{k}: {'OK' if v else 'FALTA'}")
        return 0
    if "--setup" in sys.argv:
        install_sidecar_ffmpeg()
        done = setup_with_progress() if tk is not None else {"py": B.ensure_ready()}
        if done.get("err"):
            _error(done["err"])
            return 1
        print("Pronto.")
        return 0

    if needs_setup():
        done = setup_with_progress()
        if done.get("err"):
            _error(done["err"])
            return 1
        py = done["py"]
    else:
        install_sidecar_ffmpeg()
        py = B.ensure_ready()

    return launch(py)


if __name__ == "__main__":
    sys.exit(main())
