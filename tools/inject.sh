#!/usr/bin/env bash
# Injeta um prompt na sessao tmux da {{AGENTE_NAME}} (mesma via que o bot usa).
#
# POR QUE ESTE ARQUIVO TEM LOG E FILA (07/08/2026):
# A versao anterior era `tmux has-session || exit 0`. Sem sessao, ela saia em
# SILENCIO, com codigo 0, dizendo ao cron que tinha dado certo. Nada era
# entregue e nada ficava registrado.
#
# Como isso apareceu: o Chefe pediu em 28/07 um briefing de mercado. O script e
# o cron foram criados no mesmo dia. Em 07/08, dez dias depois, o Rafael reparou
# que ele nunca tinha recebido nenhum. Nao havia log, nao havia erro, nao havia
# nada pra investigar.
#
# Sao 8 automaticos dependendo deste arquivo (briefing, lembretes, cobranca do
# Rafael, ingles, aprendizado, relatorio, promessas, monitores). Todos tinham o
# mesmo buraco: sumir sem deixar rastro.
#
# Agora: toda tentativa fica no log, e o que nao pode ser entregue vai pra fila
# em vez de evaporar. Quem estiver vivo depois entrega.
set -u
MSG="${1:-}"
LOG=/opt/{{AGENTE_NAME_LOWERCASE}}-bot/logs/inject.log
FILA=/opt/{{AGENTE_NAME_LOWERCASE}}/.rtk/inject-fila
mkdir -p "$(dirname "$LOG")" "$FILA" 2>/dev/null

carimbo() { date -u +%FT%TZ; }
resumo=$(printf '%s' "$MSG" | head -c 90 | tr '\n' ' ')

if [ -z "$MSG" ]; then
  echo "$(carimbo) RECUSADO mensagem vazia" >> "$LOG"
  exit 2
fi

if ! tmux has-session -t {{AGENTE_NAME_LOWERCASE}} 2>/dev/null; then
  # Nao perde: guarda pra proxima sessao. O nome do arquivo ordena por chegada.
  arq="$FILA/$(date -u +%Y%m%dT%H%M%S)-$$.txt"
  printf '%s' "$MSG" > "$arq"
  echo "$(carimbo) SEM SESSAO, enfileirado em $arq | $resumo" >> "$LOG"
  exit 0
fi

# 13/08/2026: has-session acima confirma sessao viva NO INSTANTE do check, mas
# a sessao pode morrer no meio (restart do {{AGENTE_NAME_LOWERCASE}}-agent cruzando com o inject).
# Sem checar o retorno do send-keys, essa corrida vazava erro cru do tmux pro
# log de quem chamou (ex: aprendizado.log) e a mensagem sumia sem cair na fila,
# contradizendo o motivo deste arquivo existir. Agora tambem enfileira nesse caso.
if ! tmux send-keys -t {{AGENTE_NAME_LOWERCASE}} -l "$MSG" 2>>"$LOG"; then
  arq="$FILA/$(date -u +%Y%m%dT%H%M%S)-$$.txt"
  printf '%s' "$MSG" > "$arq"
  echo "$(carimbo) SESSAO MORREU NO MEIO, enfileirado em $arq | $resumo" >> "$LOG"
  exit 0
fi
sleep 0.4
tmux send-keys -t {{AGENTE_NAME_LOWERCASE}} Enter 2>>"$LOG"
echo "$(carimbo) ENTREGUE | $resumo" >> "$LOG"
