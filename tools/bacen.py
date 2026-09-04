#!/usr/bin/env python3
"""Índices oficiais do Banco Central, sem cadastro e sem chave.

Criado em 16/08/2026, ordem dele: "Instale a do Bacen". O buraco que fecha:
até hoje, quando ele perguntava CDI ou IPCA, eu não tinha fonte oficial — ou
pesquisava na web e citava um blog, ou chutava. Agora tem série oficial, com a
data do dado ao lado, que é o que separa número de palpite.

API pública do BCB (SGS). Sem chave, sem cadastro, sem limite publicado. Ainda
assim, este arquivo guarda em cache por 6 horas: índice diário não muda de
minuto em minuto e não há motivo para bater no servidor deles a cada pergunta.

Uso:
    python3 tools/bacen.py resumo
    python3 tools/bacen.py serie cdi --desde 2026-01-01
    python3 tools/bacen.py serie 433 --ultimos 12

ARMADILHA MEDIDA, não suposta: a série 432 (meta Selic) vem carimbada com a
data de VALIDADE da decisão do Copom, que pode ser no FUTURO. Em 16/08/2026 ela
respondeu "16/09/2026". Não é dado errado nem relógio adiantado: é a meta que
passa a valer na próxima reunião. Por isso o resumo marca essa linha quando a
data é futura, em vez de anunciar como se fosse hoje.

Os percentuais vêm como estão na fonte: `selic_dia` e `cdi_dia` são ao DIA
(0,0517% ≈ 14% ao ano), `ipca` e `igpm` são do MÊS, `selic_meta` e `cdi_ano`
são ao ANO. Misturar isso é o erro clássico, então o rótulo anda junto do
número em toda saída.
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

CACHE = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/.rtk/bacen-cache.json")
VALIDADE_S = 6 * 3600
BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"

# Apelido -> (código SGS, o que é, unidade)
SERIES = {
    "selic_dia": (11, "Selic efetiva", "% ao dia"),
    "selic_meta": (432, "Meta Selic do Copom", "% ao ano"),
    "cdi_dia": (12, "CDI", "% ao dia"),
    "cdi_ano": (4389, "CDI anualizado (base 252)", "% ao ano"),
    "ipca": (433, "IPCA do mês", "% no mês"),
    # IPCA em 12 meses NÃO sai pronto de uma série. Eu tinha posto a 4390 aqui
    # com esse rótulo e conferi antes de usar: ela devolveu 0,52% enquanto os
    # 12 meses da 433, compostos, dão 4,44%. Não é a mesma coisa, e publicar
    # 0,52% como "inflação do ano" seria erro grosseiro num número que ele usa
    # para decidir. A 4390 ficou de fora até alguém saber dizer o que ela é.
    # O acumulado se calcula abaixo, compondo a própria 433.
    "igpm": (189, "IGP-M do mês", "% no mês"),
    "dolar": (1, "Dólar PTAX venda", "R$"),
}


def _cache_ler() -> dict:
    try:
        d = json.loads(CACHE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _buscar(url: str, chave: str, usar_cache: bool = True) -> list:
    cache = _cache_ler()
    item = cache.get(chave)
    if usar_cache and item and time.time() - item.get("em", 0) < VALIDADE_S:
        return item["dados"]

    req = urllib.request.Request(url, headers={"User-Agent": "{{AGENTE_NAME_LOWERCASE}}/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        dados = json.loads(r.read().decode("utf-8"))

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache[chave] = {"em": time.time(), "dados": dados}
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return dados


def _codigo(nome: str) -> tuple:
    if nome in SERIES:
        return SERIES[nome]
    if nome.isdigit():
        return (int(nome), f"série {nome}", "")
    raise SystemExit(
        f"não conheço '{nome}'. Apelidos: {', '.join(SERIES)} — ou passe o código SGS."
    )


def serie(nome: str, ultimos: int, desde: str | None) -> None:
    cod, rotulo, unidade = _codigo(nome)
    if desde:
        a, m, d = desde.split("-")
        url = f"{BASE.format(cod=cod)}?formato=json&dataInicial={d}/{m}/{a}"
        chave = f"{cod}|desde|{desde}"
    else:
        url = f"{BASE.format(cod=cod)}/ultimos/{ultimos}?formato=json"
        chave = f"{cod}|ultimos|{ultimos}"
    for linha in _buscar(url, chave):
        print(f"{linha['data']}  {linha['valor']:>12}  {unidade}")
    print(f"({rotulo}, série {cod}, fonte Banco Central)")


def _dia_mes_ano(s: str) -> tuple:
    d, m, a = s.split("/")
    return int(a), int(m), int(d)


def resumo() -> None:
    hoje = time.localtime()
    agora = (hoje.tm_year, hoje.tm_mon, hoje.tm_mday)
    print(f"{'':14} {'valor':>10}  {'':14} data")
    for apelido, (cod, rotulo, unidade) in SERIES.items():
        try:
            dados = _buscar(
                f"{BASE.format(cod=cod)}/ultimos/1?formato=json", f"{cod}|ultimos|1"
            )
        except Exception as erro:  # rede caiu, série mudou de código, etc.
            print(f"{apelido:14} {'não veio':>10}  ({erro})")
            continue
        if not dados:
            print(f"{apelido:14} {'vazia':>10}")
            continue
        linha = dados[-1]
        marca = "  <- vale a partir dessa data" if _dia_mes_ano(linha["data"]) > agora else ""
        print(f"{apelido:14} {linha['valor']:>10}  {unidade:14} {linha['data']}{marca}")

    # Acumulado de 12 meses, composto (não somado): (1+i1)(1+i2)...-1. Somar
    # dá quase o mesmo com inflação baixa e erra feio quando ela sobe.
    try:
        meses = _buscar(
            f"{BASE.format(cod=433)}/ultimos/12?formato=json", "433|ultimos|12"
        )
        fator = 1.0
        for x in meses:
            fator *= 1 + float(x["valor"]) / 100
        print(
            f"{'ipca_12m':14} {round((fator - 1) * 100, 2):>10}  "
            f"{'% em 12 meses':14} até {meses[-1]['data']} (calculado da 433)"
        )
    except Exception as erro:
        print(f"{'ipca_12m':14} {'não deu':>10}  ({erro})")

    print("\nfonte: Banco Central (SGS), sem chave. Cache de 6h em .rtk/bacen-cache.json")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("resumo", help="uma linha por índice, com a data de cada um")
    s = sub.add_parser("serie", help="histórico de uma série")
    s.add_argument("nome", help="apelido (cdi_ano, ipca, dolar...) ou código SGS")
    s.add_argument("--ultimos", type=int, default=12)
    s.add_argument("--desde", help="AAAA-MM-DD")
    a = p.parse_args()
    if a.cmd == "resumo":
        resumo()
    else:
        serie(a.nome, a.ultimos, a.desde)


if __name__ == "__main__":
    main()
