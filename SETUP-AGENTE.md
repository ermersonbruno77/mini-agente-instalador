# SETUP-AGENTE.md v4 - Instalacao do agente Claude + Telegram (fork com time de 4 agentes pronto (fixo, sem criar agente novo))

> Claude, esse arquivo e pra voce executar. Pode ser executado em DOIS modos:
>
> **MODO A - Local (dentro da VPS):** voce esta rodando DENTRO da VPS, como o usuario dedicado do agente (nao como root - veja o aviso no final do `bootstrap.sh` sobre por que). Pula direto pra ETAPA 0.
>
> **MODO B - Remoto (o mais comum):** voce esta rodando no PC de quem esta instalando (Mac/Win/Linux), controlando a VPS via SSH. A pessoa tem so o IP/senha da VPS na mao. Le a secao **"INSTRUCOES PRO CLAUDE QUE ESTA EXECUTANDO REMOTAMENTE"** logo abaixo.
>
> Sua missao em qualquer modo: seguir esse manual do inicio ao fim, fazendo perguntas claras quando precisar, e entregar:
> - Agente principal rodando 24/7 no tmux, usando o `CLAUDE.md` e os 4 subagentes que **ja vem prontos neste repo** em `.claude/agents/` (voce NAO cria agente do zero - so substitui os placeholders na ETAPA 0 e copia os arquivos)
> - Bot externo Python (audio bidirecional) - `bot/bot.py`, tambem ja pronto no repo
> - Servico de memoria vetorial (`bot/memory_api.py`, porta 3007)
> - Crontab de manutencao (healthcheck, promessas, backup - ver `crontab-referencia.txt`)
>
> Esse fork **nao inclui** `agent-manager.py`/PM2/Caddy/tunel Cloudflare nem "Clone SDR" -
> isso existia numa versao anterior generica do template e nao faz parte do que este repo
> entrega. Se alguma etapa abaixo mencionar isso, e sinal de que ficou desatualizada - ignore
> e siga o que esta descrito aqui em cima.

---

## INSTRUCOES PRO CLAUDE QUE ESTA EXECUTANDO REMOTAMENTE (MODO B)

Use essa secao se o aluno esta no PC dele e nao quer mexer em terminal.

### Pre-checks no PC do aluno

Antes de tentar SSH, garanta que tem `ssh` e `sshpass` disponiveis localmente:

**Mac/Linux:**
```bash
which ssh           # geralmente ja vem
which sshpass || (
  # Mac:  brew install sshpass    (ou hudochenkov/sshpass)
  # Linux Debian/Ubuntu: sudo apt-get install -y sshpass
  echo "instale sshpass conforme o SO do aluno"
)
```

**Windows:** se o aluno estiver no Windows, prefira instruir ele a usar o WSL2, ou use a lib Python `paramiko` invocando via `python3 -c "import paramiko; ..."`.

### Coleta de dados da VPS (pergunta uma por vez)

Pergunta ao aluno (uma resposta de cada vez, espera ele responder antes da proxima):

1. "Qual o IP publico da sua VPS?" -> guarda como `VPS_IP`
2. "Qual o usuario de acesso? (geralmente `root`)" -> guarda como `VPS_USER`
3. "Qual a senha que o provedor te mandou?" -> guarda como `VPS_PASS` (NUNCA mostra ela em log)

### Helper de SSH

Define um wrapper. Use SEMPRE esse wrapper, nao expoe senha em comando isolado:

```bash
ssh_run() {
  sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$VPS_USER@$VPS_IP" "$@"
}

ssh_copy() {
  sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$1" "$VPS_USER@$VPS_IP:$2"
}
```

> **Boas praticas opcional**: depois do primeiro acesso, gere uma chave SSH local, copia pra VPS via `ssh-copy-id`, e desabilita login por senha no `/etc/ssh/sshd_config`. Mas isso e otimizacao, nao bloqueia o setup.

### Teste a conexao

```bash
ssh_run "uname -a && cat /etc/os-release | head -5"
```

Se falhar, pergunta de novo o IP/usuario/senha. Se a VPS for nova, pode levar 1-3 min pra bootar SSH apos o provisionamento.

### Rode o bootstrap remotamente

```bash
ssh_run "curl -fsSL https://raw.githubusercontent.com/ermersonbruno77/mini-agente-instalador/main/bootstrap.sh | bash"
```

Vai demorar 5-10 min. Avise o aluno: "to instalando Node, Postgres, Caddy e dependencias na sua VPS, espera ~10 min".

### Auth Claude na VPS

A autenticacao Claude precisa de browser. Voce nao consegue fazer isso 100% remoto, e o
comando `claude auth submit` **nao existe** (nao invente flag - `claude auth --help` so
tem `login`, `logout`, `status`). O jeito que funciona de verdade, testado ao vivo:

**Passo 1 - sessao tmux pra poder colar o codigo.** `claude auth login`/`setup-token` sao
interativos (TUI em modo raw), entao voce precisa deles rodando dentro de uma sessao tmux
pra poder mandar o codigo depois via `tmux send-keys`/`paste-buffer`:
```bash
ssh_run "tmux new-session -d -s authsetup -x 200 -y 50 bash"
ssh_run "tmux send-keys -t authsetup 'claude setup-token' Enter"
sleep 5
ssh_run "tmux capture-pane -t authsetup -p -J"
```
Isso imprime uma URL com `Paste code here if prompted >` no final. Capture a URL e manda
pra pessoa que esta instalando: "Abra essa URL **no navegador do seu PC** (de preferencia
com sua conta Claude separada do dia a dia, pra nao dividir a janela de uso de 5h - pergunte
se ela quer isso antes), autorize, copie o codigo de volta pra mim."

**Passo 2 - cola o codigo de volta:**
```bash
ssh_run "tmux set-buffer -t authsetup 'CODIGO_AQUI' && tmux paste-buffer -t authsetup && tmux send-keys -t authsetup Enter"
sleep 5
ssh_run "tmux capture-pane -t authsetup -p -J"
```
Se aparecer `Long-lived authentication token created successfully!`, funcionou. Guarda o
token (comeca com `sk-ant-oat01-`) em `/root/.agente-secrets.env`:
```bash
ssh_run "echo 'CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...' >> /root/.agente-secrets.env && chmod 600 /root/.agente-secrets.env"
```

**Atencao - esse token NAO pula o login da sessao interativa.** Mesmo com
`CLAUDE_CODE_OAUTH_TOKEN` no ambiente, a primeira vez que voce abrir
`claude --dangerously-skip-permissions` de verdade (dentro da sessao tmux 24/7 do agente, na
ETAPA 9) ele ainda vai pedir: tema, metodo de login (escolhe "1. Claude account with
subscription"), o mesmo fluxo de colar codigo (repete o Passo 1/2 acima dentro **dessa**
sessao tmux, que sera a definitiva), aviso de seguranca, "trust this folder?" (sim), e o
aviso de bypass permissions (a opcao certa e a **segunda**, "Yes, I accept" - o cursor
comeca na primeira por padrao, manda `Down` antes do `Enter`). So depois disso o prompt
`❯` aparece e o agente esta pronto pra receber mensagens do bot.

O `setup-token` do Passo 1 ainda vale a pena gerar: alguns scripts em `tools/` podem rodar
`claude --print` de forma nao-interativa, e esses sim usam `CLAUDE_CODE_OAUTH_TOKEN` direto
do ambiente sem pedir login de novo.

### Continue o setup remoto

Daqui em diante, todas as `bash` lines do manual abaixo voce executa via `ssh_run "..."`. Continua na ETAPA 0 normalmente, so prefixando `ssh_run` em cada bloco.

Quando precisar editar arquivos na VPS, use `cat <<'EOF' | ssh_run "cat > /caminho/do/arquivo"` ou `scp` via `ssh_copy`.

### Final do setup remoto

Apos systemd subir e bot estar online, peca pro aluno mandar um `/start` no bot dele no Telegram. Confirme que o agente respondeu. Se sim, missao cumprida.

---

## O QUE ESSE FORK ENTREGA

1. **`CLAUDE.md` + 4 subagentes prontos** em `.claude/agents/`: paulo-dev, juliana-ops,
   jonathan-copy, rafael-projetos. So precisa trocar os placeholders (ETAPA 0), nao criar do
   zero.
2. **Memoria vetorial PostgreSQL + pgvector**: embeddings 384-dim (fastembed local, sem
   OpenAI), HNSW index pra busca semantica. Ver `database/schema.sql`.
3. **Bot externo Python robusto**: `bot/bot.py`, long polling, audio bidirecional
   (faster-whisper local na entrada, ElevenLabs/Gemini na saida), `Restart=always` via
   systemd, independente da sessao do Claude.
4. **`tools/`**: scripts de apoio (log de delegacao, promessas, aprendizado, backup,
   deteccao de intrusao, buscas web/CNPJ, browser automation) que o `CLAUDE.md` e os
   agentes ja esperam encontrar em `/opt/AGENTE/tools/`.

---

## Regras de execucao

1. Leia esse arquivo INTEIRO antes de comecar.
2. Execute na ordem exata.
3. Quando precisar de info do aluno, **pergunte claramente** e **espere a resposta**.
4. Apos cada bloco grande, valide com check.
5. Se falhar, pare e explique. Nao chute solucao.
6. Fala PT-BR direto. Sem travessoes.

---

## ETAPA 0 - PLACEHOLDERS (PERSONALIZACAO PRO ALUNO)

Esse repo e a versao publica/sanitizada. Antes de qualquer ETAPA tecnica, voce, Claude, deve fazer ao aluno UMA PERGUNTA POR VEZ pra coletar os valores reais que substituirao os placeholders no formato `{{NOME}}` espalhados por todos os arquivos do projeto. Depois faz um find+replace global no `/opt/AGENTE/` (ou onde for) trocando placeholder por valor real.

> **Caminho curto (recomendado pra este fork, com `.claude/agents/` ja pronto):** o `CLAUDE.md`,
> os 4 arquivos de agente e o `tools/` deste repo so usam `{{AGENTE_NAME}}`,
> `{{AGENTE_NAME_LOWERCASE}}`, `{{AGENTE_NAME_UPPER}}` (nome de variavel de ambiente, ex:
> `PG_PASSWORD_TMB`) e `{{DONO}}`. Os outros placeholders da tabela abaixo so aparecem em `SETUP-AGENTE.md`,
> `README.md`, `bootstrap.sh` e `.env.example` (mecanica de instalacao, nao o comportamento do
> agente) e boa parte e opcional ou nem se aplica a uma instalacao de time. Perguntas realmente
> obrigatorias pra esse fork: **nome do agente, nome do admin/Chefe, IP+usuario+senha da VPS,
> token do bot no @BotFather, ID do Telegram do admin no @userinfobot.** O resto (dominio, GitHub,
> Instagram, mentoria/formacao/comunidade) e ruido do template generico: pule se nao usar.

**Tabela completa de placeholders** (na ordem que voce deve perguntar):

| # | Placeholder | Pergunta pro aluno | Exemplo |
|---|---|---|---|
| 0 | `{{AGENTE_NAME}}` | "Qual o nome do agente, com capitalizacao normal? (ex: Nexus, Aria, Vega)" | `Nexus` |
| 0b | `{{AGENTE_NAME_LOWERCASE}}` | "Versao minuscula, sem espaco, pros caminhos e nomes de servico (default: minusculo do anterior)" | `nexus` |
| 0c | `{{AGENTE_NAME_UPPER}}` | "Versao CAIXA ALTA, pra nome de variavel de ambiente (default: maiusculo do primeiro)" | `NEXUS` |
| 1 | `{{DONO}}` | "Qual o primeiro nome (ou apelido) do admin/Chefe que vai aparecer no agente?" | `Joao` |
| 2 | `{{DONO_NOME_COMPLETO}}` | "E o nome completo? (opcional, so usado fora deste fork)" | `Joao Silva` |
| 3 | `{{DONO_SLUG}}` | "Versao 'slug' do seu nome (lowercase, sem espacos, sem acentos). Default: lowercase do anterior." | `joao` |
| 4 | `{{DONO_UPPER}}` | "Nome em CAIXA ALTA (default: uppercase do {{DONO}})" | `JOAO` |
| 5 | `{{EMAIL_DONO}}` | "Seu email (vai virar email do agente nos commits e logs)" | `joao@meusite.com` |
| 6 | `{{NICHO_DONO}}` | "Nome da sua empresa/marca/produto principal" | `Empresa X` |
| 7 | `{{NICHO_DONO_SLUG}}` | "Slug da empresa (lowercase, sem espacos)" | `empresax` |
| 8 | `{{NICHO_DONO_UPPER}}` | "Empresa em CAIXA ALTA" | `EMPRESAX` |
| 9 | `{{TELEGRAM_USER_ID_DONO}}` | "Seu ID numerico no Telegram. Mande `/start` pra @userinfobot e cola o numero aqui." | `123456789` |
| 10 | `{{TELEGRAM_BOT_USERNAME}}` | "Username do bot que voce criou no @BotFather (com `_bot` no final, sem o @)" | `meuagente_bot` |
| 11 | `{{INSTAGRAM_HANDLE_DONO}}` | "Seu @ no Instagram (sem o @)" | `joao.silva` |
| 12 | `{{VPS_IP}}` | "IP da VPS principal onde o agente vai rodar" | `123.45.67.89` |
| 13 | `{{VPS_IP_ALT}}` | "(Opcional) IP de VPS secundaria. Pula se nao tiver." | `123.45.67.90` |
| 14 | `{{VPS_IP_ALT_2}}` | "(Opcional) IP de VPS terciaria. Pula se nao tiver." | `123.45.67.91` |
| 15 | `{{VPS_IP_ALT_3}}` | "(Opcional) IP de VPS quaternaria. Pula se nao tiver." | `123.45.67.92` |
| 16 | `{{DOMINIO_PRINCIPAL}}` | "Seu dominio raiz (sem https, sem www)" | `meusite.com` |
| 17 | `{{DOMINIO_AI}}` | "(Opcional) Dominio secundario .ai ou outro. Pula se nao tiver." | `meusite.ai` |
| 18 | `{{DOMINIO_CRM}}` | "(Opcional) Dominio do seu CRM" | `crm.meusite.com` |
| 19 | `{{DOMINIO_CLIENTE_EXEMPLO}}` | "(Opcional) Subdominio exemplo de cliente" | `cliente1.meusite.com` |
| 20 | `{{DOMINIO_CLIENTE}}` | "(Opcional) Dominio de um cliente real (so pra exemplo)" | `cliente1.com.br` |
| 22 | `{{PRODUTO_DONO}}` | "Nome do seu produto/SaaS principal" | `Meu CRM` |
| 23 | `{{PRODUTO_DONO_SLUG}}` | "Slug do produto" | `meu-crm` |
| 24 | `{{MENTORIA_DONO}}` | "(Opcional) Nome da sua mentoria" | `Mentoria X` |
| 25 | `{{FORMACAO_DONO}}` | "(Opcional) Nome da sua formacao/curso" | `Formacao X em IA` |
| 26 | `{{COMUNIDADE_DONO}}` | "(Opcional) Nome da sua comunidade paga" | `Comunidade X` |
| 27 | `{{SENHA_PADRAO}}` | "(Nao se aplica a esse fork - so usado em painel web que este repo nao inclui. Pule.)" | `meusite2026` |
| 28 | `{{GITHUB_USERNAME}}` | "Seu username no GitHub" | `joaodev` |

**Como executar a substituicao depois de coletar tudo:**

```bash
cd /opt/AGENTE  # ou onde for o diretorio raiz do agente
# Cria arquivo de replacements
cat > /tmp/replace.txt <<EOF
{{DONO}}|VALOR_REAL_1
{{DONO_NOME_COMPLETO}}|VALOR_REAL_2
{{DONO_SLUG}}|VALOR_REAL_3
{{DONO_UPPER}}|VALOR_REAL_4
{{EMAIL_DONO}}|VALOR_REAL_5
{{NICHO_DONO}}|VALOR_REAL_6
{{NICHO_DONO_SLUG}}|VALOR_REAL_7
{{NICHO_DONO_UPPER}}|VALOR_REAL_8
{{TELEGRAM_USER_ID_DONO}}|VALOR_REAL_9
{{TELEGRAM_BOT_USERNAME}}|VALOR_REAL_10
{{INSTAGRAM_HANDLE_DONO}}|VALOR_REAL_11
{{VPS_IP}}|VALOR_REAL_12
{{DOMINIO_PRINCIPAL}}|VALOR_REAL_13
{{PRODUTO_DONO}}|VALOR_REAL_14
{{PRODUTO_DONO_SLUG}}|VALOR_REAL_15
{{SENHA_PADRAO}}|VALOR_REAL_16
{{GITHUB_USERNAME}}|VALOR_REAL_17
EOF

# Aplica em todos os arquivos texto do projeto
while IFS='|' read -r placeholder valor; do
  find . -type f \( -name "*.md" -o -name "*.txt" -o -name "*.sh" -o -name "*.py" -o -name "*.sql" -o -name "*.json" -o -name "*.example" -o -name "*.plist.example" -o -name "*.service" -o -name ".env*" \) \
    -print0 | xargs -0 sed -i "s|$placeholder|$valor|g"
done < /tmp/replace.txt
```

Apos rodar, valida com:
```bash
grep -r "{{[A-Z_]*}}" . | head -10  # deve ser ZERO matches
```

So depois disso, segue pra ETAPA 1.

---

## ETAPA 1 - BOOTSTRAP

> Pre-requisito ja feito pelo aluno via `bootstrap.sh`. Confirma:

```bash
node --version       # v22.x
python3 --version    # 3.10+
psql --version       # PostgreSQL 16
claude --version     # 2.1.118
tmux -V              # 3.x
pm2 --version        # 5.x
caddy version        # 2.x
ffmpeg -version | head -1
```

Se algo faltar, manda o aluno rodar de novo:
```bash
curl -fsSL https://raw.githubusercontent.com/ermersonbruno77/mini-agente-instalador/main/bootstrap.sh | bash
```

---

## ETAPA 2 - CLAUDE AUTH LOGIN

Confirma se ja existe um `CLAUDE_CODE_OAUTH_TOKEN` em `/root/.agente-secrets.env`:
```bash
grep -c CLAUDE_CODE_OAUTH_TOKEN /root/.agente-secrets.env 2>/dev/null || echo 0
```

Se der `0`, siga o processo completo descrito em **"Auth Claude na VPS"** no topo deste
arquivo (secao de instrucoes remotas) - vale tanto pra MODO A quanto MODO B. Resumindo:
`claude setup-token` dentro de uma sessao tmux, capturar o link, pessoa autoriza no
navegador, colar o codigo de volta via `tmux paste-buffer`. Isso gera o token de longa
duracao, usado por scripts `--print` nao-interativos.

**Isso NAO substitui o login da sessao 24/7 do agente** - aquele acontece na ETAPA 9,
dentro da sessao tmux definitiva, e pede o mesmo fluxo de navegador de novo (a CLI nao
usa o `CLAUDE_CODE_OAUTH_TOKEN` do ambiente pra pular login em modo interativo). Nao pule
esse aviso achando que ja resolveu aqui.

---

## ETAPA 3 - USUARIO DEDICADO + CLONAR O REPO + .ENV

Pergunta ao aluno e guarda:

| Variavel | Onde pegar | Obrigatorio? |
|---|---|---|
| `AGENTE_NAME` | minusculas, sem espaco. ex `jonas`, `ana` | sim |
| `OWNER_NAME` | nome do dono pro CLAUDE.md. ex `Jonas` | sim |
| `TELEGRAM_BOT_TOKEN` | @BotFather no Telegram | sim |
| `ALLOWED_USERS` | @userinfobot no Telegram (ID numerico) | sim |
| `OPENAI_API_KEY` | platform.openai.com/api-keys | opcional (audio) |
| `ELEVENLABS_API_KEY` | elevenlabs.io/profile | opcional (audio) |
| `ELEVENLABS_VOICE_ID` | elevenlabs.io/voice-library | opcional |

**ATENCAO**: ele NAO precisa fornecer tudo de uma vez. So as obrigatorias. As outras pode adicionar depois.

**O `useradd` abaixo NAO e opcional.** `claude --dangerously-skip-permissions` recusa
rodar como root ("cannot be used with root/sudo privileges for security reasons") -
testado ao vivo, nao e suposicao. A sessao 24/7 do agente TEM que rodar sob um usuario
comum, e o bot Python (que injeta mensagem via `tmux send-keys`) precisa rodar sob **o
mesmo usuario**, senao cada um enxerga um socket de tmux diferente e o bot nunca acha a
sessao do agente.

```bash
useradd -m -s /bin/bash AGENTE 2>/dev/null || echo "ja existe"

# Clona o proprio repo do fork pra dentro da VPS - e daqui que vem o CLAUDE.md,
# os 4 agentes, tools/, database/schema.sql, o bot etc. Nao recria nada do zero.
git clone --depth 1 https://github.com/ermersonbruno77/mini-agente-instalador.git /opt/AGENTE-src

mkdir -p /opt/AGENTE/{logs,knowledge,workspace,hooks,cron-scripts,.claude/agents}
mkdir -p /opt/AGENTE-bot/{inbox,outbox,sent,processed,state,logs,audio/incoming,audio/outgoing,images,docs}

cp /opt/AGENTE-src/CLAUDE.md /opt/AGENTE/CLAUDE.md
cp /opt/AGENTE-src/CONCISAO.md /opt/AGENTE/CONCISAO.md 2>/dev/null || true
cp -r /opt/AGENTE-src/.claude/agents/. /opt/AGENTE/.claude/agents/
cp -r /opt/AGENTE-src/knowledge/. /opt/AGENTE/knowledge/
cp -r /opt/AGENTE-src/tools /opt/AGENTE/tools
cp -r /opt/AGENTE-src/database /opt/AGENTE/database
cp -r /opt/AGENTE-src/systemd /opt/AGENTE/systemd
cp -r /opt/AGENTE-src/skills /opt/AGENTE/skills 2>/dev/null || true

cp /opt/AGENTE-src/bot/bot.py /opt/AGENTE-bot/bot.py
cp /opt/AGENTE-src/bot/healthcheck.sh /opt/AGENTE-bot/healthcheck.sh
cp /opt/AGENTE-src/bot/consolidate-conversations.py /opt/AGENTE-bot/consolidate-conversations.py
cp /opt/AGENTE-src/bot/memory_api.py /opt/AGENTE-bot/memory_api.py
```

**So agora** roda a substituicao de placeholders da ETAPA 0 (o find+sed), apontando pra
`/opt/AGENTE` e `/opt/AGENTE-bot` (nao pro `/opt/AGENTE-src`, que pode ficar com os
tokens `{{...}}` originais ou ser apagado depois - nao roda nada a partir dele).

Cria `/opt/AGENTE-bot/.env` (o bot le esse arquivo direto no codigo, formato `CHAVE=valor`
por linha, sem aspas):
```
TELEGRAM_BOT_TOKEN=<TOKEN>
ALLOWED_USERS=<ID>
TMUX_SESSION=AGENTE
TMUX_USER=AGENTE
DEBOUNCE_SECONDS=8
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```
(a ETAPA 4 acrescenta `PG_PASSWORD` nesse mesmo arquivo - `memory_api.py` e
`consolidate-conversations.py` leem a senha do Postgres daqui, nao de
`/root/.agente-secrets.env`, porque esse ultimo so root consegue ler e esses dois
processos rodam como o usuario AGENTE.)

```bash
chmod 600 /opt/AGENTE-bot/.env
chown -R AGENTE:AGENTE /opt/AGENTE /opt/AGENTE-bot
```

Depois do chown acima, ajusta a permissão de `.claude/agents/` assim:

```bash
chown -R root:root /opt/AGENTE/.claude/agents
chmod 755 /opt/AGENTE/.claude/agents
chmod 644 /opt/AGENTE/.claude/agents/*.md
```

Confere que ficou correto (deve dar "Permission denied"):
```bash
sudo -u AGENTE touch /opt/AGENTE/.claude/agents/teste.md
```

---

## ETAPA 4 - INICIALIZAR BANCO POSTGRESQL

```bash
PGPASS=$(openssl rand -hex 24)
echo "PG_PASSWORD=$PGPASS" >> /root/.agente-secrets.env
chmod 600 /root/.agente-secrets.env
# Copia tambem pro .env do bot (usuario AGENTE nao le /root/.agente-secrets.env)
echo "PG_PASSWORD=$PGPASS" >> /opt/AGENTE-bot/.env

sudo -u postgres psql -c "CREATE USER AGENTE WITH PASSWORD '$PGPASS';"
sudo -u postgres psql -c "CREATE DATABASE AGENTE_memory OWNER AGENTE;"
sudo -u postgres psql -d AGENTE_memory -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d AGENTE_memory -c "GRANT ALL PRIVILEGES ON DATABASE AGENTE_memory TO AGENTE;"
```

Aplica o `schema.sql` que **ja vem pronto no repo** (`/opt/AGENTE/database/schema.sql`,
copiado na ETAPA 3) - nao cria as tabelas na mao, esse arquivo ja tem
`conversation_history`, `memory_chunks`, `memory_facts`, `transcript_chunks`,
`agente_atividade`, `promessas`, `lembretes` etc, todas com `embedding vector(384)`
(fastembed local, **nao** 1536 - esse era o tamanho do embedding da OpenAI, esse fork
nao usa OpenAI pra isso) e os index HNSW ja inclusos.

```bash
sudo -u postgres psql -d AGENTE_memory -f /opt/AGENTE/database/schema.sql
```

**Passo que falta em qualquer tutorial generico e QUEBRA o app se pular**: aplicar o
schema como `postgres` (superuser) deixa as tabelas com **dono `postgres`**, nao `AGENTE`.
O usuario `AGENTE` so tem os privilegios de DATABASE (`GRANT ALL ... ON DATABASE`
la em cima), que nao da acesso de escrita nas tabelas em si. Sem o passo abaixo, todo
`INSERT`/`UPDATE` do agente falha com "permission denied":
```bash
sudo -u postgres psql -d AGENTE_memory -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO AGENTE; GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO AGENTE; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO AGENTE;"
```

Confere que ficou 384 (nao 1536) antes de seguir:
```bash
sudo -u postgres psql -d AGENTE_memory -c "\d conversation_history" | grep embedding
```

---

## ETAPA 5 - INSTALAR DEPENDENCIAS PYTHON + SUBIR BOT E MEMORY API

Se ainda nao perguntou, pergunta o `TELEGRAM_BOT_TOKEN` (do @BotFather) e o
`ALLOWED_USERS` (do @userinfobot) - como criar o bot, passo pra pessoa:
1. Telegram, busca `@BotFather`, manda `/newbot`
2. Escolhe nome (ex "Assistente do Jonas")
3. Escolhe username terminando em `bot` (ex `jonas_assistente_bot`)
4. Copia o token retornado
5. Busca `@userinfobot`, manda qualquer msg, copia o ID numerico

`TELEGRAM_BOT_TOKEN` e `ALLOWED_USERS` ja devem estar no `/opt/AGENTE-bot/.env` desde a
ETAPA 3 (se nao, adiciona agora). `bot.py`, `healthcheck.sh`, `consolidate-conversations.py`
e `memory_api.py` **ja foram copiados** na ETAPA 3 - nao recria nada, so instala as
dependencias Python que eles precisam:
```bash
pip3 install requests fastapi 'uvicorn[standard]' fastembed pydantic psycopg2-binary
```

Copia os templates de systemd **prontos no repo** (foram parar em `/opt/AGENTE/systemd/`
na ETAPA 3, entao a substituicao de placeholders da ETAPA 0 ja trocou
`{{AGENTE_NAME_LOWERCASE}}` pelo nome real dentro deles). Eles ja usam `Type=oneshot` +
`RemainAfterExit=yes` pro service do agente (NAO `Type=forking`: uma sessao tmux daemoniza
sozinha, `forking` faz o systemd perder o rastro e reiniciar em loop - testado ao vivo, os
dois formatos errados foram tentados antes de chegar nesse):
```bash
cp /opt/AGENTE/systemd/start-agente.sh /usr/local/bin/start-agente.sh
chmod +x /usr/local/bin/start-agente.sh
cp /opt/AGENTE/systemd/agente-agent.service /etc/systemd/system/AGENTE-agent.service
cp /opt/AGENTE/systemd/agente-bot.service /etc/systemd/system/AGENTE-bot.service
cp /opt/AGENTE/systemd/agente-memory.service /etc/systemd/system/AGENTE-memory.service
systemctl daemon-reload
```
(O nome do arquivo `/etc/systemd/system/AGENTE-agent.service` acima usa "AGENTE" como
placeholder de nomenclatura pra voce trocar pelo nome real ao rodar - ex: `nexus-agent.service`
- diferente do conteudo interno do arquivo, que ja veio substituido.)

Sobe o bot e o servico de memoria agora (o agente em si so na ETAPA 9, depois do login):
```bash
systemctl enable --now AGENTE-bot
systemctl enable --now AGENTE-memory
sleep 3
systemctl status AGENTE-bot --no-pager | head -10
systemctl status AGENTE-memory --no-pager | head -10
curl -s http://127.0.0.1:3007/health   # deve responder {"ok":true,...}
```

---

## ETAPA 6 - CONFERIR CLAUDE.MD E OS 4 AGENTES (JA PRONTOS)

Nao cria nada nessa etapa - `CLAUDE.md` e os 4 arquivos em `.claude/agents/` **ja foram
copiados** do repo na ETAPA 3, com os placeholders (`{{AGENTE_NAME}}`, `{{DONO}}`, etc)
ja substituidos pela ETAPA 0. So confere que ficou tudo certo:

```bash
grep -rc "{{[A-Z_]*}}" /opt/AGENTE/CLAUDE.md /opt/AGENTE/.claude/agents/ | grep -v ':0' || echo "OK - zero placeholder sobrando"
ls /opt/AGENTE/.claude/agents/   # deve listar os 4 arquivos .md
```

Se a pessoa quiser personalizar tom, adicionar conhecimento especifico do negocio dela, ou
tirar algum dos 4 agentes que nao faz sentido pro caso dela, isso e edicao manual do
`/opt/AGENTE/CLAUDE.md` e dos arquivos em `.claude/agents/` - pergunta se ela quer isso
agora ou prefere ajustar depois (nao bloqueia o resto da instalacao).

---

## ETAPA 7 E 8 - NAO SE APLICAM A ESSE FORK

`agent-manager.py`/PM2/Caddy/tunel Cloudflare e "Clone SDR" fazem parte de uma versao
generica mais antiga do template, de antes deste fork existir. Esse repo **nao** entrega
esses dois componentes - pula direto pra ETAPA 9. Se a pessoa realmente quiser algo
assim depois, e customizacao fora do escopo do instalador (nao trava a instalacao base).

---

## ETAPA 9 - PRIMEIRO BOOT DO AGENTE (LOGIN INTERATIVO) E VALIDAR

Sobe a sessao tmux do agente pela primeira vez:
```bash
systemctl enable --now AGENTE-agent
sleep 5
sudo -u AGENTE tmux ls   # deve listar uma sessao chamada AGENTE
```

**Primeiro boot sempre pede um assistente interativo** (mesmo com `CLAUDE_CODE_OAUTH_TOKEN`
setado - explicado na ETAPA 2). Acompanha via `tmux capture-pane` e vai respondendo:

```bash
sudo -u AGENTE tmux capture-pane -t AGENTE -p -J
```

Na ordem que aparece:
1. **Escolha de tema** -> `sudo -u AGENTE tmux send-keys -t AGENTE Enter` (aceita o default)
2. **"Select login method"** -> `Enter` de novo (aceita "1. Claude account with subscription")
3. **URL de autorizacao** aparece com `Paste code here if prompted >`. Repete o fluxo de
   colar codigo da ETAPA 2 (manda a URL pra pessoa, ela autoriza, ela manda o codigo de
   volta, voce cola com `tmux set-buffer`/`paste-buffer` **nessa sessao `AGENTE`**, nao
   mais na sessao `authsetup` temporaria da ETAPA 2):
   ```bash
   sudo -u AGENTE tmux set-buffer -t AGENTE 'CODIGO_AQUI' && sudo -u AGENTE tmux paste-buffer -t AGENTE && sudo -u AGENTE tmux send-keys -t AGENTE Enter
   ```
4. **"Login successful. Press Enter to continue"** -> `Enter`
5. **"Security notes"** -> `Enter`
6. **"Is this a project you created or one you trust?"** -> `Enter` (aceita "1. Yes, I trust this folder")
7. **"WARNING: Bypass Permissions mode"** -> o cursor comeca em "1. No, exit" - manda
   `Down` e so depois `Enter`:
   ```bash
   sudo -u AGENTE tmux send-keys -t AGENTE Down
   sudo -u AGENTE tmux send-keys -t AGENTE Enter
   ```

Confere no fim que apareceu o prompt `❯` e `bypass permissions on` no rodape - so ai o
agente esta realmente no ar e pronto pra receber mensagem do bot.

Valida em paralelo:

```bash
# Bot externo vivo
systemctl is-active AGENTE-bot
systemctl is-active AGENTE-memory

# Agente Claude vivo
systemctl is-active AGENTE-agent
sudo -u AGENTE tmux ls | grep AGENTE

# Banco respondendo
sudo -u AGENTE psql -d AGENTE_memory -c "SELECT COUNT(*) FROM conversation_history"

# memory API respondendo
curl -s http://127.0.0.1:3007/health

# Crontab de manutencao instalado (deve ser no ROOT, nao no AGENTE - ver crontab-referencia.txt)
crontab -l | grep healthcheck
```

**Teste final de verdade**: pede pra pessoa mandar uma mensagem pro bot dela no Telegram.
Confirma que apareceu em `/opt/AGENTE-bot/inbox/` e, depois de alguns segundos/minutos
(o agente processa e responde), que apareceu em `/opt/AGENTE-bot/sent/`. So ai a
instalacao esta de fato completa - nao declara sucesso so por systemd estar `active`.

Se tudo OK, manda mensagem final pro aluno:
- Bot Telegram: `@bot_username`
- Comandos uteis (logs, restart, ver tela - proxima secao)
- Como customizar os agentes em `.claude/agents/`

---

## COMANDOS UTEIS DO DIA A DIA

**Logs ao vivo:**
```bash
tail -f /opt/AGENTE-bot/logs/bot.log        # Bot Python
journalctl -u AGENTE-memory -f              # memory API
journalctl -u AGENTE-bot -f                 # systemd do bot
sudo -u AGENTE tmux attach -t AGENTE        # tela do agente ao vivo (ver abaixo)
```

**Restart:**
```bash
systemctl restart AGENTE-agent    # restart do agente (mata a sessao tmux e sobe outra)
systemctl restart AGENTE-bot      # restart do bot
systemctl restart AGENTE-memory   # restart do servico de memoria
```
Atencao: `restart AGENTE-agent` mata a sessao tmux e cria outra vazia - **nao** refaz o
login sozinho na maioria dos casos porque a credencial fica salva em
`/home/AGENTE/.claude/` apos o primeiro login (so a primeira vez pede o assistente
interativo inteiro da ETAPA 9). Se depois de um restart a sessao nao voltar sozinha,
confere `journalctl -u AGENTE-agent -n 50` antes de repetir o fluxo de login.

**Tela do Claude ao vivo:**
```bash
sudo -u AGENTE tmux attach -t AGENTE
# pra sair sem fechar: Ctrl+B, D
```

**Editar personalidade:**
```bash
nano /opt/AGENTE/CLAUDE.md
systemctl restart AGENTE-agent
```

**Editar subagente:**
```bash
nano /opt/AGENTE/.claude/agents/paulo-dev.md
# nao precisa restart
```

---

## TROUBLESHOOTING

| Problema | Solucao |
|---|---|
| `claude --dangerously-skip-permissions` da erro "cannot be used with root" | Voce esta como root. Precisa rodar como o usuario dedicado (`sudo -u AGENTE ...` ou `su - AGENTE`), nao root. Ver ETAPA 3. |
| `AGENTE-agent.service` fica reiniciando em loop / "activating (auto-restart)" | `Type=` do service tem que ser `oneshot` + `RemainAfterExit=yes`, nao `forking`. Confere `/etc/systemd/system/AGENTE-agent.service` contra `systemd/agente-agent.service` do repo. |
| Sessao tmux `AGENTE` nao aparece depois de subir o service | O pane provavelmente crashou na inicializacao (ex: `claude` recusando rodar por algum motivo) - tmux fecha sessao com pane vazio sozinho. Roda o comando do `start-AGENTE-agent.sh` na mao (sem `-d`) pra ver o erro real. |
| Bot reage mas agente nao responde | `systemctl is-active AGENTE-agent`. Se inactive, restart. Confere tambem se a sessao tmux esta viva e nao travada num prompt de onboarding (ETAPA 9). |
| Insert/update no banco falha com "permission denied" | Faltou o `GRANT ALL ... TO AGENTE` da ETAPA 4 depois de aplicar o schema. |
| `memory_api.py`/`consolidate-conversations.py` erro de conexao no banco | Confere se `PG_PASSWORD` esta em `/opt/AGENTE-bot/.env` (nao so em `/root/.agente-secrets.env` - esses dois processos rodam como AGENTE, que nao le arquivo do root). |
| Audio nao transcreve | `faster-whisper` roda local, sem chave. Se nao esta transcrevendo, confere log do bot por erro de modelo/ffmpeg. |
| Audio nao sai | Confere `ELEVENLABS_API_KEY` ou `GEMINI_API_KEY` no `/opt/AGENTE-bot/.env`. |
| Agente nao lembra conversa antiga | Cron `consolidate-conversations.py` instalado no crontab do **root** (nao do AGENTE)? Ver `crontab-referencia.txt`. |
| VPS reboot e nao volta | `systemctl is-enabled AGENTE-agent AGENTE-bot AGENTE-memory` deve dar `enabled` em todos. |

---

## FIM DO SETUP v4

Em caso de duvida, abrir issue:
https://github.com/ermersonbruno77/mini-agente-instalador/issues
