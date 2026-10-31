# LiveCapture

**Versão do código-fonte: 1.2.3** — veja [CHANGELOG-1.2.3.md](CHANGELOG-1.2.3.md) para as novidades.

Detecta palavras-chave na **voz** de uma live (YouTube, Twitch, Kick) e salva um
clipe MP4 com alguns segundos **antes e depois** da palavra. Tem uma interface
gráfica simples e mostra uma tabela com cada ocorrência (tempo da live, relógio,
palavra, frase) e o clipe gerado.

> Guia de instalação passo a passo: **[INSTALACAO.md](INSTALACAO.md)**.

## Como funciona

O programa mantém só os últimos ~2,5 minutos da live numa pasta temporária,
apagando o que fica velho. Quando uma palavra aparece, ele junta os pedaços do
buffer ao redor daquele momento e salva um MP4 em `clipes/`. Ao parar, aguarda
a finalização dos clipes em andamento antes de apagar a pasta temporária — só os
clipes (e o `ocorrencias.csv`) permanecem. São processados no máximo dois clipes
ao mesmo tempo para controlar o uso de recursos.

## Onde ficam os arquivos

- **Programa e dependências:** `%LOCALAPPDATA%\LiveCapture` (`app\`, `venv\` e o
  `ffmpeg.exe`). Para desinstalar, apague essa pasta.
- **Clipes e registro:** `Vídeos\LiveCapture` (`clipes\` e `ocorrencias.csv`).
  Use o botão **Abrir pasta de clipes**. Quando rodado direto pelo código-fonte,
  ficam na pasta atual do projeto.

## Instalação

O jeito mais fácil: baixe o **`LiveCapture.zip`** em
<https://github.com/Vellllloooiiiraam/LiveCapture/releases/latest>, extraia (não
rode de dentro do ZIP) e dê duplo clique em `LiveCapture.exe`. O ZIP **já inclui
o `ffmpeg.exe`**; na primeira execução o programa baixa o Python e as
dependências. Veja o passo a passo em [INSTALACAO.md](INSTALACAO.md).

### A partir do código-fonte

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1    # instala e cria atalho
powershell -ExecutionPolicy Bypass -File build_exe.ps1   # gera dist\LiveCapture.exe
```

Atalhos do exe: `LiveCapture.exe --check` (só verifica) e `LiveCapture.exe --setup`
(só instala/atualiza).

## Uso

1. Cole o link da live.
2. Digite as palavras-chave (uma por linha).
3. (Opcional) Informe o início da live em `HH:MM` ou clique em **Detectar**.
4. Escolha o **idioma da fala** do streamer (ou `auto`), escolha **Baixar clipe**
   (**Sim**/**Não**) e ajuste os segundos antes/depois. Em **Não**, o programa
   registra só o tempo da live, a frase e o relógio (sem clipe e sem áudio
   gravado).
5. Clique em **Iniciar**. Dois cliques numa linha copiam o tempo da live.

Dicas durante o uso: se a placa NVIDIA não tiver CUDA, o programa **cai sozinho
para o processador**; se a transcrição não acompanhar a live, aparece o aviso
*"o PC está atrasado"* (use um modelo menor); e se a live cair, o motivo do
`streamlink` aparece no fim da mensagem.

## Requisitos

- Windows.
- Python 3.11–3.13 (o instalador resolve isso; no 3.14+ o PyAV ainda não tem
  wheel).
- `ffmpeg`: o ZIP das releases **já inclui** o `ffmpeg.exe`. Pelo código-fonte, se
  não houver nenhum no sistema, o instalador **baixa um build** automaticamente
  (e o `winget` fica só como plano B).

Arquivo `requirements.txt`: `numpy`, `faster-whisper`, `streamlink`, `yt-dlp` e
`av>=11,<19` (a versão 19 do PyAV removeu um parâmetro usado pelo faster-whisper).

## Avisos

- **Download do modelo:** o modelo de transcrição **não** vem no download. Ele é
  baixado na primeira live (`tiny` ~75 MB, `base` ~140 MB, `small` ~500 MB), ou
  seja, a primeira live também precisa de internet. Depois fica em cache.
- **Falso positivo de antivírus:** executáveis feitos com PyInstaller costumam
  ser sinalizados por antivírus/Windows Defender. É esperado e **não** indica
  vírus. Libere o arquivo nas exceções ou clique em *Executar mesmo assim*.
- **ffmpeg:** o ZIP das releases inclui `ffmpeg.exe`; pelo código-fonte o
  instalador baixa um build se faltar. O ffmpeg é um projeto separado
  (LGPL/GPL) — veja <https://ffmpeg.org/legal.html>.

## Testes

```powershell
$venv = "$env:LOCALAPPDATA\LiveCapture\venv\Scripts\python.exe"
& $venv test_livecapture.py            # testes rápidos, sem rede
$env:LC_SLOW="1"; & $venv test_livecapture.py         # inclui o Whisper
$env:LC_LIVE_URL="https://www.twitch.tv/algumcanal"; & $venv test_livecapture.py  # live real
```

## Build

`build_exe.ps1` cria um venv de build (`.venv-build`), instala o PyInstaller e
gera `dist\LiveCapture.exe` empacotando `launcher.py`, `bootstrap.py`,
`livecapture_gui.py` e `requirements.txt`.

O workflow `.github/workflows/build-release.yml` (Python 3.11, `windows-latest`)
faz o mesmo no GitHub ao enviar uma tag `v*`: compila o exe, **baixa o ffmpeg** e
publica um **`LiveCapture.zip`** com `LiveCapture.exe` + `ffmpeg.exe` +
`LEIA-ME.md` na release.

## Estrutura

- `livecapture_gui.py` — programa e interface.
- `launcher.py` / `bootstrap.py` — entrada do exe e instalação das dependências.
- `instalar.ps1` / `instalar.bat` — instalador.
- `build_exe.ps1` — build do executável.
- `.github/workflows/build-release.yml` — build e release automáticos.
- `INSTALACAO.md` — tutorial de instalação.
- `test_livecapture.py` — testes.
