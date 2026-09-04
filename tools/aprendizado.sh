#!/usr/bin/env bash
# Aciona a {{AGENTE_NAME}} para rodar a consolidação de aprendizado do time.
#
# Por que existe: em 06/08/2026 o Chefe perguntou se os agentes conseguem ir
# aprendendo com os erros e se moldando a ele. Agente não retém nada entre
# execuções: o único aprendizado possível é reescrever o .md dele. Se isso
# dependesse de a {{AGENTE_NAME}} lembrar, teria o mesmo defeito que existe para corrigir.
#
# Roda diariamente. Se a fila estiver vazia, não incomoda ninguém.
set -euo pipefail

FILA=/opt/{{AGENTE_NAME_LOWERCASE}}/memory/aprendizado/fila.md

# Conta só as entradas (linhas "## AAAA-MM-DD"), não o cabeçalho de exemplo.
# Bug corrigido em 13/08/2026: `grep -c` sai com status 1 quando a contagem e
# zero, mesmo tendo impresso "0" certinho. Com `|| echo 0` DENTRO do
# $(...), as duas saidas se juntavam ("0\n0"), e o teste de integer quebrava
# em silencio, deixando o script seguir e chamar o inject.sh com fila vazia.
# `|| N=0` FORA do $(...) evita a duplicacao: so substitui se o grep falhar
# de verdade (arquivo sumiu), nunca por causa do proprio "zero matches".
# Bug corrigido em 17/08/2026 (promessa #398, achado pela Aria em 14/08): a contagem
# exigia o separador `·` do template, e boa parte das entradas usa travessão `—`.
# O gatilho ficava cego para a maioria e a fila crescia sem ninguém ver: em 14/08
# reportou 2 de 10, e em 17/08 reportou 3 quando havia bem mais. A data já
# identifica a entrada, então o separador não entra no teste.
N=$(grep -cE '^## [0-9]{4}-[0-9]{2}-[0-9]{2}' "$FILA" 2>/dev/null) || N=0

[ "$N" -eq 0 ] && exit 0

# Quantidade de agentes CONTADA, não escrita à mão. O texto antigo dizia "os 12"
# e eram 16; número escrito à mão neste repositório apodrece sempre, e aqui ele
# ainda viajava dentro do briefing e virava erro do agente.
A=$(ls /opt/{{AGENTE_NAME_LOWERCASE}}/.claude/agents/*.md 2>/dev/null | wc -l)

/opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh "[sistema] Consolidação de aprendizado: a fila em memory/aprendizado/fila.md tem $N lição(ões) ainda não gravadas. Este fork não tem arquivista (Aria) e .claude/agents/ é read-only, então ninguém grava automaticamente no arquivo do agente. Leia a fila, resuma pro Chefe em uma linha o que tem pendente, e sugira se ele quer atualizar algum dos $A arquivos manualmente."
