"""
Testes do LiveCapture.

Rode com o Python do ambiente virtual:

    C:\\Users\\dgcav\\.venv-livecapture\\Scripts\\python.exe test_livecapture.py

Testes pesados (opcionais), ligados por variavel de ambiente:

    LC_SLOW=1                       -> testa o Whisper de verdade (baixa o modelo "tiny")
    LC_LIVE_URL=https://...         -> testa captura de uma live real (usa o Worker)
    LC_LIVE_SEC=30                  -> tempo de captura da live (padrao 30s)

Exemplos (PowerShell):
    $env:LC_SLOW=1; & $venv test_livecapture.py
    $env:LC_LIVE_URL="https://www.twitch.tv/gratis150ml"; & $venv test_livecapture.py
"""
import csv
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

import livecapture_gui as L

FFMPEG = L.find_tool("ffmpeg")
FFPROBE = L.find_tool("ffprobe")
HAVE_FFMPEG = bool(shutil.which(FFMPEG) or os.path.exists(FFMPEG))
HAVE_FFPROBE = bool(shutil.which(FFPROBE) or os.path.exists(FFPROBE))

# ------------------------------------------------------------------ helpers
def _make_segments(tmp_dir, n=6, seconds=2):
    """Gera n segmentos .ts de teste e devolve uma lista.csv no formato do ffmpeg."""
    segs = []
    for i in range(n):
        p = os.path.join(tmp_dir, f"seg_{i:06d}.ts")
        subprocess.run(
            [FFMPEG, "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "testsrc=size=320x240:rate=15",
             "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds),
             "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
             "-f", "mpegts", p], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segs.append(p)
    list_path = os.path.join(tmp_dir, "lista.csv")
    with open(list_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for i, p in enumerate(segs):
            w.writerow([os.path.basename(p), f"{i * seconds:.6f}", f"{(i + 1) * seconds:.6f}"])
    return list_path


def _duration(path):
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip()
    return float(out) if out else None


# ------------------------------------------------------------- funcoes puras
class TestUtils(unittest.TestCase):
    def test_normalize_remove_acento_e_pontuacao(self):
        self.assertEqual(L.normalize("AÇÃO! Ção,"), "acao cao")

    def test_normalize_colapsa_espacos(self):
        # pontuacao no meio nao pode quebrar palavra-chave de varias palavras
        self.assertEqual(L.normalize("Bom!  Dia,"), "bom dia")
        self.assertIn(" bom dia ", " " + L.normalize("Bom, dia!") + " ")

    def test_normalize_preserva_alfabetos_unicode(self):
        self.assertEqual(L.normalize("こんにちは 世界! Привет мир!"),
                         "こんにちは 世界 привет мир")
        self.assertEqual(L.normalize("مرحبا بالعالم"), "مرحبا بالعالم")

    def test_fmt(self):
        self.assertEqual(L.fmt(0), "00:00:00")
        self.assertEqual(L.fmt(3661), "01:01:01")
        self.assertEqual(L.fmt(-5), "00:00:00")

    def test_safe_name(self):
        self.assertEqual(L.safe_name("Olá Mundo!"), "ola_mundo")
        self.assertEqual(L.safe_name("!!!"), "palavra")
        self.assertEqual(L.safe_name("日本語"), "日本語")

    def test_parse_start_valido(self):
        self.assertIsNotNone(L.parse_start("21:30"))
        self.assertIsNotNone(L.parse_start("21:30:15"))
        self.assertIsNone(L.parse_start(""))

    def test_find_tool_ffmpeg(self):
        self.assertTrue(shutil.which(FFMPEG) or os.path.exists(FFMPEG), FFMPEG)


# --------------------------------------------------------- buffer / clipes
class TestBuffer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lctest_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg nao instalado")
    def test_read_segments(self):
        list_path = _make_segments(self.tmp, n=6)
        rows = L.read_segments(list_path)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0], ("seg_000000.ts", 0.0, 2.0))
        self.assertEqual(rows[-1][2], 12.0)

    def test_read_segments_ignora_linha_parcial(self):
        list_path = os.path.join(self.tmp, "lista.csv")
        with open(list_path, "w", encoding="utf-8") as f:
            f.write("seg_000000.ts,0.0,2.0\n")
            f.write("seg_000001.ts,2.0")          # incompleta (sendo escrita)
        self.assertEqual(len(L.read_segments(list_path)), 1)

    def test_cleanup_old_apaga_antigos_e_preserva_recentes(self):
        list_path = os.path.join(self.tmp, "lista.csv")
        names = []
        with open(list_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for i in range(100):                   # 200s de buffer
                name = f"seg_{i:06d}.ts"
                open(os.path.join(self.tmp, name), "wb").close()
                w.writerow([name, f"{i * 2:.6f}", f"{(i + 1) * 2:.6f}"])
                names.append(name)
        deleted = set()
        L.cleanup_old(self.tmp, list_path, deleted)
        # newest end=200, limite=200-150=50 -> apaga segmentos com end<50 (ends 2..48 = 24)
        self.assertEqual(len(deleted), 24)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, names[0])))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, names[23])))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, names[24])))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, names[-1])))

    @unittest.skipUnless(HAVE_FFMPEG and HAVE_FFPROBE, "ffmpeg/ffprobe nao instalados")
    def test_make_clip_gera_mp4_valido(self):
        list_path = _make_segments(self.tmp, n=6)
        out = os.path.join(self.tmp, "out", "clipe_teste.mp4")
        ok = L.make_clip(self.tmp, list_path, media_t=6, pre=3, post=3,
                         out_path=out, stop=threading.Event())
        self.assertTrue(ok and os.path.exists(out), out)
        dur = _duration(out)
        self.assertIsNotNone(dur)
        # janela pedida [3,9] cai em 4 segmentos inteiros de 2s = ~8s
        self.assertTrue(4.5 <= dur <= 9.5, dur)

    def test_make_clip_sem_pedacos_retorna_false(self):
        list_path = os.path.join(self.tmp, "lista.csv")
        open(list_path, "w").close()
        out = os.path.join(self.tmp, "x.mp4")
        self.assertFalse(L.make_clip(self.tmp, list_path, 10, 3, 3, out,
                                     threading.Event()))


# ------------------------------------------- stop, fallback de GPU, find_tool
class TestRobustez(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="lctest2_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipUnless(HAVE_FFMPEG and HAVE_FFPROBE, "ffmpeg/ffprobe nao instalados")
    def test_make_clip_ainda_corta_depois_de_parar(self):
        list_path = _make_segments(self.tmp, n=6)
        out = os.path.join(self.tmp, "out", "clipe_stop.mp4")
        stop = threading.Event()
        stop.set()                               # usuario ja clicou em Parar
        ok = L.make_clip(self.tmp, list_path, media_t=6, pre=3, post=3,
                         out_path=out, stop=stop)
        self.assertTrue(ok and os.path.exists(out))

    def test_transcribe_cai_para_cpu_quando_gpu_falha(self):
        class Seg:
            text = "ok"; start = 0.0

        class GpuQuebrada:
            def transcribe(self, audio, **kw):
                def gen():
                    raise RuntimeError("Library cublas64_12.dll is not found")
                    yield
                return gen(), None

        class Cpu:
            def transcribe(self, audio, **kw):
                return iter([Seg()]), None

        w = L.Worker("http://x", ["a"], "tiny", None, queue.Queue(),
                     threading.Event(), False, 3, 3)
        w.model = GpuQuebrada()
        w._load_model = lambda device="auto": Cpu()
        segs = w._transcribe(b"")
        self.assertEqual([s.text for s in segs], ["ok"])
        self.assertTrue(w.on_cpu)

    def test_worker_idioma_auto_vira_none(self):
        w = L.Worker("http://x", ["a"], "tiny", None, queue.Queue(),
                     threading.Event(), False, 3, 3, lang="auto")
        self.assertIsNone(w.lang)
        w2 = L.Worker("http://x", ["a"], "tiny", None, queue.Queue(),
                      threading.Event(), False, 3, 3)
        self.assertEqual(w2.lang, "pt")

    def test_find_tool_acha_na_pasta_extra(self):
        fake = os.path.join(self.tmp, "ferramenta_falsa_lc.exe")
        open(fake, "wb").close()
        old = L._extra_tool_dirs
        L._extra_tool_dirs = lambda: [self.tmp]
        try:
            self.assertEqual(L.find_tool("ferramenta_falsa_lc"), fake)
        finally:
            L._extra_tool_dirs = old


# --------------------------------------------------------------- whisper
class TestWhisper(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("LC_SLOW") == "1",
                         "defina LC_SLOW=1 para testar o Whisper (baixa o modelo)")
    @unittest.skipUnless(HAVE_FFMPEG, "ffmpeg nao instalado")
    def test_transcreve_audio(self):
        from faster_whisper import WhisperModel
        tmp = tempfile.mkdtemp(prefix="lcwhisper_")
        try:
            wav = os.path.join(tmp, "tom.wav")
            subprocess.run(
                [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "sine=frequency=440", "-t", "3", "-ar", "16000", "-ac", "1", wav],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segs, _ = model.transcribe(wav, language="pt", vad_filter=True, beam_size=1)
            list(segs)  # nao deve levantar
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------- live
class TestLive(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("LC_LIVE_URL"),
                         "defina LC_LIVE_URL=<url> para testar uma live real")
    def test_worker_captura_live(self):
        url = os.environ["LC_LIVE_URL"]
        secs = int(os.environ.get("LC_LIVE_SEC", "30"))
        work = tempfile.mkdtemp(prefix="lclive_")
        cwd = os.getcwd()
        os.chdir(work)
        try:
            out = queue.Queue()
            stop = threading.Event()
            w = L.Worker(url, ["a", "de", "que"], "tiny", None, out, stop,
                         True, 6, 4)
            w.start()
            monitored = hit = clip_ok = False
            t0 = time.time()
            while time.time() - t0 < secs:
                try:
                    m = out.get(timeout=1)
                except queue.Empty:
                    continue
                if m[0] == "status" and m[1] == "Monitorando...":
                    monitored = True
                elif m[0] == "hit":
                    hit = True
                elif m[0] == "clip" and m[2]:
                    clip_ok = True
                elif m[0] == "end":
                    break
            stop.set()
            w.kill()
            time.sleep(4)
            self.assertTrue(monitored, "o Worker nao chegou a monitorar a live")
            if clip_ok:
                clips = glob_clips(os.path.join(work, "clipes"))
                self.assertTrue(clips, "clip reportado como ok, mas nenhum arquivo encontrado")
                self.assertGreater(os.path.getsize(clips[0]), 0)
            else:
                # pode nao haver fala no trecho (ex.: musica) e nenhum clipe sair
                print(f"\n[live] sem clipe em {secs}s (hits={hit}); "
                      f"o pipeline de captura funcionou.")
        finally:
            os.chdir(cwd)
            shutil.rmtree(work, ignore_errors=True)


def glob_clips(clip_dir):
    if not os.path.isdir(clip_dir):
        return []
    return [os.path.join(clip_dir, f) for f in sorted(os.listdir(clip_dir))
            if f.endswith(".mp4")]


if __name__ == "__main__":
    unittest.main(verbosity=2)
