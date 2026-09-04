#!/usr/bin/env python3
"""
Relatorio de consumo de tokens da {{AGENTE_NAME}} — CORRETO.

Corrige os dois bugs do relatorio improvisado anterior:
  1. FUSO: converte UTC -> BRT (UTC-3) ANTES de extrair data E hora.
     O bug antigo usava a hora UTC crua rotulada como BRT e filtrava o dia
     pela data-calendario UTC, o que (a) roubava 3h do dia anterior e
     (b) descartava as 3 ultimas horas reais do dia (~40% do volume).
  2. DEDUP: o streaming loga o mesmo message.id varias vezes com usage
     cumulativo. Somar linha a linha infla o total em ~72%. Aqui cada
     message.id conta uma vez, mantendo a ultima (= maior) ocorrencia.

Uso:
    python3 relatorio-tokens.py            # ontem
    python3 relatorio-tokens.py 2026-07-28 # dia especifico
    python3 relatorio-tokens.py hoje
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOGS = Path("/root/.claude/projects/-opt-{{AGENTE_NAME_LOWERCASE}}")
BRT = timezone(timedelta(hours=-3))

# Preco por milhao de tokens (input, output). Referencia — a conta real
# roda em assinatura Max, entao isso NAO e fatura, e so ordem de grandeza.
# Sonnet 5 em preco introdutorio ($2/$10) ate 2026-08-31.
PRECOS = {
    "claude-opus-5":    (5.00, 25.00),
    "claude-opus-4-8":  (5.00, 25.00),
    "claude-sonnet-5":  (2.00, 10.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}
PRECO_DESCONHECIDO = (3.00, 15.00)

CACHE_READ_MULT = 0.10   # cache lido custa ~10% do input
CACHE_CREATE_MULT = 1.25  # cache criado custa ~125% do input


def custo(modelo, inp, out, c_create, c_read):
    p_in, p_out = PRECOS.get(modelo, PRECO_DESCONHECIDO)
    return (
        inp / 1e6 * p_in
        + out / 1e6 * p_out
        + c_create / 1e6 * p_in * CACHE_CREATE_MULT
        + c_read / 1e6 * p_in * CACHE_READ_MULT
    )


def coletar(dia_brt):
    """Retorna {message_id: registro} deduplicado, so do dia BRT pedido."""
    vistos = {}
    arquivos = list(LOGS.glob("*.jsonl")) + list(LOGS.glob("*/subagents/*.jsonl"))

    for arq in arquivos:
        eh_sub = "subagents" in str(arq)
        try:
            with arq.open(encoding="utf-8", errors="replace") as fh:
                for linha in fh:
                    linha = linha.strip()
                    if not linha:
                        continue
                    try:
                        d = json.loads(linha)
                    except json.JSONDecodeError:
                        continue

                    msg = d.get("message")
                    if not isinstance(msg, dict):
                        continue
                    uso = msg.get("usage")
                    if not isinstance(uso, dict):
                        continue
                    ts = d.get("timestamp")
                    mid = msg.get("id")
                    if not ts or not mid:
                        continue

                    try:
                        dt_utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue

                    # >>> A CORRECAO: converte pra BRT ANTES de olhar data/hora <<<
                    dt_brt = dt_utc.astimezone(BRT)
                    if dt_brt.date() != dia_brt:
                        continue

                    total = (
                        uso.get("input_tokens", 0)
                        + uso.get("output_tokens", 0)
                        + uso.get("cache_creation_input_tokens", 0)
                        + uso.get("cache_read_input_tokens", 0)
                    )
                    # dedup: mantem a ocorrencia de maior usage (a final)
                    ant = vistos.get(mid)
                    if ant and ant["total"] >= total:
                        continue
                    vistos[mid] = {
                        "total": total,
                        "hora": dt_brt.hour,
                        "modelo": msg.get("model", "?"),
                        "sub": eh_sub,
                        "inp": uso.get("input_tokens", 0),
                        "out": uso.get("output_tokens", 0),
                        "cc": uso.get("cache_creation_input_tokens", 0),
                        "cr": uso.get("cache_read_input_tokens", 0),
                    }
        except OSError:
            continue
    return vistos


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    hoje = datetime.now(BRT).date()
    if arg in (None, "ontem"):
        dia = hoje - timedelta(days=1)
    elif arg == "hoje":
        dia = hoje
    else:
        dia = datetime.strptime(arg, "%Y-%m-%d").date()

    regs = coletar(dia)
    if not regs:
        print(f"Sem atividade registrada em {dia:%d/%m/%Y} (BRT).")
        return

    tot = sum(r["total"] for r in regs.values())
    inp = sum(r["inp"] for r in regs.values())
    out = sum(r["out"] for r in regs.values())
    cc = sum(r["cc"] for r in regs.values())
    cr = sum(r["cr"] for r in regs.values())

    pct = lambda v: (v / tot * 100) if tot else 0

    print(f"\n{'='*62}")
    print(f"  CONSUMO {{AGENTE_NAME_UPPER}} — {dia:%d/%m/%Y} (horario de Brasilia)")
    print(f"{'='*62}\n")

    print(f"TOTAL BRUTO: {tot:,}".replace(",", ".") + " tokens")
    print(f"  Cache lido (~10% do preco) {cr:>15,}  {pct(cr):5.2f}%".replace(",", "."))
    print(f"  Cache criado               {cc:>15,}  {pct(cc):5.2f}%".replace(",", "."))
    print(f"  SAIDA (trabalho real)      {out:>15,}  {pct(out):5.2f}%".replace(",", "."))
    print(f"  Input novo                 {inp:>15,}  {pct(inp):5.2f}%".replace(",", "."))
    print(f"\n  >> A metrica honesta de esforco e a SAIDA: {out:,} tokens".replace(",", "."))

    # por modelo
    print(f"\n{'-'*62}\nPOR MODELO\n{'-'*62}")
    mod = defaultdict(lambda: {"n": 0, "tot": 0, "out": 0, "inp": 0, "cc": 0, "cr": 0})
    for r in regs.values():
        m = mod[r["modelo"]]
        m["n"] += 1
        for k in ("tot", "out", "inp", "cc", "cr"):
            m[k] += r["total"] if k == "tot" else r[k]
    custo_total = 0.0
    for nome, m in sorted(mod.items(), key=lambda x: -x[1]["tot"]):
        c = custo(nome, m["inp"], m["out"], m["cc"], m["cr"])
        custo_total += c
        print(f"  {nome:<20} {m['n']:>5} turnos  {m['tot']:>14,} tok  saida {m['out']:>9,}  ~US$ {c:6.2f}".replace(",", "."))

    # principal vs subagente
    print(f"\n{'-'*62}\nPRINCIPAL vs SUBAGENTES\n{'-'*62}")
    for rotulo, flag in (("Principal", False), ("Subagentes", True)):
        sel = [r for r in regs.values() if r["sub"] is flag]
        if not sel:
            continue
        st = sum(r["total"] for r in sel)
        so = sum(r["out"] for r in sel)
        print(f"  {rotulo:<20} {len(sel):>5} turnos  {st:>14,} tok  saida {so:>9,}".replace(",", "."))

    # por hora
    print(f"\n{'-'*62}\nPOR HORA (BRT — fuso corrigido)\n{'-'*62}")
    horas = defaultdict(int)
    for r in regs.values():
        horas[r["hora"]] += r["total"]
    soma_h = 0
    for h in range(24):
        v = horas.get(h, 0)
        soma_h += v
        if v:
            barra = "#" * min(40, int(v / max(horas.values()) * 40))
            print(f"  {h:02d}h  {v:>14,}  {barra}".replace(",", "."))
    print(f"\n  Soma das horas: {soma_h:,}".replace(",", ".") +
          f"  (confere com o total: {'SIM' if soma_h == tot else 'NAO'})")

    print(f"\n{'-'*62}")
    print(f"CUSTO REFERENCIA: ~US$ {custo_total:.2f}")
    print("  ATENCAO: isso NAO e fatura. A conta roda em assinatura Max,")
    print("  que e preco fixo — nao ha cobranca por token. Este valor serve")
    print("  so pra comparar intensidade de uso entre dias.")
    print("  O que limita de verdade e a QUOTA (Opus tem teto semanal proprio).")
    print(f"{'-'*62}\n")


if __name__ == "__main__":
    main()
