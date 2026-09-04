#!/usr/bin/env python3
import psycopg2, subprocess
PG=None
for line in open('/root/.agente-secrets.env'):
    if line.startswith('PG_PASSWORD_{{AGENTE_NAME_UPPER}}='):
        PG=line.strip().split('=',1)[1]
conn=psycopg2.connect(f"postgres://{{AGENTE_NAME_LOWERCASE}}:{PG}@127.0.0.1:5432/{{AGENTE_NAME_LOWERCASE}}_memory")
conn.autocommit=True; cur=conn.cursor()
cur.execute("SELECT id, texto FROM lembretes WHERE NOT enviado AND quando <= now()")
for lid, texto in cur.fetchall():
    prompt=f"[sistema] LEMBRETE agendado disparou: '{texto}'. Envie agora ao Chefe no Telegram (outbox, chat {{TELEGRAM_USER_ID_DONO}}) de forma natural, lembrando ele disso."
    subprocess.run(["/opt/{{AGENTE_NAME_LOWERCASE}}/tools/inject.sh", prompt], timeout=15)
    cur.execute("UPDATE lembretes SET enviado=true WHERE id=%s",(lid,))
cur.close(); conn.close()
