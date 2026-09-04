#!/usr/bin/env python3
"""Tira print das páginas do painel Raio-X, no desktop e no celular.

Existe porque em 03/08/2026 o Chefe começou a revisar o painel pelo celular e eu
precisava conferir cada página nas duas larguras antes de mostrar.

Uso:
    python3 tools/painel_print.py <destino> <caminho> [<caminho> ...]
    python3 tools/painel_print.py /tmp/prints / /dfc /caixa

Três armadilhas que já me morderam e estão resolvidas aqui:

1. Esperar o seletor aparecer NÃO é esperar o React hidratar. Preencher antes da
   hidratação faz o React limpar o campo, o submit virar POST nativo e a tela
   voltar pro login sem mensagem de erro, parecendo senha errada.
2. `wait_for_url` não serve para detectar login: o App Router troca de página no
   cliente, sem navegação de documento, então o wait estoura mesmo quando o
   login funcionou. O sinal confiável é o botão Sair.
3. Cada login gasta uma das 5 tentativas que o painel permite em 15 minutos. Eu
   já enchi o contador testando e o Chefe é quem seria bloqueado. Por isso a
   sessão é guardada e reaproveitada entre execuções.

O arquivo de sessão contém um cookie válido do Chefe. Fica em modo 600 e deve ser
apagado quando a rodada de revisão terminar: `--limpar-sessao` faz isso.
"""
import json
import os
import stat
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://raiox-{{AGENTE_NAME_LOWERCASE}}.vercel.app"
ENV = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/.env")
CACHE_SESSAO = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/painel-raiox/.sessao-print.json")
LARGURAS = {"1280": 1280, "390": 390}   # desktop dele e celular dele


def ler_env(chave):
    for linha in ENV.read_text().splitlines():
        if linha.startswith(f"{chave}="):
            return linha.split("=", 1)[1].strip().strip("'\"")
    return ""


def salvar_sessao(estado):
    CACHE_SESSAO.write_text(json.dumps(estado))
    os.chmod(CACHE_SESSAO, stat.S_IRUSR | stat.S_IWUSR)


def sessao_guardada(navegador):
    """Devolve o storage_state salvo se ele ainda estiver valendo, senão None."""
    if not CACHE_SESSAO.exists():
        return None
    try:
        estado = json.loads(CACHE_SESSAO.read_text())
        ctx = navegador.new_context(storage_state=estado,
                                    viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        pg.goto(f"{BASE}/", wait_until="networkidle")
        valido = "/login" not in pg.url
        ctx.close()
        return estado if valido else None
    except Exception:
        return None


def logar(navegador, email, senha):
    """Faz o login pelo formulário e devolve o storage_state, ou None se falhar."""
    ctx = navegador.new_context(locale="pt-BR", timezone_id="America/Fortaleza",
                                viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(45000)
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.wait_for_selector('input[name="email"]')
    pg.wait_for_timeout(4000)              # hidratação do React, ver docstring
    pg.fill('input[name="email"]', email)
    pg.fill('input[name="senha"]', senha)
    pg.click('button[type="submit"]')
    try:
        pg.wait_for_selector("text=Sair", timeout=30000)
    except Exception:
        visivel = ""
        for sel in (".cartao-login__mensagem", ".tela-login"):
            try:
                visivel = (pg.inner_text(sel, timeout=2000) or "").strip()
                if visivel:
                    break
            except Exception:
                continue
        print(f"não consegui logar. a tela diz: {visivel[:200] or '(sem mensagem)'}")
        ctx.close()
        return None
    estado = ctx.storage_state()
    ctx.close()
    return estado


def main():
    if "--limpar-sessao" in sys.argv:
        CACHE_SESSAO.unlink(missing_ok=True)
        print("sessão apagada")
        return 0
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    destino = Path(sys.argv[1])
    destino.mkdir(parents=True, exist_ok=True)
    caminhos = sys.argv[2:]

    email, senha = ler_env("PAINEL_EMAIL"), ler_env("PAINEL_SENHA")
    if not email or not senha:
        print("PAINEL_EMAIL/PAINEL_SENHA não estão em /opt/{{AGENTE_NAME_LOWERCASE}}/.env")
        return 1

    gerados = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True)
        try:
            estado = sessao_guardada(navegador)
            if estado is None:
                estado = logar(navegador, email, senha)
                if estado is None:
                    return 1
                salvar_sessao(estado)

            for rotulo, largura in LARGURAS.items():
                ctx = navegador.new_context(locale="pt-BR", timezone_id="America/Fortaleza",
                                            viewport={"width": largura, "height": 900},
                                            storage_state=estado)
                pg = ctx.new_page()
                pg.set_default_timeout(45000)
                for caminho in caminhos:
                    pg.goto(f"{BASE}{caminho}", wait_until="networkidle")
                    pg.wait_for_timeout(1500)
                    nome = (caminho.strip("/") or "home").replace("/", "-")
                    saida = destino / f"{nome}-{rotulo}.png"
                    pg.screenshot(path=str(saida), full_page=True)
                    gerados.append(str(saida))
                    print(f"ok {saida}")
                ctx.close()
        finally:
            navegador.close()

    return 0 if gerados else 1


if __name__ == "__main__":
    sys.exit(main())
