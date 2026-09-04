#!/usr/bin/env python3
"""Consolida inbox/+sent/ no Postgres com embeddings locais (via memory-api /embed)."""
import os, json, glob, requests, psycopg2

BOT_DIR = '/opt/{{AGENTE_NAME_LOWERCASE}}-bot'
API = 'http://127.0.0.1:3007/embed'
_env = {}
_env_file = f'{BOT_DIR}/.env'
if os.path.exists(_env_file):
    for line in open(_env_file):
        if '=' in line and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            _env[k.strip()] = v.strip()
PG = _env.get('PG_PASSWORD') or os.environ.get('PG_PASSWORD')
DSN = f"postgres://{{AGENTE_NAME_LOWERCASE}}:{PG}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory"
SESSION = 'telegram:{{TELEGRAM_USER_ID_DONO}}'

def embed(text):
    try:
        r = requests.post(API, json={'text': (text or '')[:4000]}, timeout=60)
        return r.json().get('embedding')
    except Exception as e:
        print('embed err:', e); return None

def vec(v):
    return ('[' + ','.join(repr(float(x)) for x in v) + ']') if v else None

def main():
    conn = psycopg2.connect(DSN); conn.autocommit = True; cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS ingested_files (fname text PRIMARY KEY, ingested_at timestamptz DEFAULT now())")
    cur.execute("SELECT fname FROM ingested_files"); done = {r[0] for r in cur.fetchall()}
    inserted = 0

    def ingest(pattern, role, tsfield):
        nonlocal inserted
        for f in sorted(glob.glob(pattern)):
            key = ('inbox:' if role == 'user' else 'sent:') + os.path.basename(f)
            if key in done:
                continue
            try:
                d = json.load(open(f, encoding='utf-8'))
                text = (d.get('text') or '').strip(); ts = d.get(tsfield)
                if text:
                    emb = vec(embed(text))
                    cur.execute(
                        "INSERT INTO conversation_history(session_key,agent_id,role,content,embedding,created_at) "
                        "VALUES(%s,'main',%s,%s,%s::vector,COALESCE(%s::timestamptz,now()))",
                        (SESSION, role, text, emb, ts))
                    inserted += 1
                cur.execute("INSERT INTO ingested_files(fname) VALUES(%s) ON CONFLICT DO NOTHING", (key,))
            except Exception as e:
                print('erro', f, e)

    ingest(f'{BOT_DIR}/inbox/*.json', 'user', 'timestamp')
    ingest(f'{BOT_DIR}/sent/*.json', 'assistant', 'sent_at')

    # backfill embeddings faltantes
    cur.execute("SELECT id, content FROM conversation_history WHERE embedding IS NULL")
    back = 0
    for cid, content in cur.fetchall():
        emb = vec(embed(content or ''))
        if emb:
            cur.execute("UPDATE conversation_history SET embedding=%s::vector WHERE id=%s", (emb, cid)); back += 1

    cur.execute("SELECT count(*), count(embedding) FROM conversation_history")
    tot, withemb = cur.fetchone()
    print(f'inseridos={inserted} backfill={back} total={tot} com_embedding={withemb}')
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
