#!/usr/bin/env python3
"""
produtor_radar.py — radar de atividade comercial PÚBLICA de produtores digitais.

Pergunta que responde: o produtor parou de vender, ou parou de vender COM A TMB?
O modelo de churn diz quem vai parar. Este script cata sinal público de "pra onde"
ele foi: trocou de plataforma de checkout, parou de anunciar, continua ativo, ou
não deixou rastro nenhum encontrável.

LIMITE DE LGPD (não negociável, ler antes de editar):
  Só ATIVIDADE COMERCIAL PÚBLICA: site de vendas, plataforma de checkout,
  biblioteca de anúncios da Meta, cadência de post em rede social oficial de
  negócio, reclamação pública no Reclame Aqui.
  NUNCA: endereço, telefone pessoal, e-mail pessoal, CPF, dado de família ou
  qualquer coisa que identifique a pessoa física fora do papel de produtor.
  NUNCA login, NUNCA credencial, NUNCA burlar bloqueio/captcha/paywall.
  Um coletor que só funciona atrás de login para este script é um coletor que
  não existe: ele escreve nao_verificavel, não tenta contornar.

REGRA DA CASA: coletor que não conseguiu medir escreve "nao_verificavel" com o
motivo. Nunca chuta, nunca inventa valor. Um campo vazio por falha de rede não
é a mesma coisa que "produtor sem essa atividade", e o JSON sempre distingue
os dois.

USO
  Produtor avulso:
    python3 produtor_radar.py --produtor "Nome do Produtor" \\
        [--site https://site-dele.com.br] [--instagram handle] \\
        [--youtube handle_ou_UC...channel_id]

  Top N do modelo de churn (lê previsoes_atuais_6m_base_grande.csv, desc por
  score_churn_6m):
    python3 produtor_radar.py --top 10 [--csv /caminho/outro.csv]

  Saída estruturada (em vez da tabela):
    ... --json

SAÍDA
  - JSON append-only por produtor em workspace/churn/osint/<slug>.json.
    Cada execução ACRESCENTA um registro com timestamp; nada é sobrescrito.
    O valor está em comparar execuções, não na foto isolada de hoje — por
    isso a tabela de stdout mostra "mudou desde a última vez".
  - Tabela no stdout, uma linha por produtor, com veredito:
    trocou_plataforma | venda_por_whatsapp | ativo | parou_de_anunciar |
    ativo_sem_checkout_publico | sem_rastro
    Quando dois fatos coexistem (ex: home aponta pro WhatsApp E existe
    página de produto ativa numa plataforma concorrente), o veredito
    principal é o de evidência mais forte e o outro fato aparece em
    "sinais_secundarios" — nenhum dos dois é descartado.

ESTABILIDADE ENTRE EXECUÇÕES (duas rodadas de correção em 12/08/2026):
  - Rodada 1: o site do produtor era redescoberto por busca a cada
    execução, e busca é roleta — mesmo produtor, 104s de intervalo,
    veredito mudou de trocou_plataforma pra ativo sem nada ter mudado no
    mundo. Corrigido fixando o site no histórico.
  - Rodada 2 (mais grave): fixar UM site quebrou o Cardi Nigro — ele vende
    na Hotmart (achado na 1ª rodada, prova conferida na mão) mas tem site
    próprio também, e a 2ª rodada fixou a home dele, jogando fora a
    evidência que respondia a pergunta do Chefe. Um produtor não tem "um
    site": tem site próprio E página(s) de produto em plataforma. Agora é
    uma LISTA de evidências (`checkout.evidencias`), cada uma fixada e
    reverificada INDIVIDUALMENTE — nunca substituída por outra, só marcada
    caida_404 (prova de 404) ou expirada_sem_reaparecer (depois de
    LIMITE_RODADAS_SEM_APARECER rodadas seguidas sem confirmar).
  - "mudou_desde_ultima" nunca compara contra nao_verificavel/None, nem
    contra o texto relativo do Reclame Aqui ("há N dias", que muda todo dia
    só pelo tempo passar) — só o resumo agregado (plataformas ativas,
    whatsapp, site próprio, booleano de recência) entra na comparação.

AGENDAMENTO
  Este script não instala cron nenhum. Sugestão pra rodar sozinho contra os
  top produtores em risco (decisão de frequência é do Chefe):
    0 7 * * 1 cd /opt/{{AGENTE_NAME_LOWERCASE}} && /usr/bin/python3 tools/produtor_radar.py --top 15 --json >> workspace/churn/osint/execucao_semanal.log 2>&1
  (toda segunda 07:00 UTC = 04:00 Brasília — ajustar se quiser outro horário
  ou frequência; o servidor roda em UTC, ver CLAUDE.md.)
"""
import argparse, csv, json, os, re, subprocess, sys, time, unicodedata
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
WORKSPACE_CHURN = Path("/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/churn")
OSINT_DIR = WORKSPACE_CHURN / "osint"
CSV_PADRAO = WORKSPACE_CHURN / "previsoes_atuais_6m_base_grande.csv"
PLATAFORMAS_JSON = TOOLS_DIR / "produtor_radar_plataformas.json"

RATE_LIMIT_SEG = 2.0   # pausa educada entre chamadas externas (busca/fetch/browser)
TIMEOUT_SUBPROC = 60   # segundos, pra qualquer chamada a web.py/browser.py

DOMINIOS_IGNORAR_COMO_SITE = [
    "instagram.com", "facebook.com", "youtube.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com", "wikipedia.org", "google.com",
    "google.com.br", "duckduckgo.com", "linktr.ee", "amazon.com",
    "mercadolivre.com", "olx.com.br", "pinterest.com", "medium.com",
    "quora.com", "reddit.com", "threads.net", "glassdoor.com",
    "crunchbase.com", "forbes.com", "uol.com.br", "globo.com",
    "terra.com.br", "yahoo.com", "spotify.com", "apple.com",
    "play.google.com", "transfermarkt.com",
]
# Descoberta de site e busca-e-filtra, best effort: pra gente publica com
# muita cobertura de midia, o primeiro resultado que passa pelo filtro pode
# ser noticia/perfil, nao o site de vendas. Blacklist cobre agregador
# conhecido, mas nao cobre todo portal de noticia que existe. Quando o nome
# do site vier claramente errado, usar --site manual (modo avulso).

_ultima_chamada_externa = 0.0


def _throttle():
    """Rate limit educado: nunca duas chamadas externas em menos de RATE_LIMIT_SEG."""
    global _ultima_chamada_externa
    agora = time.monotonic()
    espera = RATE_LIMIT_SEG - (agora - _ultima_chamada_externa)
    if espera > 0:
        time.sleep(espera)
    _ultima_chamada_externa = time.monotonic()


def agora_iso():
    # servidor roda em UTC (ver CLAUDE.md); grava explícito pra não confundir
    # quem ler o JSON depois.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(nome):
    n = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    n = re.sub(r"[^a-zA-Z0-9]+", "-", n).strip("-").lower()
    return n or "sem-nome"


def carregar_plataformas():
    with open(PLATAFORMAS_JSON, encoding="utf-8") as f:
        dados = json.load(f)
    dados.pop("_comentario", None)
    extra_tmb = os.environ.get("TMB_CHECKOUT_DOMINIOS", "").strip()
    if extra_tmb:
        dados["tmb"] = list(dict.fromkeys(dados.get("tmb", []) + [
            d.strip() for d in extra_tmb.split(",") if d.strip()
        ]))
    return dados


# --------------------------------------------------------------------------
# Chamadas às ferramentas já existentes (web.py, browser.py), via subprocess.
# Isoladas e tolerantes: qualquer excecao/timeout devolve None, nunca propaga.
# --------------------------------------------------------------------------

def _rodar(cmd):
    _throttle()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=TIMEOUT_SUBPROC)
        if r.returncode != 0:
            return None, (r.stderr or r.stdout or "erro desconhecido")[:300]
        return r.stdout, None
    except subprocess.TimeoutExpired:
        return None, f"timeout apos {TIMEOUT_SUBPROC}s"
    except Exception as e:
        return None, f"exececao: {e}"


def web_search(query, n=6):
    out, erro = _rodar(["python3", str(TOOLS_DIR / "web.py"), "search", query])
    if out is None:
        return [], erro
    resultados = []
    for linha in out.splitlines():
        linha = linha.strip()
        m = re.match(r"^https?://", linha)
        if m:
            resultados.append(linha)
    return resultados[:n], None


def web_fetch(url):
    return _rodar(["python3", str(TOOLS_DIR / "web.py"), "fetch", url])


def browser_html(url):
    return _rodar(["python3", str(TOOLS_DIR / "browser.py"), "html", url])


def browser_text(url):
    return _rodar(["python3", str(TOOLS_DIR / "browser.py"), "text", url])


def http_get_bruto(url):
    """Fetch raro e direto, sem JS, pra casos simples (mais barato que abrir
    navegador). So usado como PRIMEIRA tentativa; se vier vazio/bloqueado, o
    coletor cai pro browser.py html."""
    import requests
    _throttle()
    try:
        r = requests.get(url, timeout=20,
                          headers={"User-Agent": "Mozilla/5.0"})
        return r.text, None
    except Exception as e:
        return None, str(e)


# --------------------------------------------------------------------------
# Coletor 1+2 (o mais valioso): evidências de venda — site próprio E toda
# página de produto em plataforma de checkout.
#
# Corrigido em 12/08/2026 depois de bug real reportado pela {{AGENTE_NAME}} no Cardi
# Nigro: o radar tratava "site do produtor" como UM valor. A primeira
# rodada achou "hotmart.com/pt-br/marketplace/produtos/..." (a prova de que
# ele vende na Hotmart, confirmada na mão pela {{AGENTE_NAME}}), a segunda rodada a
# busca devolveu "cardinigro.com.br" (a home dele) em primeiro lugar, e o
# radar TROCOU a evidência boa pela home, ficando estável na resposta
# ERRADA pra sempre ("ativo" em vez de "trocou_plataforma"). Um produtor não
# tem "um site": tem site próprio E página(s) de produto em plataforma, e a
# pergunta do Chefe ("vende com a TMB ou com a concorrência?") é respondida
# pela segunda, não pela primeira. Por isso agora é uma LISTA de evidências,
# cada uma fixada e reverificada individualmente, nunca substituída.
# --------------------------------------------------------------------------

# Link de WhatsApp como CTA de compra. Achado real em 12/08/2026 (Oficina do
# Trader, Grupo Sou): produtor vende por WhatsApp, sem plataforma de
# checkout nenhuma. Isso NAO e falha de deteccao, e modelo de negocio: quem
# vende assim e invisivel pra deteccao de checkout tradicional, e essa
# informacao importa pra quem for ligar (o script pra vendas la e outro).
WHATSAPP_PADRAO = re.compile(r"(?:wa\.me/\d|api\.whatsapp\.com/send)", re.IGNORECASE)


def _buscar_html_pagina(url):
    """So a parte de rede: devolve (html, origem, erro). origem e
    'http_direto' ou 'browser_renderizado'. html=None so quando as DUAS
    tentativas falharam de fato (timeout, 404, bloqueio) — isso e usado pra
    decidir se vale a pena redescobrir o site, "desconhecida" no checkout
    (plataforma nao reconhecida) NAO conta como falha de site."""
    if not url:
        return None, None, "sem url"
    html, erro_http = http_get_bruto(url)
    origem = "http_direto"
    if not html or len(html) < 500:
        html, erro_browser = browser_html(url)
        origem = "browser_renderizado"
        if not html:
            return None, origem, f"http: {erro_http}; browser: {erro_browser}"
    return html, origem, None


def detectar_checkout_de_html(html, origem, plataformas):
    """Recebe HTML ja buscado (nunca faz rede sozinho) e classifica."""
    html_l = html.lower()
    encontradas = []
    for plataforma, dominios in plataformas.items():
        for dominio in dominios:
            if dominio.lower() in html_l:
                encontradas.append(plataforma)
                break

    if encontradas:
        return {"ok": True, "valor": sorted(set(encontradas)), "fonte": origem}

    if WHATSAPP_PADRAO.search(html_l):
        return {"ok": True, "valor": "whatsapp", "fonte": origem,
                "motivo": "nenhuma plataforma de checkout catalogada, mas o "
                          "link dominante de compra e wa.me/api.whatsapp: "
                          "produtor vende por WhatsApp, nao por checkout"}

    return {"ok": True, "valor": "desconhecida", "fonte": origem,
            "motivo": f"pagina carregou ({origem}) mas nenhum dominio de "
                      f"checkout conhecido nem link de WhatsApp apareceu no "
                      f"HTML; pode ser checkout proprio nao catalogado ou "
                      f"botao so aparece depois de interacao (carrinho/popup)"}


LIMITE_RODADAS_SEM_APARECER = 3  # depois disso sem confirmar, marca expirada


def extrair_plataforma_de_url(url, plataformas):
    """Domínio da própria URL bate com plataforma conhecida? Uma URL de
    marketplace (ex: hotmart.com/pt-br/marketplace/produtos/xyz) É, ela
    mesma, a evidência — não precisa abrir a página pra confirmar."""
    dominio = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    ul = url.lower()
    for plataforma, dominios in plataformas.items():
        for d in dominios:
            dl = d.lower()
            if dl in dominio or dl in ul:
                return plataforma
    return None


def _status_http(url):
    """So pra reverificar evidencia JA conhecida (nao pro fetch inicial,
    que usa _buscar_html_pagina). 404 explicito e o UNICO gatilho pra
    aposentar a evidencia na hora; qualquer outro erro (timeout, DNS, 5xx)
    e inconclusivo e cai no contador de rodadas — pode ser instabilidade
    passageira do site do produtor OU da plataforma, nao prova que ele
    parou de vender la."""
    import requests
    _throttle()
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"},
                          allow_redirects=True)
        return r.status_code, None
    except Exception as e:
        return None, str(e)


def _evidencias_embutidas(classificacao, pagina_url):
    """Converte o resultado de detectar_checkout_de_html (lista de
    plataformas encontradas como LINK dentro da pagina, ou 'whatsapp') em
    evidencias tipo 'checkout_embutido'. url = a pagina onde o link foi
    achado (a home do produtor), nao um produto separado."""
    valor = classificacao.get("valor")
    out = []
    if isinstance(valor, list):
        for p in valor:
            out.append({"url": pagina_url, "tipo": "checkout_embutido", "plataforma": p})
    elif valor == "whatsapp":
        out.append({"url": pagina_url, "tipo": "checkout_embutido", "plataforma": "whatsapp"})
    return out


def descobrir_candidatos(nome, plataformas, site_hint=None):
    """Evidencias FRESCAS desta rodada (antes de mesclar com o historico).
    Devolve (candidatos, erro_busca) — um produtor pode ter site proprio E
    pagina de produto em plataforma ao mesmo tempo, e os dois importam.
    erro_busca != None quando a BUSCA falhou (ex: rate limit do DuckDuckGo,
    ja aconteceu de verdade rodando este script varias vezes em sequencia
    curta) — isso e diferente de "buscou e nao achou nada", e o agregado
    precisa dizer qual dos dois aconteceu, nunca confundir os dois."""
    if site_hint:
        return [{"url": site_hint, "tipo": "site_proprio", "plataforma": None}], None
    resultados, erro = web_search(f'"{nome}" site oficial curso')
    if erro:
        return [], erro
    candidatos = []
    site_proprio_escolhido = False
    for url in resultados:
        plataforma = extrair_plataforma_de_url(url, plataformas)
        if plataforma:
            url_limpa = url.split("?")[0].split("#")[0]
            candidatos.append({"url": url_limpa, "tipo": "pagina_produto_marketplace",
                                "plataforma": plataforma})
            continue
        if site_proprio_escolhido:
            continue
        dominio = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
        if any(d in dominio for d in DOMINIOS_IGNORAR_COMO_SITE):
            continue
        candidatos.append({"url": url, "tipo": "site_proprio", "plataforma": None})
        site_proprio_escolhido = True
    return candidatos, None


def ultimas_evidencias(historico):
    """Lista de evidencias do registro mais recente que tiver alguma (nunca
    fica vazia so porque a ultima rodada nao achou nada novo — o historico
    e a fonte da verdade acumulada, nao a foto da ultima rodada)."""
    for registro in reversed(historico):
        evid = registro.get("checkout", {}).get("evidencias")
        if evid is not None:
            return evid
    return []


def _agregar_checkout(evidencias, erro_busca=None):
    if not evidencias:
        if erro_busca:
            # nao e "buscou e nao achou nada" -- a busca em si falhou (ex:
            # rate limit do DuckDuckGo, ja aconteceu de verdade). Bug real
            # corrigido em 12/08/2026: sem essa distincao, um erro de rede
            # virava indistinguivel de "produtor sem rastro nenhum".
            return {"ok": False, "plataformas_ativas": [], "tem_whatsapp_ativo": False,
                    "site_proprio_url": None,
                    "motivo": f"a busca por evidencia falhou (nao deu pra nem "
                              f"tentar achar nada nesta rodada): {erro_busca}"}
        return {"ok": False, "plataformas_ativas": [], "tem_whatsapp_ativo": False,
                "site_proprio_url": None,
                "motivo": "nenhuma evidencia de venda encontrada (nem site "
                          "proprio nem pagina de produto em plataforma)"}
    ativas = [e for e in evidencias if e.get("status") == "ativa"]
    plataformas_ativas = sorted({e["plataforma"] for e in ativas
                                  if e.get("plataforma") and e["plataforma"] != "whatsapp"})
    tem_whatsapp_ativo = any(e.get("plataforma") == "whatsapp" for e in ativas)
    site_proprio_url = next((e["url"] for e in ativas if e["tipo"] == "site_proprio"), None)
    return {"ok": True, "plataformas_ativas": plataformas_ativas,
            "tem_whatsapp_ativo": tem_whatsapp_ativo, "site_proprio_url": site_proprio_url}


def coletar_evidencias_de_venda(nome, site_hint, plataformas, historico):
    """Substitui o antigo "site + checkout de uma URL so". Reverifica cada
    evidencia conhecida INDIVIDUALMENTE (nunca joga fora a que ja tinha:
    só marca caida_404 com prova de 404, ou expirada_sem_reaparecer depois
    de LIMITE_RODADAS_SEM_APARECER rodadas seguidas sem confirmar), e só
    então busca candidato novo. Devolve (evidencias_completas, agregado)."""
    agora = agora_iso()
    mapa = {(e["url"], e.get("plataforma")): dict(e) for e in ultimas_evidencias(historico)}

    # 1) reverificar cada evidencia ATIVA conhecida (nunca gasta rede de
    #    novo em quem ja foi aposentada — caida_404/expirada ficam quietas)
    for chave, ev in list(mapa.items()):
        if ev.get("status") != "ativa":
            continue
        url = ev["url"]
        if ev["tipo"] == "site_proprio":
            html, origem, erro_fetch = _buscar_html_pagina(url)
            if html is not None:
                ev["ultima_vez_vista"] = agora
                ev["rodadas_seguidas_sem_aparecer"] = 0
                classif = detectar_checkout_de_html(html, origem, plataformas)
                for extra in _evidencias_embutidas(classif, url):
                    k2 = (extra["url"], extra["plataforma"])
                    if k2 in mapa:
                        mapa[k2]["ultima_vez_vista"] = agora
                        mapa[k2]["rodadas_seguidas_sem_aparecer"] = 0
                        mapa[k2]["status"] = "ativa"
                    else:
                        mapa[k2] = {**extra, "primeira_vez_vista": agora,
                                    "ultima_vez_vista": agora,
                                    "rodadas_seguidas_sem_aparecer": 0, "status": "ativa"}
            else:
                ev["rodadas_seguidas_sem_aparecer"] = ev.get("rodadas_seguidas_sem_aparecer", 0) + 1
                if ev["rodadas_seguidas_sem_aparecer"] >= LIMITE_RODADAS_SEM_APARECER:
                    ev["status"] = "expirada_sem_reaparecer"
                    ev["motivo_expiracao"] = f"site nao respondeu por {LIMITE_RODADAS_SEM_APARECER} rodadas seguidas: {erro_fetch}"
        elif ev["tipo"] == "pagina_produto_marketplace":
            status_code, erro_http = _status_http(url)
            if status_code == 404:
                ev["status"] = "caida_404"
                ev["motivo_expiracao"] = "pagina retornou 404 (produto tirado do ar, confirmado)"
            elif status_code is not None and 200 <= status_code < 400:
                ev["ultima_vez_vista"] = agora
                ev["rodadas_seguidas_sem_aparecer"] = 0
            else:
                # timeout, DNS, 5xx: inconclusivo, NAO prova que saiu do ar
                ev["rodadas_seguidas_sem_aparecer"] = ev.get("rodadas_seguidas_sem_aparecer", 0) + 1
                if ev["rodadas_seguidas_sem_aparecer"] >= LIMITE_RODADAS_SEM_APARECER:
                    ev["status"] = "expirada_sem_reaparecer"
                    ev["motivo_expiracao"] = f"pagina inacessivel por {LIMITE_RODADAS_SEM_APARECER} rodadas seguidas (nao e 404): {erro_http or status_code}"
        # tipo "checkout_embutido" nao tem vida propria: e derivado da
        # reverificacao do site_proprio acima, atualiza junto com ele.

    # 2) buscar candidato NOVO. So usa --site (hint) pra achar site proprio
    #    se AINDA nao tiver nenhum na lista — senao o hint nao teria efeito
    #    depois da primeira vez, o que e o comportamento certo (hint so
    #    importa na largada).
    tem_site_proprio = any(e["tipo"] == "site_proprio" for e in mapa.values())
    if tem_site_proprio:
        candidatos_brutos, erro_busca = descobrir_candidatos(nome, plataformas)
        candidatos = [c for c in candidatos_brutos if c["tipo"] != "site_proprio"]
    else:
        candidatos, erro_busca = descobrir_candidatos(nome, plataformas, site_hint=site_hint)

    for c in candidatos:
        chave = (c["url"], c.get("plataforma"))
        if chave in mapa:
            mapa[chave]["ultima_vez_vista"] = agora
            mapa[chave]["rodadas_seguidas_sem_aparecer"] = 0
            mapa[chave]["status"] = "ativa"
            continue
        mapa[chave] = {**c, "primeira_vez_vista": agora, "ultima_vez_vista": agora,
                        "rodadas_seguidas_sem_aparecer": 0, "status": "ativa"}
        if c["tipo"] == "site_proprio":
            html, origem, erro_fetch = _buscar_html_pagina(c["url"])
            if html is None:
                mapa[chave]["status"] = "expirada_sem_reaparecer"
                mapa[chave]["motivo_expiracao"] = f"site recem-descoberto nao respondeu: {erro_fetch}"
            else:
                classif = detectar_checkout_de_html(html, origem, plataformas)
                for extra in _evidencias_embutidas(classif, c["url"]):
                    k2 = (extra["url"], extra["plataforma"])
                    if k2 not in mapa:
                        mapa[k2] = {**extra, "primeira_vez_vista": agora,
                                    "ultima_vez_vista": agora,
                                    "rodadas_seguidas_sem_aparecer": 0, "status": "ativa"}

    evidencias = list(mapa.values())
    return evidencias, _agregar_checkout(evidencias, erro_busca)


# --------------------------------------------------------------------------
# Coletor 3: Biblioteca de Anúncios da Meta (pública, sem login)
# --------------------------------------------------------------------------


# Testado em 12/08/2026: o parametro "&q=" na URL, sozinho, ACIONA a busca
# na maioria das vezes (confirmado contra "Hotmart": ~14.000 resultados,
# cards reais). Mas em rodada real contra 5 produtores a {{AGENTE_NAME}} mediu 4
# falhas em 5 com "layout nao bateu" — provavel banner de cookie/consent
# interceptando na primeira visita daquela sessao de navegador (cada
# subprocess abre um Chromium novo, sem cookie de consentimento salvo) ou
# espera curta demais pro JS pesado da lib terminar de montar a pagina.
# Por isso o fetch usa "browser.py run" com wait maior + "click_if_exists"
# no botao de cookie, em vez do "browser.py text" simples com 3.5s fixo.
_META_ADS_LANDING_FINGERPRINT = "para encontrar um anúncio, pesquise por palavras-chave"


def _meta_ads_buscar_texto(nome):
    import tempfile
    url = ("https://www.facebook.com/ads/library/?active_status=active"
           f"&ad_type=all&country=BR&q={nome.replace(' ', '%20')}"
           "&media_type=all")
    acoes = [
        {"goto": url},
        {"wait": 2000},
        {"click_if_exists": "button:has-text('Permitir todos os cookies')"},
        {"click_if_exists": "button:has-text('Aceitar todos os cookies')"},
        {"click_if_exists": "button:has-text('Allow all cookies')"},
        {"click_if_exists": "button:has-text('Accept all')"},
        {"wait": 4500},
        {"text": True},
    ]
    fd, caminho = tempfile.mkstemp(suffix=".json", dir="/tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(acoes, f)
        out, erro = _rodar(["python3", str(TOOLS_DIR / "browser.py"), "run", caminho])
    finally:
        try: os.unlink(caminho)
        except OSError: pass
    if out is None:
        return None, erro
    m = re.search(r"TEXTO:\n(.*)", out, re.S)
    return (m.group(1) if m else out), None


def _normalizar(texto):
    n = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", n).strip().lower()


def checar_meta_ads(nome):
    texto, erro = _meta_ads_buscar_texto(nome)
    if not texto:
        return {"ok": False, "valor": None,
                "motivo": f"biblioteca de anuncios nao carregou: {erro}"}
    t = texto.lower()
    if _META_ADS_LANDING_FINGERPRINT in t:
        return {"ok": False, "valor": None,
                "motivo": "a busca nao acionou de fato (pagina caiu na "
                          "landing/instrucional, mesmo apos tentar fechar "
                          "banner de cookie e esperar mais); nao afirmar "
                          "ativo nem inativo sem a busca real ter rodado."}
    if ("nenhum anúncio corresponde" in t or "nenhum resultado" in t
            or "no results" in t or "no ads match" in t):
        # frase inequivoca de zero resultado, nao precisa checar nome (nao
        # tem card de anuncio nenhum pra conferir)
        return {"ok": True, "valor": {"ativo": False, "criativos": 0}}
    # "~N resultados"/"N results", N pode ter ponto de milhar (ex: "~14.000
    # resultados"). Extrair o NUMERO primeiro e so depois decidir
    # ativo/inativo por ele. Bug real encontrado em 12/08/2026: checar
    # substring "0 resultados" sem isolar o numero bate em "~14.000
    # resultados" (termina em "...0 resultados") e classificava produtor
    # ATIVO como sem anuncio. Por isso o \b antes do grupo de digitos.
    m = re.search(r"~?(\d[\d.,]*)\s+(?:resultados?|results?)\b", t)
    if not m:
        return {"ok": False, "valor": None,
                "motivo": "pagina carregou mas o layout da biblioteca nao "
                          "bateu com o padrao esperado (mudou de novo); nao "
                          "dá pra afirmar contagem sem chutar"}
    try:
        qtd = int(re.sub(r"[.,]", "", m.group(1)))
    except ValueError:
        return {"ok": False, "valor": None,
                "motivo": f"achou contagem mas nao consegui converter "
                          f"'{m.group(1)}' pra numero"}
    # Bug real, mais grave, encontrado em 12/08/2026 depois de corrigir o
    # anterior: o "?q=" da URL NAO filtra de fato pra nome comum/generico.
    # Testei "GRUPO SOU" e "OFICINA DO TRADER" e os DOIS voltaram exatamente
    # "~24.000 resultados" com anunciantes completamente sem relacao
    # (Uninter, Dola, Dropz, Tauá Hotéis) — a pagina caiu num feed generico
    # de anuncios ativos no Brasil, nao numa busca filtrada. Se eu confiasse
    # nesse numero, TODO produtor sairia "ativo" por padrao, o que e pior
    # que nao medir nada. Por isso: so aceitar o numero se o NOME do
    # produtor aparecer de fato no texto capturado (nos cards de anuncio
    # reais tem o nome do anunciante escrito). Sem isso, nao_verificavel.
    if _normalizar(nome) not in _normalizar(texto):
        return {"ok": False, "valor": None,
                "motivo": f"a pagina mostrou ~{qtd} resultados mas o nome "
                          f"'{nome}' nao aparece em lugar nenhum do texto "
                          f"capturado; sinal forte de que o '?q=' nao "
                          f"filtrou de fato e isso e um feed generico, nao "
                          f"uma busca por esse produtor. Nao afirmar ativo "
                          f"sem essa confirmacao."}
    return {"ok": True, "valor": {"ativo": qtd > 0, "criativos": qtd}}


# --------------------------------------------------------------------------
# Coletor 4: cadência de publicação (Instagram e YouTube, melhor esforço)
# --------------------------------------------------------------------------

def checar_instagram(handle):
    if not handle:
        return {"ok": False, "valor": None, "motivo": "handle nao informado"}
    url = f"https://www.instagram.com/{handle.lstrip('@')}/"
    texto, erro = browser_text(url)
    if not texto:
        return {"ok": False, "valor": None, "motivo": f"pagina nao carregou: {erro}"}
    if "faça login" in texto.lower() or "log in" in texto.lower() and len(texto) < 3000:
        return {"ok": False, "valor": None,
                "motivo": "instagram exigiu login pra mostrar o perfil "
                          "(comportamento normal deles pra acesso sem sessao); "
                          "nao ha data de ultimo post visivel sem entrar"}
    m = re.search(r"([\d.,]+)\s*publica", texto.lower())
    if m:
        return {"ok": True, "valor": {"posts_contados": m.group(1)},
                "motivo": "instagram nao expoe data do ultimo post sem login; "
                          "so a contagem de publicacoes ficou visivel"}
    return {"ok": False, "valor": None,
            "motivo": "pagina carregou mas sem sinal reconhecivel de perfil "
                      "publico (provavel parede de login)"}


def checar_youtube(handle_ou_id):
    if not handle_ou_id:
        return {"ok": False, "valor": None, "motivo": "canal nao informado"}
    import feedparser
    if handle_ou_id.startswith("UC"):
        feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={handle_ou_id}"
    else:
        feed_url = f"https://www.youtube.com/feeds/videos.xml?user={handle_ou_id.lstrip('@')}"
    _throttle()
    try:
        d = feedparser.parse(feed_url)
    except Exception as e:
        return {"ok": False, "valor": None, "motivo": f"feed RSS falhou: {e}"}
    if not d.entries:
        return {"ok": False, "valor": None,
                "motivo": "feed RSS do youtube veio vazio (canal errado, "
                          "handle nao mapeia pra channel_id, ou canal sem video)"}
    ultimo = d.entries[0]
    return {"ok": True, "valor": {
        "titulo_ultimo_video": ultimo.get("title", ""),
        "data_ultimo_video": ultimo.get("published", ""),
    }}


# --------------------------------------------------------------------------
# Coletor 5: Reclame Aqui
# --------------------------------------------------------------------------

def _e_pagina_de_empresa_no_ra(url):
    """Bug real encontrado em 12/08/2026: o filtro antigo so checava
    "reclameaqui.com.br" IN url, e isso bate ate na home generica deles
    (https://www.reclameaqui.com.br/), que apareceu de fato num resultado
    de busca real (FEL DIGITAL). A home generica ficou fixada como se fosse
    a pagina da empresa. Exige que tenha ALGO depois do dominio."""
    m = re.search(r"reclameaqui\.com\.br(/.*)?$", url)
    if not m:
        return False
    caminho = (m.group(1) or "").strip("/")
    return bool(caminho)


def reclame_aqui_fixado(historico):
    """Mesma logica do site_fixado: a URL da pagina da empresa no Reclame
    Aqui tambem vinha de busca (roleta). Depois de achar uma vez, fixa —
    senao "mudou_desde_ultima" flica com ruido de busca mesmo quando a
    empresa nao mudou nada la. Tambem revalida o que ja esta fixado: se um
    registro antigo fixou por engano a home generica (bug acima), essa
    fixacao e ignorada, nao propagada pra sempre."""
    for registro in reversed(historico):
        ra = registro.get("reclame_aqui", {})
        if ra.get("ok") and isinstance(ra.get("valor"), dict):
            url = ra["valor"].get("url")
            if url and _e_pagina_de_empresa_no_ra(url):
                return url
    return None


# Data relativa ("há 3 dias") normalizada em UNIDADE DE DIAS antes de
# classificar "recente" — corrigido em 12/08/2026 (pedido da {{AGENTE_NAME}}, ruido
# residual que sobrou depois da correcao de estabilidade principal): o
# mesmo texto vira "há 4 dias" no dia seguinte so pelo tempo passar, e o
# regex antigo (so hora/dia) parava de casar quando o site trocava pra "há
# 1 semana", fazendo o booleano cair de True pra False SEM a reclamacao ter
# ficado mais antiga de fato. _diferencas() so compara o booleano derivado
# aqui (classificado por LIMIAR de dias), nunca o texto bruto, que fica
# guardado so pra transparencia/debug.
_RA_UNIDADE_DIAS = {"minuto": 0, "hora": 0, "dia": 1, "semana": 7,
                     "mes": 30, "mês": 30, "ano": 365}
_RA_LIMIAR_RECENTE_DIAS = 30


def _ra_recencia_em_dias(texto):
    m = re.search(r"há (\d+)\s*(minuto|hora|dia|semana|m[eê]s|ano)s?", texto, re.IGNORECASE)
    if not m:
        return None, None
    qtd = int(m.group(1))
    unidade = m.group(2).lower().replace("ê", "e")
    return m.group(0), qtd * _RA_UNIDADE_DIAS.get(unidade, 9999)


def checar_reclame_aqui(nome, historico=None):
    pagina_ra = reclame_aqui_fixado(historico or [])
    fixado = bool(pagina_ra)
    if not pagina_ra:
        resultados, erro = web_search(f'"{nome}" reclame aqui')
        if erro:
            return {"ok": False, "valor": None, "motivo": f"busca falhou: {erro}"}
        pagina_ra = next((u for u in resultados if _e_pagina_de_empresa_no_ra(u)), None)
        if not pagina_ra:
            return {"ok": True, "valor": {"tem_pagina": False},
                    "motivo": "busca nao achou pagina no reclame aqui pra esse nome"}
    texto, erro_txt = browser_text(pagina_ra)
    if not texto:
        return {"ok": False, "valor": None,
                "motivo": f"achou a pagina ({pagina_ra}) mas nao conseguiu ler "
                          f"o conteudo: {erro_txt}"}
    texto_bruto, dias_atras = _ra_recencia_em_dias(texto.lower())
    tem_reclamacao_recente = dias_atras is not None and dias_atras <= _RA_LIMIAR_RECENTE_DIAS
    return {"ok": True, "valor": {
        "tem_pagina": True, "url": pagina_ra,
        "reclamacao_recente_detectada": tem_reclamacao_recente,
        "texto_relativo_bruto": texto_bruto,
    }, "fonte": "fixado_historico" if fixado else "busca_web"}


# --------------------------------------------------------------------------
# Veredito
# --------------------------------------------------------------------------

def decidir_veredito(colhido, plataformas_concorrentes):
    """Ordem de prioridade (corrigida em 12/08/2026, dois rounds de bug real):

    1. trocou_plataforma    — QUALQUER evidencia ativa de venda em
                               plataforma concorrente (site proprio E
                               pagina de marketplace convivem; a pagina de
                               marketplace conta mesmo que a home mostre
                               outra coisa — ela e a prova mais direta)
    2. (dentro do checkout) — plataforma ativa == tmb -> ativo
    3. venda_por_whatsapp   — nenhuma plataforma de checkout ativa, mas
                               link de wa.me/api.whatsapp achado embutido
                               na home
    4. ativo                — anuncio Meta ativo OU post recente (<=45 dias)
    5. parou_de_anunciar    — anuncio Meta foi MEDIDO (nao "falhou em medir")
                               e esta inativo
    6. ativo_sem_checkout_publico — site proprio respondeu e/ou Reclame
                               Aqui tem pagina da empresa, mas nenhum sinal
                               forte foi medido.
    7. sem_rastro           — nada foi encontrado em lugar nenhum

    Quando whatsapp E plataforma concorrente coexistem (home aponta pro
    WhatsApp, mas existe pagina de produto ativa numa plataforma), o
    veredito principal e trocou_plataforma (evidencia mais forte) e
    "venda_por_whatsapp" entra em sinais_secundarios — os dois fatos
    aparecem no registro, nenhum e descartado.
    """
    checkout = colhido.get("checkout", {})
    ads = colhido.get("meta_ads", {})
    yt = colhido.get("youtube", {})
    ig = colhido.get("instagram", {})
    ra = colhido.get("reclame_aqui", {})

    sinais_secundarios = []
    plataformas_ativas = checkout.get("plataformas_ativas", []) if checkout.get("ok") else []
    tem_whatsapp_ativo = checkout.get("tem_whatsapp_ativo", False) if checkout.get("ok") else False
    concorrentes_ativas = [p for p in plataformas_ativas if p in plataformas_concorrentes]

    if concorrentes_ativas:
        if tem_whatsapp_ativo:
            sinais_secundarios.append("venda_por_whatsapp")
        return "trocou_plataforma", sinais_secundarios

    if "tmb" in plataformas_ativas:
        return "ativo", sinais_secundarios

    if tem_whatsapp_ativo:
        return "venda_por_whatsapp", sinais_secundarios

    ads_medido = ads.get("ok") is True and isinstance(ads.get("valor"), dict)
    ads_ativo = ads_medido and ads["valor"].get("ativo")
    if ads_ativo:
        return "ativo", sinais_secundarios

    post_recente = False
    if yt.get("ok") and isinstance(yt.get("valor"), dict):
        data_str = yt["valor"].get("data_ultimo_video", "")
        post_recente = _data_recente(data_str, dias=45)
    if not post_recente and ig.get("ok") and isinstance(ig.get("valor"), dict):
        # instagram raramente entrega data (login wall); so conta se algum dia
        # o coletor passar a trazer data real.
        post_recente = bool(ig["valor"].get("data_ultimo_post") and
                             _data_recente(ig["valor"]["data_ultimo_post"], dias=45))
    if post_recente:
        return "ativo", sinais_secundarios

    if ads_medido and not ads_ativo:
        return "parou_de_anunciar", sinais_secundarios

    presenca_publica_confirmada = (
        bool(checkout.get("site_proprio_url")) or
        (ra.get("ok") is True and isinstance(ra.get("valor"), dict)
         and ra["valor"].get("tem_pagina"))
    )
    if presenca_publica_confirmada:
        return "ativo_sem_checkout_publico", sinais_secundarios

    return "sem_rastro", sinais_secundarios


def _data_recente(data_str, dias):
    if not data_str:
        return False
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(data_str)
    except Exception:
        try:
            dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        except Exception:
            return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days <= dias


# --------------------------------------------------------------------------
# Orquestração por produtor
# --------------------------------------------------------------------------

def caminho_json(nome):
    return OSINT_DIR / f"{slugify(nome)}.json"


def carregar_historico(nome):
    caminho = caminho_json(nome)
    if not caminho.exists():
        return []
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return []


def rodar_produtor(nome, site_hint=None, instagram_hint=None, youtube_hint=None,
                    plataformas=None):
    plataformas = plataformas or carregar_plataformas()
    concorrentes = {p for p in plataformas if p != "tmb"}
    historico = carregar_historico(nome)

    evidencias, checkout = coletar_evidencias_de_venda(nome, site_hint, plataformas, historico)
    meta_ads = checar_meta_ads(nome)
    instagram = checar_instagram(instagram_hint)
    youtube = checar_youtube(youtube_hint)
    reclame_aqui = checar_reclame_aqui(nome, historico)

    checkout_completo = {**checkout, "evidencias": evidencias}
    colhido = {
        "checkout": checkout_completo, "meta_ads": meta_ads,
        "instagram": instagram, "youtube": youtube, "reclame_aqui": reclame_aqui,
    }
    veredito, sinais_secundarios = decidir_veredito(colhido, concorrentes)

    registro = {
        "timestamp_utc": agora_iso(),
        "produtor": nome,
        "veredito": veredito,
        "sinais_secundarios": sinais_secundarios,
        **colhido,
    }
    return registro, historico


def gravar_e_comparar(nome, registro, historico):
    """historico e o que ja foi carregado ANTES de rodar_produtor (pra
    mesclar as evidencias); aqui so acrescenta o registro novo e regrava.
    Nunca reescreve nem remove entrada anterior (append-only) — inclusive as
    evidencias antigas continuam la dentro de cada registro passado, so o
    registro NOVO tem a lista mesclada/atualizada."""
    OSINT_DIR.mkdir(parents=True, exist_ok=True)
    caminho = caminho_json(nome)
    anterior = historico[-1] if historico else None
    historico_novo = historico + [registro]
    caminho.write_text(json.dumps(historico_novo, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return _diferencas(anterior, registro)


def _valor_comparavel(chave, campo):
    """Extrai so a parte de cada campo que deve entrar na comparacao de
    "mudou" — nunca o campo bruto inteiro. Dois motivos, os dois de bugs
    reais corrigidos em 12/08/2026:
    1. "checkout" agora e uma lista de evidencias que pode oscilar de
       detalhe (contador de rodadas, timestamp de ultima_vez_vista) sem o
       FATO relevante (quais plataformas estao ativas) ter mudado. Compara
       so o resumo agregado (plataformas_ativas, whatsapp, site proprio).
    2. "reclame_aqui" guarda o texto relativo bruto ("há 3 dias") que muda
       todo santo dia so pelo tempo passar. Compara so o booleano derivado
       (recente ou nao, por LIMIAR de dias), nunca o texto.
    Devolve (valor_comparavel, foi_medido)."""
    if not campo.get("ok"):
        return None, False
    if chave == "checkout":
        return (tuple(campo.get("plataformas_ativas", [])),
                campo.get("tem_whatsapp_ativo", False),
                campo.get("site_proprio_url")), True
    if chave == "reclame_aqui":
        v = campo.get("valor")
        if not isinstance(v, dict):
            return None, False
        return (v.get("tem_pagina"), v.get("reclamacao_recente_detectada")), True
    return campo.get("valor"), True


def _diferencas(anterior, atual):
    """So marca "mudou" quando os DOIS lados foram de fato medidos e o
    valor COMPARAVEL (ver _valor_comparavel) e diferente."""
    if not anterior:
        return ["primeira_execucao"]
    mudou = []
    for chave in ("checkout", "meta_ads", "instagram", "youtube", "reclame_aqui"):
        va, medido_a = _valor_comparavel(chave, anterior.get(chave, {}))
        vb, medido_b = _valor_comparavel(chave, atual.get(chave, {}))
        if medido_a and medido_b and va != vb:
            mudou.append(chave)
    if anterior.get("veredito") != atual.get("veredito"):
        mudou.append("veredito")
    return mudou or ["nada"]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def ler_top_n_csv(caminho_csv, n):
    linhas = []
    with open(caminho_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                row["_score"] = float(row.get("score_churn_6m", "") or 0)
            except ValueError:
                row["_score"] = 0.0
            linhas.append(row)
    linhas.sort(key=lambda r: r["_score"], reverse=True)
    return linhas[:n]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--produtor")
    ap.add_argument("--site")
    ap.add_argument("--instagram")
    ap.add_argument("--youtube")
    ap.add_argument("--top", type=int)
    ap.add_argument("--csv", default=str(CSV_PADRAO))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not args.produtor and not args.top:
        ap.error("informe --produtor \"Nome\" ou --top N")

    plataformas = carregar_plataformas()
    saida = []

    if args.produtor:
        alvos = [{"nome": args.produtor, "site": args.site,
                   "instagram": args.instagram, "youtube": args.youtube}]
    else:
        if not os.path.exists(args.csv):
            print(f"CSV nao encontrado: {args.csv}", file=sys.stderr)
            sys.exit(1)
        linhas = ler_top_n_csv(args.csv, args.top)
        alvos = [{"nome": l["nome"], "site": None, "instagram": None,
                   "youtube": None, "score_churn_6m": l["_score"],
                   "faixa_risco": l.get("faixa_risco")} for l in linhas]

    for alvo in alvos:
        registro, historico = rodar_produtor(
            alvo["nome"], alvo.get("site"), alvo.get("instagram"),
            alvo.get("youtube"), plataformas)
        mudou = gravar_e_comparar(alvo["nome"], registro, historico)
        registro["_mudou_desde_ultima"] = mudou
        registro["_score_churn_6m"] = alvo.get("score_churn_6m")
        saida.append(registro)

    if args.json:
        print(json.dumps(saida, ensure_ascii=False, indent=2))
        return

    largura_nome = max([len(s["produtor"]) for s in saida] + [20])
    cab = (f'{"produtor":<{largura_nome}}  {"veredito":<28}  '
           f'{"plataformas_ativas":<20}  {"mudou_desde_ultima"}')
    print(cab)
    print("-" * len(cab))
    for r in saida:
        ck = r["checkout"]
        plats = list(ck.get("plataformas_ativas", []))
        if ck.get("tem_whatsapp_ativo"):
            plats.append("whatsapp")
        checkout_txt = ",".join(plats) if plats else "nenhuma"
        veredito_txt = r["veredito"]
        if r.get("sinais_secundarios"):
            veredito_txt += f" (+{','.join(r['sinais_secundarios'])})"
        mudou_txt = ",".join(r["_mudou_desde_ultima"])
        print(f'{r["produtor"]:<{largura_nome}}  {veredito_txt:<28}  '
              f'{checkout_txt:<20}  {mudou_txt}')


if __name__ == "__main__":
    main()
