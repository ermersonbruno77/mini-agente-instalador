#!/usr/bin/env python3
"""Navegador autonomo da {{AGENTE_NAME}} (Playwright headless). Opera a web de verdade.

Uso:
  browser.py screenshot <url> [saida.png]     -> screenshot (full page); {{AGENTE_NAME}} le com Read (visao)
  browser.py text <url>                        -> texto renderizado (JS ja executado)
  browser.py html <url>                        -> HTML renderizado (pg.content(), com hrefs;
                                                     use quando precisar achar link/dominio,
                                                     nao so o texto visivel)
  browser.py pdf <url> [saida.pdf]             -> salva a pagina em PDF
  browser.py run <acoes.json>                  -> automacao: sequencia de acoes

Acoes suportadas no run (lista JSON):
  {"goto":"https://..."}          navega
  {"waitfor":"seletor"}           espera elemento aparecer
  {"wait": 1500}                  espera ms
  {"fill":["seletor","texto"]}    preenche campo
  {"select":["seletor","label"]}  escolhe opcao de <select> pela label visivel (Playwright select_option)
  {"click":"seletor"}             clica
  {"click_if_exists":"seletor"}   clica se existir, senao segue (timeout 3s, nunca trava)
  {"press":"Enter"}               tecla
  {"viewport":[390,844]}          troca largura da janela (prova defeito de layout)
  {"text": true}                  captura texto renderizado (vai pro resultado)
  {"text": "seletor"}             texto de um elemento
  {"avaliar":"js"}                roda JS na pagina e devolve o retorno (mede o RENDERIZADO:
                                    fonte depois do zoom, caixa, o que cabe na janela)
  {"screenshot":"saida.png"}      screenshot (pagina inteira)
  {"screenshot_visivel":"x.png"}  screenshot so do que cabe na janela (sem full_page)
  {"pdf":"saida.pdf"}             pdf
  {"esperar_rota":"**/painel"}         espera a URL trocar para o padrao (glob) e a pagina
                                            ficar com <body> nao-vazio; timeout default 30s
  {"esperar_rota":["**/painel", 45000]} mesma coisa com timeout em ms customizado

  browser.py run <acoes.json> --stealth   modo furtivo: chrome HEADED de verdade
                                           dentro de um Xvfb (sem display fisico),
                                           user-agent/versao casados com o binario
                                           real e patches de fingerprint. So use
                                           quando o alvo bloquear no headless comum
                                           (ex.: login trava sem erro, sem redirect).
                                           NAO muda o comportamento padrao dos outros
                                           comandos nem do "run" sem essa flag.

Sobre navegacao client-side do Next (SPA): um clique que troca de rota (ex.: login
bem-sucedido, link interno) NAO dispara reload de pagina inteira. O <body> pode ficar
vazio por varios segundos entre uma rota e outra (o app faz checagem de sessao e ate
redirecionamentos encadeados antes de chegar na tela final -- medido em 07/08/2026,
~13s entre clicar "Entrar" e a tela de /painel aparecer). Depois de um "click" que
deve navegar, use "esperar_rota" com o padrao da URL de destino em vez de "wait" com
tempo fixo ou de forcar "goto" de novo (forcar reload manual so mascara o problema e
nao prova que a navegacao client-side funciona). "wait" com ms fixo e para casos sem
navegacao (ex.: esperar uma animacao).
"""
import sys, os, json, time, subprocess, socket
from playwright.sync_api import sync_playwright

WORK="/opt/{{AGENTE_NAME_LOWERCASE}}/workspace"
ALLOWED_DIRS=["/opt/{{AGENTE_NAME_LOWERCASE}}/workspace", "/tmp/claude-0"]
ARGS=["--no-sandbox","--disable-dev-shm-usage","--disable-gpu",
      "--disable-blink-features=AutomationControlled"]

# Sem isto, Amazon/Mercado Livre/Magalu respondem parede de antibot
# (tela de login, "clique para continuar comprando", 403). Descoberto em 03/08/2026.
UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# --- modo stealth (so usado quando cmd_run recebe --stealth) -------------
# Diferenca central: headless=True deixa marcas que servico de antifraude
# le direto (navigator.webdriver, plugins vazio, chrome runtime ausente,
# banner "Chrome is being controlled..."). Headed de verdade dentro de um
# Xvfb (ja instalado no servidor, nao precisou instalar nada) remove a
# maior parte disso na raiz; o resto e patch de fingerprint via init script.
STEALTH_ARGS=["--no-sandbox","--disable-dev-shm-usage",
              "--start-maximized","--lang=pt-BR",
              "--disable-blink-features=AutomationControlled"]

_XVFB_PROC=None

def _xvfb_display_livre():
    for n in range(90, 120):
        disp=f":{n}"
        lock=f"/tmp/.X{n}-lock"
        if not os.path.exists(lock):
            return disp
    return ":99"

def _iniciar_xvfb():
    global _XVFB_PROC
    disp=_xvfb_display_livre()
    _XVFB_PROC=subprocess.Popen(
        ["Xvfb", disp, "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)  # Xvfb precisa subir antes do chrome tentar abrir nele
    os.environ["DISPLAY"]=disp
    return disp

def _parar_xvfb():
    global _XVFB_PROC
    if _XVFB_PROC is not None:
        _XVFB_PROC.terminate()
        try: _XVFB_PROC.wait(timeout=5)
        except Exception: _XVFB_PROC.kill()
        _XVFB_PROC=None

STEALTH_INIT_JS = r"""
// so setar navigator.webdriver=undefined nao basta: sobra a property no
// PROTOTYPE (Navigator.prototype) e testes mais novos leem 'webdriver' in
// navigator, que continua true mesmo com a instancia sobrescrita. Apagar a
// property do prototipo de vez (medido: some tambem do 'in').
delete Object.getPrototypeOf(navigator).webdriver;
Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR','pt','en-US','en']});
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
  parameters && parameters.name === 'notifications'
    ? Promise.resolve({state: Notification.permission})
    : originalQuery(parameters)
);
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    {name:'PDF Viewer', filename:'internal-pdf-viewer'},
    {name:'Chrome PDF Viewer', filename:'internal-pdf-viewer'},
    {name:'Chromium PDF Viewer', filename:'internal-pdf-viewer'},
    {name:'Microsoft Edge PDF Viewer', filename:'internal-pdf-viewer'},
    {name:'WebKit built-in PDF', filename:'internal-pdf-viewer'},
  ]
});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
"""

def _check_dest(path):
    """So permite gravar screenshot/pdf dentro do workspace ou do scratchpad
    (/tmp/claude-0/). Fora disso, recusa com mensagem clara."""
    ap = os.path.abspath(path)
    for allowed in ALLOWED_DIRS:
        if ap == allowed or ap.startswith(allowed.rstrip("/") + "/"):
            return ap
    print(f"recusado: destino '{path}' fora das pastas permitidas "
          f"({', '.join(ALLOWED_DIRS)})")
    sys.exit(2)

def _new(p, stealth=False):
    if not stealth:
        b=p.chromium.launch(headless=True, args=ARGS)
        ctx=b.new_context(user_agent=UA, locale="pt-BR",
                          timezone_id="America/Fortaleza",
                          viewport={"width":1366,"height":900})
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        pg=ctx.new_page()
        pg.set_default_timeout(30000)
        return b, pg
    # modo stealth: headed de verdade dentro de um Xvfb, sem --headless.
    # Xvfb ja foi iniciado por cmd_run ANTES do "with sync_playwright()",
    # aqui so usamos o DISPLAY que ja esta no ambiente.
    b=p.chromium.launch(headless=False, args=STEALTH_ARGS,
                        ignore_default_args=["--enable-automation"])
    ua_real=(f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             f"(KHTML, like Gecko) Chrome/{b.version} Safari/537.36")
    ctx=b.new_context(user_agent=ua_real, locale="pt-BR",
                      timezone_id="America/Sao_Paulo",
                      viewport={"width":1920,"height":1080})
    ctx.add_init_script(STEALTH_INIT_JS)
    pg=ctx.new_page()
    pg.set_default_timeout(30000)
    return b, pg

def cmd_screenshot(url, out=None):
    out=out or f"{WORK}/browser_shot.png"
    out=_check_dest(out)
    with sync_playwright() as p:
        b,pg=_new(p)
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=25000)
            pg.screenshot(path=out, full_page=True)
            print(f"screenshot salvo: {out}")
        finally: b.close()

# Paginas curtas com uma destas frases sao parede de antibot, nao conteudo.
PAREDES=["continuar comprando","para continuar, acesse","não é possível acessar",
         "verifique se você é humano","acesso negado"]

def _e_parede(t):
    tl=t.lower()
    return len(t)<2500 and any(f in tl for f in PAREDES)

def cmd_text(url):
    with sync_playwright() as p:
        b,pg=_new(p)
        try:
            for tentativa in range(4):
                pg.goto(url, wait_until="domcontentloaded", timeout=25000)
                pg.wait_for_timeout(3500)  # preco/estoque entram depois do DOM
                t=pg.inner_text("body")
                if not _e_parede(t):
                    print(t[:20000]); return
                time.sleep(10)   # a loja destrava depois de uma pausa
            print("BLOQUEADO por antibot apos 4 tentativas:\n"+t[:1000])
        finally: b.close()

def cmd_html(url):
    """Igual ao cmd_text (mesmo retry contra parede de antibot), mas devolve o
    HTML renderizado (pg.content()) em vez do texto visivel. Existe porque
    innerText nao mostra href de link/iframe/script, e quem precisa detectar
    pra onde um botao de checkout aponta precisa do atributo, nao do texto
    do botao ("Comprar agora" nao diz qual plataforma processa o pagamento).
    Truncado em 150k chars: pagina de vendas real nao passa disso e time
    corre risco de virar custo alto sem ganho."""
    with sync_playwright() as p:
        b, pg = _new(p)
        try:
            t = ""
            for tentativa in range(4):
                pg.goto(url, wait_until="domcontentloaded", timeout=25000)
                pg.wait_for_timeout(2500)
                t = pg.inner_text("body")
                if not _e_parede(t):
                    print(pg.content()[:150000]); return
                time.sleep(10)
            print("BLOQUEADO por antibot apos 4 tentativas:\n" + t[:1000])
        finally: b.close()

def cmd_pdf(url, out=None):
    out=out or f"{WORK}/browser_page.pdf"
    out=_check_dest(out)
    with sync_playwright() as p:
        b,pg=_new(p)
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=25000)
            pg.pdf(path=out)
            print(f"pdf salvo: {out}")
        finally: b.close()

def cmd_run(acoes_path, stealth=False):
    acoes=json.load(open(acoes_path, encoding="utf-8"))
    results=[]
    # DISPLAY precisa existir ANTES do driver do Playwright subir (ele herda o
    # ambiente no momento em que o processo nasce, dentro do "with" abaixo).
    # Setar DISPLAY depois de entrar no "with" chega tarde pro driver ver.
    if stealth: _iniciar_xvfb()
    with sync_playwright() as p:
        b,pg=_new(p, stealth=stealth)
        try:
            for a in acoes:
                if "goto" in a: pg.goto(a["goto"], wait_until="domcontentloaded", timeout=25000)
                elif "waitfor" in a: pg.wait_for_selector(a["waitfor"])
                elif "wait" in a: pg.wait_for_timeout(int(a["wait"]))
                elif "fill" in a: pg.fill(a["fill"][0], a["fill"][1])
                elif "select" in a: pg.select_option(a["select"][0], label=a["select"][1])
                elif "click" in a: pg.click(a["click"])
                # {"click_if_exists": "seletor"} — igual a "click", mas nao
                # explode se o seletor nao aparecer (timeout curto, 3s, e
                # segue o roteiro). Existe pra banner de cookie/consentimento
                # que so aparece em algumas visitas: "click" comum ficaria
                # pendurado ate o timeout padrao de 30s quando o banner nao
                # existe naquela sessao.
                elif "click_if_exists" in a:
                    try: pg.click(a["click_if_exists"], timeout=3000)
                    except Exception: pass
                elif "press" in a: pg.keyboard.press(a["press"])
                # {"viewport":[390,844]} — troca a largura no meio do roteiro.
                # Existe porque defeito de layout só se prova na largura em que
                # ele aparece: em 10/08/2026 o Chefe mandou print do Cadastro
                elif "viewport" in a:
                    v = a["viewport"]
                    pg.set_viewport_size({"width": int(v[0]), "height": int(v[1])})
                elif "esperar_rota" in a:
                    v = a["esperar_rota"]
                    padrao, timeout = (v, None) if isinstance(v, str) else (v[0], int(v[1]))
                    kwargs = {"timeout": timeout} if timeout else {}
                    pg.wait_for_url(padrao, **kwargs)
                    # URL trocou, mas o corpo pode ainda estar vazio no meio de um
                    # redirecionamento encadeado (ex.: /login -> / -> /painel).
                    # Espera o body deixar de estar vazio antes de devolver o controle.
                    pg.wait_for_function(
                        "document.body && document.body.innerText.trim().length > 0",
                        timeout=(timeout or 30000))
                # {"avaliar":"expressao js"} — roda JS na pagina e devolve o
                # resultado (JSON) no stdout. Existe porque prova de layout se
                # mede no RENDERIZADO: tamanho de fonte depois do zoom, largura
                # de caixa, quantos elementos cabem no viewport. Ler o CSS do
                # arquivo nao responde nada disso.
                elif "avaliar" in a:
                    v=pg.evaluate(a["avaliar"])
                    results.append("AVALIAR:\n"+json.dumps(v, ensure_ascii=False, indent=1))
                # {"screenshot_visivel":"saida.png"} — so o que cabe na janela,
                # sem full_page. Para "o que ele ve sem rolar", full_page mente:
                # devolve a pagina inteira esticada.
                elif "screenshot_visivel" in a:
                    dest=_check_dest(a["screenshot_visivel"])
                    pg.screenshot(path=dest, full_page=False); results.append(f"screenshot:{dest}")
                elif "screenshot" in a:
                    dest=_check_dest(a["screenshot"])
                    pg.screenshot(path=dest, full_page=True); results.append(f"screenshot:{dest}")
                elif "pdf" in a:
                    dest=_check_dest(a["pdf"])
                    pg.pdf(path=dest); results.append(f"pdf:{dest}")
                elif "text" in a:
                    if a["text"] is True: results.append("TEXTO:\n"+pg.inner_text("body")[:5000])
                    else: results.append(f"TEXTO[{a['text']}]:\n"+pg.inner_text(a["text"])[:3000])
            print("\n".join(results) if results else "acoes executadas (sem saida capturada)")
        finally:
            b.close()
            if stealth: _parar_xvfb()

if __name__=="__main__":
    if len(sys.argv)<2: print(__doc__); sys.exit(2)
    c=sys.argv[1]
    if c=="screenshot": cmd_screenshot(sys.argv[2], sys.argv[3] if len(sys.argv)>3 else None)
    elif c=="text": cmd_text(sys.argv[2])
    elif c=="html": cmd_html(sys.argv[2])
    elif c=="pdf": cmd_pdf(sys.argv[2], sys.argv[3] if len(sys.argv)>3 else None)
    elif c=="run":
        stealth = "--stealth" in sys.argv[3:]
        cmd_run(sys.argv[2], stealth=stealth)
    else: print("comando invalido"); sys.exit(2)
