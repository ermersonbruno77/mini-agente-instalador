#!/usr/bin/env python3
"""RAG: ingere um arquivo na memoria vetorial da {{AGENTE_NAME}} (memory_chunks).
Uso: python3 ingest.py <arquivo> [rotulo]
- PDF -> pdftotext ; outros -> texto
- chunka, embeda via memory-api /embed, insere com dedup por source_file
"""
import sys, os, subprocess, hashlib, requests, psycopg2, shutil

# Resolve caminho absoluto do binario uma vez; se `which` nao achar, mantem o
# nome simples como fallback (nao quebra ambientes com PATH diferente).
BIN_PDFTOTEXT = shutil.which('pdftotext') or 'pdftotext'

def load_pg():
    for line in open('/root/.agente-secrets.env'):
        if line.startswith('PG_PASSWORD_{{AGENTE_NAME_UPPER}}='):
            return line.strip().split('=',1)[1]

def read_text(path):
    if path.lower().endswith('.pdf'):
        r=subprocess.run([BIN_PDFTOTEXT, path, '-'], capture_output=True, timeout=60)
        return r.stdout.decode('utf-8','replace')
    return open(path, encoding='utf-8', errors='replace').read()

def chunk(txt, size=1200, overlap=150):
    txt=' '.join(txt.split())
    out=[]; i=0
    while i < len(txt):
        out.append(txt[i:i+size]); i += size-overlap
    return [c for c in out if c.strip()]

def embed(text):
    r=requests.post('http://127.0.0.1:3007/embed', json={'text':text[:4000]}, timeout=60)
    return r.json()['embedding']

def vec(v): return '['+','.join(repr(float(x)) for x in v)+']'

def main():
    if len(sys.argv)<2:
        print('uso: ingest.py <arquivo> [rotulo]'); sys.exit(2)
    path=sys.argv[1]; label=sys.argv[2] if len(sys.argv)>2 else os.path.basename(path)
    txt=read_text(path)
    if not txt.strip(): print('vazio, nada ingerido'); sys.exit(1)
    fhash=hashlib.sha256(txt.encode()).hexdigest()[:16]
    chunks=chunk(txt)
    PG=load_pg()
    conn=psycopg2.connect(f"postgres://{{AGENTE_NAME_LOWERCASE}}:{PG}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory")
    conn.autocommit=True; cur=conn.cursor()
    cur.execute("DELETE FROM memory_chunks WHERE source_file=%s",(label,))  # dedup: re-ingest limpa antigo
    n=0
    for i,c in enumerate(chunks):
        e=vec(embed(c))
        cur.execute("INSERT INTO memory_chunks(source_file,agent_id,chunk_index,content,embedding,file_hash) VALUES(%s,'main',%s,%s,%s::vector,%s)",
                    (label,i,c,e,fhash))
        n+=1
    cur.close(); conn.close()
    print(f'ingerido: {n} chunks de "{label}"')

if __name__=='__main__': main()
