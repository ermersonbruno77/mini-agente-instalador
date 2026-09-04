#!/usr/bin/env python3
"""Vigia o tamanho das fichas dos agentes.

Por que existe: a ficha de um agente e lida INTEIRA em toda invocacao dele. Ficha que so
cresce vira custo fixo em cada chamada, e o crescimento e invisivel porque acontece uma
linha por vez. Em 19/08/2026 a ficha do paulo-dev tinha chegado a 618 linhas e 5.949
palavras, duas vezes e meia a segunda maior, sem ninguem ter percebido.

Ordem dele no mesmo dia: conferir a cada dois dias, "pra gente nao queimar tanto token".

Nao apaga nada e nao edita nada: mede, compara com a ultima medicao e avisa.
"""
import json
import os
import subprocess
from pathlib import Path

AGENTES = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/.claude/agents")
ESTADO = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/memory/fichas-agentes-estado.json")
INJECT = "/opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh"

# Acima disto a ficha ja pesa em toda chamada. O paulo-dev, depois da separacao de
# 19/08/2026, ficou em 4.771; o teto e folgado de proposito para avisar, nao para irritar.
TETO_PALAVRAS = 5000
# Crescimento entre duas medicoes que merece um olhar, mesmo sem estourar o teto.
CRESCIMENTO = 600


def medir():
    atual = {}
    for f in sorted(AGENTES.glob("*.md")):
        texto = f.read_text(errors="replace")
        atual[f.stem] = {"linhas": texto.count("\n") + 1, "palavras": len(texto.split())}
    return atual


def main():
    atual = medir()
    antes = json.loads(ESTADO.read_text()) if ESTADO.exists() else {}

    alertas = []
    for nome, m in atual.items():
        if m["palavras"] > TETO_PALAVRAS:
            alertas.append(f"{nome} esta com {m['palavras']} palavras, acima do teto de {TETO_PALAVRAS}")
        anterior = (antes.get(nome) or {}).get("palavras")
        if anterior and m["palavras"] - anterior >= CRESCIMENTO:
            alertas.append(f"{nome} cresceu {m['palavras'] - anterior} palavras desde a ultima medicao")

    ESTADO.write_text(json.dumps(atual, indent=1, ensure_ascii=False))

    if alertas and os.path.exists(INJECT):
        maiores = sorted(atual.items(), key=lambda x: -x[1]["palavras"])[:3]
        resumo = " · ".join(f"{n} {d['palavras']}" for n, d in maiores)
        subprocess.run([INJECT, "[monitor] FICHA DE AGENTE PESADA: " + "; ".join(alertas)
                        + f". Maiores hoje: {resumo}. Separar regra de comportamento (fica na ficha) "
                          "de conhecimento de caso (vai para arquivo lido sob demanda), sem apagar nada."])
    print(json.dumps({"alertas": alertas, "medicao": atual}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
