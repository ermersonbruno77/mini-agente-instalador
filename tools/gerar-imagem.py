#!/usr/bin/env python3
"""
Gerador de imagem via OpenAI gpt-image-2 (sem dependencia do pacote openai).

Uso:
  OPENAI_API_KEY=sk-... python3 /opt/{{AGENTE_NAME_LOWERCASE}}/tools/gerar-imagem.py \
      --prompt-file /caminho/prompt.txt \
      --out /opt/{{AGENTE_NAME_LOWERCASE}}/workspace/imagem.jpg \
      [--size 1024x1280] [--quality high] [--format jpeg]

Le a chave de OPENAI_API_KEY no ambiente ou de /opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env.
Sai com codigo != 0 e imprime o erro cru da API em caso de falha,
pra permitir o protocolo de fallback da skill carrossel (avisar + explicar + pedir OK).
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

API_URL = "https://api.openai.com/v1/images/generations"
ENV_FILE = "/opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env"


def carregar_chave() -> str:
    chave = os.environ.get("OPENAI_API_KEY", "").strip()
    if chave:
        return chave
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as fh:
            for linha in fh:
                if linha.startswith("OPENAI_API_KEY="):
                    return linha.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt-file")
    ap.add_argument("--prompt")
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", default="1024x1280")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--format", dest="fmt", default="jpeg")
    ap.add_argument("--model", default="gpt-image-2")
    args = ap.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as fh:
            prompt = fh.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        print("ERRO: informe --prompt ou --prompt-file", file=sys.stderr)
        return 2

    chave = carregar_chave()
    if not chave:
        print(
            "ERRO_CREDENCIAL: OPENAI_API_KEY ausente/vazia "
            f"(nem no ambiente nem em {ENV_FILE}). "
            "Nao e possivel chamar o gpt-image-2.",
            file=sys.stderr,
        )
        return 3

    payload = json.dumps(
        {
            "model": args.model,
            "prompt": prompt,
            "size": args.size,
            "quality": args.quality,
            "output_format": args.fmt,
            "n": 1,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {chave}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            corpo = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detalhe = exc.read().decode("utf-8", "replace")
        print(f"ERRO_API_HTTP {exc.code}: {detalhe}", file=sys.stderr)
        return 4
    except Exception as exc:  # rede, timeout, DNS
        print(f"ERRO_API_REDE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5

    try:
        b64 = corpo["data"][0]["b64_json"]
    except (KeyError, IndexError):
        print(f"ERRO_RESPOSTA_INESPERADA: {json.dumps(corpo)[:800]}", file=sys.stderr)
        return 6

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "wb") as fh:
        fh.write(base64.b64decode(b64))

    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
