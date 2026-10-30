"""
LiveCapture (interface gráfica) - detecta palavras-chave na VOZ do streamer
em lives ao vivo (YouTube, Twitch, Kick) e salva um clipe com alguns segundos
ANTES e DEPOIS da palavra.

Como o clipe funciona: o programa mantém só os últimos ~2,5 minutos da live
numa pasta temporária (apagando o que ficou velho). Quando uma palavra aparece,
ele junta os pedaços do buffer ao redor daquele momento e salva um MP4 em "clipes/".
Ao parar o programa, a pasta temporária é apagada. Nada além dos clipes fica salvo.

Uso: python livecapture_gui.py
Requisitos: ver requirements.txt (e ffmpeg instalado no sistema).
"""
import csv
import datetime as dt
import glob
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata

import numpy as np

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:          # permite importar o módulo sem interface (testes)
    tk = None

SAMPLE_RATE = 16000
BYTES_PER_SEC = SAMPLE_RATE * 2
CHUNK_SEC = 5                 # tamanho do bloco transcrito
OVERLAP_SEC = 1.5             # sobreposição para não cortar palavras
COOLDOWN_SEC = 12             # evita alerta repetido da mesma palavra
SEGMENT_SEC = 2               # tamanho dos pedaços do buffer
BUFFER_KEEP_SEC = 150         # quanto da live fica no buffer
AUDIO_QUALITY = "audio_only,worst"
VIDEO_QUALITY = "480p,360p,worst"   # qualidade usada quando o clipe está ligado
MAX_CLIP_JOBS = 2             # concatenações de clipe simultâneas
# Pasta de saida: o launcher define LIVECAPTURE_HOME (Videos\LiveCapture).
# Sem a variavel, usa a pasta atual (como antes).
DATA_DIR = os.environ.get("LIVECAPTURE_HOME", "")
LOG_FILE = os.path.join(DATA_DIR, "ocorrencias.csv") if DATA_DIR else "ocorrencias.csv"
CLIP_DIR = os.path.join(DATA_DIR, "clipes") if DATA_DIR else "clipes"
# No Windows, sem isto cada ffmpeg/streamlink abre uma janela preta de console.
NO_WINDOW = {"creationflags": 0x08000000} if sys.platform.startswith("win") else {}


# ---------------------------------------------------------------- utilidades
def _extra_tool_dirs():
    """Onde procurar ffmpeg/streamlink/yt-dlp alem do PATH (Windows).

    Inclui a pasta do proprio app (onde o ffmpeg.exe do ZIP fica) e as pastas
    que o bootstrap cria/usa (%LOCALAPPDATA%\\LiveCapture\\bin e o winget).
    """
    here = os.path.dirname(os.path.abspath(__file__))
    dirs = [here, os.path.join(here, "bin")]
    home = os.environ.get("LOCALAPPDATA") or ""
    if home:
        b = os.path.join(home, "LiveCapture", "bin")
        dirs += [b] + glob.glob(os.path.join(b, "ffmpeg*", "bin"))
        dirs.append(os.path.join(home, "Microsoft", "WinGet", "Links"))
        dirs += glob.glob(os.path.join(home, "Microsoft", "WinGet", "Packages",
                                       "*FFmpeg*", "**", "bin"), recursive=True)
    return dirs


def find_tool(name):
    """Localiza um executavel: PATH, pasta do interpretador (venv/Scripts) e
    as pastas onde o app/instalador coloca o ffmpeg."""
    exe = shutil.which(name)
    if exe:
        return exe
    for d in [os.path.dirname(sys.executable)] + _extra_tool_dirs():
        for cand in (name, name + ".exe"):
            path = os.path.join(d, cand)
            if os.path.isfile(path):
                return path
    return name                      # deixa o erro do sistema aparecer se faltar


def normalize(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    # colapsa espaços para não quebrar palavras-chave com várias palavras
    return re.sub(r"\s+", " ", text).strip()


def fmt(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", normalize(text).strip())[:30] or "palavra"


def parse_start(text):
    """'21:30' ou '21:30:15' (hora local em que a live começou) -> epoch."""
    text = text.strip()
    if not text:
        return None
    parts = [int(p) for p in text.split(":")]
    while len(parts) < 3:
        parts.append(0)
    now = dt.datetime.now()
    start = now.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0)
    if start > now:                      # horário "no futuro" = foi ontem
        start -= dt.timedelta(days=1)
    return start.timestamp()


def detect_start(url):
    """Tenta descobrir o início da live com yt-dlp. Devolve epoch ou None."""
    try:
        out = subprocess.run(
            [find_tool("yt-dlp"), "--skip-download", "--no-warnings",
             "--print", "%(release_timestamp)s|%(timestamp)s", url],
            capture_output=True, text=True, timeout=40, **NO_WINDOW,
        ).stdout.strip().splitlines()[-1]
        for value in out.split("|"):
            if value.isdigit():
                return float(value)
    except Exception:
        pass
    return None


# ------------------------------------------------------------- buffer / clipe
def read_segments(list_path):
    """Lê a lista do ffmpeg: [(arquivo, inicio_s, fim_s), ...] (tempo da mídia)."""
    rows = []
    try:
        with open(list_path, newline="", encoding="utf-8") as f:
            for r in csv.reader(f):
                if len(r) >= 3:
                    try:
                        rows.append((os.path.basename(r[0]), float(r[1]), float(r[2])))
                    except ValueError:
                        pass             # linha ainda sendo escrita
    except OSError:
        pass
    return rows


def cleanup_old(tmp_dir, list_path, deleted):
    rows = read_segments(list_path)
    if not rows:
        return
    limit = rows[-1][2] - BUFFER_KEEP_SEC
    for name, _start, end in rows:
        if end < limit and name not in deleted:
            try:
                os.remove(os.path.join(tmp_dir, name))
            except OSError:
                pass
            deleted.add(name)


def make_clip(tmp_dir, list_path, media_t, pre, post, out_path, stop):
    """Junta os pedaços do buffer de (media_t - pre) até (media_t + post)."""
    t0, t1 = max(0.0, media_t - pre), media_t + post
    deadline = time.time() + post + 45
    while not stop.is_set() and time.time() < deadline:   # espera o "depois" chegar
        rows = read_segments(list_path)
        if rows and rows[-1][2] >= t1:
            break
        time.sleep(1)
    # Mesmo se o usuario parou, corta o que ja esta no buffer (nao perde o clipe).
    pieces = [r for r in read_segments(list_path)
              if r[2] > t0 and r[1] < t1 and os.path.exists(os.path.join(tmp_dir, r[0]))]
    if not pieces:
        return False
    concat = os.path.join(tmp_dir, f"concat_{int(time.time() * 1000)}.txt")
    try:
        with open(concat, "w", encoding="utf-8") as f:
            for name, _s, _e in pieces:
                path = os.path.abspath(os.path.join(tmp_dir, name)).replace("\\", "/")
                f.write(f"file '{path}'\n")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        common = [find_tool("ffmpeg"), "-y", "-loglevel", "error", "-fflags", "+genpts",
                  "-f", "concat", "-safe", "0", "-i", concat]
        res = subprocess.run(
            common + ["-c", "copy", "-avoid_negative_ts", "make_zero",
                      "-movflags", "+faststart", out_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **NO_WINDOW)
        ok = res.returncode == 0 and os.path.exists(out_path)
        if not ok:                       # -c copy falhou: recodifica para não perder o clipe
            res = subprocess.run(
                common + ["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
                          "-movflags", "+faststart", out_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **NO_WINDOW)
            ok = res.returncode == 0 and os.path.exists(out_path)
        return ok
    finally:
        try:
            os.remove(concat)
        except OSError:
            pass


# -------------------------------------------------------------------- worker
class Worker(threading.Thread):
    def __init__(self, url, keywords, model_name, live_start, out, stop,
                 clip_on, pre, post, lang="pt"):
        super().__init__(daemon=True)
        self.url, self.out, self.stop = url, out, stop
        self.kw = {normalize(k).strip(): k for k in keywords}
        self.model_name, self.live_start = model_name, live_start
        self.clip_on, self.pre, self.post = clip_on, pre, post
        self.lang = None if lang in (None, "", "auto") else lang
        self.model, self.on_cpu, self.sl_err = None, False, ""
        self.procs, self.tmp = [], None
        self.clip_threads = []
        self.clip_sem = threading.Semaphore(MAX_CLIP_JOBS)

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.out.put(("end", f"Erro: {e}", self))
        finally:
            self.kill()
            for t in list(self.clip_threads):      # deixa os clipes em curso terminarem
                t.join(timeout=max(60, self.post + 45))
            if self.tmp:
                shutil.rmtree(self.tmp, ignore_errors=True)

    def kill(self):
        for p in self.procs:
            try:
                p.kill()
            except Exception:
                pass

    def _load_model(self, device="auto"):
        from faster_whisper import WhisperModel
        compute = "auto" if device == "auto" else "int8"
        return WhisperModel(self.model_name, device=device, compute_type=compute)

    def _transcribe(self, audio):
        """Transcreve; se a GPU falhar (CUDA/cuDNN ausente), cai para a CPU."""
        kw = dict(language=self.lang, vad_filter=True, beam_size=1,
                  condition_on_previous_text=False)
        try:
            segs, _ = self.model.transcribe(audio, **kw)
            return list(segs)             # o erro de GPU aparece ao consumir
        except Exception:
            if self.on_cpu:
                raise
            self.out.put(("status", "GPU indisponível; usando o processador..."))
            self.model, self.on_cpu = self._load_model("cpu"), True
            segs, _ = self.model.transcribe(audio, **kw)
            return list(segs)

    def _run(self):
        self.out.put(("status", f"Carregando modelo '{self.model_name}' "
                                "(na 1ª vez ele é baixado: pode demorar)..."))
        try:
            self.model = self._load_model("auto")
        except Exception:
            self.model, self.on_cpu = self._load_model("cpu"), True
        if self.stop.is_set():               # usuario clicou Parar durante o carregamento
            self.out.put(("end", "Parado.", self))
            return

        self.out.put(("status", "Abrindo a live..."))
        quality = VIDEO_QUALITY if self.clip_on else AUDIO_QUALITY
        sl = subprocess.Popen(
            [find_tool("streamlink"), self.url, quality, "--stdout", "--loglevel", "error"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **NO_WINDOW)

        def drain_err():                     # guarda o motivo se o streamlink falhar
            for line in sl.stderr:
                txt = line.decode("utf-8", "replace").strip()
                if txt:
                    self.sl_err = txt

        threading.Thread(target=drain_err, daemon=True).start()

        cmd = [find_tool("ffmpeg"), "-loglevel", "error", "-i", "pipe:0",
               "-map", "0:a:0", "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"]
        list_path = None
        if self.clip_on:
            self.tmp = tempfile.mkdtemp(prefix="livecapture_")
            list_path = os.path.join(self.tmp, "lista.csv")
            cmd += ["-map", "0:v:0?", "-map", "0:a:0", "-c", "copy",
                    "-f", "segment", "-segment_time", str(SEGMENT_SEC),
                    "-segment_format", "mpegts",
                    "-segment_list", list_path, "-segment_list_type", "csv",
                    "-segment_list_flags", "+live",
                    os.path.join(self.tmp, "seg_%06d.ts")]
        ff = subprocess.Popen(cmd, stdin=sl.stdout, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, **NO_WINDOW)
        sl.stdout.close()
        self.procs = [sl, ff]

        audio_q = queue.Queue()

        def reader():
            offset = 0
            while True:
                data = ff.stdout.read(CHUNK_SEC * BYTES_PER_SEC)
                if not data:
                    audio_q.put(None)
                    return
                audio_q.put((data, time.time(), offset))
                offset += len(data)

        threading.Thread(target=reader, daemon=True).start()
        self.out.put(("status", "Monitorando..."))

        tail, last_hit, deleted, hit_id = b"", {}, set(), 0
        last_warn, slow = 0.0, False
        while not self.stop.is_set():
            try:
                item = audio_q.get(timeout=1)
            except queue.Empty:
                continue
            if item is None:
                if self.stop.is_set():
                    msg = "Parado."
                else:
                    time.sleep(0.5)          # deixa o streamlink terminar de escrever o erro
                    msg = "Live encerrada ou indisponível."
                    if self.sl_err:
                        msg += f" ({self.sl_err[:140]})"
                self.out.put(("end", msg, self))
                return
            data, arrived, offset = item
            buf = tail + data
            if len(buf) % 2:                 # amostras int16: descarta byte solto
                buf = buf[:-1]
            window_media = (offset - len(tail)) / BYTES_PER_SEC   # tempo da mídia
            window_wall = arrived - len(buf) / BYTES_PER_SEC      # relógio
            tail = data[-int(OVERLAP_SEC * BYTES_PER_SEC):]
            audio = np.frombuffer(buf, np.int16).astype(np.float32) / 32768.0

            if list_path:
                cleanup_old(self.tmp, list_path, deleted)
            self.clip_threads = [t for t in self.clip_threads if t.is_alive()]

            t_trans = time.time()
            segments = self._transcribe(audio)
            took = time.time() - t_trans
            if took > CHUNK_SEC and time.time() - last_warn > 30:
                last_warn, slow = time.time(), True
                self.out.put(("status", f"Atenção: o PC está atrasado ({took:.0f}s para "
                                        f"{CHUNK_SEC}s de áudio). Use um modelo menor."))
            elif slow and took < CHUNK_SEC * 0.8:
                slow = False
                self.out.put(("status", "Monitorando..."))
            for seg in segments:
                norm = " " + normalize(seg.text).strip() + " "
                for kn, original in self.kw.items():
                    if f" {kn} " not in norm:
                        continue
                    when = window_wall + seg.start
                    if when - last_hit.get(kn, 0) < COOLDOWN_SEC:
                        continue
                    last_hit[kn] = when
                    hit_id += 1
                    clock = dt.datetime.fromtimestamp(when).strftime("%H:%M:%S")
                    live = fmt(when - self.live_start) if self.live_start else "—"
                    out_path = ""
                    if list_path:
                        stamp = dt.datetime.fromtimestamp(when).strftime("%Y%m%d_%H%M%S")
                        out_path = os.path.join(
                            CLIP_DIR, f"clipe_{stamp}_{safe_name(original)}.mp4")
                        t = threading.Thread(
                            target=self._clip_job,
                            args=(hit_id, list_path, window_media + seg.start, out_path),
                            daemon=True)
                        t.start()
                        self.clip_threads.append(t)
                    self.out.put(("hit", hit_id, clock, live, original,
                                  seg.text.strip(), out_path))
        self.out.put(("end", "Parado.", self))

    def _clip_job(self, hit_id, list_path, media_t, out_path):
        with self.clip_sem:                  # limita ffmpeg simultâneos
            ok = make_clip(self.tmp, list_path, media_t, self.pre, self.post,
                           out_path, self.stop)
        self.out.put(("clip", hit_id, ok, out_path))


# ----------------------------------------------------------------------- GUI
class App(tk.Tk if tk else object):
    def __init__(self):
        super().__init__()
        self.title("LiveCapture")
        self.geometry("900x600")
        self.out, self.stop_evt, self.worker = queue.Queue(), threading.Event(), None
        self.rows = {}

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Link da live:").grid(row=0, column=0, sticky="w")
        self.url = ttk.Entry(top)
        self.url.grid(row=0, column=1, columnspan=3, sticky="ew", padx=6, pady=2)

        ttk.Label(top, text="Palavras-chave\n(uma por linha):").grid(row=1, column=0, sticky="nw")
        self.words = tk.Text(top, height=5, width=30)
        self.words.grid(row=1, column=1, sticky="ew", padx=6, pady=2)

        side = ttk.Frame(top)
        side.grid(row=1, column=2, sticky="n", padx=6)
        ttk.Label(side, text="Início da live (HH:MM):").pack(anchor="w")
        row = ttk.Frame(side)
        row.pack(anchor="w")
        self.start = ttk.Entry(row, width=9)
        self.start.pack(side="left")
        ttk.Button(row, text="Detectar", command=self.auto_detect).pack(side="left", padx=4)
        ttk.Label(side, text="Modelo:").pack(anchor="w", pady=(8, 0))
        self.model = ttk.Combobox(side, values=["tiny", "base", "small", "medium"],
                                  state="readonly", width=10)
        self.model.set("small")
        self.model.pack(anchor="w")
        ttk.Label(side, text="Idioma da fala:").pack(anchor="w", pady=(8, 0))
        self.lang = ttk.Combobox(side, values=["pt", "en", "es", "auto"],
                                 state="readonly", width=10)
        self.lang.set("pt")
        self.lang.pack(anchor="w")

        opts = ttk.Frame(self, padding=(10, 0))
        opts.pack(fill="x")
        self.clip_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Salvar clipe", variable=self.clip_var).pack(side="left")
        ttk.Label(opts, text="  Segundos antes:").pack(side="left")
        self.pre = ttk.Spinbox(opts, from_=3, to=45, width=4)
        self.pre.set(10)
        self.pre.pack(side="left")
        ttk.Label(opts, text="  depois:").pack(side="left")
        self.post = ttk.Spinbox(opts, from_=3, to=45, width=4)
        self.post.set(5)
        self.post.pack(side="left")
        ttk.Button(opts, text="Abrir pasta de clipes", command=self.open_folder).pack(side="left", padx=12)

        btns = ttk.Frame(self, padding=(10, 8))
        btns.pack(fill="x")
        self.btn = ttk.Button(btns, text="Iniciar", command=self.toggle)
        self.btn.pack(side="left")
        self.status = ttk.Label(btns, text="Parado.")
        self.status.pack(side="left", padx=10)

        cols = ("live", "relogio", "palavra", "frase", "clipe")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        heads = ("Tempo da live", "Relógio", "Palavra", "Frase", "Clipe")
        widths = (100, 75, 110, 360, 190)
        for c, t, w in zip(cols, heads, widths):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree.bind("<Double-1>", self.copy_time)
        ttk.Label(self, text="Dois cliques numa linha copiam o tempo da live. "
                             "Com o clipe ligado, o vídeo é baixado em qualidade baixa.").pack(pady=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(200, self.poll)

    def open_folder(self):
        path = os.path.abspath(CLIP_DIR)
        os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def auto_detect(self):
        url = self.url.get().strip()
        if not url:
            return messagebox.showinfo("LiveCapture", "Cole o link da live primeiro.")
        self.status.config(text="Detectando início da live...")

        def job():
            ts = detect_start(url)

            def done():
                if ts:
                    self.start.delete(0, "end")
                    self.start.insert(0, dt.datetime.fromtimestamp(ts).strftime("%H:%M:%S"))
                    self.status.config(text="Início detectado.")
                else:
                    self.status.config(text="Não consegui detectar. Digite o horário manualmente.")
            self.after(0, done)

        threading.Thread(target=job, daemon=True).start()

    def toggle(self):
        if self.btn.cget("text") == "Parar":      # (um worker antigo ainda pode estar encerrando)
            self.stop_evt.set()
            if self.worker:
                self.worker.kill()
            self.btn.config(text="Iniciar")
            self.status.config(text="Parando...")
            return
        url = self.url.get().strip()
        kws = [w.strip() for w in self.words.get("1.0", "end").splitlines() if w.strip()]
        if not url or not kws:
            return messagebox.showinfo("LiveCapture", "Informe o link e ao menos uma palavra-chave.")
        try:
            live_start = parse_start(self.start.get())
            pre, post = int(self.pre.get()), int(self.post.get())
        except ValueError:
            return messagebox.showinfo(
                "LiveCapture", "Confira os campos: horário no formato HH:MM e segundos como números.")
        self.stop_evt = threading.Event()
        self.worker = Worker(url, kws, self.model.get(), live_start, self.out,
                             self.stop_evt, self.clip_var.get(), pre, post,
                             lang=self.lang.get())
        self.worker.start()
        self.btn.config(text="Parar")

    def on_close(self):
        self.stop_evt.set()
        if self.worker and self.worker.is_alive():
            self.worker.kill()
        self.destroy()

    def copy_time(self, _):
        sel = self.tree.selection()
        if sel:
            self.clipboard_clear()
            self.clipboard_append(self.tree.item(sel[0])["values"][0])

    def _log_hit(self, live, clock, word, text, clip_path):
        try:
            new = not os.path.exists(LOG_FILE)
            with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["tempo_live", "relogio", "palavra",
                                "frase", "clipe", "url"])
                w.writerow([live, clock, word, text, clip_path, self.url.get().strip()])
        except OSError:
            pass

    def poll(self):
        try:
            while not self.out.empty():
                msg = self.out.get()
                kind = msg[0]
                if kind == "status":
                    self.status.config(text=msg[1])
                elif kind == "end":
                    if len(msg) > 2 and msg[2] is not self.worker:
                        continue                  # "fim" de um worker antigo
                    self.status.config(text=msg[1])
                    self.btn.config(text="Iniciar")
                elif kind == "hit":
                    _, hid, clock, live, word, text, clip_path = msg
                    iid = self.tree.insert("", 0, values=(
                        live, clock, word, text, "gravando..." if clip_path else "—"))
                    self.rows[hid] = iid
                    self.bell()
                    self._log_hit(live, clock, word, text, clip_path)
                elif kind == "clip":
                    _, hid, ok, path = msg
                    iid = self.rows.get(hid)
                    if iid:
                        self.tree.set(iid, "clipe",
                                      ("✔ " + os.path.basename(path)) if ok else "falhou")
        except Exception as e:               # nunca deixa a interface travar
            try:
                self.status.config(text=f"Erro na interface: {e}")
            except Exception:
                pass
        finally:
            self.after(200, self.poll)


if __name__ == "__main__":
    App().mainloop()
