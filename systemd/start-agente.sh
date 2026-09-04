#!/bin/bash
# Sobe a sessao tmux persistente do agente Claude Code.
# Chamado pelo systemd ({{AGENTE_NAME_LOWERCASE}}-agent.service), roda como o
# usuario dedicado do agente (nunca como root: --dangerously-skip-permissions
# recusa rodar como root, por isso o useradd da ETAPA 3 nao e opcional).
NODE_BIN=$(dirname "$(ls -d /root/.nvm/versions/node/*/bin/node 2>/dev/null | head -1)")
if [ -z "$NODE_BIN" ]; then
  echo "ERRO: node nao encontrado em /root/.nvm/versions/node/*/bin. Rodou o bootstrap.sh?" >&2
  exit 1
fi
export PATH="$NODE_BIN:$PATH"
cd /opt/{{AGENTE_NAME_LOWERCASE}}
/usr/bin/tmux kill-session -t {{AGENTE_NAME_LOWERCASE}} 2>/dev/null || true
exec /usr/bin/tmux new-session -d -s {{AGENTE_NAME_LOWERCASE}} "$NODE_BIN/claude --dangerously-skip-permissions"
