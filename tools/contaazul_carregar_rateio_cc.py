#!/usr/bin/env python3
"""Baixa o RATEIO REAL por centro de custo dos lançamentos rateados.

Por que existe: `/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar`
devolve `centros_de_custo: [{id, nome}]`, sem valor. A carga dividia igual
entre os CCs, então o total fechava e a DRE por centro ficava errada. O valor
por CC existe no ERP e sai em:

    GET /v1/financeiro/eventos-financeiros/parcelas/{id}
        -> evento.rateio[].rateio_centro_custo[] = {id_centro_custo,
           nome_centro_custo, valor, valor_bruto}

O `{id}` é o MESMO id que o `buscar` devolve (é id de PARCELA, não de evento:
`/v1/financeiro/eventos-financeiros/{id}/parcelas` com esse id devolve `[]`).
`evento.codigo_referencia` é o número da Compra que aparece na tela.

Só GET, 1 chamada/segundo (o ritmo é do tools/contaazul.py). 429 para de vez.
Retomável: relê o cache e só busca id que falta.
"""
import json, os, sys
sys.path.insert(0, "/opt/{{AGENTE_NAME_LOWERCASE}}/tools")
import contaazul as ca

ARQ = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/contas-a-pagar.jsonl"
CACHE = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/rateio-cc.jsonl"


def ids_rateados(arq=ARQ):
    """Quem tem mais de um centro de custo no lançamento. Um CC só não precisa
    de rateio: a fatia é o total."""
    fora = []
    for linha in open(arq, encoding="utf-8"):
        d = json.loads(linha)
        if len(d.get("centros_de_custo") or []) > 1:
            fora.append(d["id"])
    return fora


def cache_atual(caminho=CACHE):
    tem = {}
    if os.path.exists(caminho):
        for linha in open(caminho, encoding="utf-8"):
            linha = linha.strip()
            if not linha:
                continue
            d = json.loads(linha)
            tem[d["id"]] = d
    return tem


def principal():
    alvo = ids_rateados()
    tem = cache_atual()
    falta = [i for i in alvo if i not in tem]
    print(f"rateados: {len(alvo)} | ja no cache: {len(alvo) - len(falta)} | a buscar: {len(falta)}", flush=True)
    erros = 0
    with open(CACHE, "a", encoding="utf-8") as saida:
        for n, pid in enumerate(falta, 1):
            try:
                r = ca.get(f"/v1/financeiro/eventos-financeiros/parcelas/{pid}")
            except ca.LimiteAtingidoError as e:
                print(f"PAROU no 429 depois de {n-1} de {len(falta)}: {e}")
                return 2
            if r.status_code != 200:
                erros += 1
                saida.write(json.dumps({"id": pid, "erro": r.status_code}) + "\n")
                saida.flush()
                if erros > 20:
                    print(f"PAROU: {erros} respostas fora de 200 (ultima {r.status_code})")
                    return 3
                continue
            c = r.json()
            ev = c.get("evento") or {}
            saida.write(json.dumps({
                "id": pid,
                "codigo_referencia": ev.get("codigo_referencia"),
                "valor_parcela": c.get("valor_composicao", {}).get("valor_bruto"),
                "rateio": ev.get("rateio") or [],
            }, ensure_ascii=False) + "\n")
            saida.flush()
            if n % 25 == 0:
                print(f"  {n}/{len(falta)}", flush=True)
    print(f"fim. erros: {erros}. cache: {len(cache_atual())} ids")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
