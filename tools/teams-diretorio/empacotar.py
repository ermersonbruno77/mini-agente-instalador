#!/usr/bin/env python3
"""
Monta o zip que vai pro PC do Chefe.

Por que existe: o {{AGENTE_NAME_LOWERCASE}}-diretorio.ps1 guardado aqui tem o texto __BLOB_TOKEN__ no
lugar do token da caixa. O token de verdade mora em /opt/{{AGENTE_NAME_LOWERCASE}}/.secrets/blob_token
e so entra no arquivo na hora de empacotar. Assim o segredo nunca fica escrito
num arquivo desta pasta.

Uso:
    python3 empacotar.py                 # gera o zip
    python3 empacotar.py --conferir      # so confere se o zip existente tem token

Depois de mandar o zip pro Chefe, apague o zip do servidor: ele carrega o token.
"""

import hashlib
import os
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
TOKEN_ARQ = "/opt/{{AGENTE_NAME_LOWERCASE}}/.secrets/blob_token"
SAIDA = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/downloads/{{AGENTE_NAME_LOWERCASE}}-diretorio.zip"

ARQUIVOS = ["{{AGENTE_NAME_LOWERCASE}}-diretorio.ps1", "rodar.cmd", "LEIA-ME.txt"]
PLACEHOLDER = "__BLOB_TOKEN__"


def main():
    if "--conferir" in sys.argv:
        if not os.path.exists(SAIDA):
            print("zip ainda nao existe:", SAIDA)
            return 1
        with zipfile.ZipFile(SAIDA) as z:
            ps1 = z.read("{{AGENTE_NAME_LOWERCASE}}-diretorio.ps1").decode("utf-8")
        print("placeholder ainda presente (RUIM):" if PLACEHOLDER in ps1 else "token substituido: ok")
        print("sha256 do zip:", hashlib.sha256(open(SAIDA, "rb").read()).hexdigest())
        return 0

    with open(TOKEN_ARQ) as fh:
        token = fh.read().strip()
    if not token.startswith("vercel_blob_"):
        print("o token do blob nao tem a cara esperada, parei")
        return 1

    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    old = os.umask(0o077)
    try:
        with zipfile.ZipFile(SAIDA, "w", zipfile.ZIP_DEFLATED) as z:
            for nome in ARQUIVOS:
                caminho = os.path.join(AQUI, nome)
                texto = open(caminho, encoding="utf-8").read()
                if nome.endswith(".ps1"):
                    if PLACEHOLDER not in texto:
                        print(f"{nome} nao tem {PLACEHOLDER}: o script foi editado a mao? parei")
                        return 1
                    texto = texto.replace(PLACEHOLDER, token)
                z.writestr(nome, texto)
    finally:
        os.umask(old)
    os.chmod(SAIDA, 0o600)

    print("gerado:", SAIDA)
    print("sha256:", hashlib.sha256(open(SAIDA, "rb").read()).hexdigest())
    print("Mande pro Chefe e depois apague este zip do servidor (ele carrega o token da caixa).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
