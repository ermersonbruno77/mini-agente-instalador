Você vai instalar um agente autônomo Claude Code + Telegram numa VPS Ubuntu, usando o
repositório público https://github.com/ermersonbruno77/mini-agente-instalador — que já vem
com `CLAUDE.md` e **exatamente 4 subagentes fixos** em `.claude/agents/` (paulo-dev,
juliana-ops, jonathan-copy, rafael-projetos). Não crie agente do zero, não invente arquivo,
copie o que já está no repo. A fonte de verdade técnica completa é o `SETUP-AGENTE.md` desse
repo — leia ele inteiro antes de começar e siga a ordem exata das etapas. Este arquivo aqui é
um resumo com os pontos que mais confundem quem executa pela primeira vez; não substitui o
SETUP-AGENTE.md, complementa.

## Colete isso do usuário primeiro, uma pergunta por vez, espere a resposta

1. Nome do agente (capitalização normal, ex: TMB, Nexus, Aria) → `{{AGENTE_NAME}}`
2. Primeiro nome/apelido do dono → `{{DONO}}`
3. IP, usuário e senha (ou chave) da VPS Ubuntu 22+
4. Token do bot Telegram (ele cria em @BotFather com `/newbot` se ainda não tiver)
5. ID numérico do Telegram do dono (ele pega em @userinfobot se ainda não tiver)

Não pergunte mais nada da tabela de placeholders do SETUP-AGENTE.md — domínio, GitHub,
Instagram, mentoria/formação/comunidade são ruído do template genérico original e não se
aplicam a este fork. Se o usuário não mencionar, não pergunte.

## Acesso remoto

Você vai operar via SSH a partir de onde você está rodando (não precisa estar dentro da
VPS). Use um wrapper tipo `ssh_run() { ssh usuario@ip "$@"; }` pra não repetir a conexão a
cada comando. Depois do primeiro acesso, prefira configurar uma chave SSH em vez de senha.

## Ordem de execução

1. `curl -fsSL https://raw.githubusercontent.com/ermersonbruno77/mini-agente-instalador/main/bootstrap.sh | bash` — 5-10 min, instala Node/Python/PostgreSQL/Claude Code CLI/Caddy. Avise o usuário que vai demorar.
2. Autenticação Claude — **isto confunde todo mundo, leia com atenção**:
   - `claude auth login` NÃO tem subcomando `submit`. Não invente flag.
   - Rode `claude setup-token` dentro de uma sessão tmux (`tmux new-session -d -s authsetup ...`), porque é um prompt interativo (TUI). Capture a URL com `tmux capture-pane`, mande pro usuário autorizar no navegador (idealmente com uma conta Claude separada da pessoal, pra não dividir a janela de uso de 5h — pergunte antes), e quando ele mandar o código de volta, cole com `tmux set-buffer` + `tmux paste-buffer` + `tmux send-keys Enter` (não `tmux send-keys -l "codigo"` direto, não funciona de forma confiável).
   - Guarde o token (`sk-ant-oat01-...`) em `/root/.agente-secrets.env` como `CLAUDE_CODE_OAUTH_TOKEN=...`.
   - **Isso NÃO elimina o segundo login.** Na ETAPA 9 (primeiro boot da sessão 24/7 do agente), o `claude --dangerously-skip-permissions` pede de novo: tema (Enter aceita default), método de login (Enter aceita "Claude account with subscription"), o mesmo fluxo de colar código, aviso de segurança (Enter), "trust this folder?" (Enter aceita "sim"), e o aviso de bypass permissions — **atenção**: o cursor começa em "1. No, exit", você precisa mandar `Down` antes do `Enter` pra selecionar "2. Yes, I accept". Só depois disso aparece o prompt `❯` e o agente está pronto.
3. `claude --dangerously-skip-permissions` recusa rodar como root ("cannot be used with root/sudo privileges"). Crie um usuário dedicado não-root (`useradd -m -s /bin/bash NOMEDOAGENTE`) — a sessão do agente E o bot Python precisam rodar sob o MESMO usuário, senão o bot não acha a sessão tmux do agente (sockets diferentes). O `bootstrap.sh` já dá `chmod o+x /root` pra esse usuário conseguir atravessar até o node/claude instalados sob `/root/.nvm`.
4. Clone o repo pra dentro da VPS (`git clone` em `/opt/AGENTE-src`), copie `CLAUDE.md`, `.claude/agents/` (só os 4 arquivos que já vêm no repo — não adicione mais nenhum), `tools/`, `database/`, `systemd/` pra `/opt/AGENTE`, e `bot/` pra `/opt/AGENTE-bot`. SÓ DEPOIS disso rode a substituição de placeholders (find+sed) — e inclua `*.service` no find, os templates de systemd usam os mesmos placeholders.
5. Postgres: depois de aplicar `database/schema.sql` como `postgres` (superuser), rode o `GRANT ALL PRIVILEGES ON ALL TABLES/SEQUENCES IN SCHEMA public TO AGENTE` — sem isso as tabelas ficam com dono errado e todo INSERT do agente falha silenciosamente depois.
6. Systemd: use os templates prontos em `systemd/` (já copiados e com placeholder trocado). NÃO improvise `Type=forking` pro service do agente — tem que ser `Type=oneshot` + `RemainAfterExit=yes`, porque uma sessão tmux daemoniza sozinha e `forking` faz o systemd perder o rastro e ficar reiniciando em loop.
7. Bot: `PG_PASSWORD` vai no `.env` do bot (`/opt/AGENTE-bot/.env`), não só em `/root/.agente-secrets.env` — o usuário do agente não lê arquivo do root.
8. Depois do `chown -R AGENTE:AGENTE /opt/AGENTE /opt/AGENTE-bot` da ETAPA 3, ajuste a
   permissão de `.claude/agents/`:
   ```bash
   chown -R root:root /opt/AGENTE/.claude/agents
   chmod 755 /opt/AGENTE/.claude/agents
   chmod 644 /opt/AGENTE/.claude/agents/*.md
   ```
   Confira: `sudo -u AGENTE touch /opt/AGENTE/.claude/agents/teste.md` deve dar
   "Permission denied". Se não der erro, algo saiu diferente do esperado — investigue antes
   de seguir.

## Validação final

Não declare sucesso só porque os serviços estão `active`. Peça pro usuário mandar uma
mensagem de verdade pro bot no Telegram, confirme que apareceu em
`/opt/AGENTE-bot/inbox/` e que a resposta apareceu em `/opt/AGENTE-bot/sent/` depois de
alguns segundos/minutos.

## Se travar em algo não coberto aqui

O `SETUP-AGENTE.md` do repo tem uma tabela de TROUBLESHOOTING com mais casos. Leia antes
de inventar solução.
