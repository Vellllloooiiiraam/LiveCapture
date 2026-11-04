# LiveCapture 1.4.0

## Novidades

- **Nome da conta/live na aba**: o botão **Detectar** agora, além do horário de
  início, puxa o **nome do canal** e o **título da live** (Twitch, Kick e
  YouTube) e já renomeia a aba sozinho. O título da live aparece na legenda
  abaixo da tabela.
  - Se a live estiver offline ou o extrator não devolver nada, a aba cai para o
    nome tirado do próprio link.
- **Renomear a aba na mão**: botão **✏️** ou **duplo clique no cabeçalho da
  aba** abre uma caixinha para editar o nome. O nome digitado é mantido e o
  indicador **●/○** (monitorando / parada) continua funcionando.
- O rótulo usado nos **nomes dos arquivos** (clipes e `falas/<canal>.txt`)
  continua sendo o nome curto do canal — assim nada de espaços/emoji vira nome
  de arquivo.

## Verificação

- `python test_livecapture.py`: 29 testes aprovados; 4 opcionais ignorados
  (modelo real, live real, nome real da live e interface pesada).
- `fetch_meta` conferido contra lives reais: `pijack11` devolveu canal e título;
  uma live offline caiu corretamente para o nome do link.
