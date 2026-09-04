#!/usr/bin/env python3
"""Ontologia leve das fichas de memoria: quem fala de quem, sem grafo e sem LLM.

Ideia roubada do kern (rafaelnicolett/kern): o markdown que a gente ja escreve
tem a relacao dentro dele, em frontmatter e em [[link]]. Isso ja e um grafo, so
que ninguem le como grafo. Aqui a leitura e deterministica, sem modelo nenhum,
e mora no Postgres que ja esta de pe.

Uso:
  ontologia.py indexar              varre as pastas e regrava o indice
  ontologia.py vizinhos <nome>      quem aponta pra ficha e pra onde ela aponta
  ontologia.py quebradas            [[link]] que aponta pra ficha que nao existe
  ontologia.py orfas                ficha que ninguem cita e que nao cita ninguem
  ontologia.py hubs [n]             as mais citadas
  ontologia.py depende <nome>       so as relacoes declaradas em depends_on
"""
import os, re, sys, glob, hashlib
import psycopg2

PASTAS = ['/root/.claude/projects/-opt-{{AGENTE_NAME_LOWERCASE}}/memory',
          '/opt/{{AGENTE_NAME_LOWERCASE}}/memory']
IGNORAR = {'memory', 'claude', 'promessas'}
LINK = re.compile(r'\[\[([^\]]+)\]\]')

def url():
    for l in open('/opt/{{AGENTE_NAME_LOWERCASE}}/.env'):
        if l.startswith('DATABASE_URL='):
            return l.split('=', 1)[1].strip().strip('"')
    raise SystemExit('DATABASE_URL nao encontrada')

def chave(s):
    """Normaliza nome de ficha. O acervo mistura hifen e underline pro mesmo
    documento: [[feedback_preview...]] e [[feedback-preview...]] sao a mesma."""
    s = s.strip().lower()
    if s.endswith('.md'):
        s = s[:-3]
    s = os.path.basename(s)
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

def frontmatter(txt):
    if not txt.startswith('---'):
        return {}, txt
    fim = txt.find('\n---', 3)
    if fim < 0:
        return {}, txt
    bloco, corpo = txt[3:fim], txt[fim+4:]
    meta, atual = {}, None
    for linha in bloco.splitlines():
        if not linha.strip():
            continue
        if re.match(r'^\s+', linha) and ':' in linha:
            k, v = linha.split(':', 1)
            meta[f'{atual}.{k.strip()}'] = v.strip()
        elif ':' in linha:
            k, v = linha.split(':', 1)
            atual = k.strip()
            meta[atual] = v.strip()
    return meta, corpo

def ler():
    fichas, relacoes = {}, []
    for pasta in PASTAS:
        for caminho in sorted(glob.glob(os.path.join(pasta, '*.md'))):
            base = chave(caminho)
            if base in IGNORAR:
                continue
            txt = open(caminho, encoding='utf-8').read()
            meta, corpo = frontmatter(txt)
            nome = chave(meta.get('name') or base)
            fichas[nome] = {
                'arquivo': caminho,
                'tipo': meta.get('metadata.type') or meta.get('type') or 'sem tipo',
                'descricao': (meta.get('description') or '')[:400],
                'hash': hashlib.sha1(txt.encode()).hexdigest()[:12],
            }
            vistos = set()
            for alvo in LINK.findall(corpo):
                a = chave(alvo)
                if a and a != nome and ('menciona', a) not in vistos:
                    vistos.add(('menciona', a)); relacoes.append((nome, a, 'menciona'))
            dep = meta.get('depends_on') or meta.get('metadata.depends_on') or ''
            for alvo in re.split(r'[,\s]+', dep.strip('[] ')):
                a = chave(alvo)
                if a and a != nome and ('depende_de', a) not in vistos:
                    vistos.add(('depende_de', a)); relacoes.append((nome, a, 'depende_de'))
    return fichas, relacoes

def indexar(cur):
    cur.execute("""
      CREATE TABLE IF NOT EXISTS memoria_ficha(
        nome text PRIMARY KEY, arquivo text NOT NULL, tipo text,
        descricao text, hash text, atualizado_em timestamptz DEFAULT now());
      CREATE TABLE IF NOT EXISTS memoria_relacao(
        de text NOT NULL, para text NOT NULL, tipo_rel text NOT NULL,
        existe boolean NOT NULL, PRIMARY KEY (de, para, tipo_rel));
    """)
    fichas, relacoes = ler()
    cur.execute('TRUNCATE memoria_ficha, memoria_relacao')
    for nome, f in fichas.items():
        cur.execute('INSERT INTO memoria_ficha(nome,arquivo,tipo,descricao,hash) VALUES (%s,%s,%s,%s,%s)',
                    (nome, f['arquivo'], f['tipo'], f['descricao'], f['hash']))
    for de, para, tipo in relacoes:
        cur.execute('INSERT INTO memoria_relacao VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                    (de, para, tipo, para in fichas))
    quebradas = sum(1 for _, p, _ in relacoes if p not in fichas)
    print(f'{len(fichas)} fichas, {len(relacoes)} relacoes, {quebradas} apontando pro vazio')

def vizinhos(cur, nome):
    n = chave(nome)
    cur.execute('SELECT tipo, descricao FROM memoria_ficha WHERE nome=%s', (n,))
    r = cur.fetchone()
    if not r:
        cur.execute("SELECT nome FROM memoria_ficha WHERE nome LIKE %s LIMIT 8", (f'%{n}%',))
        alt = [x[0] for x in cur.fetchall()]
        print(f'nao achei "{n}".' + (f' voce quis dizer: {", ".join(alt)}' if alt else ''))
        return
    print(f'== {n}  [{r[0]}]\n   {r[1]}\n')
    cur.execute("""SELECT r.para, f.tipo, coalesce(f.descricao,''), r.tipo_rel, r.existe
                   FROM memoria_relacao r LEFT JOIN memoria_ficha f ON f.nome=r.para
                   WHERE r.de=%s ORDER BY r.existe DESC, r.para""", (n,))
    saida = cur.fetchall()
    print(f'-- ela aponta para ({len(saida)}):')
    for para, tipo, desc, rel, existe in saida:
        marca = '' if existe else '   << NAO EXISTE'
        print(f'   {rel:<11} {para:<48} {desc[:70]}{marca}')
    cur.execute("""SELECT r.de, f.tipo, coalesce(f.descricao,''), r.tipo_rel
                   FROM memoria_relacao r JOIN memoria_ficha f ON f.nome=r.de
                   WHERE r.para=%s ORDER BY r.de""", (n,))
    entrada = cur.fetchall()
    print(f'\n-- apontam para ela ({len(entrada)}):')
    for de, tipo, desc, rel in entrada:
        print(f'   {rel:<11} {de:<48} {desc[:70]}')

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd = sys.argv[1]
    con = psycopg2.connect(url()); con.autocommit = True; cur = con.cursor()
    if cmd == 'indexar':
        indexar(cur)
    elif cmd == 'vizinhos':
        vizinhos(cur, sys.argv[2])
    elif cmd == 'quebradas':
        cur.execute("""SELECT para, count(*), string_agg(de,', ' ORDER BY de)
                       FROM memoria_relacao WHERE NOT existe GROUP BY 1 ORDER BY 2 DESC""")
        linhas = cur.fetchall()
        print(f'{len(linhas)} alvos inexistentes:')
        for para, n, quem in linhas:
            print(f'  {para:<50} citado {n}x por {quem[:90]}')
    elif cmd == 'orfas':
        cur.execute("""SELECT f.nome, f.tipo FROM memoria_ficha f
                       WHERE NOT EXISTS (SELECT 1 FROM memoria_relacao r WHERE r.de=f.nome)
                         AND NOT EXISTS (SELECT 1 FROM memoria_relacao r WHERE r.para=f.nome AND r.existe)
                       ORDER BY 1""")
        r = cur.fetchall()
        print(f'{len(r)} fichas sem nenhuma ligacao:')
        for nome, tipo in r:
            print(f'  [{tipo}] {nome}')
    elif cmd == 'hubs':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        cur.execute("""SELECT r.para, count(*) FROM memoria_relacao r
                       WHERE r.existe GROUP BY 1 ORDER BY 2 DESC LIMIT %s""", (n,))
        for nome, q in cur.fetchall():
            print(f'  {q:>3}x  {nome}')
    elif cmd == 'depende':
        cur.execute("""SELECT para, existe FROM memoria_relacao
                       WHERE de=%s AND tipo_rel='depende_de'""", (chave(sys.argv[2]),))
        for para, existe in cur.fetchall():
            print(f'  {para}{"" if existe else "   << NAO EXISTE"}')
    else:
        print(__doc__)
    con.close()

if __name__ == '__main__':
    main()
