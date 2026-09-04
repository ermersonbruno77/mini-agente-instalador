#!/usr/bin/env python3
"""Compara o painel de agentes com o que está REALMENTE rodando, e me cobra a diferença.

Criado em 16/08/2026, ordem dele: *"no painel tá todo mundo parado! Esse painel
precisa ser em tempo real sempre"*.

O problema não era o painel, era eu. O painel lê `agente_atividade`, e essa
tabela só tem o que EU registro à mão, antes e depois de cada delegação. Duas
falhas no mesmo dia:

  - a shannon-seguranca apareceu 10h30 "trabalhando" numa coisa entregue às
    07h50, porque eu não fechei o registro;
  - a clara-contabil ficou rodando SEM registro nenhum, e o painel mostrou
    todo mundo parado enquanto ela trabalhava.

Prometer disciplina de novo não resolve: eu já prometi de manhã e falhei à
tarde. Então isto aqui não depende da minha memória.

COMO FUNCIONA: o harness escreve um arquivo por subagente vivo em
`/tmp/claude-*/tasks/<id>.output` e continua escrevendo enquanto ele trabalha.
Arquivo tocado nos últimos minutos = agente vivo. Comparo essa contagem com o
que a tabela diz e injeto quando as duas discordam.

Não conserta o registro sozinho de propósito: quem sabe QUAL agente é e o que
ele está fazendo sou eu, e um registro inventado por script seria pior que um
registro faltando — o painel voltaria a mentir, só que com mais confiança.
"""
import json
import re
import subprocess
import time
from pathlib import Path

import psycopg2

DSN = "postgresql://{{AGENTE_NAME_LOWERCASE}}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory"
INJECT = "/opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh"
RAIZ = Path("/tmp/claude-0")
ESTADO = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/.rtk/painel-agentes-ultimo.json")
# COMO SEI QUEM ESTÁ VIVO, e este arquivo errou TRÊS vezes antes de acertar:
#   1. mtime recente com 4 min  -> agente esperando consulta longa no Oracle fica
#      10 min sem escrever e foi dado como morto;
#   2. abri para 15 min         -> agente que ACABOU de terminar seguia contando
#      como vivo por 15 minutos;
#   3. exigi duas rodadas       -> só atrasou o alarme falso em 5 minutos, porque
#      a condição errada persistia.
# O que funciona é TAMANHO: arquivo que CRESCEU entre duas medições tem alguém
# escrevendo nele; arquivo parado no mesmo tamanho terminou, por mais recente que
# seja o mtime. O agente recém-nascido ainda não cresceu, então a primeira
# medição dele vale pelo mtime curto.
NASCENDO_S = 120


def medir() -> dict:
    """Tamanho do arquivo de cada subagente. Valor negativo = nasceu agora."""
    agora = {}
    for p in RAIZ.glob("*/*/tasks/*.output"):
        # Só id de subagente (a...), não de comando em background (b...).
        if not re.match(r"^a[0-9a-f]{6,}$", p.stem):
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        novo = time.time() - st.st_mtime < NASCENDO_S
        agora[p.stem] = -st.st_size if novo else st.st_size
    return agora


def vivos(agora: dict, antes: dict) -> list:
    lista = []
    for nome, tam in agora.items():
        if tam < 0:
            lista.append(nome)
        elif nome in antes and abs(antes[nome]) != tam:
            lista.append(nome)
    return lista


def main() -> None:
    """Regras DIFERENTES para os dois sentidos, porque os dois erros não custam
    o mesmo. Iteração 5, e a razão está aqui:

    - "agente sem registro" é o que ELE reclamou, e um aviso errado desses me faz
      registrar coisa que não existe. Exijo prova forte: o arquivo CRESCEU desde a
      última medição E foi tocado agora há pouco. Agente que terminou entre duas
      medições cresceu, mas não está fresco, e para de contar.
    - "registro sem fechar" é higiene minha e ninguém se machuca se demorar 30
      minutos para avisar. Exijo que o registro esteja aberto há mais de 30 min,
      o que elimina o intervalo em que o agente acabou e eu ainda não fechei.
    """
    agora = medir()
    try:
        antes = json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        antes = {}
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(agora), encoding="utf-8")
    if not antes:
        return

    # `frescos | (cresceram & frescos)` era redundante: dava o mesmo que `frescos`.
    # Escrevendo de verdade = cresceu desde a última medição E foi tocado agora.
    frescos = {n for n, tam in agora.items() if tam < 0}
    cresceram = {n for n, tam in agora.items()
                 if n in antes and abs(antes[n]) != abs(tam)}
    escrevendo = cresceram & frescos

    with psycopg2.connect(DSN) as con, con.cursor() as cur:
        cur.execute("SELECT count(*) FROM agente_atividade WHERE status='rodando'")
        no_painel = cur.fetchone()[0]
        # 17/08/2026: "aberto há mais de 30 min" sozinho acusa tarefa LONGA como
        # se fosse registro esquecido. Aconteceu com a #565, que estava rodando
        # de verdade, e o alerta mandava fechar com `fim ok` — ou seja, mandava
        # registrar entrega que não existia. Agora um PASSO recente conta como
        # sinal de vida: quem escreve no painel não está esquecido, está longo.
        #
        # MEDIDO EM 20/08/2026, e a leitura acima está OTIMISTA: este `passo` é
        # quase decoração. A tabela `agente_atividade_passo` tem 15 linhas na
        # vida inteira e 1 no último dia, porque a sessão principal registra
        # `inicio` e `fim` e praticamente nunca `passo`. Quem de fato evita o
        # alarme falso é o `and not escrevendo` lá embaixo: arquivo tocado agora
        # prova agente vivo sem depender de ninguém lembrar de escrever passo.
        # No dia 20/08 quatro registros passaram de 30 min (#633 34min, #642 36,
        # #652 35, #661 44) e só o #661 gerou alarme, que era verdadeiro: o
        # agente tinha morrido com erro 529 da API. Zero alarme falso.
        # Buraco que sobra, para quem mexer aqui saber: tarefa longa que fica
        # PENSANDO mais de 30 min sem tocar arquivo ainda dispara alarme falso.
        # Se for consertar, conserte por aí, não pelo passo.
        cur.execute("""SELECT count(*) FROM agente_atividade a
                        WHERE a.status='rodando'
                          AND a.iniciado_em < now() - interval '30 minutes'
                          AND NOT EXISTS (
                                SELECT 1 FROM agente_atividade_passo p
                                 WHERE p.atividade_id = a.id
                                   AND p.criado_em > now() - interval '30 minutes')""")
        velhos = cur.fetchone()[0]

    # O agente que ACABOU de entregar ainda escreve a última linha e fica fresco
    # por um instante. Para o sentido "agente sem registro" eu exijo que a
    # divergência apareça em DUAS rodadas seguidas: sobrevive a registro
    # esquecido de verdade e morre no fim de tarefa. Iteração 6, e a última.
    faltando = len(escrevendo) - no_painel
    repetiu = antes.get("__faltando__") == faltando
    agora["__faltando__"] = faltando
    ESTADO.write_text(json.dumps(agora), encoding="utf-8")

    if faltando > 0 and repetiu:
        subprocess.run([INJECT,
            f"[sistema] PAINEL DESENCONTRADO: {len(escrevendo)} subagente(s) escrevendo agora e só "
            f"{no_painel} registrado(s). Ele usa esse painel para saber o que está acontecendo. "
            f"Registre com `agente_log.py inicio <agente> \"<tarefa>\"`."], check=False)
        return

    if velhos and not escrevendo:
        subprocess.run([INJECT,
            f"[sistema] PAINEL DESENCONTRADO: {velhos} registro(s) aberto(s) há mais de 30 min sem "
            f"ninguém escrevendo. É registro sem fechar, do jeito que a shannon-seguranca apareceu "
            f"10h30 numa tarefa entregue. Feche com "
            f"`agente_log.py fim <id> ok \"<resultado>\" --tokens <N>`."], check=False)


if __name__ == "__main__":
    main()
