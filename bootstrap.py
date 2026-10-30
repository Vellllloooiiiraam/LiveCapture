"""
Bootstrap do LiveCapture.

Garante um Python 3.11-3.13, cria um ambiente virtual isolado em
%LOCALAPPDATA%\\LiveCapture, instala as dependencias (requirements.txt)
e confere/obtem o ffmpeg.

Usado pelo LiveCapture.exe (launcher.py) e pelo instalar.ps1.

Uso:
    python bootstrap.py --check   # so mostra o status
    python bootstrap.py --setup   # instala/atualiza tudo
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

APP = "LiveCapture"
MIN_PY = (3, 11)
MAX_PY = (3, 13)                 # PyAV (av) ainda nao tem wheel para 3.14+; requirements usa av<19
PAYLOAD = ("livecapture_gui.py", "requirements.txt")
UV_ZIP = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
CHECK_IMPORTS = "import numpy, faster_whisper, streamlink, yt_dlp"
# ffmpeg: se nao vier embutido no ZIP, baixa direto (sem winget, sem admin,
# sem mexer no PATH). Tenta as fontes em ordem.
FFMPEG_ZIPS = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
)


def log(msg):
    print(f"[{APP}] {msg}", flush=True)


_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def _no_window():
    """Evita janelas pretas de console ao chamar programas externos no Windows."""
    return {"creationflags": _CREATE_NO_WINDOW} if _CREATE_NO_WINDOW else {}


# ------------------------------------------------------------------- caminhos
def _local_appdata():
    return os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")


def root():
    return os.path.join(_local_appdata(), APP)


def app_dir():
    return os.path.join(root(), "app")


def venv_dir():
    return os.path.join(root(), "venv")


def bin_dir():
    return os.path.join(root(), "bin")


def data_dir():
    """Onde ficam os clipes e o ocorrencias.csv (visivel para o usuario)."""
    return os.path.join(os.path.expanduser("~"), "Videos", APP)


# --------------------------------------------------------------- descoberta
def _py_version(exe):
    try:
        r = subprocess.run([exe, "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, **_no_window())
        if r.returncode != 0:
            return None
        a, b = r.stdout.strip().split(".")
        return (int(a), int(b))
    except Exception:
        return None


def _ok(v):
    return bool(v) and MIN_PY <= v <= MAX_PY


def _venv_python(vd=None):
    vd = vd or venv_dir()
    for sub in ("Scripts", "bin"):
        for name in ("python.exe", "python"):
            p = os.path.join(vd, sub, name)
            if os.path.exists(p):
                return p
    return None


def _uv_python(uv, ver):
    try:
        subprocess.run([uv, "python", "install", ver], check=False, timeout=900, **_no_window())
        r = subprocess.run([uv, "python", "find", ver], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, **_no_window())
        exe = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
        if exe and os.path.exists(exe) and _ok(_py_version(exe)):
            return exe
    except Exception:
        pass
    return None


def find_base_python():
    """Devolve um Python 3.11-3.13, ou None."""
    if shutil.which("py"):
        for v in ("3.13", "3.12", "3.11"):
            try:
                r = subprocess.run(["py", "-" + v, "-c", "import sys;print(sys.executable)"],
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=30, **_no_window())
                exe = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
                if exe and os.path.exists(exe) and _ok(_py_version(exe)):
                    return exe
            except Exception:
                pass
    for name in ("python", "python3"):
        exe = shutil.which(name)
        if exe and _ok(_py_version(exe)):
            return exe
    uv_root = os.path.join(os.environ.get("APPDATA", ""), "uv", "python")
    for exe in sorted(glob.glob(os.path.join(uv_root, "*", "python.exe"))):
        if _ok(_py_version(exe)):
            return exe
    uv = shutil.which("uv")
    if uv:
        return _uv_python(uv, "3.13")
    return None


def install_uv():
    """Baixa o uv (gerenciador de Python) para %LOCALAPPDATA%\\LiveCapture\\bin."""
    os.makedirs(bin_dir(), exist_ok=True)
    target = os.path.join(bin_dir(), "uv.exe")
    if os.path.exists(target):
        return target
    log("Baixando o gerenciador 'uv'...")
    with tempfile.TemporaryDirectory() as td:
        z = os.path.join(td, "uv.zip")
        urllib.request.urlretrieve(UV_ZIP, z)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(td)
        for dirpath, _dirs, files in os.walk(td):
            if "uv.exe" in files:
                shutil.copy2(os.path.join(dirpath, "uv.exe"), target)
                break
    return target if os.path.exists(target) else None


def ensure_base_python():
    exe = find_base_python()
    if exe:
        return exe
    uv = shutil.which("uv") or install_uv()
    if uv:
        exe = _uv_python(uv, "3.13")
        if exe:
            return exe
    raise RuntimeError("Nao encontrei um Python 3.11-3.13 e nao consegui instalar via uv.")


# --------------------------------------------------------------- instalacao
def ensure_venv(base):
    vp = _venv_python()
    if vp and _ok(_py_version(vp)):
        return vp
    if os.path.isdir(venv_dir()):
        shutil.rmtree(venv_dir(), ignore_errors=True)
    log("Criando ambiente virtual...")
    subprocess.run([base, "-m", "venv", venv_dir()], check=True, **_no_window())
    vp = _venv_python()
    if not vp:
        raise RuntimeError("Falha ao criar o ambiente virtual.")
    return vp


def ensure_deps(vp, req):
    if subprocess.run([vp, "-c", CHECK_IMPORTS], capture_output=True, text=True,
                      encoding="utf-8", errors="replace", **_no_window()).returncode == 0:
        return
    log("Instalando dependencias (pode demorar bastante na primeira vez)...")
    subprocess.run([vp, "-m", "pip", "install", "--upgrade", "pip"], check=False, **_no_window())
    subprocess.run([vp, "-m", "pip", "install", "-r", req], check=True, **_no_window())


def find_ffmpeg():
    """ffmpeg embutido (pasta do app) > baixado (bin) > PATH > winget."""
    bundled = os.path.join(app_dir(), "ffmpeg.exe")
    if os.path.exists(bundled):
        return bundled
    own = os.path.join(bin_dir(), "ffmpeg.exe")
    if os.path.exists(own):
        return own
    p = shutil.which("ffmpeg")
    if p:
        return p
    links = os.path.join(_local_appdata(), "Microsoft", "WinGet", "Links", "ffmpeg.exe")
    if os.path.exists(links):
        return links
    base = os.path.join(_local_appdata(), "Microsoft", "WinGet", "Packages")
    found = glob.glob(os.path.join(base, "*FFmpeg*", "**", "ffmpeg.exe"), recursive=True)
    return found[0] if found else None


def install_bundled_ffmpeg(src):
    """Copia ffmpeg.exe/ffprobe.exe que vierem junto do exe (ZIP) para a pasta do app."""
    os.makedirs(app_dir(), exist_ok=True)
    for name in ("ffmpeg.exe", "ffprobe.exe"):
        s = os.path.join(src, name)
        if os.path.exists(s) and os.path.abspath(s) != os.path.join(app_dir(), name):
            shutil.copy2(s, os.path.join(app_dir(), name))


def download_ffmpeg():
    """Baixa um build do ffmpeg e copia ffmpeg.exe/ffprobe.exe para a pasta bin."""
    os.makedirs(bin_dir(), exist_ok=True)
    for url in FFMPEG_ZIPS:
        try:
            log("Baixando o ffmpeg (80-150 MB, so na 1a vez)...")
            with tempfile.TemporaryDirectory() as td:
                z = os.path.join(td, "ffmpeg.zip")
                urllib.request.urlretrieve(url, z)
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(td)
                for dirpath, _dirs, files in os.walk(td):
                    if "ffmpeg.exe" in files:
                        for name in ("ffmpeg.exe", "ffprobe.exe"):
                            if name in files:
                                shutil.copy2(os.path.join(dirpath, name),
                                             os.path.join(bin_dir(), name))
                        return os.path.join(bin_dir(), "ffmpeg.exe")
        except Exception as e:
            log(f"Falhou ({e}); tentando outra fonte...")
    return None


def _add_user_path(d):
    try:
        ps = (f"$p=[Environment]::GetEnvironmentVariable('Path','User');"
              f"if($p -notlike '*{d}*'){{[Environment]::SetEnvironmentVariable('Path',$p+';{d}','User')}}")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, **_no_window())
    except Exception:
        pass


def ensure_ffmpeg():
    p = find_ffmpeg()
    if p:
        return p
    p = download_ffmpeg()
    if p:
        return p
    if shutil.which("winget"):             # plano B
        log("Instalando ffmpeg via winget...")
        subprocess.run(["winget", "install", "--id", "Gyan.FFmpeg", "-e",
                        "--accept-source-agreements", "--accept-package-agreements"],
                       check=False, **_no_window())
        p = find_ffmpeg()
        if p:
            _add_user_path(os.path.dirname(p))
            return p
    log("AVISO: ffmpeg nao encontrado. Instale manualmente: winget install Gyan.FFmpeg")
    return None


def install_payload(src):
    """Copia os arquivos do app (do exe ou do repositorio) para a pasta de instalacao."""
    os.makedirs(app_dir(), exist_ok=True)
    for name in PAYLOAD:
        s = os.path.join(src, name)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(app_dir(), name))
    return app_dir()


def ensure_ready():
    base = ensure_base_python()
    log(f"Python base: {base}")
    vp = ensure_venv(base)
    log(f"Ambiente: {venv_dir()}")
    ensure_deps(vp, os.path.join(app_dir(), "requirements.txt"))
    ff = ensure_ffmpeg()
    log(f"ffmpeg: {ff or 'NAO ENCONTRADO'}")
    return vp


def status():
    vp = _venv_python()
    deps = bool(vp) and subprocess.run(
        [vp, "-c", CHECK_IMPORTS], capture_output=True, text=True,
        encoding="utf-8", errors="replace", **_no_window()).returncode == 0
    return {"base_python": bool(find_base_python()), "venv": bool(vp),
            "deps": deps, "ffmpeg": bool(find_ffmpeg())}


def main():
    ap = argparse.ArgumentParser(description="Bootstrap do LiveCapture")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="mostra o status atual")
    g.add_argument("--setup", action="store_true", help="instala/atualiza o ambiente")
    g.add_argument("--base-python", action="store_true", help="imprime o Python base 3.11-3.13")
    a = ap.parse_args()
    if a.base_python:
        print(ensure_base_python())
        return 0
    if a.check:
        for k, v in status().items():
            print(f"{k}: {'OK' if v else 'FALTA'}")
        return 0
    ensure_ready()
    log("Pronto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
