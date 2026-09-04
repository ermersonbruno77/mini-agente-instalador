#!/usr/bin/env python3
"""Uma linha por dia com o custo do time, para a semana de comparação que o
Chefe pediu em 08/08/2026 ("consegue fazer assim e monitorar por uma semana
se melhorou?").

Mede o que dá para medir daqui: chamadas e tokens por agente, da tabela
`agente_atividade`. NÃO mede o custo da sessão principal — a fatura não passa
por mim, e inventar esse número seria pior que não ter.

Escreve em memory/custo-diario.tsv, uma linha por dia, idempotente: rodar duas
vezes no mesmo dia atualiza a linha, não duplica.
"""
import os
from datetime import date, timedelta
from pathlib import Path

import psycopg2

DSN = os.environ.get("DATABASE_URL", "postgresql://{{AGENTE_NAME_LOWERCASE}}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory")
ARQ = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/memory/custo-diario.tsv")
CABECALHO = "dia\tchamadas\tcom_token\tpct_com_token\ttokens\ttop_agente\ttokens_top\n"


def medir(dia: date):
    with psycopg2.connect(DSN) as con, con.cursor() as cur:
        cur.execute(
            """SELECT count(*), count(tokens), coalesce(sum(tokens), 0)
                 FROM agente_atividade
                WHERE iniciado_em >= %s AND iniciado_em < %s""",
            (dia, dia + timedelta(days=1)),
        )
        chamadas, com_token, tokens = cur.fetchone()
        cur.execute(
            """SELECT agente, coalesce(sum(tokens), 0) t
                 FROM agente_atividade
                WHERE iniciado_em >= %s AND iniciado_em < %s
                GROUP BY agente ORDER BY t DESC LIMIT 1""",
            (dia, dia + timedelta(days=1)),
        )
        linha = cur.fetchone()
    top, tokens_top = (linha[0], linha[1]) if linha else ("-", 0)
    pct = round(100 * com_token / chamadas) if chamadas else 0
    return f"{dia}\t{chamadas}\t{com_token}\t{pct}\t{tokens}\t{top}\t{tokens_top}\n"


def main():
    ontem = date.today() - timedelta(days=1)
    nova = medir(ontem)
    linhas = ARQ.read_text().splitlines(keepends=True) if ARQ.exists() else [CABECALHO]
    if not linhas or not linhas[0].startswith("dia\t"):
        linhas.insert(0, CABECALHO)
    linhas = [l for l in linhas if not l.startswith(f"{ontem}\t")]
    linhas.append(nova)
    corpo = [linhas[0]] + sorted(l for l in linhas[1:] if l.strip())
    ARQ.write_text("".join(corpo))
    print(nova.strip())


if __name__ == "__main__":
    raise SystemExit(main())
