# Como instalar o LiveCapture (passo a passo)

Este tutorial é para quem só quer usar o programa. Você **não precisa** saber
programar nem instalar o Python: o pacote pronto já vem com tudo dentro.

## Opção 1 — Baixar o programa pronto (mais fácil)

1. Abra a página de **Releases**:
   <https://github.com/Vellllloooiiiraam/LiveCapture/releases/latest>
2. Em **Assets**, baixe o arquivo **`LiveCapture-portatil.zip`**.
3. Clique com o botão direito no ZIP → **Extrair tudo...** → escolha uma pasta
   (por exemplo `C:\LiveCapture`) e confirme.
   - **Não** rode direto de dentro do ZIP: extraia primeiro.
4. Dentro da pasta extraída, dê **duplo clique** em **`LiveCapture.exe`**.

Pronto — o programa **não precisa de Python instalado**: `streamlink`, `yt-dlp`
e `ffmpeg` já vão embutidos no pacote. Junto com o `LiveCapture.exe` também vem
o `LiveCapture-cli.exe`, que monitora uma live pelo terminal (sem janela):

```powershell
.\LiveCapture-cli.exe --monitor https://www.twitch.tv/algumcanal --kws palavra1,palavra2
```

### Sobre o modelo de transcrição

O modelo do Whisper **não** vem no pacote (o ZIP ficaria gigante). Ele é baixado
sozinho na **primeira live** de cada modelo escolhido:

- `tiny` ~75 MB, `base` ~140 MB, `small` ~500 MB, `medium` ~1,5 GB.

Ou seja, a **primeira live também precisa de internet**. Depois o modelo fica
guardado em cache e não é baixado de novo.

## Como usar (resumo)

1. Abra uma aba por live com **＋ Nova live** (fecha com **Fechar aba ✕**).
2. Cole o link da live e digite as **palavras-chave** (uma por linha).
3. (Opcional) Clique em **Detectar**: ele preenche o início da live e o **nome
   do canal + título** na aba. Dá para renomear na mão com **✏️** ou duplo
   clique no cabeçalho da aba.
4. Escolha o **modelo** (`tiny`/`base`/`small`; com várias lives, comece por
   `base`/`tiny`), e marque **Salvar clipe** — desligado, o programa registra
   só o tempo da live no `ocorrencias.csv`, para clipar na mão depois.
5. Clique em **Iniciar live**. Cada palavra detectada gera uma linha na tabela
   e um clipe `clipes/clipe_<canal>_<data>_<palavra>.mp4`.
6. A transcrição **completa** de cada live fica em `falas/<canal>.txt`
   (o caminho aparece na aba quando a primeira fala sai).

## Opção 2 — Rodar pelo código-fonte

Se você baixou o repositório em vez do ZIP:

1. Instale o **Python 3.11–3.13** de <https://www.python.org/downloads/>
   (marque *"Add python.exe to PATH"*). No 3.14+ o PyAV ainda não tem wheel.
2. No terminal, dentro da pasta do projeto:

   ```powershell
   python -m venv .venv-livecapture
   ".\.venv-livecapture\Scripts\python.exe" -m pip install -r requirements.txt
   ".\.venv-livecapture\Scripts\python.exe" livecapture_gui.py
   ```

   (é preciso ter um `ffmpeg` no sistema).

3. Para gerar o pacote portátil no seu PC:

   ```powershell
   powershell -ExecutionPolicy Bypass -File build_livecapture.ps1
   ```

   Resultado: `dist\LiveCapture\` com os dois exe e o
   `LiveCapture-portatil.zip`.

## Onde as coisas ficam

- **Clipes, registro e falas:** `Vídeos\LiveCapture` — `clipes\`,
  `ocorrencias.csv` e `falas\<canal>.txt` (use o botão **Abrir pasta de
  clipes**). Quando rodado pelo código-fonte, ficam na pasta atual do projeto.

## Problemas comuns

**"O Windows protegeu o seu PC" / antivírus acusa o exe.**
Programas feitos com PyInstaller costumam dar **falso positivo** — é comum e não
significa que há vírus. Para continuar: clique em **Mais informações** →
**Executar mesmo assim**, ou adicione a pasta à lista de exceções do antivírus.

**A janela não abre / nada acontece.**
Confirme que extraiu o ZIP antes de rodar. Para testar a parte de linha de
comando do pacote:

```powershell
.\LiveCapture-cli.exe --lctool streamlink --version
.\LiveCapture-cli.exe --lctool yt-dlp --version
```

Se os dois responderem a versão, o pacote está íntegro.

**Deu erro durante a captura da live.**
Confira se o `streamlink` consegue ver o canal (o programa usa ele por baixo).
Lives privadas ou que exigem login podem falhar. A live que cair avisa na aba
sem derrubar as outras.

**A transcrição demora / se atrasa.**
Com várias lives abertas, use um modelo menor (`tiny` ou `base`) — o modelo é
**compartilhado** entre as abas, então o escolhido em cada aba define o peso
extra de memória só de ter mais de um modelo diferente aberto. Se a placa
NVIDIA não tiver CUDA, o programa usa o processador automaticamente.

## Requisitos

- Windows 10/11.
- Internet na **primeira live** (baixa o modelo do Whisper; depois fica em
  cache). O resto — streamlink, yt-dlp e ffmpeg — já vai no pacote.
