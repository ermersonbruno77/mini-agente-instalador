#!/usr/bin/env python3
"""Acuracia do motor de credito (aba 'Pedidos de julho' do artefato FPD).

Uso: python3 tools/acuracia_motor_fpd.py <artefato-fpd.html>
Medido em 21/08/2026: so 3.958 dos 14.279 tinham parcela 1 vencida com folga
(venc 10/08); 9.523 vencem em 20/08, que e o corte da replica. Rodar de novo
depois da carga de ~03/09, quando o bloco medivel vai a ~13,5 mil.

Le a lista congelada dentro do HTML do artefato (nao altera nada) e confronta
com o pagamento real que ja entrou na replica da TMB. Nada do banco vira
arquivo: a consulta roda pelo tools/tmb.py, o resultado fica em memoria e so
o agregado e impresso.
"""
import json, re, subprocess, sys
from collections import defaultdict

import os
# O array congelado vive DENTRO do artefato dele (nao alterar o artefato):
#   https://claude.ai/code/artifact/64a4d603-7bab-4d48-81df-3f53dbae4e9c  (aba "Pedidos de julho")
# Baixar com WebFetch e passar o caminho do HTML como argumento.
ART = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ARTEFATO_FPD", "")
HORIZONTE = "2026-08-20"   # ultima data com pagamento na replica

h = open(ART, encoding="utf-8", errors="replace").read()
julho = json.loads(re.search(r"const JULHO=(\[.*?\]);", h, re.S).group(1))
prev = {int(x["id"]): x for x in julho}

SQL = """
WITH j AS (
  SELECT id, fpd FROM pedidos
  WHERE criado_em >= '2026-07-01' AND criado_em < '2026-08-01'
)
SELECT j.id,
       j.fpd,
       max(CASE WHEN pp.parcela = 0 AND pp.data_pagamento IS NOT NULL THEN 1 ELSE 0 END) AS entrada_paga,
       min(pp.vencimento_parcela::date) FILTER (WHERE pp.parcela = 1) AS venc1,
       min(pp.data_pagamento::date)     FILTER (WHERE pp.parcela = 1) AS pgto1,
       count(*) FILTER (WHERE pp.parcela >= 1) AS n_parc,
       count(*) FILTER (WHERE pp.parcela >= 1 AND pp.data_pagamento IS NOT NULL) AS n_pagas
FROM j JOIN pedido_parcelas pp ON pp.pedido_id = j.id
GROUP BY 1, 2
"""

r = subprocess.run(
    ["python3", "/opt/{{AGENTE_NAME_LOWERCASE}}/tools/tmb.py", "--formato", "tsv", SQL,
     "acuracia do motor de credito: desfecho real dos pedidos congelados de julho"],
    capture_output=True, text=True, timeout=900)
if r.returncode != 0:
    sys.exit("consulta falhou: " + r.stderr[-500:])

linhas = r.stdout.splitlines()
cols = linhas[0].split("\t")
real = {}
for l in linhas[1:]:
    v = dict(zip(cols, l.split("\t")))
    real[int(v["id"])] = v

casados = [i for i in prev if i in real]
print(f"congelados no artefato ....... {len(prev)}")
print(f"encontrados no banco ......... {len(casados)}")

# So da para medir quem tem parcela 1 com alguma folga depois do vencimento.
# A replica tem pagamento ate 20/08, e as duas datas grandes de vencimento sao
# 10/08 (10 dias de folga) e 20/08 (nenhuma). Mede-se a de 10/08.
def grupo(venc):
    g = []
    for i in casados:
        v = real[i]
        if v["entrada_paga"] != "1":   # sem entrada paga nao entra na definicao de FPD
            continue
        if v["venc1"] == venc:
            g.append(i)
    return g

MED = grupo("2026-08-10")
NAO = grupo("2026-08-20")
sem_entrada = sum(1 for i in casados if real[i]["entrada_paga"] != "1")
print(f"entrada nao paga (fora) ...... {sem_entrada}")
print(f"parcela 1 em 10/08 (mede) .... {len(MED)}")
print(f"parcela 1 em 20/08 (cego) .... {len(NAO)}")
print(f"outros vencimentos ........... {len(casados)-sem_entrada-len(MED)-len(NAO)}")

def naopago(i):
    return real[i]["pgto1"] == ""

FAIXA = {"V":"Verde (<15%)","A":"Amarelo (15-30%)","R":"Vermelho (30-60%)","T":"Trava (>=60%)"}
print("\n=== bloco medivel: 4,4 mil pedidos com parcela 1 em 10/08, foto em 20/08 (d+10) ===")
print(f"{'faixa':18} {'pedidos':>8} {'prev.medio':>11} {'nao pagou':>10} {'qtd':>6}")
for f in ("V","A","R","T"):
    g=[i for i in MED if prev[i]["f"]==f]
    if not g: continue
    pm=sum(prev[i]["p"] for i in g)/len(g)
    nf=[i for i in g if naopago(i)]
    print(f"{FAIXA[f]:18} {len(g):>8} {pm:>10.1f}% {100*len(nf)/len(g):>9.1f}% {len(nf):>6}")
nf=[i for i in MED if naopago(i)]
print(f"{'TOTAL':18} {len(MED):>8} {sum(prev[i]['p'] for i in MED)/len(MED):>10.1f}% {100*len(nf)/len(MED):>9.1f}% {len(nf):>6}")

# poder de ordenar dentro do bloco medivel
import bisect
aval=sorted(MED,key=lambda i:prev[i]["p"])
n=len(aval)
print("\n=== quintis da nota (mais seguro -> mais arriscado) ===")
for d in range(5):
    g=aval[d*n//5:(d+1)*n//5]
    print(f"  quintil {d+1}: prev {sum(prev[i]['p'] for i in g)/len(g):5.1f}%   real {100*sum(1 for i in g if naopago(i))/len(g):5.1f}%   ({len(g)} pedidos)")
pos=[prev[i]["p"] for i in aval if naopago(i)]; neg=[prev[i]["p"] for i in aval if not naopago(i)]
neg_s=sorted(neg); soma=0.0
for x in pos:
    lo=bisect.bisect_left(neg_s,x); hi=bisect.bisect_right(neg_s,x); soma+=lo+(hi-lo)/2
print(f"\nAUC ......................... {soma/(len(pos)*len(neg)):.3f}   (0,50 = moeda; 0,70 = util; 0,80 = bom)")
print(f"nao pagou / pagou ........... {len(pos)} / {len(neg)}")

# recorte que o motor trataria
trat=[i for i in MED if prev[i]["f"] in ("R","T")]
tf=[i for i in trat if naopago(i)]
print(f"\n=== recorte vermelho+trava dentro do bloco medivel ===")
print(f"marcados ..................... {len(trat)} ({100*len(trat)/len(MED):.1f}% do bloco)")
print(f"nao pagaram .................. {len(tf)} ({100*len(tf)/max(1,len(trat)):.1f}% deles)")
print(f"fatia do nao pagamento total .. {100*len(tf)/max(1,len(pos)):.1f}%")
print(f"bons pagadores no recorte .... {len(trat)-len(tf)}")
print(f"R$ marcado ................... {sum(prev[i]['v'] for i in trat):,.0f}")
