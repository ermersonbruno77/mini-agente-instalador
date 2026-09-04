#!/usr/bin/env python3
"""Servico de memoria local (pgvector + fastembed, sem OpenAI). Porta 3007."""
import os
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
from fastembed import TextEmbedding

ENV_FILE = Path('/opt/{{AGENTE_NAME_LOWERCASE}}-bot/.env')
_env = {}
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().split('\n'):
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            _env[k.strip()] = v.strip()
PG = _env.get('PG_PASSWORD') or os.environ.get('PG_PASSWORD')
DSN = f"postgres://{{AGENTE_NAME_LOWERCASE}}:{PG}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory"
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

model = TextEmbedding(model_name=MODEL_NAME)
app = FastAPI(title="{{AGENTE_NAME_LOWERCASE}}-memory")

def embed_one(text: str):
    return list(model.embed([text or ""]))[0].tolist()

def vec_str(v):
    return '[' + ','.join(repr(float(x)) for x in v) + ']'

@app.get('/health')
def health():
    return {"ok": True, "model": MODEL_NAME, "dim": 384}

class EmbedReq(BaseModel):
    text: Optional[str] = None
    texts: Optional[List[str]] = None

@app.post('/embed')
def embed(req: EmbedReq):
    if req.texts is not None:
        return {"embeddings": [e.tolist() for e in model.embed(req.texts)]}
    return {"embedding": embed_one(req.text or "")}

class SearchReq(BaseModel):
    query: str
    limit: int = 10
    # Conversa e regra de negocio disputam o MESMO ranking, e frase de
    # conversa costuma ganhar de texto de regra quase sempre, porque a
    # pergunta e falada e a conversa tambem. Por isso existe o filtro:
    # pergunta de REGRA busca so em memoria (arquivo), nao em conversa.
    # Sem o campo, o comportamento e o de sempre (nada quebra pra quem ja chama).
    fonte: Optional[str] = None  # "memoria" | "conversa" | None (as duas)

@app.post('/search')
def search(req: SearchReq):
    q = vec_str(embed_one(req.query))
    k = int(req.limit)
    fonte = (req.fonte or "").strip().lower() or None
    if fonte not in (None, "memoria", "conversa"):
        return {"erro": f"fonte invalida: {fonte}. use memoria, conversa, ou omita"}

    BLOCO_CONVERSA = """
    (SELECT content AS text, 'conversa' AS source, created_at, 1-(embedding<=>%(q)s::vector) AS sim
       FROM conversation_history WHERE embedding IS NOT NULL ORDER BY embedding<=>%(q)s::vector LIMIT %(k)s)
    """
    BLOCO_MEMORIA = """
    (SELECT content AS text, 'memoria:'||coalesce(source_file,'') AS source, created_at, 1-(embedding<=>%(q)s::vector) AS sim
       FROM memory_chunks WHERE embedding IS NOT NULL ORDER BY embedding<=>%(q)s::vector LIMIT %(k)s)
    UNION ALL
    (SELECT fact, 'fato:'||coalesce(category,''), created_at, 1-(embedding<=>%(q)s::vector)
       FROM memory_facts WHERE embedding IS NOT NULL ORDER BY embedding<=>%(q)s::vector LIMIT %(k)s)
    UNION ALL
    (SELECT content, 'transcricao', created_at, 1-(embedding<=>%(q)s::vector)
       FROM transcript_chunks WHERE embedding IS NOT NULL ORDER BY embedding<=>%(q)s::vector LIMIT %(k)s)
    """
    if fonte == "memoria":
        corpo = BLOCO_MEMORIA
    elif fonte == "conversa":
        corpo = BLOCO_CONVERSA
    else:
        corpo = BLOCO_CONVERSA + "UNION ALL" + BLOCO_MEMORIA
    sql = corpo + " ORDER BY sim DESC LIMIT %(k)s"
    conn = psycopg2.connect(DSN); cur = conn.cursor()
    cur.execute(sql, {'q': q, 'k': k})
    rows = cur.fetchall(); cur.close(); conn.close()
    results = [{"text": r[0], "source": r[1], "created_at": str(r[2]), "similarity": round(float(r[3]), 4)} for r in rows]
    return {"query": req.query, "count": len(results), "results": results}
