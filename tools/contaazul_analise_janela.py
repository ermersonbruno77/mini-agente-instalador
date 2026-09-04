"""
Analise da janela de pagamento (contas a pagar), comparando contra o
historico carregado em contas-a-pagar.jsonl.

Uso: python3 contaazul_analise_janela.py
Le: /opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/contas-a-pagar.jsonl (historico completo)
    /opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/janela-hoje-11-15ago.json (janela de hoje)
"""

import json
import statistics
from collections import defaultdict

HISTORICO = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/contas-a-pagar.jsonl"
JANELA = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/janela-hoje-11-15ago.json"

JANELA_INICIO = "2026-08-11"
JANELA_FIM = "2026-08-15"


def carregar_historico():
    """Historico ANTES da janela de hoje, por fornecedor (nome, ja que so ele existe no payload)."""
    por_fornecedor = defaultdict(list)
    primeiro_venc_por_fornecedor = {}
    total = 0
    with open(HISTORICO) as f:
        for linha in f:
            item = json.loads(linha)
            venc = item.get("data_vencimento") or ""
            if venc >= JANELA_INICIO:
                continue  # so historico anterior a janela de hoje
            total += 1
            nome = (item.get("fornecedor") or {}).get("nome") or "(sem fornecedor)"
            por_fornecedor[nome].append(item)
            if nome not in primeiro_venc_por_fornecedor or venc < primeiro_venc_por_fornecedor[nome]:
                primeiro_venc_por_fornecedor[nome] = venc
    print(f"historico anterior a {JANELA_INICIO}: {total} registros, {len(por_fornecedor)} fornecedores unicos")
    return por_fornecedor, primeiro_venc_por_fornecedor


def analisar():
    hist, primeiro_venc = carregar_historico()
    janela = json.load(open(JANELA))

    achados = []

    # concentracao: fornecedor com varios lancamentos na propria janela
    por_fornecedor_janela = defaultdict(list)
    for item in janela:
        nome = (item.get("fornecedor") or {}).get("nome") or "(sem fornecedor)"
        por_fornecedor_janela[nome].append(item)

    # repetido dentro da janela: mesmo fornecedor + mesmo valor
    for nome, itens_f in por_fornecedor_janela.items():
        valores = defaultdict(list)
        for it in itens_f:
            valores[round(it["total"], 2)].append(it)
        for valor, itens_v in valores.items():
            if len(itens_v) > 1:
                achados.append({
                    "tipo": "repetido_na_janela",
                    "fornecedor": nome,
                    "valor": valor,
                    "qtd": len(itens_v),
                    "ids": [i["id"] for i in itens_v],
                    "datas": [i["data_vencimento"] for i in itens_v],
                    "descricoes": [i["descricao"] for i in itens_v],
                })

    # repetido vs historico: mesmo fornecedor + mesmo valor exato pago antes
    for item in janela:
        nome = (item.get("fornecedor") or {}).get("nome") or "(sem fornecedor)"
        valor = round(item["total"], 2)
        historico_fornecedor = hist.get(nome, [])
        iguais = [h for h in historico_fornecedor if round(h["total"], 2) == valor]
        if iguais:
            # ignora recorrencia mensal legitima: mesmo valor, intervalo ~30 dias regular
            datas_iguais = sorted(h["data_vencimento"] for h in iguais)
            achados.append({
                "tipo": "valor_igual_no_historico",
                "fornecedor": nome,
                "valor": valor,
                "id": item["id"],
                "data_vencimento": item["data_vencimento"],
                "descricao": item["descricao"],
                "qtd_ocorrencias_historico": len(iguais),
                "ultimas_datas_historico": datas_iguais[-5:],
            })

    # destoa da media do fornecedor
    for item in janela:
        nome = (item.get("fornecedor") or {}).get("nome") or "(sem fornecedor)"
        valor = item["total"]
        historico_fornecedor = hist.get(nome, [])
        if len(historico_fornecedor) < 3:
            continue  # sem historico suficiente, nao inventa media
        valores_hist = [h["total"] for h in historico_fornecedor]
        media = statistics.mean(valores_hist)
        desvio = statistics.pstdev(valores_hist) if len(valores_hist) > 1 else 0
        if desvio == 0:
            if valor != media and media > 0 and abs(valor - media) / media > 0.5:
                achados.append({
                    "tipo": "destoa_media_fornecedor",
                    "fornecedor": nome,
                    "valor": valor,
                    "media_historico": media,
                    "desvio_historico": desvio,
                    "n_historico": len(valores_hist),
                    "id": item["id"],
                    "descricao": item["descricao"],
                })
        else:
            z = (valor - media) / desvio
            if abs(z) >= 3:
                achados.append({
                    "tipo": "destoa_media_fornecedor",
                    "fornecedor": nome,
                    "valor": valor,
                    "media_historico": round(media, 2),
                    "desvio_historico": round(desvio, 2),
                    "z": round(z, 2),
                    "n_historico": len(valores_hist),
                    "id": item["id"],
                    "descricao": item["descricao"],
                })

    # fornecedor novo ou recente com valor alto
    for item in janela:
        nome = (item.get("fornecedor") or {}).get("nome") or "(sem fornecedor)"
        valor = item["total"]
        historico_fornecedor = hist.get(nome, [])
        if len(historico_fornecedor) == 0 and valor >= 1000:
            achados.append({
                "tipo": "fornecedor_sem_historico_valor_alto",
                "fornecedor": nome,
                "valor": valor,
                "id": item["id"],
                "descricao": item["descricao"],
                "data_vencimento": item["data_vencimento"],
            })

    # parcela estranha: descricao com padrao n/m
    import re
    padrao = re.compile(r"(\d+)\s*/\s*(\d+)")
    for item in janela:
        desc = item.get("descricao") or ""
        m = padrao.search(desc)
        if not m:
            continue
        indice, qtd_total = int(m.group(1)), int(m.group(2))
        if indice <= 1:
            continue  # primeira parcela, nada a comparar
        nome = (item.get("fornecedor") or {}).get("nome") or "(sem fornecedor)"
        historico_fornecedor = hist.get(nome, [])
        # busca parcelas anteriores da mesma serie (mesma raiz de descricao, indice menor)
        raiz = padrao.sub("", desc).strip()
        anteriores = []
        for h in historico_fornecedor:
            hd = h.get("descricao") or ""
            hm = padrao.search(hd)
            if hm and padrao.sub("", hd).strip() == raiz:
                anteriores.append((int(hm.group(1)), h["total"]))
        indices_vistos = sorted(set(a[0] for a in anteriores))
        faltantes = [i for i in range(1, indice) if i not in indices_vistos]
        valores_serie = set(round(a[1], 2) for a in anteriores)
        if faltantes or (valores_serie and round(item["total"], 2) not in valores_serie):
            achados.append({
                "tipo": "parcela_estranha",
                "fornecedor": nome,
                "descricao": desc,
                "indice": indice,
                "total_parcelas_esperado": qtd_total,
                "parcelas_anteriores_encontradas": indices_vistos,
                "parcelas_faltantes": faltantes,
                "valores_parcelas_anteriores": sorted(valores_serie),
                "valor_atual": item["total"],
                "id": item["id"],
            })

    # concentracao: fornecedor com >=3 lancamentos na janela (mesmo com valores diferentes)
    for nome, itens_f in por_fornecedor_janela.items():
        if len(itens_f) >= 3:
            total_fornecedor = sum(i["total"] for i in itens_f)
            achados.append({
                "tipo": "concentracao",
                "fornecedor": nome,
                "qtd_lancamentos": len(itens_f),
                "total": round(total_fornecedor, 2),
                "ids": [i["id"] for i in itens_f],
                "descricoes": [i["descricao"] for i in itens_f],
            })

    json.dump(achados, open("/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/contaazul/achados-brutos.json", "w"), ensure_ascii=False, indent=2)
    print(f"achados brutos: {len(achados)}")
    return achados


if __name__ == "__main__":
    analisar()
