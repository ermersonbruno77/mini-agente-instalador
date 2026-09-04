#!/usr/bin/env bash
SUS=""
for pid in $(ls /proc 2>/dev/null | grep -E '^[0-9]+$'); do
  exe=$(readlink "/proc/$pid/exe" 2>/dev/null)
  case "$exe" in
    /tmp/*|/dev/shm/*|/var/tmp/*) SUS="$SUS | proc suspeito pid=$pid exe=$exe" ;;
  esac
done
for name in xmrig minerd kdevtmpfsi kinsing cnrig xmr-stak nanominer phoenixminer; do
  p=$(pgrep -x "$name" 2>/dev/null)
  [ -n "$p" ] && SUS="$SUS | miner conhecido: $name (pid $p)"
done
if [ -n "$SUS" ]; then
  echo "[$(date '+%F %T')] ALERTA:$SUS" >> /opt/{{AGENTE_NAME_LOWERCASE}}-bot/logs/security.log
  /opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh "[sistema][SEGURANCA] Possível minerador/invasão na VPS: $SUS . Avise o Chefe AGORA no Telegram, com urgência, e liste os processos suspeitos."
fi
