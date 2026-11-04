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
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager

import livecapture_gui as L


@contextmanager
def temp_dir():
    """Roda os passos dentro de uma pasta temporária (e volta ao sair)."""
    work = tempfile.mkdtemp(prefix="lctxt_")
    cwd = os.getcwd()
    os.chdir(work)
    try:
        yield work
    finally:
        os.chdir(cwd)
        shutil.rmtree(work, ignore_errors=True)

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
    def test_normalize_remove_acento_e_pontuacao(self):        self.assertEqual(L.normalize("AÇÃO! Ção,"), "acao cao")

    def test_normalize_colapsa_espacos(self):
        # pontuacao no meio nao pode quebrar palavra-chave de varias palavras
        self.assertEqual(L.normalize("Bom!  Dia,"), "bom dia")
        self.assertIn(" bom dia ", " " + L.normalize("Bom, dia!") + " ")

    def test_fmt(self):
        self.assertEqual(L.fmt(0), "00:00:00")
        self.assertEqual(L.fmt(3661), "01:01:01")
        self.assertEqual(L.fmt(-5), "00:00:00")

    def test_safe_name(self):
        self.assertEqual(L.safe_name("Olá Mundo!"), "ola_mundo")
        self.assertEqual(L.safe_name("!!!"), "palavra")

    def test_parse_start_valido(self):
        self.assertIsNotNone(L.parse_start("21:30"))
        self.assertIsNotNone(L.parse_start("21:30:15"))
        self.assertIsNone(L.parse_start(""))

    def test_parse_meta_canal_e_titulo(self):
        self.assertEqual(L.parse_meta("Dersin2k\nbora ranked"), ("Dersin2k", "bora ranked"))
        self.assertEqual(L.parse_meta("Canal"), ("Canal", None))     # sem título
        self.assertEqual(L.parse_meta("NA\nNA"), (None, None))       # extrator vazio
        self.assertEqual(L.parse_meta(""), (None, None))
        self.assertEqual(L.parse_meta("  \n  "), (None, None))

    def test_fetch_meta_live_real(self):
        url = os.environ.get("LC_LIVE_URL")
        if not url:
            self.skipTest("defina LC_LIVE_URL=<url> para testar o nome real da live")
        canal, _ = L.fetch_meta(url)
        self.assertTrue(canal, f"nao achei o nome do canal em {url}")

    def test_find_tool_ffmpeg(self):
        self.assertTrue(shutil.which(FFMPEG) or os.path.exists(FFMPEG), FFMPEG)

    def test_live_tag_tira_o_nome_do_link(self):
        self.assertEqual(L.live_tag("https://www.twitch.tv/cblol"), "cblol")
        self.assertEqual(L.live_tag("https://kick.com/nome-do-canal"), "nome_do_canal")
        # youtube termina em "streams"/"watch": cai para o nivel anterior
        self.assertEqual(L.live_tag("https://www.youtube.com/@Canal/streams"), "canal")
        self.assertEqual(L.live_tag("https://kick.com/aaa/?" + "x=1"), "aaa")
        # sem nada aproveitavel -> rotulo generico
        self.assertEqual(L.live_tag("https://youtube.com/live"), "live")

    def test_get_model_compartilha_a_mesma_instancia(self):
        if os.environ.get("LC_SLOW") != "1":
            self.skipTest("defina LC_SLOW=1 para testar o modelo real")
        a = L.get_model("tiny")
        b = L.get_model("tiny")
        self.assertIs(a, b)

    def test_tool_argv_dev_usa_o_exe_da_venv(self):
        argv = L.tool_argv("streamlink")
        self.assertEqual(len(argv), 1, argv)
        self.assertNotIn("--lctool", argv)

    def test_tool_argv_frozen_relanca_em_modo_cli(self):
        old = sys.__dict__.get("frozen", None)
        try:
            sys.frozen = True
            argv = L.tool_argv("streamlink")
            self.assertIn("--lctool", argv, argv)
            self.assertEqual(argv[argv.index("--lctool") + 1], "streamlink")
            self.assertTrue(argv[0].lower().endswith(".exe"), argv[0])
        finally:
            if old is None:
                sys.__dict__.pop("frozen", None)
            else:
                sys.frozen = old

    def test_falas_path_cai_na_pasta_falas(self):
        self.assertTrue(L.falas_path("canal").replace("\\", "/")
                        .startswith("falas/"), L.falas_path("canal"))

    def test_falalog_grava_falas_com_tempos(self):
        with temp_dir():
            f = L.FalaLog("canal")
            path = f.write("00:01:02", "12:34:56", "  olá mundo  ")
            f.close()
            self.assertTrue(path and os.path.exists(path), path)
            txt = open(path, encoding="utf-8").read()
            self.assertIn("00:01:02 | 12:34:56 | olá mundo", txt)
            self.assertIn("# LiveCapture", txt)          # cabeçalho na 1ª fala

    def test_falalog_continua_sem_duplicar_cabecalho(self):
        with temp_dir():
            a = L.FalaLog("canal")
            a.write("00:00:01", "12:00:00", "primeira")
            a.close()
            b = L.FalaLog("canal")
            b.write("00:00:02", "12:00:01", "segunda")
            b.close()
            txt = open(L.falas_path("canal"), encoding="utf-8").read()
            self.assertIn("primeira", txt)
            self.assertIn("segunda", txt)
            self.assertEqual(txt.count("# LiveCapture"), 1)

    def test_falalog_ignora_fala_vazia(self):
        with temp_dir():
            f = L.FalaLog("canal")
            self.assertIsNone(f.write("00:00:01", "12:00:00", "   "))
            f.close()
            self.assertFalse(os.path.exists(L.falas_path("canal")))


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


# ------------------------------------------------------------------- multi-live
@unittest.skipUnless(L.tk, "tkinter ausente (o teste nao abre janela de verdade)")
class TestMultiLive(unittest.TestCase):
    """A interface com abas: cada live vive em uma aba independente."""

    def setUp(self):
        self.app = L.App()

    def tearDown(self):
        self.app.destroy()

    def test_come_com_uma_aba_e_adiciona(self):
        self.assertEqual(len(self.app.panels), 1)
        self.app.add_panel()
        self.assertEqual(len(self.app.panels), 2)

    def test_fechar_aba_remove_e_para_o_worker(self):
        p0 = self.app.panels[0]
        self.app.add_panel()
        p1 = self.app.panels[1]
        app = self.app
        app.remove_panel(p1)
        self.assertNotIn(p1, app.panels)
        self.assertTrue(p1._closed)              # parou o laco de mensagens
        app.remove_panel(p0)
        self.assertEqual(len(app.panels), 0)

    def test_remocao_nao_perde_outra_aba(self):
        self.app.add_panel()
        self.app.add_panel()
        meio = self.app.panels[1]
        self.app.remove_panel(meio)
        self.assertEqual([p for p in self.app.panels][0], self.app.panels[0])
        self.assertEqual(len(self.app.panels), 2)

    def test_apply_name_renomeia_a_aba(self):
        p = self.app.panels[0]
        p.apply_name("Dersin2k — bora ranked")
        self.assertEqual(self.app.nb.tab(p, "text"), "○ Dersin2k — bora ranked")

    def test_apply_name_ignora_vazio(self):
        p = self.app.panels[0]
        p.display_name = "nome bom"
        p.apply_name("   ")
        self.assertEqual(p.display_name, "nome bom")

    def test_refresh_tab_mostra_nome_display(self):
        p = self.app.panels[0]
        p.tag = "canal_x"
        p.apply_name("Canal X")
        self.assertEqual(self.app.nb.tab(p, "text"), "○ Canal X")


def glob_clips(clip_dir):
    if not os.path.isdir(clip_dir):
        return []
    return [os.path.join(clip_dir, f) for f in sorted(os.listdir(clip_dir))
            if f.endswith(".mp4")]


if __name__ == "__main__":
    unittest.main(verbosity=2)
