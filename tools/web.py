#!/usr/bin/env python3
"""Ferramenta web GRATIS pra {{AGENTE_NAME}} (sem chave). Uso:
  python3 web.py search "consulta"       -> resultados do DuckDuckGo
  python3 web.py fetch "https://url"     -> texto limpo da pagina
  python3 web.py fetch "https://url" --tudo   -> texto limpo SEM corte
  python3 web.py fetch "https://url" --sem-firecrawl  -> nao usa o 3o degrau

Como o fetch decide o caminho (medido em 22/08/2026):
  1. tenta `requests` (barato, ~1s);
  2. se o texto vier sem prosa util (pagina renderizada por JavaScript, ou
     parede de antibot com 403/429), refaz pelo NAVEGADOR (Playwright, via
     tools/browser.py html) e usa esse resultado SE ele trouxer mais prosa;
  3. SO se os dois anteriores falharem POR BLOQUEIO (403, 429 ou parede de
     verificacao), tenta o FIRECRAWL no modo sem chave. Nunca entra por
     pagina magra, nunca por 404, nunca em pagina que respondeu bem;
  4. escreve em stderr qual caminho respondeu: "[web] requests",
     "[web] navegador" ou "[web] firecrawl". stdout continua sendo so o
     conteudo.

Por que existe: em 22/08/2026 o `fetch` respondeu 200 com texto plausivel em
duas paginas (mercotintas, maton) e a {{AGENTE_NAME}} concluiu que "nao tinha a
informacao". Uma estava CORTADA em silencio (o limite era 6000 chars, sem
aviso) e a outra dependia de JS. 200 com texto plausivel nao e prova de que
a pagina foi lida inteira.

O terceiro degrau busca a pagina pelo servidor DO FIRECRAWL, entao tudo que
passa por ali eles veem. Por isso ele nasce com uma trava de privacidade
(FIRECRAWL_PROIBIDOS + parametro sensivel + rede privada) que recusa ANTES de
chamar, e com contador de uso em FIRECRAWL_LOG, porque o plano gratis tem teto
(as fontes divergem entre 500 e 1000 paginas por mes).
"""
import re
import sys

LIMITE_DEFAULT = 12000
BROWSER = "/opt/{{AGENTE_NAME_LOWERCASE}}/tools/browser.py"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# Piso de prosa para considerar que a pagina respondeu de verdade. Calibrado
# com paginas reais em 22/08/2026 (prosa util / paragrafos):
#   claude.com/.../sf-beyond-the-basics  435 / 2   -> requests basta
#   maton.ai                            1757 / 10  -> requests basta
#   mercotintas.com.br                   946 / 2   -> requests basta
#   raiox-{{AGENTE_NAME_LOWERCASE}}.vercel.app (SPA)            0 / 0   -> so o navegador ve
# Mexer nesses numeros sem remedir as quatro paginas acima e chute.
PISO_PROSA = 300
LINK_MD = re.compile(r"\[[^\]]*\]\([^)]*\)")
SUJEIRA = re.compile(r"[\s*_#>|`\-]+")

# Pagina CURTA com uma destas frases e parede de verificacao (Cloudflare e
# afins), nao conteudo. Sem isto o navegador "conseguia" a pagina e a {{AGENTE_NAME}}
# lia o desafio como se fosse a resposta do site: aconteceu em 22/08/2026
# testando um 404 do claude.com, que voltou 403 + desafio da Cloudflare com
# aparencia de texto legitimo.
PAREDES = ["verificação de segurança", "verificacao de segurança",
           "enable javascript and cookies", "checking your browser",
           "verify you are human", "verifique se você é humano",
           "attention required", "acesso negado", "access denied",
           "just a moment", "ray id"]

# ---------------------------------------------------------------- firecrawl
FIRECRAWL_URL = "https://api.firecrawl.dev/v2/scrape"
FIRECRAWL_LOG = "/opt/{{AGENTE_NAME_LOWERCASE}}/memory/firecrawl-uso.log"

# LISTA EDITAVEL, de proposito. Nada daqui pode passar pelo servidor de
# terceiro: e sistema nosso, do Chefe, ou fornecedor onde a URL sozinha ja
# entrega contexto interno. Acrescentar dominio aqui e a forma certa de
# apertar a trava. Casa por sufixo (o dominio e qualquer subdominio dele).
FIRECRAWL_PROIBIDOS = [
    "vercel.app",       # painel Raio-X do Chefe
    "contaazul.com",
    "hubspot.com", "hubapi.com",
    "supabase.co", "supabase.com",
    "sharepoint.com",
    "google.com", "googleapis.com",
    "maton.ai",
]

# Sufixos de nome de parametro que nunca saem daqui. A comparacao tira tudo
# que nao e letra/numero antes ("x-api-key" -> "xapikey", que termina em
# "key"). Nao uso "contem" porque "?keyword=notebook" e busca legitima.
FIRECRAWL_PARAM_PROIBIDO = ("token", "key", "secret", "senha", "password", "auth")

# Sufixo de host que e rede interna por convencao, mesmo que resolva.
FIRECRAWL_SUFIXO_INTERNO = (".local", ".internal", ".intranet", ".lan",
                            ".home", ".localdomain", ".test", ".invalid")


def _e_parede(txt):
    t = txt.lower()
    return len(txt) < 3000 and any(f in t for f in PAREDES)


def _erro(msg):
    print(msg, file=sys.stderr)


def _html2texto(html):
    import html2text
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    # Sem unicode_snob o html2text troca acento por letra ASCII em silencio
    # ("voce" no lugar de "voce" com circunflexo). Medido em mercotintas:
    # 230 caracteres acentuados sem, 253 com.
    h.unicode_snob = True
    return h.handle(html)


def _medir(txt):
    """Devolve (prosa, paragrafos) ignorando linha que e so menu/link.
    Serve para separar "a pagina respondeu" de "veio so a navegacao"."""
    prosa = 0
    paras = 0
    for linha in txt.splitlines():
        s = SUJEIRA.sub(" ", LINK_MD.sub("", linha)).strip()
        if len(s) < 20:
            continue
        prosa += len(s)
        if len(s) >= 60:
            paras += 1
    return prosa, paras


def _magro(txt):
    prosa, paras = _medir(txt)
    return prosa < PISO_PROSA or paras == 0


def _via_requests(url):
    """(texto, status, problema). problema=None quando deu certo."""
    import requests
    try:
        r = requests.get(url, timeout=(10, 25), headers={"User-Agent": UA})
    except requests.exceptions.Timeout:
        return "", None, "tempo esgotado (10s para conectar, 25s para ler)"
    except requests.exceptions.SSLError as e:
        return "", None, f"certificado TLS recusado: {e.__class__.__name__}"
    except requests.exceptions.ConnectionError as e:
        alvo = "nome nao resolveu (DNS)" if "Name or service not known" in str(e) else "conexao recusada ou caiu"
        return "", None, f"nao consegui conectar: {alvo}"
    except requests.exceptions.RequestException as e:
        return "", None, f"{e.__class__.__name__}: {e}"
    if not r.encoding or "charset" not in (r.headers.get("content-type") or "").lower():
        r.encoding = r.apparent_encoding or r.encoding
    tipo = (r.headers.get("content-type") or "").lower()
    if "html" not in tipo and "xml" not in tipo and "text" not in tipo:
        return r.text, r.status_code, None if r.ok else f"HTTP {r.status_code}"
    return _html2texto(r.text), r.status_code, None if r.ok else f"HTTP {r.status_code}"


def _via_navegador(url):
    """Renderiza com Playwright reusando tools/browser.py (nao duplico o
    Playwright aqui de proposito: quem cuida de antibot/UA/retry e ele).
    Devolve texto ou None."""
    import subprocess
    try:
        p = subprocess.run([sys.executable, BROWSER, "html", url],
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        _erro("[web] navegador: tempo esgotado (180s)")
        return None
    saida = p.stdout or ""
    if p.returncode != 0 or not saida.strip():
        detalhe = (p.stderr or "").strip().splitlines()
        _erro("[web] navegador falhou: " + (detalhe[-1] if detalhe else f"codigo {p.returncode}"))
        return None
    if saida.startswith("BLOQUEADO por antibot"):
        _erro("[web] navegador: bloqueado por antibot depois de 4 tentativas")
        return None
    return _html2texto(saida)


def _param_sensivel(nome):
    n = re.sub(r"[^a-z0-9]", "", nome.lower())
    return any(n == p or n.endswith(p) for p in FIRECRAWL_PARAM_PROIBIDO)


def _host_privado(host):
    """True se o nome resolve para rede privada/loopback/link-local, ou se nao
    resolve (nao consigo provar que e publico, entao nao mando para fora)."""
    import ipaddress
    import socket
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True, "o nome nao resolve daqui"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return True, f"resolve para endereco de rede privada ({ip})"
    return False, ""


def _firecrawl_recusa(url):
    """Devolve o motivo da recusa, ou None quando pode chamar.
    Roda ANTES de qualquer requisicao: o Firecrawl busca a pagina pelo
    servidor dele, entao URL recusada aqui nunca chega la."""
    from urllib.parse import parse_qsl, urlsplit
    try:
        u = urlsplit(url)
    except ValueError as e:
        return f"URL invalida ({e})"
    if u.scheme.lower() not in ("http", "https"):
        return f"esquema '{u.scheme or '(vazio)'}' nao e http/https publico"
    if u.username or u.password or "@" in u.netloc:
        return "a URL carrega credencial embutida (usuario:senha@)"
    host = (u.hostname or "").lower().rstrip(".")
    if not host:
        return "URL sem host"
    for nome, _valor in parse_qsl(u.query, keep_blank_values=True):
        if _param_sensivel(nome):
            return f"parametro de consulta sensivel na URL ('{nome}')"
    if "." not in host:
        return f"host '{host}' nao tem dominio (parece maquina interna)"
    if host.endswith(FIRECRAWL_SUFIXO_INTERNO):
        return f"host '{host}' tem sufixo de rede interna"
    for proibido in FIRECRAWL_PROIBIDOS:
        if host == proibido or host.endswith("." + proibido):
            return f"'{host}' esta na lista de dominios proibidos (FIRECRAWL_PROIBIDOS)"
    privado, detalhe = _host_privado(host)
    if privado:
        return f"host '{host}' {detalhe}"
    return None


def _firecrawl_registrar(host, ok):
    """Uma linha por chamada: data, host (NUNCA a URL inteira, que pode
    carregar parametro de busca), e se deu certo. Depois imprime em stderr
    quantas chamadas ja foram feitas no mes corrente."""
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc)
    mes = agora.strftime("%Y-%m")
    linha = f"{agora.strftime('%Y-%m-%dT%H:%M:%SZ')}\t{host}\t{'ok' if ok else 'falha'}\n"
    try:
        with open(FIRECRAWL_LOG, "a", encoding="utf-8") as f:
            f.write(linha)
    except OSError as e:
        _erro(f"[web] AVISO: nao consegui gravar {FIRECRAWL_LOG}: {e}")
        return
    try:
        with open(FIRECRAWL_LOG, encoding="utf-8") as f:
            n = sum(1 for l in f if l.startswith(mes))
    except OSError:
        return
    _erro(f"[web] firecrawl: {n} chamada(s) em {mes} "
          "(teto do plano gratis fica entre 500 e 1000/mes, as fontes divergem)")


def _via_firecrawl(url):
    """Terceiro degrau. So deve ser chamado depois de bloqueio comprovado.
    Devolve o markdown ou None."""
    from urllib.parse import urlsplit
    motivo = _firecrawl_recusa(url)
    if motivo:
        _erro(f"[web] firecrawl NAO chamado (trava de privacidade): {motivo}. "
              "Nenhuma requisicao saiu daqui.")
        return None
    import requests
    host = (urlsplit(url).hostname or "").lower()
    _erro(f"[web] tentando o firecrawl (modo sem chave) para {host}")
    try:
        r = requests.post(FIRECRAWL_URL, timeout=(10, 180),
                          headers={"Content-Type": "application/json"},
                          json={"url": url, "formats": ["markdown"]})
    except requests.exceptions.RequestException as e:
        _firecrawl_registrar(host, False)
        _erro(f"[web] firecrawl falhou na conexao: {e.__class__.__name__}")
        return None
    if not r.ok:
        _firecrawl_registrar(host, False)
        _erro(f"[web] firecrawl devolveu HTTP {r.status_code} "
              "(pode ser teto do plano gratis, limite por minuto, ou o site tambem barrou eles)")
        return None
    try:
        j = r.json()
    except ValueError:
        _firecrawl_registrar(host, False)
        _erro("[web] firecrawl devolveu resposta que nao e JSON")
        return None
    md = ((j.get("data") or {}).get("markdown") or "") if j.get("success") else ""
    if not md.strip():
        _firecrawl_registrar(host, False)
        _erro(f"[web] firecrawl respondeu sem conteudo (success={j.get('success')})")
        return None
    if _e_parede(md):
        _firecrawl_registrar(host, False)
        _erro("[web] firecrawl tambem caiu em parede de verificacao")
        return None
    _firecrawl_registrar(host, True)
    return md


def _tentar_firecrawl(url, usar, limite):
    """Imprime o conteudo e devolve True se o terceiro degrau resolveu."""
    if not usar:
        _erro("[web] terceiro degrau desligado por --sem-firecrawl")
        return False
    fc = _via_firecrawl(url)
    if not fc:
        return False
    _erro("[web] firecrawl")
    _mostrar(fc, limite)
    return True


def _mostrar(txt, limite):
    txt = txt.strip("\n")
    if limite is None or len(txt) <= limite:
        print(txt)
        return
    print(txt[:limite])
    print(f"\n[web] CORTADO em {limite} caracteres. Faltam {len(txt) - limite} "
          f"(pagina tem {len(txt)}). Use --tudo para ler o resto.")


def do_search(q, n=6):
    try:
        from ddgs import DDGS
        with DDGS() as d:
            resultados = list(d.text(q, max_results=n))
    except Exception as e:
        _erro(f"[web] ERRO na busca: {e.__class__.__name__}: {e}")
        sys.exit(3)
    if not resultados:
        _erro("[web] busca sem resultado (pode ser limite do DuckDuckGo, nao ausencia de conteudo)")
        return
    for i, r in enumerate(resultados, 1):
        print(f"{i}. {r.get('title','')}\n   {r.get('href','')}\n   {r.get('body','')[:200]}\n")


def do_fetch(url, limite=LIMITE_DEFAULT, firecrawl=True):
    txt, status, problema = _via_requests(url)

    # 403/429 nao e "a pagina nao tem o conteudo": e o site recusando este
    # cliente. Tenta o navegador (UA e fingerprint de browser de verdade) e,
    # se tambem falhar, o firecrawl. Se nem ele passar, avisa que o bloqueio
    # pode ser do IP deste servidor.
    if status in (403, 429):
        _erro(f"[web] HTTP {status} no caminho simples, tentando pelo navegador")
        nav = _via_navegador(url)
        if nav and _e_parede(nav):
            _erro("[web] navegador tambem caiu em parede de verificacao (Cloudflare e afins)")
            nav = None
        if nav and not _magro(nav):
            _erro("[web] navegador")
            _mostrar(nav, limite)
            return
        if _tentar_firecrawl(url, firecrawl, limite):
            return
        nome = "403 Forbidden" if status == 403 else "429 Too Many Requests"
        _erro(f"[web] ERRO {nome}: o site esta recusando este cliente. "
              "Pode ser bloqueio do IP DESTE SERVIDOR (nao adianta repetir, "
              "precisa de outra saida de rede) ou exigencia de login.")
        sys.exit(4)

    if problema and problema.startswith("HTTP"):
        # 404 e afins: a pagina respondeu, dizendo que nao existe. Nao e
        # bloqueio, entao o firecrawl NAO entra aqui.
        _erro(f"[web] ERRO {problema} em {url}")
        prosa, _ = _medir(txt)
        if prosa >= 200:
            _erro("[web] o corpo da resposta de erro vai abaixo (pode explicar o motivo)")
            _mostrar(txt, limite)
        sys.exit(4)

    if problema:
        _erro(f"[web] ERRO {problema} em {url}")
        sys.exit(3)

    parede = _e_parede(txt)
    if not parede and not _magro(txt):
        _erro("[web] requests")
        _mostrar(txt, limite)
        return

    # Pouca prosa: pagina montada por JavaScript, so o menu chegou, ou parede
    # de verificacao. Nos tres casos o navegador pode ver o que o requests nao ve.
    # O firecrawl so entra no caso PAREDE (bloqueio), nunca por pagina magra.
    prosa, paras = _medir(txt)
    motivo = ("parede de verificacao no caminho simples" if parede else
              f"caminho simples trouxe pouca prosa ({prosa} chars, {paras} paragrafos)")
    _erro(f"[web] {motivo}, refazendo pelo navegador")
    nav = _via_navegador(url)
    if nav is not None and _e_parede(nav):
        _erro("[web] parede de verificacao tambem no navegador (Cloudflare e afins)")
        if _tentar_firecrawl(url, firecrawl, limite):
            return
        _erro("[web] ERRO nao consegui passar da parede de verificacao. "
              "O site pode estar bloqueando o IP DESTE SERVIDOR: repetir nao resolve, "
              "precisa de outra saida de rede.")
        sys.exit(4)
    if nav is None:
        if parede:
            if _tentar_firecrawl(url, firecrawl, limite):
                return
            _erro("[web] ERRO parede de verificacao e o navegador nao respondeu. "
                  "Nao consegui ler esta pagina daqui.")
            sys.exit(4)
        _erro("[web] requests (navegador nao respondeu; o que vai abaixo pode estar incompleto)")
        _mostrar(txt, limite)
        return
    prosa_nav, _ = _medir(nav)
    # Empate em prosa (tipico de tela de login/app, que e toda rotulo curto)
    # se decide pelo tamanho bruto: quem renderizou mais texto ganha.
    if prosa_nav > prosa or (prosa_nav == prosa and len(nav.strip()) > len(txt.strip())):
        _erro(f"[web] navegador (prosa {prosa} -> {prosa_nav}, texto {len(txt.strip())} -> {len(nav.strip())})")
        _mostrar(nav, limite)
    elif parede and _magro(nav):
        # Continua bloqueado: o navegador nao trouxe nada melhor que a parede.
        if _tentar_firecrawl(url, firecrawl, limite):
            return
        _erro("[web] ERRO parede de verificacao no caminho simples e o navegador "
              "nao trouxe mais nada. Nao consegui ler esta pagina daqui.")
        sys.exit(4)
    else:
        _erro(f"[web] requests (navegador tentado e trouxe menos: prosa {prosa_nav}, "
              f"texto {len(nav.strip())}; a pagina pode exigir login ou o conteudo "
              "estar em outra URL)")
        _mostrar(txt, limite)


if __name__ == "__main__":
    argv = sys.argv[1:]
    tudo = "--tudo" in argv
    firecrawl = "--sem-firecrawl" not in argv
    argv = [a for a in argv if a not in ("--tudo", "--sem-firecrawl")]
    if len(argv) < 2:
        _erro('uso: web.py search "q" | web.py fetch "url" [--tudo] [--sem-firecrawl]')
        sys.exit(2)
    if argv[0] == "search":
        do_search(argv[1])
    elif argv[0] == "fetch":
        do_fetch(argv[1], None if tudo else LIMITE_DEFAULT, firecrawl)
    else:
        _erro(f'acao invalida: {argv[0]} (use search ou fetch)')
        sys.exit(2)
