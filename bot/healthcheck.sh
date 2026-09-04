#!/bin/bash
# Health-check da arquitetura (bot externo + claude code).
# Roda a cada 2 min via cron. Alerta no Telegram do Chefe se algo crashar.
# Auto-restart de servicos parados.

LOG=/opt/{{AGENTE_NAME_LOWERCASE}}-bot/logs/healthcheck.log
TOKEN=$(grep ^TELEGRAM_BOT_TOKEN= /opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env | cut -d= -f2-)
CHAT_ID=$(grep ^ALLOWED_USERS= /opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env | cut -d= -f2- | cut -d, -f1)
ALERT_FILE=/tmp/{{AGENTE_NAME_LOWERCASE}}-health-last-alert
NOW=$(date '+%Y-%m-%d %H:%M:%S')

log() { echo "[$NOW] $*" >> "$LOG"; }

alert() {
    local msg="$1"
    # Throttle: nao manda mesmo alerta mais de 1x a cada 5 minutos
    local key=$(echo "$msg" | md5sum | cut -c1-16)
    local last=$(grep "^$key:" "$ALERT_FILE" 2>/dev/null | cut -d: -f2)
    local now_ts=$(date +%s)
    if [ -n "$last" ] && [ $((now_ts - last)) -lt 300 ]; then
        log "alert SUPPRESSED (throttled): $msg"
        return
    fi
    grep -v "^$key:" "$ALERT_FILE" 2>/dev/null > "${ALERT_FILE}.tmp" || true
    echo "$key:$now_ts" >> "${ALERT_FILE}.tmp"
    mv "${ALERT_FILE}.tmp" "$ALERT_FILE"

    log "ALERT: $msg"
    curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
        -d "chat_id=${CHAT_ID}" \
        --data-urlencode "text=⚠️ HEALTH ALERT: ${msg}" \
        > /dev/null 2>&1 || true
}

# Check 1: bot Python esta rodando?
if ! systemctl is-active --quiet {{AGENTE_NAME_LOWERCASE}}-bot; then
    alert "Bot Python parado. Reiniciando..."
    systemctl restart {{AGENTE_NAME_LOWERCASE}}-bot
fi

# Check 2: sessao Claude Code do agente esta rodando?
if ! systemctl is-active --quiet {{AGENTE_NAME_LOWERCASE}}-agent; then
    alert "Sessao do agente parada. Reiniciando..."
    systemctl restart {{AGENTE_NAME_LOWERCASE}}-agent
fi

# Check 3: tmux session do agente existe?
if ! tmux has-session -t {{AGENTE_NAME_LOWERCASE}} 2>/dev/null; then
    alert "tmux session do agente nao existe. Reiniciando {{AGENTE_NAME_LOWERCASE}}-agent..."
    systemctl restart {{AGENTE_NAME_LOWERCASE}}-agent
fi

log "OK - tudo saudavel"
