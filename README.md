# LiveCapture

Detecta palavras-chave na **voz** de uma live (YouTube, Twitch, Kick) e salva um
clipe MP4 com alguns segundos **antes e depois** da palavra. Tem uma interface
gráfica simples e mostra uma tabela com cada ocorrência (tempo da live, relógio,
palavra, frase) e o clipe gerado.

## Como funciona

O programa mantém só os últimos ~2,5 minutos da live numa pasta temporária,
apagando o que fica velho. Quando uma palavra aparece, ele junta os pedaços do
buffer ao redor daquele momento e salva um MP4 em `clipes/`. Ao parar, a pasta
temporária é apagada — só os clipes (e o `ocorrencias.csv`) permanecem.

## Instalação

Precisa de internet na primeira vez (baixa o Python, os pacotes e o ffmpeg).

### Opção 1: instalador

```powershell
powershell -ExecutionPolicy Bypass -File instalar.ps1
```

Cria o ambiente em `%LOCALAPPDATA%\LiveCapture`, instala as dependências,
confere/instala o ffmpeg e cria um atalho na Área de Trabalho.
(ou dê duplo clique em `instalar.bat`)

### Opção 2: executável

Gere o `LiveCapture.exe`:

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1
# gera dist\LiveCapture.exe
```

O exe é leve: na primeira execução ele baixa as dependências e depois abre a
interface. Atalhos úteis: `LiveCapture.exe --check` (só verifica) e
`LiveCapture.exe --setup` (só instala/atualiza).

## Uso

1. Cole o link da live.
2. Digite as palavras-chave (uma por linha).
3. (Opcional) Informe o início da live em `HH:MM` ou clique em **Detectar**.
4. Marque **Salvar clipe** e ajuste os segundos antes/depois.
5. Clique em **Iniciar**. Dois cliques numa linha copiam o tempo da live.

## Requisitos

- Windows.
- Python 3.11–3.13 (o instalador resolve isso; no 3.14+ o PyAV ainda não tem
  wheel).
- `ffmpeg` no PATH (o instalador tenta instalar via `winget`).

Arquivo `requirements.txt`: `numpy`, `faster-whisper`, `streamlink`, `yt-dlp` e
`av>=11,<19` (a versão 19 do PyAV removeu um parâmetro usado pelo faster-whisper).

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

## Estrutura

- `livecapture_gui.py` — programa e interface.
- `launcher.py` / `bootstrap.py` — entrada do exe e instalação das dependências.
- `instalar.ps1` / `instalar.bat` — instalador.
- `build_exe.ps1` — build do executável.
- `test_livecapture.py` — testes.
