#!/usr/bin/env python3
"""Registro de delegação a subagente.

Por que existe: em 03/08/2026 o Chefe abriu a página de agentes do painel e disse
"aqui nos agentes eu quero clicar no Paulo e ver que ele tá mudando uma página,
por exemplo". Essa informação não existia em lugar nenhum. Quando eu delegava, o
trabalho acontecia dentro da minha sessão e morria com ela, sem deixar rastro.

Agora toda delegação passa por aqui. A regra para mim: registrar ANTES de chamar
o subagente e encerrar assim que ele responder. Se eu esquecer de encerrar, a
tarefa fica "rodando" para sempre e o painel mostra isso, o que é melhor do que
apagar o rastro.

Uso:
    # ao delegar (imprime o id, que eu uso para encerrar)
    python3 tools/agente_log.py inicio paulo-dev "arrumar a pagina de caixa do painel"

    # ao receber o resultado
    python3 tools/agente_log.py fim <id> ok "reescrita em cards, 3 arquivos"
    python3 tools/agente_log.py fim <id> falha "nao consegui, VPN fora"

    # opcional: arquivos tocados, separados por virgula
    python3 tools/agente_log.py fim <id> ok "pronto" --arquivos web/app/caixa/page.tsx,web/lib/tipos.ts

    # passo intermediário, enquanto a tarefa ainda está rodando (dá vida ao
    # painel /agentes: é o texto que aparece no balão do bonequinho)
    python3 tools/agente_log.py passo <id> "conferindo o consolidado"

    # ver o que está rodando agora
    python3 tools/agente_log.py agora

    # marcar uma execução como RETRABALHO (26/08/2026, ver bloco abaixo)
    python3 tools/agente_log.py retrabalho <id> "eu tinha dito que o campo X existia"
    python3 tools/agente_log.py fim <id> ok "pronto" --tokens 85257 --retrabalho "escopo errado meu"

    # relatório semanal de custo (roda sozinho na sexta pelo cron do digest)
    python3 tools/agente_log.py custo-semanal [--dias 7] [--sem-arquivo]

CUSTO DE RETRABALHO — decisão de 26/08/2026
-------------------------------------------
O Chefe aprovou o artefato "Do Pedido ao Processo" e uma das mudanças era medir
quanto custa, em token, a rodada de subagente que só existiu porque a {{AGENTE_NAME}}
descreveu o escopo errado (o caso do dia: o Paulo descobriu no meio do trabalho
que um campo descrito como fato não existia, e refez do zero).

Não existia marcação de retrabalho no schema, e existiam duas saídas:
  (a) marcar na hora e somar só o marcado — honesto, mas depende de lembrar;
  (b) somar TODO token da semana sem separar nada — visível, mas não responde
      a pergunta que foi feita.

Aqui está implementado (c) = as duas juntas, com a cobertura declarada em voz
alta no relatório. O total da semana sai sempre, do banco, sem depender de
ninguém lembrar de nada; a marca de retrabalho é explícita e some do relatório
quando não existe, com a frase "ausência de marca não é ausência de
retrabalho" impressa no arquivo. Relatório que soma zero e não avisa que ninguém
marcou nada mente por omissão.

Onde a marca mora, e por que NÃO é coluna nova no Postgres: quem escreveu isto
foi um subagente, e subagente não faz DDL em tabela de produção (regra do
CLAUDE.md, "escrita no banco só pela sessão principal"). Então a marca vai para
`memory/retrabalho.tsv`, que é campo de verdade num arquivo próprio, e não um
prefixo enfiado no texto de `resultado` para depois ser caçado com LIKE. Se um
dia a coluna existir (`ALTER TABLE agente_atividade ADD COLUMN retrabalho text`),
o relatório passa a ler as duas fontes sozinho: ele testa a existência da coluna
em `information_schema` antes de consultar.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras

DSN = os.environ.get(
    "DATABASE_URL", "postgresql://{{AGENTE_NAME_LOWERCASE}}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory"
)
STATUS_FINAL = ("ok", "falha", "cancelado")

RAIZ = Path("/opt/{{AGENTE_NAME_LOWERCASE}}")
ARQ_RETRABALHO = RAIZ / "memory" / "retrabalho.tsv"
CAB_RETRABALHO = "marcado_em\tatividade_id\tmotivo\n"
BRT = timezone(timedelta(hours=-3))


def conectar():
    return psycopg2.connect(DSN)


def conectar_leitura():
    """Só-leitura quando ela existir. O relatório semanal não escreve nada no
    banco, então ele roda com a credencial que o Postgres impede de escrever,
    em vez de depender de disciplina. Cai no DSN normal se a RO não estiver no
    .env (ex.: máquina de teste)."""
    try:
        for linha in open(RAIZ / ".env"):
            if linha.startswith("{{AGENTE_NAME_UPPER}}_RO_URL="):
                return psycopg2.connect(linha.split("=", 1)[1].strip())
    except OSError:
        pass
    return psycopg2.connect(DSN)


def cmd_inicio(agente, tarefa, frente=None):
    """Abre uma atividade, ou devolve a que já está aberta se for a mesma.

    A janela de 3 minutos existe por causa de 14/08/2026: a Sofia abriu três
    registros para o MESMO trabalho em 13 segundos (ela por dentro, eu por
    fora), eu fechei só um, e os outros dois ficaram "rodando". Duas horas
    depois o Chefe mandou print do painel com o card dela marcado como "pode
    estar travada/esquecida há 2h11" — trabalho que já tinha terminado.

    O estrago é duplo e os dois lados enganam: o painel mostra agente travado
    que não está, e o consumo de token aparece somado duas ou três vezes,
    inflando quem mais trabalha no ranking de custo.

    Por que 3 minutos e não "nunca deixar repetir": o Paulo abre frentes
    diferentes de propósito e o painel mostra as duas mesas ocupadas, que é
    comportamento certo. Duplicata acidental nasce em segundos, frente de
    verdade nasce com minutos de diferença. Quem quiser mesmo uma segunda
    mesa imediata passa `--frente`, que é justamente o campo para isso.
    """
    with conectar() as con, con.cursor() as cur:
        if frente is None:
            cur.execute(
                "SELECT id, tarefa FROM agente_atividade"
                " WHERE agente = %s AND terminado_em IS NULL"
                "   AND iniciado_em > now() - interval '3 minutes'"
                " ORDER BY id DESC LIMIT 1",
                (agente,),
            )
            ja_aberta = cur.fetchone()
            if ja_aberta:
                sys.stderr.write(
                    f"ja existe atividade aberta #{ja_aberta[0]} para {agente}"
                    f" ha menos de 3 min ({ja_aberta[1][:40]}...); reaproveitando"
                    " em vez de abrir outra. Use --frente para uma segunda mesa.\n"
                )
                print(ja_aberta[0])
                return 0
        cur.execute(
            "INSERT INTO agente_atividade(agente, tarefa, sessao, frente)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (agente, tarefa, os.environ.get("{{AGENTE_NAME_UPPER}}_SESSAO"), frente),
        )
        print(cur.fetchone()[0])
    return 0


def cmd_fim(ident, status, resultado, arquivos=None, tokens=None):
    if status not in STATUS_FINAL:
        print(f"status inválido: {status}. use um de {', '.join(STATUS_FINAL)}")
        return 1
    with conectar() as con, con.cursor() as cur:
        cur.execute(
            """UPDATE agente_atividade
                  SET terminado_em = now(), status = %s, resultado = %s,
                      arquivos = COALESCE(%s, arquivos),
                      tokens = COALESCE(%s, tokens)
                WHERE id = %s AND terminado_em IS NULL
             RETURNING agente""",
            (status, resultado, arquivos, tokens, ident),
        )
        linha = cur.fetchone()
    if not linha:
        # Não invento sucesso: ou o id não existe, ou já estava encerrado.
        print(f"nada a encerrar no id {ident} (inexistente ou já fechado)")
        return 1
    print(f"encerrado: {linha[0]} #{ident} -> {status}")
    return 0


def cmd_passo(atividade_id, texto):
    with conectar() as con, con.cursor() as cur:
        # Só registra passo em atividade que existe e ainda está aberta — não
        # faz sentido reportar progresso de algo que já fechou, e um id
        # inventado não pode criar rastro de trabalho que não houve.
        cur.execute(
            "SELECT 1 FROM agente_atividade WHERE id = %s AND terminado_em IS NULL",
            (atividade_id,),
        )
        if not cur.fetchone():
            print(f"id {atividade_id} não existe ou já está encerrado; passo não gravado")
            return 1
        cur.execute(
            "INSERT INTO agente_atividade_passo(atividade_id, texto) VALUES (%s, %s) RETURNING id",
            (atividade_id, texto),
        )
        print(cur.fetchone()[0])
    return 0


def cmd_agora():
    with conectar() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(
            """SELECT id, agente, tarefa, iniciado_em,
                      round(extract(epoch from (now() - iniciado_em)) / 60) AS minutos
                 FROM agente_atividade
                WHERE terminado_em IS NULL
                ORDER BY iniciado_em"""
        )
        linhas = cur.fetchall()
    if not linhas:
        print("nenhum agente rodando")
        return 0
    for r in linhas:
        print(f"#{r['id']} {r['agente']}: {r['tarefa']} (há {int(r['minutos'])} min)")
    return 0


def desmarcar_retrabalho(atividade_id):
    """O caminho de volta. Marca errada que não sai infla o percentual da semana
    e não tem como ser contestada; toda ação que escreve nasce com o desfazer."""
    if not ARQ_RETRABALHO.exists():
        print("nenhuma marca registrada ainda")
        return 1
    linhas = ARQ_RETRABALHO.read_text().splitlines(keepends=True)
    cab = linhas[0] if linhas and linhas[0].startswith("marcado_em\t") else CAB_RETRABALHO
    corpo = [l for l in linhas[1:] if l.strip()]
    fica = [l for l in corpo if l.split("\t")[1:2] != [str(atividade_id)]]
    ARQ_RETRABALHO.write_text(cab + "".join(fica))
    if len(fica) == len(corpo):
        print(f"#{atividade_id} não estava marcado; nada mudou")
        return 1
    print(f"marca de retrabalho removida de #{atividade_id}")
    return 0


def marcar_retrabalho(atividade_id, motivo):
    """Marca UMA execução como retrabalho. Regravar o mesmo id substitui o
    motivo, não empilha duas linhas: a última leitura minha do que aconteceu é
    a que vale, e linha duplicada somaria o mesmo token duas vezes no relatório.

    Exige que a atividade exista (leitura). Id inventado não pode criar rastro
    de trabalho que não houve, mesmo padrão do `passo`."""
    motivo = (motivo or "").strip().replace("\t", " ").replace("\n", " ")
    if not motivo:
        print('retrabalho exige o motivo: o que EU tinha dito errado.\n'
              'Vale: "eu disse que o campo saldo_fgts existia e ele não existe".\n'
              'Não vale: "erro", "refazer", "escopo".')
        return 1
    with conectar_leitura() as con, con.cursor() as cur:
        cur.execute(
            "SELECT agente, tarefa FROM agente_atividade WHERE id = %s", (atividade_id,)
        )
        linha = cur.fetchone()
    if not linha:
        print(f"atividade {atividade_id} não existe; nada marcado")
        return 1
    ARQ_RETRABALHO.parent.mkdir(parents=True, exist_ok=True)
    if ARQ_RETRABALHO.exists():
        antigas = ARQ_RETRABALHO.read_text().splitlines(keepends=True)
    else:
        antigas = [CAB_RETRABALHO]
    if not antigas or not antigas[0].startswith("marcado_em\t"):
        antigas.insert(0, CAB_RETRABALHO)
    corpo = [l for l in antigas[1:]
             if l.strip() and l.split("\t")[1:2] != [str(atividade_id)]]
    corpo.append(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}\t"
                 f"{atividade_id}\t{motivo}\n")
    ARQ_RETRABALHO.write_text(antigas[0] + "".join(corpo))
    print(f"retrabalho marcado: #{atividade_id} {linha[0]} ({linha[1][:50]})")
    return 0


def _ids_retrabalho():
    """Lê as marcas do arquivo. Devolve {id: motivo}."""
    if not ARQ_RETRABALHO.exists():
        return {}
    marcas = {}
    for linha in ARQ_RETRABALHO.read_text().splitlines()[1:]:
        partes = linha.split("\t")
        if len(partes) >= 3 and partes[1].strip().isdigit():
            marcas[int(partes[1])] = partes[2].strip()
    return marcas


def relatorio_custo_semanal(dias=7, escrever=True):
    """Custo do time na janela, por agente e por dia, mais o recorte de
    retrabalho MARCADO. Devolve um dicionário e (opcionalmente) escreve
    `memory/custo-semanal-AAAA-MM-DD.md`.

    Só lê. Criado em 26/08/2026 junto com o `digest-semanal` das promessas: o
    cron de sexta chama os dois e injeta UMA mensagem só."""
    fim = datetime.now(timezone.utc)
    ini = fim - timedelta(days=dias)
    with conectar_leitura() as con, con.cursor() as cur:
        cur.execute(
            """SELECT agente, count(*), count(tokens), coalesce(sum(tokens),0)
                 FROM agente_atividade
                WHERE iniciado_em >= %s AND iniciado_em < %s
                GROUP BY agente ORDER BY 4 DESC, 2 DESC""",
            (ini, fim),
        )
        por_agente = cur.fetchall()
        cur.execute(
            """SELECT (iniciado_em AT TIME ZONE 'America/Sao_Paulo')::date,
                      count(*), coalesce(sum(tokens),0)
                 FROM agente_atividade
                WHERE iniciado_em >= %s AND iniciado_em < %s
                GROUP BY 1 ORDER BY 1""",
            (ini, fim),
        )
        por_dia = cur.fetchall()
        # Se a coluna existir um dia, ela entra sem precisar mexer aqui de novo.
        cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name='agente_atividade'"
            " AND column_name='retrabalho'"
        )
        tem_coluna = bool(cur.fetchone())
        marcas = _ids_retrabalho()
        if tem_coluna:
            cur.execute(
                "SELECT id, retrabalho FROM agente_atividade"
                " WHERE retrabalho IS NOT NULL AND iniciado_em >= %s", (ini,)
            )
            for i, motivo in cur.fetchall():
                marcas.setdefault(i, motivo)
        detalhe_retrabalho = []
        if marcas:
            cur.execute(
                """SELECT id, agente, tarefa, coalesce(tokens,0), iniciado_em
                     FROM agente_atividade
                    WHERE id = ANY(%s) AND iniciado_em >= %s AND iniciado_em < %s
                    ORDER BY coalesce(tokens,0) DESC""",
                (list(marcas), ini, fim),
            )
            detalhe_retrabalho = cur.fetchall()

    chamadas = sum(r[1] for r in por_agente)
    com_token = sum(r[2] for r in por_agente)
    tokens = sum(r[3] for r in por_agente)
    tk_retrab = sum(r[3] for r in detalhe_retrabalho)
    resumo = {
        "de": ini, "ate": fim, "dias": dias,
        "chamadas": chamadas, "com_token": com_token, "tokens": tokens,
        "retrabalho_execucoes": len(detalhe_retrabalho),
        "retrabalho_tokens": tk_retrab,
        "pct_retrabalho": round(100 * tk_retrab / tokens, 1) if tokens else 0.0,
        "arquivo": None,
    }
    if not escrever:
        return resumo

    def n(v):
        return f"{v:,}".replace(",", ".")

    out = [
        f"# Custo do time, {dias} dias até {fim.astimezone(BRT):%d/%m/%Y %H:%M} (Brasília)",
        "",
        "Gerado por `tools/agente_log.py custo-semanal`. **Não editar à mão.**",
        "Fonte: `agente_atividade`. Não inclui o custo da sessão principal, que não",
        "passa por esta tabela; inventar esse número seria pior que não ter.",
        "",
        f"- Delegações na janela: **{chamadas}**",
        f"- Tokens somados: **{n(tokens)}**",
        f"- Execuções que informaram token: **{com_token} de {chamadas}**"
        + (f" ({round(100*com_token/chamadas)}%)" if chamadas else ""),
        "",
        "## Retrabalho marcado",
        "",
    ]
    if detalhe_retrabalho:
        q = len(detalhe_retrabalho)
        out += [f"**{q} execução{'ões' if q > 1 else ''}**, "
                f"**{n(tk_retrab)} tokens**, que é "
                f"**{str(resumo['pct_retrabalho']).replace('.', ',')}%** "
                "do gasto da janela.", "",
                "| # | agente | tokens | o que eu tinha dito errado | tarefa |",
                "|---|---|---|---|---|"]
        for i, agente, tarefa, tk, _ini in detalhe_retrabalho:
            motivo = marcas.get(i, "").replace("|", "/")
            out.append(f"| {i} | {agente} | {n(tk)} | {motivo} | {tarefa[:70]} |")
    else:
        out.append("Nenhuma execução marcada como retrabalho nesta janela.")
    out += [
        "",
        "> **Ausência de marca não é ausência de retrabalho.** Só entra aqui o que",
        "> foi marcado à mão com `agente_log.py retrabalho <id> \"motivo\"` (ou com",
        "> `--retrabalho` no `fim`). O número acima é piso, nunca total.",
        "",
        "## Por agente",
        "",
        "| agente | chamadas | com token | tokens |",
        "|---|---|---|---|",
    ]
    for agente, ch, ct, tk in por_agente:
        out.append(f"| {agente} | {ch} | {ct} | {n(tk)} |")
    out += ["", "## Por dia (Brasília)", "", "| dia | chamadas | tokens |", "|---|---|---|"]
    for dia, ch, tk in por_dia:
        out.append(f"| {dia:%d/%m} | {ch} | {n(tk)} |")
    out.append("")

    caminho = RAIZ / "memory" / f"custo-semanal-{fim.astimezone(BRT):%Y-%m-%d}.md"
    caminho.write_text("\n".join(out))
    resumo["arquivo"] = str(caminho)
    return resumo


def cmd_custo_semanal(dias, escrever=True):
    r = relatorio_custo_semanal(dias, escrever)
    print(f"custo-semanal: {r['chamadas']} delegações, {r['tokens']} tokens, "
          f"{r['retrabalho_execucoes']} marcada(s) como retrabalho "
          f"({r['retrabalho_tokens']} tokens, {r['pct_retrabalho']}%)")
    if r["arquivo"]:
        print(r["arquivo"])
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "inicio":
        if len(sys.argv) < 4:
            print("uso: inicio <agente> <tarefa> [--frente Nome]")
            return 1
        # 05/08/2026: mesma história do campo `tokens` — a coluna `frente` existia
        # e a CLI não sabia gravar. Resultado: as 23 execuções de hoje caíram em
        # "sem frente" no painel, e a quebra "onde o token está sendo gasto" ficou
        # inútil justamente no dia de maior uso.
        frente = None
        if "--frente" in sys.argv:
            i = sys.argv.index("--frente")
            if i + 1 < len(sys.argv):
                frente = sys.argv[i + 1].strip() or None
        return cmd_inicio(sys.argv[2], sys.argv[3], frente)
    if cmd == "fim":
        if len(sys.argv) < 5:
            print("uso: fim <id> <ok|falha|cancelado> <resultado> [--arquivos a,b] [--tokens N]")
            return 1
        arquivos = None
        if "--arquivos" in sys.argv:
            i = sys.argv.index("--arquivos")
            if i + 1 < len(sys.argv):
                arquivos = [a.strip() for a in sys.argv[i + 1].split(",") if a.strip()]
        # 05/08/2026: o campo `tokens` existia na tabela e a CLI nunca soube gravar.
        # Resultado: 28 de 45 execuções ficaram "sem token informado" no painel, e o
        # Chefe viu isso na tela. O número sempre esteve no retorno do subagente; era
        # só eu ter onde escrever.
        tokens = None
        if "--tokens" in sys.argv:
            i = sys.argv.index("--tokens")
            if i + 1 < len(sys.argv):
                try:
                    tokens = int(str(sys.argv[i + 1]).replace(".", "").replace(",", ""))
                except ValueError:
                    print("--tokens precisa ser número inteiro; ignorando")
        # 26/08/2026: marcar retrabalho no mesmo comando que encerra, porque
        # dois comandos para um ato só viram um comando esquecido (mesma
        # história do `--despachada` no promessas.py). A marca vale mesmo que o
        # `fim` falhe por id já fechado? Não: só marca se o encerramento valeu.
        motivo_retrabalho = None
        if "--retrabalho" in sys.argv:
            i = sys.argv.index("--retrabalho")
            if i + 1 < len(sys.argv):
                motivo_retrabalho = sys.argv[i + 1]
        saida = cmd_fim(int(sys.argv[2]), sys.argv[3], sys.argv[4], arquivos, tokens)
        if saida == 0 and motivo_retrabalho:
            marcar_retrabalho(int(sys.argv[2]), motivo_retrabalho)
        return saida
    if cmd == "retrabalho":
        if len(sys.argv) >= 4 and sys.argv[3] == "--desmarcar":
            return desmarcar_retrabalho(int(sys.argv[2]))
        if len(sys.argv) < 4:
            print('uso: retrabalho <id> "o que eu tinha dito errado"\n'
                  '     retrabalho <id> --desmarcar')
            return 1
        return marcar_retrabalho(int(sys.argv[2]), sys.argv[3])
    if cmd == "custo-semanal":
        dias = 7
        if "--dias" in sys.argv:
            i = sys.argv.index("--dias")
            if i + 1 < len(sys.argv):
                dias = int(sys.argv[i + 1])
        return cmd_custo_semanal(dias, "--sem-arquivo" not in sys.argv)
    if cmd == "passo":
        if len(sys.argv) < 4:
            print("uso: passo <id> <texto curto>")
            return 1
        return cmd_passo(int(sys.argv[2]), sys.argv[3])
    if cmd == "agora":
        return cmd_agora()
    print(f"comando desconhecido: {cmd}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
