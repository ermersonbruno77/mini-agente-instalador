#!/usr/bin/env bash
# Monitor de saude da memoria da {{AGENTE_NAME}}.
#
# Motivo (01/08/2026): o CLAUDE.md afirmava 6.072 chunks indexados e 25.660
# mensagens no historico. A realidade era 3 chunks. Ninguem percebeu porque
# nada olhava. Este monitor existe pra que uma degradacao dessas apareca no
# mesmo dia em vez de so aparecer quando a {{AGENTE_NAME}} responde errado.
#
# Nao envia texto ao Telegram por conta propria: so aciona a {{AGENTE_NAME}} via
# inject.sh, e ela escreve a mensagem. Regra suprema do CLAUDE.md.
#
# Roda 1x por dia via cron.

set -u
LOG=/opt/{{AGENTE_NAME_LOWERCASE}}/logs/saude-memoria.log
STAMP=$(date '+%Y-%m-%d %H:%M:%S')
PSQL="psql -h 127.0.0.1 -U {{AGENTE_NAME_LOWERCASE}} -d {{AGENTE_NAME_LOWERCASE}}_memory -tA"

log() { echo "[$STAMP] $*" >> "$LOG"; }

alertas=""
add() { alertas="${alertas}- $1"$'\n'; }

# 1. servico de busca semantica responde?
if ! curl -s -m 10 -o /dev/null -X POST http://127.0.0.1:3007/search \
        -H 'Content-Type: application/json' -d '{"query":"teste","limit":1}'; then
  add "a API de busca semantica na porta 3007 nao respondeu"
fi

# 2. o indice de arquivos esvaziou?
chunks=$($PSQL -c "SELECT count(*) FROM memory_chunks" 2>/dev/null || echo 0)
if [ "${chunks:-0}" -lt 30 ]; then
  add "memory_chunks caiu para $chunks (esperado 50+); reindexar com tools/ingest.py"
fi

# 3. o historico parou de crescer? (consolidate roda a cada 5 min)
recentes=$($PSQL -c "SELECT count(*) FROM conversation_history WHERE created_at > now() - interval '24 hours'" 2>/dev/null || echo 0)
if [ "${recentes:-0}" -eq 0 ]; then
  add "nenhuma conversa salva nas ultimas 24h; consolidate-conversations.py pode estar quebrado"
fi

# 4. conversa sem embedding fica invisivel na busca
sem_emb=$($PSQL -c "SELECT count(*) FROM conversation_history WHERE embedding IS NULL" 2>/dev/null || echo 0)
if [ "${sem_emb:-0}" -gt 50 ]; then
  add "$sem_emb mensagens sem embedding, invisiveis na busca semantica"
fi

# 5. backup envelheceu?
if [ -f /root/{{AGENTE_NAME_LOWERCASE}}-backups-repo/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz.enc ]; then
  idade=$(( ( $(date +%s) - $(stat -c %Y /root/{{AGENTE_NAME_LOWERCASE}}-backups-repo/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz.enc) ) / 3600 ))
  [ "$idade" -gt 30 ] && add "ultimo backup tem $idade horas (deveria rodar todo dia 03:30)"
else
  add "arquivo de backup nao encontrado em /root/{{AGENTE_NAME_LOWERCASE}}-backups-repo"
fi

# 6. arquivos que o boot do CLAUDE.md manda ler existem mesmo?
faltando=""
for f in /opt/{{AGENTE_NAME_LOWERCASE}}/knowledge/user/USER.md /opt/{{AGENTE_NAME_LOWERCASE}}/memory/decisions.md \
         /opt/{{AGENTE_NAME_LOWERCASE}}/memory/projects.md /opt/{{AGENTE_NAME_LOWERCASE}}/memory/pending.md; do
  [ -s "$f" ] || faltando="$faltando $(basename "$f")"
done
[ -n "$faltando" ] && add "arquivos de boot ausentes ou vazios:$faltando"

if [ -n "$alertas" ]; then
  log "ALERTA"$'\n'"$alertas"
  /opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh "[sistema] Monitor de memoria achou problema. Avalie, conserte se der, e explique ao Chefe com suas palavras: $(echo "$alertas" | tr '\n' ' ')"
else
  log "ok | chunks=$chunks conversas_24h=$recentes sem_embedding=$sem_emb"
fi
