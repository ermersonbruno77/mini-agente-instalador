#!/usr/bin/env python3
"""Dados BR gratis (sem chave).
  br.py cep 01310100
  br.py cnpj 00000000000191
  br.py feriados 2026
"""
import sys, requests
B="https://brasilapi.com.br/api"
def cep(c):
    c=''.join(ch for ch in c if ch.isdigit())
    r=requests.get(f"{B}/cep/v2/{c}",timeout=20).json()
    print(f"{r.get('street','')}, {r.get('neighborhood','')} - {r.get('city','')}/{r.get('state','')} (CEP {r.get('cep','')})")
def cnpj(c):
    c=''.join(ch for ch in c if ch.isdigit())
    # 1) BrasilAPI
    try:
        r=requests.get(f"{B}/cnpj/v1/{c}",timeout=25)
        if r.status_code==200:
            d=r.json()
            print(f"Razao: {d.get('razao_social','')}\nFantasia: {d.get('nome_fantasia','')}\nSituacao: {d.get('descricao_situacao_cadastral','')}\nCidade: {d.get('municipio','')}/{d.get('uf','')}\nCNAE: {d.get('cnae_fiscal_descricao','')}")
            return
    except Exception:
        pass
    # 2) fallback ReceitaWS (gratis, 3/min)
    try:
        d=requests.get(f"https://receitaws.com.br/v1/cnpj/{c}",timeout=25,headers={'User-Agent':'Mozilla/5.0'}).json()
        if d.get('status')=='OK':
            ativ=(d.get('atividade_principal') or [{}])[0].get('text','')
            print(f"Razao: {d.get('nome','')}\nFantasia: {d.get('fantasia','')}\nSituacao: {d.get('situacao','')}\nCidade: {d.get('municipio','')}/{d.get('uf','')}\nAtividade: {ativ}")
        else:
            print(f"CNPJ nao encontrado: {d.get('message','erro')}")
    except Exception as e:
        print(f"erro consulta CNPJ: {e}")
def feriados(ano):
    for f in requests.get(f"{B}/feriados/v1/{ano}",timeout=20).json():
        print(f"{f['date']}  {f['name']}")

# Acrescentados em 16/08/2026, ordem dele depois de eu medir que a BrasilAPI
# entrega 11 servicos sem chave e a gente so usava 3. Ficam AQUI, no arquivo
# que ja fala com essa API, em vez de virar arquivo novo: e a mesma fonte.
# NAO entrou o `taxas` (Selic/CDI/IPCA) de proposito: isso agora vem do
# tools/bacen.py, direto do Banco Central. Entre a fonte e o intermediario,
# fica a fonte.
def ddd(d):
    d=''.join(ch for ch in d if ch.isdigit())
    r=requests.get(f"{B}/ddd/v1/{d}",timeout=20).json()
    if 'state' not in r: print(f"DDD {d} nao encontrado"); return
    cid=r.get('cities',[])
    print(f"DDD {d}: {r['state']}, {len(cid)} cidades. Ex: {', '.join(cid[:6])}")
def bancos(termo):
    achou=0
    for b in requests.get(f"{B}/banks/v1",timeout=25).json():
        nome=(b.get('fullName') or b.get('name') or '')
        if termo.lower() in nome.lower() or termo==str(b.get('code','')):
            print(f"{str(b.get('code','')):>4}  ISPB {b.get('ispb','')}  {nome}")
            achou+=1
    if not achou: print(f"nenhum banco com '{termo}'")
def ncm(termo):
    r=requests.get(f"{B}/ncm/v1",params={'search':termo},timeout=30).json()
    if not r: print(f"nenhum NCM com '{termo}'"); return
    for x in r[:12]: print(f"{x.get('codigo','')}  {x.get('descricao','')[:80]}")
def isbn(cod):
    cod=cod.replace('-','').strip()
    r=requests.get(f"{B}/isbn/v1/{cod}",timeout=30)
    if r.status_code!=200: print(f"ISBN {cod} nao encontrado"); return
    d=r.json()
    print(f"{d.get('title','')}\n{', '.join(d.get('authors') or [])}\n{d.get('publisher','')} {d.get('year','')}")
def pix(termo):
    achou=0
    for p in requests.get(f"{B}/pix/v1/participants",timeout=30).json():
        # Os dois campos, porque o nome de marca costuma estar so num deles:
        # "nubank" nao acha nada, "NU PAGAMENTOS" acha. Procurar nos dois
        # aumenta a chance de o termo que a gente tem na cabeca bater.
        nome=p.get('nome_reduzido') or ''
        longo=p.get('nome') or ''
        if termo.lower() in nome.lower() or termo.lower() in longo.lower():
            print(f"ISPB {p.get('ispb','')}  {nome}  ({p.get('tipo_participacao','')})")
            achou+=1
    if not achou: print(f"nenhum participante PIX com '{termo}'")
def dominio(nome):
    d=requests.get(f"{B}/registrobr/v1/{nome}",timeout=25).json()
    print(f"{d.get('fqdn',nome)}: {d.get('status','?')}"
          + (f" | expira {d.get('expires-at','')[:10]}" if d.get('expires-at') else ""))
def cambio(moeda):
    # Precisa de data, e a serie do BC nao tem fim de semana. Anda para tras
    # ate achar o ultimo dia util com cotacao, em vez de dizer "nao tem".
    import datetime
    hoje=datetime.date.today()
    for tras in range(0,8):
        dia=(hoje-datetime.timedelta(days=tras)).isoformat()
        r=requests.get(f"{B}/cambio/v1/cotacao/{moeda.upper()}/{dia}",timeout=25)
        if r.status_code==200 and (r.json().get('cotacoes') or []):
            c=r.json()['cotacoes'][-1]
            print(f"{moeda.upper()} em {dia}: compra {c.get('cotacao_compra')} venda {c.get('cotacao_venda')}")
            return
    print(f"sem cotacao de {moeda.upper()} nos ultimos 8 dias")

if __name__=='__main__':
    acoes={'cep':cep,'cnpj':cnpj,'feriados':feriados,'ddd':ddd,'bancos':bancos,
           'ncm':ncm,'isbn':isbn,'pix':pix,'dominio':dominio,'cambio':cambio}
    if len(sys.argv)<3 or sys.argv[1] not in acoes:
        print("uso: br.py "+"|".join(acoes)+" <valor>"); sys.exit(2)
    acoes[sys.argv[1]](sys.argv[2])
