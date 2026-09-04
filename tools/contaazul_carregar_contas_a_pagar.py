"""
Carga do historico de contas a pagar da Conta Azul.

SOMENTE LEITURA. Ritmo maximo 1 req/s (ver tools/contaazul.py, topo do
arquivo). Se vier 429, contaazul.get() levanta LimiteAtingidoError e este
script para de vez, sem retry.

Saida: um registro JSON por linha em
/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/contas-a-pagar.jsonl
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import contaazul  # noqa: E402

ENDPOINT = "/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar"
SAIDA = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/contas-a-pagar.jsonl"
TAMANHO_PAGINA = 1000
DATA_DE = "1990-01-01"
DATA_ATE = "2099-12-31"


def carregar():
    # retomada: se ja existe arquivo com N linhas cheias de paginas de
    # TAMANHO_PAGINA, comeca da proxima pagina em vez de do zero.
    pagina_inicial = 1
    if os.path.exists(SAIDA):
        with open(SAIDA) as f_check:
            linhas_existentes = sum(1 for _ in f_check)
        if linhas_existentes > 0 and linhas_existentes % TAMANHO_PAGINA == 0:
            pagina_inicial = (linhas_existentes // TAMANHO_PAGINA) + 1
            print(f"retomando: {linhas_existentes} linhas ja gravadas, comecando na pagina {pagina_inicial}")
        elif linhas_existentes > 0:
            print(f"arquivo com {linhas_existentes} linhas nao alinhadas a pagina, recomece manualmente")
            return 0

    pagina = pagina_inicial
    total_gravado = pagina_inicial > 1 and (pagina_inicial - 1) * TAMANHO_PAGINA or 0
    itens_totais_esperado = None
    inicio = time.time()

    modo_arquivo = "a" if pagina_inicial > 1 else "w"
    with open(SAIDA, modo_arquivo) as f:
        while True:
            r = contaazul.get(
                ENDPOINT,
                params={
                    "pagina": pagina,
                    "tamanho_pagina": TAMANHO_PAGINA,
                    "data_vencimento_de": DATA_DE,
                    "data_vencimento_ate": DATA_ATE,
                },
            )
            if r.status_code != 200:
                print(f"PAROU na pagina {pagina}: status {r.status_code} corpo {r.text[:500]}")
                break

            d = r.json()
            if itens_totais_esperado is None:
                itens_totais_esperado = d.get("itens_totais")
                print(f"itens_totais reportado pela API: {itens_totais_esperado}")

            itens = d.get("itens", [])
            if not itens:
                print(f"pagina {pagina} vazia, encerrando paginacao")
                break

            for item in itens:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            total_gravado += len(itens)

            decorrido = time.time() - inicio
            print(
                f"pagina {pagina}: +{len(itens)} itens, total {total_gravado}"
                f"/{itens_totais_esperado}, {decorrido:.0f}s decorridos"
            )

            if len(itens) < TAMANHO_PAGINA:
                print("ultima pagina (menor que o tamanho pedido), encerrando")
                break

            pagina += 1

    print(f"FIM: {total_gravado} registros gravados em {SAIDA}")
    return total_gravado


if __name__ == "__main__":
    try:
        carregar()
    except contaazul.LimiteAtingidoError as e:
        print(f"LIMITE ATINGIDO, PARADO DE VEZ: {e}")
        sys.exit(2)
