# LiveCapture

**Versão do código-fonte: 1.4.0** — veja [CHANGELOG-1.4.0.md](CHANGELOG-1.4.0.md) para as novidades.

Monitora **várias lives ao mesmo tempo** (YouTube, Twitch, Kick), uma em cada
aba, e detecta palavras-chave na **voz** do streamer, salvando um clipe MP4 com
alguns segundos **antes e depois** da palavra. Cada aba mostra uma tabela com
cada ocorrência (tempo da live, relógio, palavra, frase) e o clipe gerado.

> Guia de instalação passo a passo: **[INSTALACAO.md](INSTALACAO.md)**.

## Como funciona

O programa mantém só os últimos ~2,5 minutos de cada live numa pasta
temporária, apagando o que fica velho. Quando uma palavra aparece, ele junta os
pedaços do buffer ao redor daquele momento e salva um MP4 em `clipes/` — com o
**rótulo do canal** no nome do arquivo. Ao fechar a aba, a pasta temporária
daquela live é apagada — só os clipes, o `ocorrencias.csv` e as falas
permanecem. São processados no máximo dois clipes ao mesmo tempo para
controlar o uso de recursos.

## Onde ficam os arquivos

- **Clipes, registro e falas:** `Vídeos\LiveCapture` (`clipes\`,
  `ocorrencias.csv`, `falas\<canal>.txt`). Use o botão **Abrir pasta de
  clipes**. Quando rodado pelo código-fonte, ficam na pasta atual do projeto.

## Instalação

O jeito mais fácil: baixe o **`LiveCapture-portatil.zip`** em
<https://github.com/Vellllloooiiiraam/LiveCapture/releases/latest>, extraia (não
rode de dentro do ZIP) e dê duplo clique em `LiveCapture.exe`. O pacote já vem
com **streamlink, yt-dlp e ffmpeg embutidos** — **não precisa de Python
instalado**. Junto vai o `LiveCapture-cli.exe` (modo console).

> **Atenção (primeira live):** o modelo de transcrição **não** vai no pacote;
> ele é baixado sozinho na primeira execução (precisa de internet uma vez).

### A partir do código-fonte

Rodando da venv do projeto (`.venv-livecapture`):

```powershell
powershell -ExecutionPolicy Bypass -File build_livecapture.ps1   # gera dist\LiveCapture\ + zip
```

O script reúne o ffmpeg, roda o PyInstaller e gera o
`LiveCapture-portatil.zip` final.

## Uso

1. Abra uma aba por live (**＋ Nova live**; dele com **Fechar aba ✕**).
2. Cole o link da live e digite as palavras-chave (uma por linha).
3. (Opcional) Clique em **Detectar**: ele preenche o início da live **e** puxa o
   nome do canal e o título para a aba. Para renomear na mão, use **✏️** ou dê
   **duplo clique no cabeçalho** da aba.
4. Escolha o modelo (`tiny`/`base`/`small`...; no multi-live, comece por
   **`base`/`tiny`**), marque ou desmarque **Salvar clipe** e ajuste os
   segundos antes/depois. Com o clipe **desligado**, o programa registra só o
   tempo da live, a frase e o relógio (sem clipe e sem áudio gravado) — para
   clipar na mão depois.
5. Clique em **Iniciar live**. Dois cliques numa linha copiam o tempo da live.
   Quando a primeira fala sai, aparece embaixo o TXT com a transcrição
   completa (`falas/<canal>.txt`).

Modo console (sem janela):

```powershell
.\LiveCapture-cli.exe --monitor https://www.twitch.tv/algumcanal --kws palavra1,palavra2
```

Dicas durante o uso: se a placa NVIDIA não tiver CUDA, o programa **cai sozinho
para o processador**; e se a live cair, a aba avisa sem derrubar as outras.

## Requisitos

- Windows.
- O ZIP das releases **não precisa de nada instalado** (tudo embutido).
- Rodando pelo código-fonte: Python 3.11–3.13 (no 3.14+ o PyAV ainda não tem
  wheel) e `ffmpeg` no sistema.

Arquivo `requirements.txt`: `numpy`, `faster-whisper`, `streamlink`, `yt-dlp` e
`av>=11,<19` (a versão 19 do PyAV removeu um parâmetro usado pelo faster-whisper).

## Avisos

- **Download do modelo:** o modelo de transcrição **não** vem no download. Ele é
  baixado na primeira live (`tiny` ~75 MB, `base` ~140 MB, `small` ~500 MB), ou
  seja, a primeira live também precisa de internet. Depois fica em cache.
- **Falso positivo de antivírus:** executáveis feitos com PyInstaller costumam
  ser sinalizados por antivírus/Windows Defender. É esperado e **não** indica
  vírus. Libere o arquivo nas exceções ou clique em *Executar mesmo assim*.
- **ffmpeg:** o ZIP das releases inclui o `ffmpeg.exe` na pasta `_internal\bin`.
  O ffmpeg é um projeto separado (LGPL/GPL) — veja
  <https://ffmpeg.org/legal.html>.

## Testes

```powershell
$venv = "C:\Users\dgcav\.venv-livecapture\Scripts\python.exe"
& $venv test_livecapture.py            # testes rápidos, sem rede
$env:LC_SLOW="1"; & $venv test_livecapture.py                        # inclui o modelo real
$env:LC_LIVE_URL="https://www.twitch.tv/algumcanal"; & $venv test_livecapture.py  # live real
```

## Build

`build_livecapture.ps1` copia o `ffmpeg` do sistema para `build_bin\`,
executa o PyInstaller com `livecapture.spec` e gera:

- `dist\LiveCapture\LiveCapture.exe` — interface gráfica;
- `dist\LiveCapture\LiveCapture-cli.exe` — modo console (`--monitor`/`--lctool`);
- `LiveCapture-portatil.zip` — pacote final (~220 MB).

O spec faz `collect_all` de `streamlink`, `yt_dlp` e `faster_whisper` e leva os
assets do VAD (silero) junto — os dois executáveis saem de um mesmo
`Analysis`/`PYZ`.

## Estrutura

- `livecapture_gui.py` — programa e interface (multi-live com abas).
- `livecapture.spec` / `build_livecapture.ps1` — empacotamento (exe congelado).
- `test_livecapture.py` — testes.
- Legado da 1.2.x (bootstrap/instalador): `launcher.py`, `bootstrap.py`,
  `instalar.ps1`/`instalar.bat`, `build_exe.ps1` e
  `.github/workflows/build-release.yml` — mantidos no repositório, mas o
  caminho principal das releases agora é o ZIP congelado.
- `INSTALACAO.md` — tutorial de instalação.
