#!/usr/bin/env bash
set -e
source /root/.agente-secrets.env
export BACKUP_PASSPHRASE
REPO=/root/{{AGENTE_NAME_LOWERCASE}}-backups-repo
GSSH="ssh -i /root/.ssh/bkp_deploy -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"
rm -rf /tmp/bkp && mkdir -p /tmp/bkp

# dump do banco (memoria/RAG/conversas/promessas/agenda)
PGPASSWORD="$PG_PASSWORD" pg_dump -h 127.0.0.1 -U {{AGENTE_NAME_LOWERCASE}} {{AGENTE_NAME_LOWERCASE}}_memory | gzip > /tmp/bkp/{{AGENTE_NAME_LOWERCASE}}_memory.sql.gz

# config essencial (sem caches/audio/workspace, que sao grandes e reproduziveis)
tar czf /tmp/bkp/config.tar.gz -C / \
  opt/{{AGENTE_NAME_LOWERCASE}}/CLAUDE.md opt/{{AGENTE_NAME_LOWERCASE}}/.claude opt/{{AGENTE_NAME_LOWERCASE}}/tools \
  opt/{{AGENTE_NAME_LOWERCASE}}/memory opt/{{AGENTE_NAME_LOWERCASE}}/database opt/{{AGENTE_NAME_LOWERCASE}}/knowledge \
  opt/{{AGENTE_NAME_LOWERCASE}}-bot/bot.py opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env opt/{{AGENTE_NAME_LOWERCASE}}-bot/healthcheck.sh \
  opt/{{AGENTE_NAME_LOWERCASE}}-bot/consolidate-conversations.py opt/{{AGENTE_NAME_LOWERCASE}}-bot/memory_api.py \
  root/.agente-secrets.env 2>/dev/null || true

cp /etc/systemd/system/{{AGENTE_NAME_LOWERCASE}}-*.service /tmp/bkp/ 2>/dev/null || true
crontab -l > /tmp/bkp/crontab.txt 2>/dev/null || true

# empacota e criptografa AES-256
tar czf /tmp/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz -C /tmp/bkp .
openssl enc -aes-256-cbc -pbkdf2 -salt -in /tmp/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz \
  -out "$REPO/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz.enc" -pass env:BACKUP_PASSPHRASE
echo "ultimo backup: $(date '+%F %T')  tamanho: $(du -h "$REPO/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz.enc" | cut -f1)" > "$REPO/ultimo-backup.txt"

# commit + push (so roda se REPO ja for um repositorio git configurado;
# backup local em /tmp/bkp acontece de qualquer jeito antes disso)
cd "$REPO"
git add -A
git -c user.email="{{AGENTE_NAME_LOWERCASE}}@vps" -c user.name="{{AGENTE_NAME_LOWERCASE}}-backup" commit -q -m "backup $(date '+%F %H:%M')" 2>/dev/null || true
GIT_SSH_COMMAND="$GSSH" git push -q origin main
rm -rf /tmp/bkp "/tmp/{{AGENTE_NAME_LOWERCASE}}-backup.tar.gz"
echo "backup enviado ao GitHub OK"
