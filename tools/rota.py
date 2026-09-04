#!/usr/bin/env python3
"""Calcula distância e tempo de carro entre dois pontos, na malha viária real.

Criado em 02/08/2026 por ordem direta do Chefe: "sempre calcula no mapa antes de me
mandar, sempre, não faça especulação nenhuma". Eu tinha dito que Bitupitá ficava a
1h30 de Acaraú; o Google Maps dele mostrou 2h21.

Usa o OSRM público (OpenStreetMap). Não precisa de chave.

Por que não usar os sites de distância: `adistanciaentre.com` devolveu, para
Acaraú -> Icaraí de Amontada, a rota de Beja para Faro, em Portugal. Fonte que
responde bonito com o dado errado é pior que não ter fonte.

Uso:
    python3 tools/rota.py "-40.12,-2.8858" "-39.6394,-2.8836"
    python3 tools/rota.py --lugar Acarau --lugar "Icarai de Amontada"   (usa o cache abaixo)
"""
import json
import sys
import urllib.parse
import urllib.request

OSRM = 'http://router.project-osrm.org/route/v1/driving/%s;%s?overview=false'
NOMINATIM = 'https://nominatim.openstreetmap.org/search?q=%s&format=json&limit=1'

# Lugares que já usei com o Chefe, para não geocodificar de novo. lon,lat
CACHE = {
    'acarau': (-40.1200, -2.8858),
    'icarai de amontada': (-39.6394, -2.8836),
    'almofala': (-39.8069, -2.9364),
    'camocim': (-40.8408, -2.9019),
    'itarema': (-39.9167, -2.9206),
    'meruoca': (-40.4536, -3.5397),
    'sobral': (-40.3497, -3.6861),
    'jijoca de jericoacoara': (-40.5439, -2.7981),
    'bitupita': (-41.1500, -2.9000),
}


def coord(lugar):
    k = lugar.strip().lower()
    if k in CACHE:
        return CACHE[k]
    req = urllib.request.Request(NOMINATIM % urllib.parse.quote(lugar + ', Brasil'),
                                 headers={'User-Agent': '{{AGENTE_NAME_LOWERCASE}}/1.0'})
    d = json.load(urllib.request.urlopen(req, timeout=25))
    if not d:
        raise SystemExit('nao achei o lugar: %s' % lugar)
    return float(d[0]['lon']), float(d[0]['lat'])


def rota(a, b):
    url = OSRM % ('%f,%f' % a, '%f,%f' % b)
    r = json.load(urllib.request.urlopen(url, timeout=30))['routes'][0]
    return r['distance'] / 1000, r['duration']


def main(argv):
    lugares = [a for a in argv if a != '--lugar']
    if len(lugares) < 2:
        raise SystemExit(__doc__)
    pontos = []
    for l in lugares:
        if ',' in l and l.replace(',', '').replace('.', '').replace('-', '').isdigit():
            lon, lat = l.split(',')
            pontos.append((float(lon), float(lat)))
        else:
            pontos.append(coord(l))
    origem = pontos[0]
    for nome, p in zip(lugares[1:], pontos[1:]):
        km, seg = rota(origem, p)
        print('%-24s %6.1f km   %dh%02dmin' % (nome, km, seg // 3600, (seg % 3600) // 60))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
