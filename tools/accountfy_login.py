#!/usr/bin/env python3
"""Login coordenado no Accountfy, mantendo a sessao viva ate o codigo chegar.

POR QUE ESTE SCRIPT EXISTE (nao e so um "run" de browser.py):
O codigo de verificacao so e disparado ao e-mail do Chefe DEPOIS que a senha
e submetida. Um roteiro comum de browser.py fecha o navegador no fim da lista
de acoes; se fechasse aqui, a sessao morreria antes de alguem conseguir
escrever o codigo. Este script SUBMETE a senha e then FICA ESPERANDO um
arquivo aparecer no disco com o codigo, com o navegador aberto o tempo todo.

Uso (SO NA TENTATIVA COORDENADA, ao vivo com o Chefe. Ver aviso no leia-me
do pedido: nao executar por conta propria):
    python3 /opt/{{AGENTE_NAME_LOWERCASE}}/tools/accountfy_login.py

Fluxo:
  1. Stealth mode (Xvfb + chrome headed real), igual ao --stealth do browser.py.
  2. Aceita cookies, preenche e-mail, AVANCAR.
  3. Preenche senha. Marca "Confiar neste dispositivo" ANTES de qualquer
     submit, em toda tela onde a opcao existir (login pede duas vezes: uma
     na tela de senha, possivelmente outra na tela de codigo).
  4. Submete a senha (Enter). A partir daqui o codigo cai no e-mail dele.
  5. Poll a cada 2s por ATE 5 MINUTOS no arquivo
     /tmp/claude-0/-opt-{{AGENTE_NAME_LOWERCASE}}/95f41be7-c07f-43b1-a369-c863f1ef3bc5/scratchpad/accountfy_codigo.txt
     Sem esse arquivo aparecer no prazo, desiste, fecha o navegador, sai com
     erro. NAO fica pendurado para sempre.
  6. Le o codigo, procura o campo (ou os campos, se for OTP em caixas
     separadas), preenche, marca "Confiar neste dispositivo" de novo se
     aparecer nesta tela, submete.
  7. Espera a URL sair de /login e entrar em /app (sinal de sucesso).
  8. Salva o storage_state (cookies + localStorage) em
     /opt/{{AGENTE_NAME_LOWERCASE}}/.accountfy_session.json, chmod 600, para as proximas
     execucoes reaproveitarem a sessao sem passar por login de novo.
  9. Navega: card "TMB SERVICOS" -> "Demonstracoes Financeiras". Se a URL
     direta https://platform.accountfy.com/#/app/demonstracoes-financeiras
     funcionar sem passar pelo card, usa ela como atalho e loga qual caminho
     deu certo.
  10. Screenshot + texto renderizado da tela final, para confirmar visualmente
      que chegamos no quadro de resultado mes a mes (01/2026 a 12/2026, com
      valores preenchidos ate 06/2026).

REGRA DE SOMENTE LEITURA: este script nunca clica em salvar, editar, excluir
ou exportar nada dentro do Accountfy. So navega e le.
"""
import os
import sys
import time
import json
import stat

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright  # noqa: E402
import browser as bw  # reaproveita _iniciar_xvfb/_parar_xvfb/STEALTH_* ja testados  # noqa: E402

ENV_PATH = "/opt/{{AGENTE_NAME_LOWERCASE}}/.env"
SCRATCH = "/tmp/claude-0/-opt-{{AGENTE_NAME_LOWERCASE}}/95f41be7-c07f-43b1-a369-c863f1ef3bc5/scratchpad"
CODIGO_PATH = f"{SCRATCH}/accountfy_codigo.txt"
SESSION_PATH = "/opt/{{AGENTE_NAME_LOWERCASE}}/.accountfy_session.json"
SCREENSHOT_PATH = f"{SCRATCH}/accountfy_demonstracoes.png"
TEXTO_PATH = f"{SCRATCH}/accountfy_demonstracoes.txt"
TIMEOUT_CODIGO_S = 300  # 5 minutos
POLL_S = 2

ROTA_DEMONSTRACOES = "https://platform.accountfy.com/#/app/demonstracoes-financeiras"


def log(msg):
    print(f"[accountfy_login] {msg}", flush=True)


def _ler_env():
    """Le ACCOUNTFY_URL/USER/SENHA do .env sem depender de lib externa.
    Nunca imprime o valor lido, so a chave, para nao vazar segredo em log."""
    valores = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            k, _, v = linha.partition("=")
            k = k.strip()
            if k in ("ACCOUNTFY_URL", "ACCOUNTFY_USER", "ACCOUNTFY_SENHA"):
                valores[k] = v.strip().strip('"')
    faltando = [k for k in ("ACCOUNTFY_URL", "ACCOUNTFY_USER", "ACCOUNTFY_SENHA") if k not in valores]
    if faltando:
        raise SystemExit(f"faltando no {ENV_PATH}: {faltando}")
    return valores


def _marcar_confiar_dispositivo(pg):
    """Marca 'Confiar neste dispositivo' se o checkbox existir e nao estiver
    marcado. Silencioso (so loga) se nao existir na tela atual."""
    try:
        alvo = pg.get_by_text("Confiar neste dispositivo", exact=False).first
        if alvo.count() == 0:
            log("checkbox 'Confiar neste dispositivo' nao apareceu nesta tela")
            return False
        # o texto costuma ser o <label> ao lado do checkbox; sobe pro container
        # e procura o input dentro dele.
        container = alvo.locator(
            "xpath=ancestor::*[self::label or self::div][1]"
        )
        checkbox = container.locator("input[type=checkbox]").first
        if checkbox.count() == 0:
            # fallback: clica no proprio texto (label geralmente ativa o input)
            alvo.click()
            log("cliquei no texto 'Confiar neste dispositivo' (sem input direto achado)")
            return True
        if not checkbox.is_checked():
            checkbox.check()
            log("marquei 'Confiar neste dispositivo'")
        else:
            log("'Confiar neste dispositivo' ja estava marcado")
        return True
    except Exception as e:
        log(f"nao consegui marcar 'Confiar neste dispositivo': {e}")
        return False


def _preencher_codigo(pg, codigo):
    """Tenta achar o campo de codigo. Cobre dois padroes comuns:
    (a) um input unico que recebe o codigo inteiro;
    (b) varias caixas de 1 digito cada."""
    codigo = codigo.strip()
    # padrao (b): varios inputs curtos (maxlength 1) e visiveis
    caixas = pg.locator("input[maxlength='1']")
    n = caixas.count()
    if n >= len(codigo) and n > 1:
        log(f"encontrei {n} caixas de 1 digito, preenchendo dígito a dígito")
        for i, ch in enumerate(codigo):
            caixas.nth(i).fill(ch)
        return True

    # padrao (a): campo unico. tenta seletores plausiveis, na ordem.
    candidatos = [
        "input[placeholder*='ódigo' i]",
        "input[placeholder*='code' i]",
        "input[name*='code' i]",
        "input[type=text]:visible",
        "input[type=tel]:visible",
    ]
    for sel in candidatos:
        try:
            campo = pg.locator(sel).first
            if campo.count() > 0:
                campo.fill(codigo)
                log(f"preenchi codigo no seletor '{sel}'")
                return True
        except Exception:
            continue
    log("NAO ACHEI campo de codigo com os seletores conhecidos")
    return False


def main():
    env = _ler_env()
    os.makedirs(SCRATCH, exist_ok=True)

    if os.path.exists(CODIGO_PATH):
        log(f"aviso: {CODIGO_PATH} ja existe de uma rodada anterior, removendo antes de comecar")
        os.remove(CODIGO_PATH)

    log("iniciando Xvfb + chromium stealth")
    bw._iniciar_xvfb()
    with sync_playwright() as p:
        b, pg = bw._new(p, stealth=True)
        try:
            log(f"abrindo {env['ACCOUNTFY_URL']}")
            pg.goto(env["ACCOUNTFY_URL"], wait_until="domcontentloaded", timeout=25000)
            pg.wait_for_timeout(1200)

            try:
                pg.click("button:has-text('OK, CONTINUAR')", timeout=5000)
                log("banner de cookies aceito")
            except Exception:
                log("banner de cookies nao apareceu (ja aceito antes?)")

            log("preenchendo e-mail")
            pg.fill("input[type=email], input[placeholder='Digite seu e-mail']", env["ACCOUNTFY_USER"])
            pg.click("button:has-text('AVANÇAR')")
            pg.wait_for_timeout(2000)

            log("aguardando campo de senha")
            pg.wait_for_selector("input[type=password]", timeout=15000)
            pg.fill("input[type=password]", env["ACCOUNTFY_SENHA"])

            _marcar_confiar_dispositivo(pg)

            log("submetendo senha (Enter) -- a partir de agora o codigo cai no e-mail dele")
            pg.keyboard.press("Enter")

            log(f"aguardando ate {TIMEOUT_CODIGO_S}s por {CODIGO_PATH}")
            inicio = time.time()
            codigo = None
            while time.time() - inicio < TIMEOUT_CODIGO_S:
                if os.path.exists(CODIGO_PATH):
                    with open(CODIGO_PATH, encoding="utf-8") as f:
                        codigo = f.read().strip()
                    if codigo:
                        log("codigo encontrado no arquivo")
                        break
                time.sleep(POLL_S)

            if not codigo:
                log(f"TIMEOUT: nenhum codigo apareceu em {TIMEOUT_CODIGO_S}s, desistindo")
                pg.screenshot(path=f"{SCRATCH}/accountfy_timeout.png", full_page=True)
                raise SystemExit(1)

            pg.wait_for_timeout(500)  # deixa a tela de codigo assentar, se ainda estiver carregando
            _marcar_confiar_dispositivo(pg)

            if not _preencher_codigo(pg, codigo):
                pg.screenshot(path=f"{SCRATCH}/accountfy_sem_campo_codigo.png", full_page=True)
                raise SystemExit(2)

            log("submetendo codigo")
            try:
                pg.keyboard.press("Enter")
            except Exception:
                pass
            for texto_botao in ("CONFIRMAR", "VERIFICAR", "AVANÇAR", "ENTRAR"):
                try:
                    pg.click(f"button:has-text('{texto_botao}')", timeout=1500)
                    log(f"cliquei no botao '{texto_botao}'")
                    break
                except Exception:
                    continue

            log("aguardando a URL entrar em /app (sinal de login concluido)")
            try:
                pg.wait_for_url("**/app/**", timeout=30000)
            except Exception as e:
                log(f"nao vi a URL trocar para /app a tempo: {e}. Seguindo mesmo assim para checar o estado real.")
            pg.wait_for_timeout(2000)

            log(f"logado (url atual: {pg.url}). salvando storage_state em {SESSION_PATH}")
            state = pg.context.storage_state()
            with open(SESSION_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f)
            os.chmod(SESSION_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600
            log("sessao salva com permissao 600")

            log(f"tentando atalho direto: {ROTA_DEMONSTRACOES}")
            chegou_por_atalho = False
            try:
                pg.goto(ROTA_DEMONSTRACOES, wait_until="domcontentloaded", timeout=15000)
                pg.wait_for_timeout(2500)
                texto_atual = pg.inner_text("body")
                if "emonstra" in texto_atual or "esultado" in texto_atual:
                    chegou_por_atalho = True
                    log("atalho direto funcionou, cheguei na tela certa sem passar pelo card")
                else:
                    log("atalho direto abriu uma tela que nao parece ser Demonstracoes Financeiras, tentando pelo card")
            except Exception as e:
                log(f"atalho direto falhou: {e}. Tentando pelo caminho do card.")

            if not chegou_por_atalho:
                try:
                    log("clicando no card 'TMB SERVIÇOS'")
                    pg.click("text=TMB SERVIÇOS", timeout=10000)
                    pg.wait_for_timeout(2000)
                    log("clicando em 'Demonstrações Financeiras'")
                    pg.click("text=Demonstrações Financeiras", timeout=10000)
                    pg.wait_for_timeout(3000)
                except Exception as e:
                    log(f"nao consegui navegar pelo card/menu: {e}")

            pg.wait_for_timeout(1500)
            pg.screenshot(path=SCREENSHOT_PATH, full_page=True)
            texto_final = pg.inner_text("body")
            with open(TEXTO_PATH, "w", encoding="utf-8") as f:
                f.write(texto_final)
            log(f"screenshot salvo em {SCREENSHOT_PATH}")
            log(f"texto renderizado salvo em {TEXTO_PATH}")
            log(f"url final: {pg.url}")
            log("FIM: revisar screenshot e texto para confirmar que e o quadro de resultado mes a mes (01/2026 a 12/2026, valores até 06/2026)")

        finally:
            b.close()
            bw._parar_xvfb()
            if os.path.exists(CODIGO_PATH):
                os.remove(CODIGO_PATH)
                log(f"limpei {CODIGO_PATH} (nao deixar codigo usado no disco)")


if __name__ == "__main__":
    main()
