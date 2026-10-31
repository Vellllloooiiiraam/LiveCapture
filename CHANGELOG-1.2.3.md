# LiveCapture 1.2.3

## Novidades

- Escolha explícita **Baixar clipe (vídeo MP4): Sim / Não** antes de iniciar a
  captura (antes era uma caixa "Salvar clipe").
- Legenda da opção **Não**: registra só o tempo da live, a frase e o relógio
  (sem clipe e sem áudio gravado).
- A opção foi agrupada num quadro **Clipe**, junto dos segundos antes/depois e do
  botão **Abrir pasta de clipes**, deixando claro que a decisão é feita antes de
  clicar em **Iniciar**.

## Verificação

- `py_compile`: aprovado para os módulos Python principais.
- `python -m unittest -q`: 18 testes aprovados; 2 testes opcionais ignorados (Whisper real e transmissão ao vivo real).
