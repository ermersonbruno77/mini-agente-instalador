#!/usr/bin/env python3
"""
Lado servidor da caixa de entrega do diretorio do Microsoft 365 (Teams/Entra ID).

Pergunta pra caixa (Vercel Blob) se o PC do Chefe entregou um CSV do diretorio.
Se entregou, baixa, resume, APAGA da caixa e aciona a {{AGENTE_NAME}}.

Diferencas em relacao ao puxar.py do DFC, de proposito:
  - roda a mao, nao tem cron. Isto e uma exportacao pontual pra corrigir a base
    de um painel interno, nao um pipeline diario.
  - apaga o arquivo da caixa depois de baixar. O CSV tem nome e e-mail de todo
    mundo da empresa, e a URL do Vercel Blob e publica (aleatoria, mas publica).
    Quanto menos tempo la, melhor. Use --manter pra nao apagar.
  - nao escreve NADA no Postgres. Cruzar com orc_pessoa e outra etapa, decidida
    pela {{AGENTE_NAME}} depois de conferir o arquivo.
  - nao imprime nome de pessoa na tela, so contagem e departamento.

Uso:
    puxar_diretorio.py            # baixa o mais recente, apaga da caixa, aciona a {{AGENTE_NAME}}
    puxar_diretorio.py --check    # so diz o que tem la, sem baixar
    puxar_diretorio.py --force    # baixa de novo mesmo se ja tiver baixado
    puxar_diretorio.py --manter   # nao apaga da caixa depois de baixar
    puxar_diretorio.py --calado   # nao aciona a {{AGENTE_NAME}}
"""

import csv
import io
import json
import os
import subprocess
import sys
import urllib.request

# Mesma caixa do DFC. Nao mistura porque o prefixo do caminho e outro:
# o puxar.py do DFC filtra "dfc/" e "dfc-log/", este aqui filtra "diretorio/".
ENDPOINT = "https://{{AGENTE_NAME_LOWERCASE}}-dfc-box.vercel.app/"
SEGREDO_ARQ = "/opt/{{AGENTE_NAME_LOWERCASE}}/.secrets/dfc_box_secret"
TOKEN_ARQ = "/opt/{{AGENTE_NAME_LOWERCASE}}/.secrets/blob_token"
BLOB_API = "https://blob.vercel-storage.com"

PREFIXO = "diretorio/"
PREFIXO_LOG = "diretorio-log/"

DESTINO = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/diretorio-teams"
ESTADO = "/opt/{{AGENTE_NAME_LOWERCASE}}/.secrets/diretorio_puxado.json"
INJECT = "/opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh"


def segredo():
    with open(SEGREDO_ARQ) as fh:
        return fh.read().strip()


def token():
    with open(TOKEN_ARQ) as fh:
        return fh.read().strip()


def buscar(url, binario=False, timeout=180):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read() if binario else json.loads(r.read())


def listar():
    return buscar(f"{ENDPOINT}?action=list&secret={segredo()}")


def apagar(urls):
    """Apaga blobs da caixa. A caixa nao tem acao de delete, entao falamos
    direto com a API do Vercel Blob, com o token de escrita do servidor."""
    req = urllib.request.Request(
        f"{BLOB_API}/delete",
        data=json.dumps({"urls": list(urls)}).encode(),
        method="POST",
    )
    req.add_header("authorization", "Bearer " + token())
    req.add_header("x-api-version", "7")
    req.add_header("content-type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status


def estado():
    if os.path.exists(ESTADO):
        try:
            with open(ESTADO) as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}


def salvar_estado(d):
    old = os.umask(0o077)
    try:
        with open(ESTADO, "w") as fh:
            json.dump(d, fh, indent=2)
    finally:
        os.umask(old)


def resumir(caminho):
    """Le o CSV e devolve so numero. Nome de gente nao vai pra tela nem pro log."""
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        linhas = list(csv.DictReader(fh, delimiter=";"))

    def cheio(linha, campo):
        return bool((linha.get(campo) or "").strip())

    deps = {}
    for l in linhas:
        d = (l.get("departamento") or "").strip() or "(vazio)"
        deps[d] = deps.get(d, 0) + 1

    return {
        "linhas": len(linhas),
        "colunas": list(linhas[0].keys()) if linhas else [],
        "com_departamento": sum(1 for l in linhas if cheio(l, "departamento")),
        "com_gerente": sum(1 for l in linhas if cheio(l, "gerente_nome")),
        "com_matricula": sum(1 for l in linhas if cheio(l, "matricula")),
        "com_cargo": sum(1 for l in linhas if cheio(l, "cargo")),
        "ativos": sum(1 for l in linhas if (l.get("ativo") or "").strip().lower() in ("true", "1", "verdadeiro")),
        "departamentos": sorted(deps.items(), key=lambda kv: -kv[1]),
    }


def main():
    check = "--check" in sys.argv
    force = "--force" in sys.argv
    manter = "--manter" in sys.argv
    calado = "--calado" in sys.argv

    dados = listar()
    todos = dados.get("todos", [])
    csvs = [b for b in todos if b["pathname"].startswith(PREFIXO)]
    logs = [b for b in todos if b["pathname"].startswith(PREFIXO_LOG)]

    if not csvs and not logs:
        print("caixa vazia: o PC do Chefe ainda nao entregou o diretorio")
        return 0

    ja = estado()
    recente = max(csvs, key=lambda b: b["uploadedAt"]) if csvs else None
    ultimo_log = max(logs, key=lambda b: b["uploadedAt"]) if logs else None

    if check:
        print(f"csv: {len(csvs)} | relatorios de execucao: {len(logs)}")
        if recente:
            print(f"mais recente: {recente['pathname']} | {recente['size']} bytes | {recente['uploadedAt']}")
            print("ja baixado" if ja.get("url") == recente["url"] else "NOVO, ainda nao baixado")
        if ultimo_log:
            print(f"ultimo relatorio: {ultimo_log['pathname']} | {ultimo_log['uploadedAt']}")
        return 0

    # O relatorio de execucao vem primeiro: e ele que diz se o login do Chefe
    # conseguiu ler tudo ou se esbarrou na aprovacao da TI.
    resumo_exec = None
    if ultimo_log:
        try:
            resumo_exec = json.loads(buscar(ultimo_log["url"], binario=True).decode("utf-8-sig"))
            enxuto = {k: v for k, v in resumo_exec.items() if k not in ("eventos", "departamentos")}
            print("relatorio do agente:", json.dumps(enxuto, ensure_ascii=False))
        except Exception as e:
            print("nao consegui ler o relatorio do agente:", e)

    if resumo_exec and resumo_exec.get("precisa_admin"):
        print("\nATENCAO: o agente reportou precisa_admin=True.")
        print("Classe do erro:", resumo_exec.get("classe_do_erro"))
        print("Ou seja: o login do Chefe nao libera departamento/gerente dos outros.")
        print("Proximo passo e pedido de consentimento de administrador para a TI,")
        print("mesma trava do SharePoint em julho/2026.")

    if not recente:
        print("\nnenhum CSV na caixa (so relatorio de execucao)")
        if not calado and os.path.exists(INJECT) and resumo_exec:
            aviso = (
                "[sistema] Diretorio Teams: o agente do PC do Chefe rodou e NAO entregou CSV. "
                f"modo={resumo_exec.get('modo')} classe={resumo_exec.get('classe_do_erro')} "
                f"precisa_admin={resumo_exec.get('precisa_admin')}. "
                "Leia /opt/{{AGENTE_NAME_LOWERCASE}}/tools/teams-diretorio/LEIA-ME.txt e escreva pro Chefe o que fazer."
            )
            subprocess.run([INJECT, aviso], check=False)
            print("{{AGENTE_NAME}} acionada")
        return 0

    if ja.get("url") == recente["url"] and not force:
        print(f"nada novo (ultimo ja baixado: {recente['uploadedAt']})")
        return 0

    os.makedirs(DESTINO, exist_ok=True)
    os.chmod(DESTINO, 0o700)
    nome = os.path.basename(recente["pathname"])
    caminho = os.path.join(DESTINO, nome)

    old = os.umask(0o077)
    try:
        with open(caminho, "wb") as fh:
            fh.write(buscar(recente["url"], binario=True))
    finally:
        os.umask(old)
    os.chmod(caminho, 0o600)
    print(f"\nbaixado: {caminho} ({os.path.getsize(caminho)} bytes)")

    try:
        r = resumir(caminho)
        print(f"linhas: {r['linhas']} | ativas: {r['ativos']} | com departamento: {r['com_departamento']} "
              f"| com gerente: {r['com_gerente']} | com matricula: {r['com_matricula']} | com cargo: {r['com_cargo']}")
        print("colunas:", ", ".join(r["colunas"]))
        print("departamentos (contagem):")
        for d, n in r["departamentos"]:
            print(f"  {n:4d}  {d}")
    except Exception as e:
        r = None
        print("nao consegui resumir o CSV:", e)

    salvar_estado({
        "url": recente["url"],
        "pathname": recente["pathname"],
        "uploadedAt": recente["uploadedAt"],
        "local": caminho,
        "resumo": {k: v for k, v in (r or {}).items() if k != "departamentos"},
    })

    # Some da caixa: dado de pessoa nao fica parado em armazenamento publico.
    if not manter:
        try:
            alvos = [recente["url"]] + ([ultimo_log["url"]] if ultimo_log else [])
            apagar(alvos)
            print(f"apagado da caixa: {len(alvos)} arquivo(s)")
        except Exception as e:
            print("AVISO: nao consegui apagar da caixa:", e)
    else:
        print("--manter: o arquivo continua na caixa")

    if not calado and os.path.exists(INJECT):
        aviso = (
            f"[sistema] Diretorio do Microsoft 365 baixado em {caminho}. "
            f"modo={resumo_exec.get('modo') if resumo_exec else '?'}, "
            f"linhas={r['linhas'] if r else '?'}, "
            f"com_gerente={r['com_gerente'] if r else '?'}, "
            f"com_departamento={r['com_departamento'] if r else '?'}, "
            f"precisa_admin={resumo_exec.get('precisa_admin') if resumo_exec else '?'}. "
            "NAO grave em orc_pessoa antes de conferir: compare por matricula, "
            "depois por e-mail, e so por nome no que sobrar. Escreva pro Chefe o resultado."
        )
        subprocess.run([INJECT, aviso], check=False)
        print("{{AGENTE_NAME}} acionada")

    return 0


if __name__ == "__main__":
    sys.exit(main())
