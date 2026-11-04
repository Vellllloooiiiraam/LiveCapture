# LiveCapture 1.3.0

## Novidades

- **Multi-live com abas**: cada live monitorada fica em uma aba própria
  (link, palavras-chave, início da live, modelo e clipe individuais), com
  botões **＋ Nova live** e **Fechar aba ✕**. Uma live que cai não derruba as
  outras.
- **Modelo de voz compartilhado**: todas as abas usam uma única cópia do
  Whisper na memória (antes, cada live carregava o modelo de novo).
- **Transcrição completa por live**: além do `ocorrencias.csv`, cada live grava
  tudo que foi dito em `falas/<canal>.txt` (`tempo_live | relógio | fala`),
  útil para revisar as falas e clipar na mão depois.
- **Rótulo da live nos arquivos**: os clipes ganham o nome do canal —
  `clipe_<canal>_<data>_<palavra>.mp4` — para não colidir quando várias lives
  capturam ao mesmo tempo.
- **Executável 100% portátil (novo empacotamento)**: `build_livecapture.ps1`
  + `livecapture.spec` geram dois exe com PyInstaller, embutindo
  `streamlink`, `yt-dlp` e `ffmpeg` — **não precisa de Python** na máquina que
  recebe o pacote:
  - `LiveCapture.exe` — interface gráfica;
  - `LiveCapture-cli.exe` — modo console: `--monitor URL --kws kw1,kw2`
    (monitora sem janela e imprime os eventos) e `--lctool` (os subprocessos
    de streamlink/yt-dlp saem daqui).
- O modo CLI embutido acompanha a nova estrutura do `yt-dlp` (2026.10.26:
  `yt_dlp:main`, sem `yt_dlp.cli`).
- Os `assets` do VAD do faster-whisper (silero) agora vão no pacote — sem ele
  o empacotado falhava com `NO_SUCHFILE silero_vad_v6.onnx`.

## Diferenças em relação à 1.2.x

Empacotamento trocado: a 1.2.x gerava um `LiveCapture.exe` com *bootstrap*
(baixava Python e dependências na primeira execução). A 1.3.0 congela tudo no
PyInstaller; `launcher.py`, `bootstrap.py` e `instalar.ps1` continuam no
repositório, mas o caminho principal das releases passa a ser o ZIP congelado.

## Verificação

- `py_compile`: aprovado para os módulos Python principais.
- `python test_livecapture.py`: 24 testes aprovados; 3 opcionais ignorados
  (modelo real, interface pesada e live ao vivo real).
- Teste real com **duas lives simultâneas**: hits detectados em ambas, 12
  clipes MP4 válidos (h264+aac) sem colisão de nomes e nenhum processo
  remanescente ao encerrar.
- A/B dev × executável congelado na **mesma live e no mesmo instante**:
  detecção, clipes e encerramento limpos no empacotado.
