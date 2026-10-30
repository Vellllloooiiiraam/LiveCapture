# Como instalar o LiveCapture (passo a passo)

Este tutorial é para quem só quer usar o programa. Você **não precisa** saber
programar nem instalar o Python: o próprio programa baixa o que falta na
primeira vez.

## Opção 1 — Baixar o programa pronto (mais fácil)

1. Abra a página de **Releases**:
   <https://github.com/Vellllloooiiiraam/LiveCapture/releases/latest>
2. Em **Assets**, baixe o arquivo **`LiveCapture.zip`**.
3. Clique com o botão direito no ZIP → **Extrair tudo...** → escolha uma pasta
   (por exemplo `C:\LiveCapture`) e confirme.
   - **Não** rode direto de dentro do ZIP: extraia primeiro.
4. Dentro da pasta extraída, dê **duplo clique** em **`LiveCapture.exe`**.
5. Na **primeira execução** aparece uma janelinha *"Preparando o LiveCapture"*.
   Ela baixa Python, as dependências e já vem com o `ffmpeg.exe` na pasta.
   Isso demora alguns minutos e **precisa de internet**.
6. Quando a janela principal abrir, cole o link da live, escreva as
   palavras-chave, marque **Salvar clipe** e clique em **Iniciar**.

Pronto. A pasta `LiveCapture.zip` extraída pode ficar onde você quiser.

> Da segunda vez em diante o programa abre em segundos — só a instalação inicial
> é demorada.

### Sobre o modelo de transcrição

O modelo do Whisper **não** vem no download. Ele é baixado na primeira vez que
você usa, quando a transcrição começa (ao clicar em **Iniciar**):

- `tiny` ~75 MB, `base` ~140 MB, `small` ~500 MB, `medium` ~1,5 GB.

Ou seja, a **primeira live também precisa de internet** para baixar o modelo.
Depois ele fica guardado e não é baixado de novo.

## Opção 2 — Pelo instalador (a partir do código)

Se você baixou o repositório (código-fonte) em vez do ZIP:

1. Instale o **Python 3.11** (ou 3.13) de <https://www.python.org/downloads/>
   (marque *"Add python.exe to PATH"*). No Windows também serve o
   `winget install Python.Python.3.11`.
2. No terminal, dentro da pasta do projeto:

   ```powershell
   powershell -ExecutionPolicy Bypass -File instalar.ps1
   ```

   (ou dê duplo clique em `instalar.bat`)
3. O instalador cria o ambiente em `%LOCALAPPDATA%\LiveCapture`, instala as
   dependências, confere/instala o `ffmpeg` e cria um atalho na Área de Trabalho.

## Onde as coisas ficam

- **Programa e ambiente:** `%LOCALAPPDATA%\LiveCapture`
  (contém `app\`, `venv\` e o `ffmpeg.exe`).
- **Clipes e registro:** na pasta onde o programa está rodando — `clipes\` e
  `ocorrencias.csv`.

## Problemas comuns

**"O Windows protegeu o seu PC" / antivírus acusa o exe.**
Programas feitos com PyInstaller costumam dar **falso positivo** — é comum e não
significa que há vírus. Para continuar: clique em **Mais informações** →
**Executar mesmo assim**, ou adicione a pasta à lista de exceções do antivírus.

**A janela não abre / nada acontece.**
Rode o exe com o parâmetro de diagnóstico para ver o que falta:

```powershell
LiveCapture.exe --check
```

Ele mostra `base_python`, `venv`, `deps` e `ffmpeg` como `OK` ou `FALTA`.
Para forçar a instalação/atualização do ambiente:

```powershell
LiveCapture.exe --setup
```

**Deu erro durante a captura da live.**
Confira se o `streamlink` consegue ver o canal (o programa usa ele por baixo).
Lives privadas ou que exigem login podem falhar.

## Requisitos

- Windows 10/11.
- Internet na **primeira** execução (dependências) e na **primeira live**
  (modelo de transcrição).
- `ffmpeg` já vem no ZIP. Se você rodou pelo código-fonte e não tiver, o
  instalador tenta instalar via `winget install Gyan.FFmpeg`.
