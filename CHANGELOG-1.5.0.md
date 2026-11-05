# LiveCapture 1.5.0

## Novidades

- **Sem janelas de console**: os subprocessos (streamlink, yt-dlp, ffmpeg) não
  abrem mais aquelas janelinhas pretas de CMD no Windows — tudo roda escondido
  (`CREATE_NO_WINDOW`).
- **Muito mais leve (RAM e CPU)**:
  - o modelo passou a rodar em **`int8`** em vez de `float32`. Medido com fala
    real (modelo `tiny`, 11s): carregar caiu de 1,61s → **0,58s**; transcrever
    de 1,34s → **0,75s**; RAM do modelo de 190 MB → **54 MB** (~3,5× menos).
    No modelo `small` (padrão antigo) isso significa ~500 MB → ~150 MB.
  - `num_workers` de 3 → **2** e **limite de 2 núcleos** por transcrição, pra o
    Whisper não chupar 100% da máquina.
  - modelo padrão das abas novas: **`base`** (em vez de `small`).
- Ajustável por variável de ambiente, se precisar afrouxar:
  `LC_COMPUTE=int8_float32` (ou `float32`) e `LC_THREADS=0` (todos os núcleos).

## Verificação

- `python test_livecapture.py`: 31 testes aprovados; 4 opcionais ignorados.
- Bench com fala real (jfk.wav, 11s) comparando `float32` e `int8` — números
  acima.
- Captura real: encerramento limpo quando o canal está offline, sem processos
  sobrando.
