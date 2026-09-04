"""
Cliente Conta Azul, SOMENTE LEITURA.

REGRA 1 (inegociavel): este modulo so faz GET. Nunca POST, PATCH, PUT, DELETE
contra a API da Conta Azul. O token deles e de administrador e nao separa
leitura de escrita; a trava e nossa, no codigo.

REGRA 2 (ordem direta do Chefe, 11/08/2026, repetida 18x): NAO PESAR O SISTEMA.
O Conta Azul e o ERP em que o financeiro da empresa trabalha o dia todo. O teto
deles e 600 req/min e 10 req/s, mas nos usamos NO MAXIMO 1 requisicao por
segundo, com pausa explicita entre chamadas. Lentidao nossa nao custa nada;
lentidao do lado deles custa o projeto inteiro. Se vier 429 (ou qualquer sinal
de limite), PARAR DE VEZ, sem retry agressivo, e avisar. Preferir poucas
chamadas com pagina grande a muitas chamadas pequenas. Carga pesada se faz em
fatias, avisando quanto falta, mesmo que demore horas.

Uso:
    from contaazul import get, refresh_token_se_necessario
    dados = get("/v1/categorias")
"""

import base64
import os
import time
import requests

ENV_PATH = "/opt/{{AGENTE_NAME_LOWERCASE}}/.env"
TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
API_BASE = "https://api-v2.contaazul.com"

# metodos HTTP permitidos por este modulo. Qualquer coisa fora disso e bloqueada.
METODOS_PERMITIDOS = {"GET"}

# teto proprio, bem abaixo do teto da Conta Azul (600/min, 10/s). Nunca subir isso
# sem nova instrucao explicita do Chefe.
INTERVALO_MINIMO_ENTRE_CHAMADAS_SEGUNDOS = 1.0
_ultima_chamada_em = [0.0]

# lock de arquivo: o ritmo precisa ser GLOBAL na maquina, nao por processo.
# Um script de carga e uma consulta pontual, rodando ao mesmo tempo, cada um
# com seu proprio contador em memoria, somados podem passar de 1 req/s mesmo
# que cada um ache que esta sozinho no teto. O lock forca todo mundo a
# esperar a vez.
_LOCK_PATH = "/tmp/contaazul_ritmo.lock"


class LimiteAtingidoError(RuntimeError):
    """A API sinalizou limite de uso. Parar de vez, sem retry automatico."""
    pass


def _respeitar_ritmo():
    """
    Garante ao menos 1s entre chamadas GET a API da Conta Azul, contando
    TODOS os processos que usam este modulo na maquina (nao so o processo
    atual). Usa um arquivo de lock com timestamp da ultima chamada.
    """
    import fcntl

    with open(_LOCK_PATH, "a+") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            lock_file.seek(0)
            conteudo = lock_file.read().strip()
            ultima = float(conteudo) if conteudo else 0.0

            agora = time.monotonic()
            espera = INTERVALO_MINIMO_ENTRE_CHAMADAS_SEGUNDOS - (agora - ultima)
            if espera > 0:
                time.sleep(espera)

            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(str(time.monotonic()))
            lock_file.flush()
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _ler_env():
    """Le o .env inteiro para um dict, preservando ordem e comentarios originais."""
    linhas = []
    valores = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            linhas = f.readlines()
    for linha in linhas:
        s = linha.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        chave, _, valor = s.partition("=")
        valores[chave.strip()] = valor.strip().strip('"')
    return linhas, valores


def _escrever_env(linhas, chave, novo_valor):
    """Substitui ou adiciona uma chave no .env, mantendo permissao 600."""
    achou = False
    novas_linhas = []
    for linha in linhas:
        s = linha.strip()
        if s.startswith(f"{chave}=") or s.startswith(f"{chave} ="):
            novas_linhas.append(f"{chave}={novo_valor}\n")
            achou = True
        else:
            novas_linhas.append(linha)
    if not achou:
        novas_linhas.append(f"{chave}={novo_valor}\n")

    tmp_path = ENV_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        f.writelines(novas_linhas)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, ENV_PATH)


def _valor_env(chave):
    return os.environ.get(chave) or _ler_env()[1].get(chave)


def _token_provavelmente_valido(valores):
    """
    Decide sem chamada de rede (cada checagem por rede conta contra o teto de
    1 req/s). Usa CONTAAZUL_TOKEN_OBTIDO_EM (epoch, gravado no .env a cada
    renovacao) e uma margem de seguranca de 5 minutos antes do 1h de validade.
    Sem esse timestamp (ambiente antigo), assume expirado e renova uma vez.
    """
    access_token = os.environ.get("CONTAAZUL_ACCESS_TOKEN") or valores.get("CONTAAZUL_ACCESS_TOKEN")
    if not access_token:
        return False
    obtido_em = os.environ.get("CONTAAZUL_TOKEN_OBTIDO_EM") or valores.get("CONTAAZUL_TOKEN_OBTIDO_EM")
    if not obtido_em:
        return False
    try:
        idade_segundos = time.time() - float(obtido_em)
    except ValueError:
        return False
    margem_seguranca_segundos = 5 * 60
    validade_segundos = 60 * 60
    return idade_segundos < (validade_segundos - margem_seguranca_segundos)


def refresh_token_se_necessario(forcar=False):
    """
    Garante que CONTAAZUL_ACCESS_TOKEN no .env esteja valido.
    Se estiver expirado (ou perto disso, ou forcar=True), renova via refresh_token
    e regrava o .env com permissao 600. Renovacao usa o endpoint de token, que
    NAO conta contra o teto da API principal, mas mesmo assim so roda quando
    necessario (nunca a cada get()).
    Retorna o access_token valido.
    """
    linhas, valores = _ler_env()
    access_token = os.environ.get("CONTAAZUL_ACCESS_TOKEN") or valores.get("CONTAAZUL_ACCESS_TOKEN")

    if not forcar and _token_provavelmente_valido(valores):
        return access_token

    refresh_token = os.environ.get("CONTAAZUL_REFRESH_TOKEN") or valores.get("CONTAAZUL_REFRESH_TOKEN")
    client_id = os.environ.get("CONTAAZUL_CLIENT_ID") or valores.get("CONTAAZUL_CLIENT_ID")
    client_secret = os.environ.get("CONTAAZUL_CLIENT_SECRET") or valores.get("CONTAAZUL_CLIENT_SECRET")

    if not refresh_token or not client_id or not client_secret:
        raise RuntimeError("Faltam credenciais Conta Azul no .env (refresh_token/client_id/client_secret)")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Falha ao renovar token Conta Azul: {resp.status_code} {resp.text}")

    corpo = resp.json()
    novo_access = corpo["access_token"]
    novo_refresh = corpo.get("refresh_token", refresh_token)

    obtido_em = str(time.time())
    linhas, _ = _ler_env()
    _escrever_env(linhas, "CONTAAZUL_ACCESS_TOKEN", novo_access)
    linhas, _ = _ler_env()
    _escrever_env(linhas, "CONTAAZUL_REFRESH_TOKEN", novo_refresh)
    linhas, _ = _ler_env()
    _escrever_env(linhas, "CONTAAZUL_TOKEN_OBTIDO_EM", obtido_em)

    # variaveis de processo tambem atualizam, para chamadas seguintes na mesma execucao
    os.environ["CONTAAZUL_ACCESS_TOKEN"] = novo_access
    os.environ["CONTAAZUL_REFRESH_TOKEN"] = novo_refresh
    os.environ["CONTAAZUL_TOKEN_OBTIDO_EM"] = obtido_em

    return novo_access


def get(path, params=None, max_tentativas=2):
    """
    GET autenticado contra a API da Conta Azul. Renova token se preciso.
    path: comeca com /v1/...

    Ritmo: no maximo 1 chamada/segundo (ver INTERVALO_MINIMO_ENTRE_CHAMADAS_SEGUNDOS).
    Se vier 429 (limite atingido), NAO tenta de novo: levanta LimiteAtingidoError
    para quem chamou decidir, e a carga deve parar ali.
    """
    access_token = refresh_token_se_necessario()
    url = path if path.startswith("http") else f"{API_BASE}{path}"

    for tentativa in range(max_tentativas):
        _respeitar_ritmo()
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=params or {},
            timeout=30,
        )
        if r.status_code == 401 and tentativa == 0:
            access_token = refresh_token_se_necessario(forcar=True)
            continue
        if r.status_code == 429:
            raise LimiteAtingidoError(
                f"429 da Conta Azul em {url}. Parando de vez, sem retry. "
                f"Corpo: {r.text[:500]}"
            )
        return r

    return r


def request(metodo, *args, **kwargs):
    """Bloqueio explicito: este modulo nunca escreve na Conta Azul."""
    if metodo.upper() not in METODOS_PERMITIDOS:
        raise RuntimeError(
            f"Metodo {metodo} bloqueado. Este modulo e SOMENTE LEITURA (GET). "
            "Nunca escrever na Conta Azul a partir daqui."
        )
    return get(*args, **kwargs)


if __name__ == "__main__":
    import sys
    r = get("/v1/categorias", params={"pagina": 1, "tamanho_pagina": 5})
    print(r.status_code)
    print(r.text[:500])
