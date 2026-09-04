#!/usr/bin/env python3
"""
Gerador de imagem via API do Gemini (nano banana / gemini-*-image),
equivalente ao gerar-imagem.py mas usando generativelanguage.googleapis.com.

Uso:
  python3 /opt/{{AGENTE_NAME_LOWERCASE}}/tools/gerar-imagem-gemini.py \
      --prompt-file /caminho/prompt.txt \
      --out /opt/{{AGENTE_NAME_LOWERCASE}}/workspace/imagem.png \
      [--aspect 4:5] [--size 2K] [--model gemini-3-pro-image]

Le a chave de GEMINI_API_KEY no ambiente ou de /opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env.
NUNCA imprime o valor da chave (mascara em qualquer mensagem de erro).
Sai com codigo != 0 e imprime o erro cru da API em caso de falha,
pra permitir o protocolo de fallback da skill carrossel.

Modelos uteis (verificados em 2026-07):
  gemini-3-pro-image        -> nano banana pro, melhor render de texto/acento
  nano-banana-pro-preview   -> alias preview do mesmo
  gemini-3.1-flash-image    -> mais rapido/barato
  gemini-2.5-flash-image    -> nano banana original
"""
import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ENV_FILE = "/opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env"
BASE = "https://generativelanguage.googleapis.com/v1beta/models"

EXT_POR_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
}


def carregar_chave() -> str:
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if chave:
        return chave
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as fh:
            for linha in fh:
                linha = linha.strip()
                if linha.startswith("GEMINI_API_KEY="):
                    return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def mascarar(texto: str, chave: str) -> str:
    """Remove a chave de qualquer saida, por seguranca."""
    if chave and chave in texto:
        texto = texto.replace(chave, "***REDACTED***")
    return re.sub(r"key=[A-Za-z0-9_\-]+", "key=***REDACTED***", texto)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemini-3-pro-image")
    ap.add_argument("--aspect", default="4:5",
                    help="1:1 2:3 3:2 3:4 4:3 4:5 5:4 9:16 16:9 21:9")
    ap.add_argument("--size", default="2K", choices=["1K", "2K", "4K"])
    ap.add_argument("--tentativas", type=int, default=3)
    args = ap.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as fh:
            prompt = fh.read().strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        print("ERRO: informe --prompt ou --prompt-file", file=sys.stderr)
        return 2

    chave = carregar_chave()
    if not chave:
        print(
            "ERRO_CREDENCIAL: GEMINI_API_KEY ausente/vazia "
            f"(nem no ambiente nem em {ENV_FILE}).",
            file=sys.stderr,
        )
        return 3

    payload = json.dumps({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {
                "aspectRatio": args.aspect,
                "imageSize": args.size,
            },
        },
    }).encode("utf-8")

    url = f"{BASE}/{args.model}:generateContent"
    corpo = None
    ultimo_erro = ""

    for tentativa in range(1, args.tentativas + 1):
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": chave,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                corpo = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detalhe = mascarar(exc.read().decode("utf-8", "replace"), chave)
            ultimo_erro = f"ERRO_API_HTTP {exc.code}: {detalhe[:900]}"
            # 429/5xx valem retry com backoff; 4xx de payload nao
            if exc.code in (429, 500, 502, 503, 504) and tentativa < args.tentativas:
                time.sleep(5 * tentativa)
                continue
            print(ultimo_erro, file=sys.stderr)
            return 4
        except Exception as exc:
            ultimo_erro = f"ERRO_API_REDE: {type(exc).__name__}: {mascarar(str(exc), chave)}"
            if tentativa < args.tentativas:
                time.sleep(5 * tentativa)
                continue
            print(ultimo_erro, file=sys.stderr)
            return 5

    if corpo is None:
        print(ultimo_erro or "ERRO_DESCONHECIDO", file=sys.stderr)
        return 5

    # Extrai a primeira parte inlineData de imagem
    dados = None
    mime = "image/png"
    try:
        cand = corpo["candidates"][0]
        for parte in cand["content"]["parts"]:
            inline = parte.get("inlineData") or parte.get("inline_data")
            if inline and str(inline.get("mimeType", inline.get("mime_type", ""))).startswith("image/"):
                dados = inline["data"]
                mime = inline.get("mimeType") or inline.get("mime_type")
                break
    except (KeyError, IndexError, TypeError):
        pass

    if not dados:
        resumo = mascarar(json.dumps(corpo)[:900], chave)
        print(f"ERRO_RESPOSTA_SEM_IMAGEM: {resumo}", file=sys.stderr)
        return 6

    saida = os.path.abspath(args.out)
    ext_certa = EXT_POR_MIME.get(mime, ".png")
    raiz, ext_pedida = os.path.splitext(saida)
    # Se o mime nao casa com a extensao pedida, salva com a extensao real
    if ext_pedida.lower() not in (ext_certa, ".jpeg" if ext_certa == ".jpg" else ext_certa):
        saida = raiz + ext_certa

    os.makedirs(os.path.dirname(saida), exist_ok=True)
    with open(saida, "wb") as fh:
        fh.write(base64.b64decode(dados))

    uso = corpo.get("usageMetadata", {})
    print(saida)
    print(f"MIME={mime}", file=sys.stderr)
    print(f"MODELO={args.model} ASPECT={args.aspect} SIZE={args.size}", file=sys.stderr)
    print(f"TOKENS={json.dumps(uso)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
