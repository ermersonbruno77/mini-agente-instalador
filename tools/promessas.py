#!/usr/bin/env python3
"""Registro de promessas da {{AGENTE_NAME}}.

Existe por causa de 07/08/2026. Às 00h51 eu descrevi pro Chefe a ficha da
pessoa virando tela com endereço próprio, nunca despachei, e ele descobriu
sozinho às 02h20 usando o sistema. A frase dele foi "PARA DE DEIXAR AS COISAS
PASSAR. RAFAEL TA SERVINDO DE NADA NE?", e ele estava certo nas duas partes.

O Rafael não servia porque ele só lê arquivo, e entrega não deixa rastro em
arquivo: o código muda, o banco muda, o site sobe, e nenhum `.md` fica sabendo.
Então ele só conseguia listar "pendente" no chute, e duas vezes em dois dias
listou como pendente coisa que já estava entregue.

Este arquivo resolve os dois lados:

  - a promessa entra numa TABELA no momento em que eu prometo, não depois;
  - o sweep escreve `memory/promessas.md`, que é um arquivo que o Rafael
    CONSEGUE ler, com a verdade do banco dentro.

Uso:

    promessas.py add "texto" --prazo 2h --dono paulo-dev --evidencia "rota /pessoa/[id]"
    promessas.py despachar <id> --agent-id abc123
    promessas.py entregar <id> --nota "no ar, conferido logado"
    promessas.py cancelar <id> --nota "o Chefe mudou de ideia"
    promessas.py lista
    promessas.py sweep          # cron: cobra o que venceu e reescreve o .md
    promessas.py digest-semanal # cron de sexta: bloco do que espera decisão dele

FECHAMENTO SEMANAL EM BLOCO (26/08/2026)
----------------------------------------
O sweep de hora em hora resolve um problema e cria outro. Ele NÃO cobra item
`bloqueada`, de propósito (ver o comentário dentro de `cmd_sweep`, 07/08/2026),
porque item travado esperando decisão do Chefe não é item que eu deixei parado.
A consequência é que ele fica no arquivo do Rafael e nunca me empurra: eu só
lembro dele se resolver ir olhar. Em 26/08 já eram 161 itens bloqueados.

O `digest-semanal` é o empurrão que faltava: toda sexta ele monta UM bloco com
os candidatos organizados por dono, tema e idade, escreve o arquivo e injeta uma
mensagem só.

O que ele NÃO faz, e é o mais importante: ele não decide o que "já foi decidido
implicitamente", o que "virou obsoleto" e o que "eu posso fechar sozinha". Essa
separação em três baldes é julgamento da {{AGENTE_NAME}}, feito na hora de processar a
injeção, item por item. Script que fecha promessa por idade transforma "o Chefe
não respondeu" em "não precisava mais", que é exatamente o esquecimento que este
arquivo inteiro existe para impedir. Aqui ele só ORGANIZA os candidatos.
"""

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import psycopg2

RAIZ = "/opt/{{AGENTE_NAME_LOWERCASE}}"
ARQUIVO_RAFAEL = f"{RAIZ}/memory/promessas.md"
INJECT = f"{RAIZ}/tools/inject.sh"
BRT = timezone(timedelta(hours=-3))

# Quantos dias uma promessa `aberta`/`despachada` precisa estar vencida para
# entrar TAMBÉM no bloco de sexta. Três dias é o critério, e a razão é medível:
# o sweep roda de hora em hora, então um item vencido há 3 dias já foi cobrado
# umas 72 vezes sem virar entrega. Cobrança que não funcionou 72 vezes não vai
# funcionar na 73ª; ela precisa de decisão, não de mais um lembrete. Menos que
# isso encheria o bloco de trabalho que está andando normalmente.
DIAS_ARRASTANDO = 3


def conectar():
    """Escrita exige DATABASE_URL. Subagente não chega aqui: ele usa
    {{AGENTE_NAME_UPPER}}_RO_URL e o Postgres recusa o INSERT, que é a trava boa."""
    url = None
    with open(f"{RAIZ}/.env") as f:
        for linha in f:
            if linha.startswith("DATABASE_URL="):
                url = linha.split("=", 1)[1].strip()
    if not url:
        sys.exit("DATABASE_URL não está no .env")
    return psycopg2.connect(url)


def prazo_para_data(texto):
    """Aceita '2h', '30m', '3d' ou uma data ISO. Sem prazo o item nunca vence,
    e item que nunca vence é exatamente o que já me mordeu."""
    if not texto:
        return None
    m = re.fullmatch(r"(\d+)([hmd])", texto.strip())
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[u]
        return datetime.now(timezone.utc) + delta
    return datetime.fromisoformat(texto)


def brt(dt):
    return dt.astimezone(BRT).strftime("%d/%m %H:%M") if dt else "sem prazo"


# Palavras que aparecem em quase toda promessa e por isso não distinguem uma
# da outra. Sem esta lista, "o Chefe" e "na tela" casariam tudo com tudo.
_RUIDO = {
    "chefe", "dele", "para", "pra", "que", "com", "sem", "por", "uma", "dos", "das",
    "nao", "não", "esta", "está", "isso", "mais", "meu", "minha", "ele", "ela", "tem",
    "ser", "vai", "ate", "até", "quando", "depois", "antes", "sobre", "cada", "onde",
    "perguntar", "pergunta", "decidir", "decisao", "decisão", "pedido", "aberta",
}


def avisar_parecidas(cursor, texto, limite=0.34):
    """Avisa quando já existe promessa viva sobre o mesmo assunto.

    Criada em 11/08/2026 porque eu dupliquei duas vezes no mesmo dia. A #100 e a
    #178 eram a mesma pergunta (o FAP real da TMB) com números DIFERENTES: a
    velha ainda carregava uma estimativa que eu já tinha corrigido, então o
    Chefe seria cobrado duas vezes e uma das cobranças estava errada. Horas
    depois registrei a #229 e a #230 sem ver que a #193 já dizia as duas coisas.

    Só avisa, nunca bloqueia: promessa parecida de verdade existe (a mesma tela
    volta com defeito novo), e ferramenta que me impede de registrar empurra o
    registro pra fora do sistema, que é o problema que ela deveria resolver."""
    palavras = {p for p in re.findall(r"[a-zà-ú0-9]{3,}", (texto or "").lower())
                if p not in _RUIDO}
    if len(palavras) < 3:
        return
    cursor.execute(
        "SELECT id, status, texto FROM promessas "
        "WHERE status IN ('aberta', 'bloqueada', 'despachada')"
    )
    parecidas = []
    for pid, status, outro in cursor.fetchall():
        dela = {p for p in re.findall(r"[a-zà-ú0-9]{3,}", (outro or "").lower())
                if p not in _RUIDO}
        if not dela:
            continue
        # Jaccard: comum / total. Mede sobreposição sem premiar texto longo.
        score = len(palavras & dela) / len(palavras | dela)
        if score >= limite:
            parecidas.append((score, pid, status, outro))
    for score, pid, status, outro in sorted(parecidas, reverse=True)[:3]:
        print(f"  ATENCAO: #{pid} ({status}) parece a mesma coisa "
              f"[{int(score * 100)}% de sobreposicao]: {outro[:90]}", file=sys.stderr)
    if parecidas:
        print("  -> se for a mesma, cancele a velha em vez de deixar as duas "
              "cobrando ele com numeros diferentes.", file=sys.stderr)


def cmd_add(a):
    # `--despachada` existe porque eu erro o segundo passo. Em 07/08/2026 eu
    # criei a #105 e a #108, chamei a Juliana no mesmo minuto, e esqueci de
    # rodar `despachar` nas duas. O Rafael me apontou lendo "aberta" com o
    # trabalho já rodando. Duas linhas de comando pra um único ato viram uma
    # linha esquecida; agora o ato é um comando só.
    status = "despachada" if getattr(a, "despachada", False) else "aberta"
    with conectar() as conn, conn.cursor() as c:
        avisar_parecidas(c, a.texto)
        c.execute(
            "INSERT INTO promessas (texto, dono, evidencia, prazo, msg_id, status) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (a.texto, a.dono, a.evidencia, prazo_para_data(a.prazo), a.msg_id, status),
        )
        conn.commit()
        print(f"promessa #{c.fetchone()[0]} registrada como {status}, "
              f"vence {brt(prazo_para_data(a.prazo))}")


def cmd_estado(a, status):
    # Trava criada 40 minutos depois do resto, porque eu fechei a promessa #3
    # como entregue tendo só o código pronto, quando a prova que eu mesma
    # tinha escrito era "a tela sem a chave técnica". Ferramenta contra o meu
    # esquecimento não serve se ela aceita eu me enganar no último passo.
    if status == "entregue" and not a.nota:
        sys.exit(
            "entregar exige --nota com a PROVA, não com a intenção.\n"
            "Vale: tela conferida logada, rota respondendo, linha no banco.\n"
            'Não vale: "código pronto", "subiu", "200", "testes verdes".'
        )
    # Mesma trava para bloquear: o motivo é a única coisa que distingue
    # "travado esperando ele" de "eu desisti e escondi da cobrança".
    if status == "bloqueada" and not a.nota:
        sys.exit(
            "bloquear exige --nota dizendo EM QUE está travada.\n"
            'Vale: "espera a resposta dele na #77", "precisa de perfil total".\n'
            'Não vale: "depois", "complicado", "sem tempo".'
        )
    # `--prazo` no despachar existe porque o prazo antigo continuava valendo
    # depois do despacho, e o sweep cobrava de hora em hora um item que tinha
    # comecado a ser feito naquele minuto. Aconteceu quatro vezes em 07/08.
    # O relogio que importa e o do trabalho em curso, nao o da hora em que eu
    # registrei a promessa. Continua explicito de proposito: quem despacha diz
    # em quanto tempo espera, em vez de a ferramenta empurrar sozinha.
    novo_prazo = prazo_para_data(getattr(a, "prazo", None))
    with conectar() as conn, conn.cursor() as c:
        fechado = "now()" if status in ("entregue", "cancelada") else "NULL"
        c.execute(
            f"UPDATE promessas SET status=%s, fechado_em={fechado}, "
            "nota=COALESCE(%s, nota), agent_id=COALESCE(%s, agent_id), "
            "prazo=COALESCE(%s, prazo) WHERE id=%s",
            (status, a.nota, getattr(a, "agent_id", None), novo_prazo, a.id),
        )
        conn.commit()
        print(f"promessa #{a.id} -> {status}" if c.rowcount else f"promessa #{a.id} não existe")


def abertas(conn):
    with conn.cursor() as c:
        c.execute(
            "SELECT id, criado_em, texto, dono, evidencia, prazo, status, nota "
            "FROM promessas WHERE status IN ('aberta','despachada','bloqueada') "
            "ORDER BY prazo NULLS LAST, id"
        )
        return c.fetchall()


def cmd_lista(_):
    with conectar() as c:
        linhas = abertas(c)
        if not linhas:
            print("nada em aberto")
            return
        agora = datetime.now(timezone.utc)
        for i, criado, texto, dono, _ev, prazo, status, _n in linhas:
            venceu = "VENCIDA" if prazo and prazo < agora else ""
            print(f"#{i:<4} {status:<11} {dono:<16} vence {brt(prazo):<12} {venceu:<8} {texto[:60]}")


def escrever_para_rafael(linhas):
    """O Rafael lê arquivo, não lê banco. Este é o arquivo dele, e ele é
    gerado, nunca escrito à mão: número escrito à mão apodrece."""
    agora = datetime.now(timezone.utc)
    out = [
        "# Promessas em aberto",
        "",
        "Gerado por `tools/promessas.py sweep`. **Não editar à mão**, o próximo",
        "sweep sobrescreve. Quem fecha item é a {{AGENTE_NAME}}, pelo comando, não pelo arquivo.",
        "",
        f"Atualizado em {agora.astimezone(BRT).strftime('%d/%m/%Y %H:%M')} (Brasília).",
        "",
    ]
    if not linhas:
        out += ["Nada em aberto.", ""]
    else:
        out += ["| # | prometida | vence | dono | estado | o que é | prova esperada | por que está travada |",
                "|---|---|---|---|---|---|---|---|"]
        for i, criado, texto, dono, ev, prazo, status, nota in linhas:
            venceu = " **VENCIDA**" if prazo and prazo < agora else ""
            # A coluna do motivo existe por causa de 07/08/2026: o Rafael auditou
            # 14 itens bloqueados e classificou 7 como "não deveria estar
            # bloqueada", porque a nota com o motivo estava no banco e ELE NÃO
            # LIA. Auditor que não enxerga a justificativa não audita bloqueio
            # nenhum, só adivinha. Só aparece em `bloqueada` de propósito: nas
            # outras a nota é histórico de trabalho e ia poluir a tabela dele.
            motivo = (nota or "").replace("|", "/").replace("\n", " ") if status == "bloqueada" else ""
            if status == "bloqueada" and not motivo:
                motivo = "**SEM MOTIVO ESCRITO — cobrar a {{AGENTE_NAME}}**"
            out.append(
                f"| {i} | {brt(criado)} | {brt(prazo)}{venceu} | {dono} | {status} | "
                f"{texto} | {ev or 'não definida'} | {motivo[:400]} |"
            )
        out += ["", "**Prova esperada** é o que faz o item poder ser fechado: uma rota que",
                "responde, um campo na tela, uma linha no banco. Item sem prova definida",
                "não pode ser dado como entregue por ninguém, nem por mim.", ""]
    with open(ARQUIVO_RAFAEL, "w") as f:
        f.write("\n".join(out))


def cmd_sweep(_):
    with conectar() as c:
        linhas = abertas(c)
        escrever_para_rafael(linhas)
        agora = datetime.now(timezone.utc)
        # "bloqueada" continua APARECENDO na lista e no arquivo do Rafael, de
        # propósito: nada sai do radar. O que ela não faz é gerar cobrança de
        # hora em hora, porque item travado esperando resposta do Chefe não é
        # item que eu deixei parado. Criado em 07/08/2026, depois de a mesma
        # dupla (#13 e #17) ser cobrada três vezes no mesmo dia estando uma em
        # execução e a outra dependendo de uma decisão dele.
        vencidas = [l for l in linhas if l[5] and l[5] < agora and l[6] != "bloqueada"]
        # Só grita pelo que venceu. Cobrança de item no prazo vira ruído, e
        # aviso que vira ruído deixa de ser lido, que é como eu cheguei aqui.
        if not vencidas:
            print(f"sweep ok, {len(linhas)} em aberto, nenhuma vencida")
            return
        resumo = "; ".join(f"#{l[0]} {l[2][:50]} (dono {l[3]})" for l in vencidas[:5])
        # 07/08/2026: cada disparo daqui virou reflexo de acionar um subagente
        # inteiro (Rafael, sem cache, recarrega tudo do zero) mesmo pra 1 item
        # vencido isolado. 12 execucoes num dia so por causa disso. A ordem
        # agora e explicita: pouco item com prova facil, confere ela mesma.
        orientacao = (
            "Confira voce mesma, na sessao principal, sem acionar subagente."
            if len(vencidas) < 3 else
            "Volume alto, delegar pro rafael-projetos investigar em bloco faz sentido aqui."
        )
        msg = (
            f"[sistema] PROMESSA VENCIDA: {len(vencidas)} item(ns) passaram do prazo "
            f"sem entrega confirmada. {resumo}. {orientacao} Feche com "
            f"tools/promessas.py entregar, e se ainda nao despachou, despache agora."
        )
        subprocess.run([INJECT, msg], check=False)
        print(f"sweep: {len(vencidas)} vencida(s), cobrança injetada")


def conectar_leitura():
    """O digest só lê. Usa a credencial que o Postgres impede de escrever
    quando ela existe, em vez de depender de disciplina."""
    try:
        for linha in open(f"{RAIZ}/.env"):
            if linha.startswith("{{AGENTE_NAME_UPPER}}_RO_URL="):
                return psycopg2.connect(linha.split("=", 1)[1].strip())
    except OSError:
        pass
    return conectar()


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


# Gramática, não assunto. Esta lista PODE ser fixa justamente porque palavra
# funcional não envelhece: "como" e "qual" vão continuar sendo conectivo no ano
# que vem, enquanto uma lista de assuntos ("vendas, financeiro, operacao") estaria
# velha em dois meses. Fica separada do _RUIDO de propósito: mexer no _RUIDO
# mudaria também o detector de duplicata do `add`, que já funciona e não é
# assunto meu. Primeira rodada de teste (26/08) sem ela devolveu como "temas"
# as palavras "como", "quem" e "qual", que não agrupam nada.
_RUIDO_TEMA = _RUIDO | {
    "como", "quem", "qual", "quais", "esse", "essa", "esses", "essas", "isso",
    "aqui", "ainda", "mesmo", "mesma", "todo", "toda", "todos", "todas",
    "outro", "outra", "outros", "outras", "fazer", "feito", "feita", "ficar",
    "ficou", "existe", "existem", "tambem", "porque", "seja", "sobre", "entre",
    "apos", "cada", "muito", "pouco", "tudo", "nada", "agora", "hoje", "ontem",
    "amanha", "precisa", "preciso", "coisa", "item", "itens", "novo", "nova",
    "estao", "estava", "eram", "sera", "seria", "deve", "devia", "pode",
    "podia", "poder", "quero", "queria", "vamos", "sendo", "foram", "havia",
    "usar", "usa", "dizer", "disse", "falar", "olhar", "ver", "vem", "vai",
    "entao", "porem", "assim", "onde", "antes", "depois", "durante", "nunca",
    "sempre", "so", "ja", "tem", "ter", "tinha", "sem", "com", "por", "num",
    "numa", "nos", "nas", "dos", "das", "pelo", "pela", "aos", "que", "qua",
}


def _tokens(texto):
    """Palavras que distinguem um item do outro. Parte do mesmo _RUIDO do
    detector de duplicata (dois lugares medindo 'assunto' com réguas diferentes
    dariam respostas diferentes para a mesma pergunta) e soma só gramática."""
    return {p for p in re.findall(r"[a-z0-9]{4,}", _sem_acento(texto or "").lower())
            if p not in _RUIDO_TEMA and not p.isdigit()}


def agrupar_por_tema(itens):
    """Devolve {tema: [item, ...]}.

    O tema sai do próprio texto dos candidatos, NÃO de uma lista de assuntos
    escrita no código. Lista de assunto escrita à mão apodrece igual a número
    escrito à mão: hoje seria "vendas, financeiro, operacao", em dois meses o trabalho
    é outro e o agrupador continuaria jurando que o mundo é o de agosto.

    Como funciona: conta em quantos itens cada palavra aparece; o tema de um
    item é a palavra mais frequente entre as dele, ignorando palavra que aparece
    em mais de 40% do bloco (essa não separa nada, só descreve o mês) e palavra
    que aparece uma vez só (essa não agrupa ninguém). Sobrou nada, o item cai em
    "avulsos", que é resposta honesta e não um balde inventado.

    Isto é sugestão de leitura, não classificação oficial. Quem decide o que o
    item é sou eu, lendo."""
    freq = Counter()
    toks = {}
    for it in itens:
        toks[it["id"]] = _tokens(it["texto"])
        freq.update(toks[it["id"]])
    teto = max(2, int(0.4 * len(itens)))
    grupos = defaultdict(list)
    for it in itens:
        candidatas = [(freq[t], t) for t in toks[it["id"]] if 2 <= freq[t] <= teto]
        # Desempate alfabético de propósito: o mesmo bloco tem que gerar o mesmo
        # agrupamento em duas execuções seguidas, senão eu comparo semanas
        # diferentes de coisas que só mudaram de nome.
        it["tema"] = max(sorted(candidatas), default=(0, "avulsos"))[1]
        grupos[it["tema"]].append(it)
    # Grupo de um item só não é grupo, é ruído de índice.
    soltos = []
    for tema in [t for t, v in grupos.items() if len(v) == 1 and t != "avulsos"]:
        soltos += grupos.pop(tema)
    for it in soltos:
        it["tema"] = "avulsos"
    if soltos:
        grupos["avulsos"] += soltos
    return grupos


def candidatos_digest(conn, dias_arrastando=DIAS_ARRASTANDO):
    """Tudo que está bloqueado, mais o que está vencido há mais de
    `dias_arrastando`. Nunca muda o estado de nada."""
    agora = datetime.now(timezone.utc)
    with conn.cursor() as c:
        c.execute(
            "SELECT id, criado_em, texto, dono, evidencia, prazo, status, nota "
            "FROM promessas "
            "WHERE status = 'bloqueada' "
            "   OR (status IN ('aberta','despachada') AND prazo IS NOT NULL "
            "       AND prazo < now() - %s::interval) "
            "ORDER BY criado_em",
            (f"{dias_arrastando} days",),
        )
        itens = []
        for i, criado, texto, dono, ev, prazo, status, nota in c.fetchall():
            itens.append({
                "id": i, "criado": criado, "texto": texto, "dono": dono,
                "evidencia": ev, "prazo": prazo, "status": status,
                "nota": nota, "idade": (agora - criado).days,
            })
    return itens


def escrever_digest(itens, caminho, dias_arrastando=DIAS_ARRASTANDO):
    agora = datetime.now(timezone.utc)
    bloqueadas = [i for i in itens if i["status"] == "bloqueada"]
    arrastando = [i for i in itens if i["status"] != "bloqueada"]
    out = [
        f"# Fechamento semanal de promessas, {agora.astimezone(BRT):%d/%m/%Y}",
        "",
        "Gerado por `tools/promessas.py digest-semanal`. **Não editar à mão.**",
        "",
        f"- Esperando decisão do Chefe (`bloqueada`): **{len(bloqueadas)}**",
        f"- Vencidas há mais de {dias_arrastando} dias e ainda andando: **{len(arrastando)}**",
        "",
        "## Como processar",
        "",
        "Três baldes, item por item, e quem separa sou eu, não o script:",
        "",
        "1. **Posso fechar sozinha** — já foi feito, ou a decisão dele já veio em",
        "   outra conversa e eu não fechei o registro. Fecha com `entregar` (com a",
        "   prova) ou `cancelar` (com o motivo).",
        "2. **Precisa da palavra dele** — vira UMA pergunta no Telegram, agrupada por",
        "   tema, nunca 40 perguntas soltas.",
        "3. **Obsoleto** — o mundo mudou e o item perdeu sentido. `cancelar` dizendo",
        "   o que mudou. Silêncio dele nunca é o motivo: silêncio não é sim.",
        "",
    ]
    for titulo, lista in (("Esperando decisão dele", bloqueadas),
                          (f"Arrastando (vencidas há mais de {dias_arrastando} dias)",
                           arrastando)):
        out += [f"## {titulo} ({len(lista)})", ""]
        if not lista:
            out += ["Nada aqui.", ""]
            continue
        por_dono = defaultdict(list)
        for it in lista:
            por_dono[it["dono"]].append(it)
        for dono in sorted(por_dono, key=lambda d: -len(por_dono[d])):
            do_dono = por_dono[dono]
            out += [f"### dono: {dono} ({len(do_dono)})", ""]
            grupos = agrupar_por_tema(do_dono)
            for tema in sorted(grupos, key=lambda t: (t == "avulsos", -len(grupos[t]), t)):
                out += [f"**tema: {tema}** ({len(grupos[tema])})", "",
                        "| # | idade | prometida | prazo | o que é | por que está parada |",
                        "|---|---|---|---|---|---|"]
                for it in sorted(grupos[tema], key=lambda x: -x["idade"]):
                    motivo = (it["nota"] or "").replace("|", "/").replace("\n", " ")
                    if it["status"] == "bloqueada" and not motivo:
                        motivo = "**SEM MOTIVO ESCRITO**"
                    if it["status"] != "bloqueada":
                        motivo = f"({it['status']}) " + motivo
                    texto = it["texto"].replace("|", "/").replace("\n", " ")
                    out.append(
                        f"| {it['id']} | {it['idade']}d | {brt(it['criado'])} | "
                        f"{brt(it['prazo'])} | {texto[:220]} | {motivo[:220]} |"
                    )
                out.append("")
    with open(caminho, "w") as f:
        f.write("\n".join(out))


def cmd_digest_semanal(a):
    # `is None`, nunca `or`: com `or`, passar 0 caía no padrão 3 calado e as
    # duas execuções davam a MESMA saída, o que fingia que o ramo tinha sido
    # exercido. Peguei isso rodando os dois valores, não lendo o código.
    dias = getattr(a, "dias_arrastando", None)
    dias = DIAS_ARRASTANDO if dias is None else dias
    with conectar_leitura() as conn:
        itens = candidatos_digest(conn, dias)
    hoje = datetime.now(timezone.utc).astimezone(BRT)
    caminho = f"{RAIZ}/memory/digest-semanal-{hoje:%Y-%m-%d}.md"
    escrever_digest(itens, caminho, dias)

    bloqueadas = [i for i in itens if i["status"] == "bloqueada"]
    arrastando = [i for i in itens if i["status"] != "bloqueada"]
    grupos = agrupar_por_tema(list(itens))
    maiores = sorted(((len(v), t) for t, v in grupos.items() if t != "avulsos"),
                     reverse=True)[:3]
    velhas = sorted(itens, key=lambda x: -x["idade"])[:3]

    # O relatório de custo mora no dono da tabela dele (agente_log.py). Se ele
    # sumir ou quebrar, o digest continua saindo com o bloco de custo faltando e
    # dizendo que faltou, em vez de morrer junto: quem consome dado de outro
    # traduz o que reconhece e degrada legível o resto.
    custo = ""
    try:
        sys.path.insert(0, f"{RAIZ}/tools")
        import agente_log
        r = agente_log.relatorio_custo_semanal(7)
        # Separador de milhar trocado no NÚMERO, nunca na frase inteira: o
        # primeiro teste rodou um .replace(",", ".") na string toda e o texto
        # saiu "219 delegacoes. 28.421.455 tokens.", com ponto no lugar da
        # vírgula da frase.
        def _n(v):
            return f"{v:,}".replace(",", ".")
        custo = (f" CUSTO DA SEMANA: {r['chamadas']} delegacoes, "
                 f"{_n(r['tokens'])} tokens, {r['retrabalho_execucoes']} marcada(s) "
                 f"como retrabalho ({_n(r['retrabalho_tokens'])} tokens, "
                 f"{str(r['pct_retrabalho']).replace('.', ',')}% do gasto; "
                 "ausencia de marca nao e ausencia de retrabalho); "
                 f"detalhe em {r['arquivo']}.")
    except Exception as e:  # noqa: BLE001
        custo = f" (o relatorio de custo nao rodou: {type(e).__name__}: {e})"

    msg = (
        f"[sistema] FECHAMENTO SEMANAL: {len(bloqueadas)} promessa(s) esperando "
        f"decisao do Chefe e {len(arrastando)} vencida(s) ha mais de "
        f"{dias} dias. Maiores temas: "
        + ("; ".join(f"{t} ({n})" for n, t in maiores) or "sem tema repetido")
        + ". Mais antigas: "
        + "; ".join(f"#{i['id']} ({i['idade']}d) {i['texto'][:40]}" for i in velhas)
        + f". Lista completa agrupada por dono e tema em {caminho}."
        " Processe em TRES baldes, item por item: (1) posso fechar sozinha,"
        " (2) precisa da palavra dele e vira UMA pergunta agrupada por tema,"
        " (3) obsoleto, cancelar dizendo o que mudou. O script nao decidiu nada"
        " disso, o julgamento e meu." + custo
    )
    if a.simular:
        print(msg)
    else:
        subprocess.run([INJECT, msg], check=False)
    print(f"digest: {len(bloqueadas)} bloqueada(s), {len(arrastando)} arrastando, "
          f"arquivo {caminho}"
          + (" (simulado, nada injetado)" if a.simular else ", injetado"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add")
    a.add_argument("texto")
    a.add_argument("--dono", default="{{AGENTE_NAME_LOWERCASE}}")
    a.add_argument("--evidencia")
    a.add_argument("--prazo")
    a.add_argument("--msg-id", dest="msg_id")
    a.add_argument("--despachada", action="store_true",
                   help="nasce despachada: use quando voce ja esta chamando o agente agora")
    a.set_defaults(fn=cmd_add)

    for nome, status in [("despachar", "despachada"), ("entregar", "entregue"),
                         ("cancelar", "cancelada"), ("bloquear", "bloqueada")]:
        s = sub.add_parser(nome)
        s.add_argument("id", type=int)
        s.add_argument("--nota")
        s.add_argument("--agent-id", dest="agent_id")
        s.add_argument("--prazo", help="reposiciona o prazo (ex: 2h). Use ao despachar: o relogio conta do inicio do trabalho")
        s.set_defaults(fn=lambda x, st=status: cmd_estado(x, st))

    sub.add_parser("lista").set_defaults(fn=cmd_lista)
    sub.add_parser("sweep").set_defaults(fn=cmd_sweep)

    d = sub.add_parser("digest-semanal")
    d.add_argument("--dias-arrastando", dest="dias_arrastando", type=int,
                   help=f"sobrepoe o padrao de {DIAS_ARRASTANDO} dias (use 0 para "
                        "conferir o ramo com pouco dado)")
    d.add_argument("--simular", action="store_true",
                   help="escreve o arquivo e IMPRIME a mensagem em vez de injetar")
    d.set_defaults(fn=cmd_digest_semanal)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
