# LiveCapture 1.2.2

## Correções

- Registra o Streamlink assim que ele é iniciado e encerra o processo se o FFmpeg não puder iniciar.
- Faz o encerramento dos processos com `terminate`/`kill` e espera os processos terminarem.
- Aguarda a finalização dos trabalhos de clipe antes de apagar o buffer temporário.
- Ao parar a captura, permite que os clipes em andamento aguardem o trecho posterior disponível (com limite de tempo).
- Impõe limite de dois trabalhos de clipe ativos/pendentes para evitar crescimento ilimitado de threads.
- Registra a ocorrência na interface antes de iniciar a geração do clipe, evitando linhas presas em “gravando...” por uma corrida entre threads.
- Evita fechar a interface antes de o worker terminar a limpeza e os clipes em andamento.
- Valida os segundos anteriores e posteriores entre 3 e 45.
- Preserva caracteres Unicode na normalização e nos nomes de arquivos.
- O atalho criado pelo instalador usa `launcher.py`, que configura a pasta `Vídeos\\LiveCapture` corretamente.

## Verificação

- `py_compile`: aprovado para os módulos Python principais.
- `python -m unittest -q`: 18 testes aprovados; 2 testes opcionais ignorados (Whisper real e transmissão ao vivo real).
