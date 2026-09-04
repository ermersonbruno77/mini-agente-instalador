#!/usr/bin/env python3
"""
Cliente SharePoint da TMB, SOMENTE LEITURA.

REGRA INQUEBRAVEL (ordem do Chefe, 2026-07-29):
  SharePoint e INTOCAVEL para edicao ou delecao. Apenas consulta.

Como essa regra e garantida aqui, nao so prometida:
  1. _graph() so aceita metodo GET. Qualquer outro verbo levanta excecao.
  2. Os escopos pedidos no login sao *.Read (nao pedimos ReadWrite),
     entao o proprio token e incapaz de escrever, mesmo se o codigo tentasse.
  3. Nenhuma funcao deste arquivo constroi corpo de requisicao (PUT/PATCH/POST/DELETE).
"""

import json
import os
import sys
import urllib.parse

import msal
import requests

TENANT = "cce6ac43-cd83-476a-9977-7dcb3941fad9"  # tmbeducacao.com.br
AUTHORITY = f"https://login.microsoftonline.com/{TENANT}"

# App publico da propria Microsoft (Microsoft Graph Command Line Tools).
# Fallback: Azure CLI. Nenhum segredo de cliente envolvido, e fluxo de
# cliente publico, autenticado como o proprio usuario.
CLIENT_IDS = [
    # App proprio da TMB, registrado pelo Chefe em 12/08/2026 ("Leitura SharePoint TMB").
    # So tem Files.Read.All e Sites.Read.All delegadas, nenhuma permissao de escrita.
    ("Leitura SharePoint TMB", "3705d4e2-1e3c-4bda-9e30-4ad3d5c20a86"),
    ("Microsoft Graph Command Line Tools", "14d82eec-204b-4c2f-b7e8-296a70dab67e"),
    ("Azure CLI", "04b07795-8ddb-461a-bbee-02f9e1bf7b46"),
]

SCOPES = ["Files.Read.All", "Sites.Read.All"]  # somente leitura, de proposito

CACHE_PATH = "/opt/{{AGENTE_NAME_LOWERCASE}}/.secrets/sp_token.json"

GRAPH = "https://graph.microsoft.com/v1.0"

# Unica pasta autorizada pelo Chefe. Nada fora daqui e lido.
SITE_HOST = "tmbeducacao.sharepoint.com"
SITE_PATH = "/"  # site raiz
DRIVE_NAME = "Documentos Compartilhados"
FOLDER = "Financeiro/FP&A/Fluxo de Caixa/Novo Fluxo de Caixa"


# --------------------------------------------------------------------------
# autenticacao
# --------------------------------------------------------------------------

def _cache():
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as fh:
            cache.deserialize(fh.read())
    return cache


def _save_cache(cache):
    if cache.has_state_changed:
        old = os.umask(0o077)
        try:
            with open(CACHE_PATH, "w") as fh:
                fh.write(cache.serialize())
        finally:
            os.umask(old)
        os.chmod(CACHE_PATH, 0o600)


def _app(client_id, cache):
    return msal.PublicClientApplication(client_id, authority=AUTHORITY, token_cache=cache)


def token(interactive=False):
    """Devolve access token. Silencioso se ja existe sessao; senao device code."""
    cache = _cache()
    last_err = None

    for name, cid in CLIENT_IDS:
        app = _app(cid, cache)
        accounts = app.get_accounts()
        if accounts:
            res = app.acquire_token_silent(SCOPES, account=accounts[0])
            if res and "access_token" in res:
                _save_cache(cache)
                return res["access_token"]

        if not interactive:
            continue

        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            last_err = f"[{name}] {flow.get('error_description', flow)}"
            continue

        print(f"\n=== LOGIN via {name} ===", flush=True)
        print(flow["message"], flush=True)
        print("=" * 40, flush=True)

        res = app.acquire_token_by_device_flow(flow)
        if "access_token" in res:
            _save_cache(cache)
            print(f"OK, autenticado via {name}.", flush=True)
            return res["access_token"]

        last_err = f"[{name}] {res.get('error')}: {res.get('error_description')}"
        print(f"Falhou: {last_err}", flush=True)

    raise SystemExit(f"Sem token. Ultimo erro: {last_err or 'nenhuma sessao salva, rode com login'}")


# --------------------------------------------------------------------------
# leitura
# --------------------------------------------------------------------------

def _graph(path, tok, method="GET", **kw):
    if method != "GET":
        raise RuntimeError(
            "BLOQUEADO: este cliente e somente leitura. SharePoint da TMB "
            "nao pode ser editado nem deletado (regra do Chefe)."
        )
    url = path if path.startswith("http") else f"{GRAPH}{path}"
    r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=90, **kw)
    r.raise_for_status()
    return r


def site_id(tok):
    return _graph(f"/sites/{SITE_HOST}:{SITE_PATH}", tok).json()["id"]


def drive_id(tok, sid):
    for d in _graph(f"/sites/{sid}/drives", tok).json()["value"]:
        if d["name"] in (DRIVE_NAME, "Shared Documents", "Documents"):
            return d["id"]
    raise SystemExit("Nao achei a biblioteca de documentos.")


def list_folder(tok, did, folder=FOLDER):
    enc = urllib.parse.quote(folder)
    items = _graph(f"/drives/{did}/root:/{enc}:/children", tok).json()["value"]
    return [
        {
            "name": i["name"],
            "size": i.get("size"),
            "modified": i.get("lastModifiedDateTime"),
            "modified_by": (i.get("lastModifiedBy", {}).get("user", {}) or {}).get("displayName"),
            "id": i["id"],
            "is_folder": "folder" in i,
        }
        for i in items
    ]


def download(tok, did, item_id, dest):
    url = f"{GRAPH}/drives/{did}/items/{item_id}/content"
    r = _graph(url, tok, stream=True)
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(1 << 16):
            fh.write(chunk)
    return dest


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ls"

    if cmd == "login":
        token(interactive=True)
        sys.exit(0)

    tok = token()
    sid = site_id(tok)
    did = drive_id(tok, sid)

    if cmd == "ls":
        for f in sorted(list_folder(tok, did), key=lambda x: x["modified"] or "", reverse=True):
            kind = "DIR " if f["is_folder"] else "    "
            print(f"{kind}{f['modified']}  {f['size'] or 0:>10}  {f['name']}  ({f['modified_by']})")

    elif cmd == "get":
        name = sys.argv[2]
        dest = sys.argv[3]
        for f in list_folder(tok, did):
            if f["name"] == name:
                print(download(tok, did, f["id"], dest))
                break
        else:
            raise SystemExit(f"Arquivo nao encontrado: {name}")

    elif cmd == "json":
        print(json.dumps(list_folder(tok, did), indent=2, ensure_ascii=False))

    else:
        raise SystemExit("uso: spclient.py [login|ls|json|get <nome> <destino>]")
