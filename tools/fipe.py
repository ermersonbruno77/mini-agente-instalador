#!/usr/bin/env python3
"""Tabela FIPE por nome, sem cadastro e sem chave.

Criado em 16/08/2026, ordem dele: "Fipe, instale". Serve para acompanhar o
preço de um carro sozinho, sem depender de site de anúncio, que sempre puxa o
preço para o lado de quem está vendendo.

Busca por NOME de propósito. A API oficial exige três chamadas encadeadas com
código numérico (marca -> modelo -> ano), e ninguém tem esse código na cabeça.
Aqui se escreve "amarok highline" e o programa acha.

TRÊS PROVEDORES, nesta ordem, e a ordem mudou em 22/08/2026:

1. `veiculos.fipe.org.br`, a API OFICIAL. É a primária desde 22/08/2026.
   Responde sem chave e sem teto de requisição medido. Exige POST com os
   cabeçalhos `Referer` e `User-Agent`, senão devolve erro.
2. `parallelum.com.br`, espelho. Era o primário até 22/08/2026, quando passou
   a responder "limite de taxa excedido... obter um token" em modelos, anos e
   preço. Fica como reserva.
3. `brasilapi.com.br`, espelho. Serve para listar marca e modelo. **Não fecha
   preço**: a listagem de modelos dela não devolve `codigoFipe`, que o preço
   dela exige. Por isso só entra em `marcas` e na listagem de modelos.

O que derrubou o espelho em 22/08/2026 foi o DESENHO daqui, não só o provedor:
buscar por nome varria as ~100 marcas, uma requisição por marca, a cada busca.
Quatro buscas em paralelo bloquearam o provedor. Daí as três travas de agora:
cache em disco de 1 dia (`workspace/.cache-fipe/`), uma requisição por vez com
pausa mínima entre elas, e `--marca` para não varrer o catálogo inteiro.

`--ano` faz parte da BUSCA, não é filtro aplicado depois. "hb20s" tem 48
versões e só 6 existem em 2016: cortar em `--limite` antes de olhar o ano
jogava fora justamente a versão certa.

O valor vem com o MÊS DE REFERÊNCIA junto, sempre. Preço de tabela sem o mês é
número solto: a FIPE muda todo mês, e citar o valor sem dizer de quando é o
mesmo erro de citar saldo sem data.

Uso:
    python3 tools/fipe.py preco "amarok highline" --ano 2022
    python3 tools/fipe.py preco "t-cross" --ano 2021 --marca vw
    python3 tools/fipe.py preco "biz 125" --tipo motos
    python3 tools/fipe.py marcas --tipo carros --filtro volks
"""
import argparse
import json
import os
import sys
import time
import unicodedata
import urllib.request

OFICIAL = "https://veiculos.fipe.org.br/api/veiculos"
PARALLELUM = "https://parallelum.com.br/fipe/api/v1"
BRASILAPI = "https://brasilapi.com.br/api/fipe"
TIPOS = ("carros", "motos", "caminhoes")

# Código do tipo de veículo e o rótulo, do jeito que a API oficial pede.
COD_TIPO = {"carros": 1, "motos": 2, "caminhoes": 3}
NOME_TIPO = {"carros": "carro", "motos": "moto", "caminhoes": "caminhao"}

CACHE = "/opt/{{AGENTE_NAME_LOWERCASE}}/workspace/.cache-fipe"
VALIDADE = 86400  # 1 dia

# Pausa entre duas requisições, sempre em série. Medido em 22/08/2026: a
# oficial também devolve 429 se apertar. Varrendo as 107 marcas de carro a
# 0,35s ela recusou 3. A pausa começa em 0,6s e SOBE sozinha a cada 429, e o
# que era recusa vira espera, não vira modelo faltando na lista.
PAUSA = 0.6
PAUSA_TETO = 3.0
TENTATIVAS = 3
_ultima = 0.0


def _aviso(msg: str) -> None:
    """Diagnóstico vai para stderr para não sujar a saída que o humano lê."""
    print(f"[fipe] {msg}", file=sys.stderr)


def _esperar() -> None:
    """Nunca dispara duas requisições juntas, nem sem intervalo."""
    global _ultima
    falta = PAUSA - (time.monotonic() - _ultima)
    if falta > 0:
        time.sleep(falta)
    _ultima = time.monotonic()


def _devagar(e: Exception) -> None:
    """Levou 429: espera e passa a andar mais devagar pelo resto da execução."""
    global PAUSA
    if "429" in str(e) or "limite" in str(e).lower():
        PAUSA = min(PAUSA * 1.6, PAUSA_TETO)


def _tentar(fazer):
    """Uma requisição por vez, com repetição em série. Nunca em paralelo."""
    erro = None
    for i in range(TENTATIVAS):
        try:
            _esperar()
            return fazer()
        except Exception as e:  # noqa: BLE001 - qualquer falha de rede repete
            erro = e
            _devagar(e)
            if i < TENTATIVAS - 1:
                time.sleep(2.0 * (i + 1))
    raise erro


def _get(url: str):
    def uma():
        req = urllib.request.Request(url, headers={"User-Agent": "{{AGENTE_NAME_LOWERCASE}}/1.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.loads(r.read().decode("utf-8"))
        if isinstance(d, dict) and "error" in d:
            # O espelho devolve 200 com {"error": "limite de taxa excedido"}.
            raise RuntimeError(str(d["error"])[:120])
        return d

    return _tentar(uma)


def _post(rota: str, corpo: dict):
    req = urllib.request.Request(
        f"{OFICIAL}/{rota}",
        data=json.dumps(corpo).encode(),
        headers={
            "Content-Type": "application/json",
            # Os dois cabeçalhos abaixo são obrigatórios: sem eles a oficial recusa.
            "Referer": "https://veiculos.fipe.org.br/",
            "User-Agent": "Mozilla/5.0",
        },
    )

    def uma():
        with urllib.request.urlopen(req, timeout=45) as r:
            d = json.loads(r.read().decode("utf-8"))
        if isinstance(d, dict) and ("erro" in d or "error" in d):
            raise RuntimeError(str(d.get("erro") or d.get("error"))[:120])
        return d

    return _tentar(uma)


def _cache_ler(chave: str):
    caminho = os.path.join(CACHE, chave + ".json")
    try:
        if time.time() - os.path.getmtime(caminho) > VALIDADE:
            return None
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _cache_gravar(chave: str, dados) -> None:
    try:
        os.makedirs(CACHE, exist_ok=True)
        caminho = os.path.join(CACHE, chave + ".json")
        tmp = caminho + ".parcial"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f)
        os.replace(tmp, caminho)
    except OSError as e:
        _aviso(f"cache não gravou ({e}), segue sem cache")


def _simples(s: str) -> str:
    """Sem acento e minúsculo, para comparar 'Citroën' com 'citroen'."""
    n = unicodedata.normalize("NFD", s)
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower()


# ----------------------------------------------------------------------------
# Provedores. Cada um fala o MESMO formato interno:
#   marca/modelo -> {"codigo": str, "nome": str}
#   ano          -> {"codigo": "2016-1", "nome": "2016 Gasolina"}
#   valor        -> dict com Valor, AnoModelo, Marca, Modelo, CodigoFipe, MesReferencia
#
# O código de marca e de modelo NÃO se mistura entre provedores. Por isso a
# cadeia inteira de uma busca roda no MESMO provedor, e o cache é separado por
# provedor no nome do arquivo.
# ----------------------------------------------------------------------------
class Oficial:
    nome = "oficial"
    faz_preco = True

    def __init__(self):
        self._tab = None
        self._mes = ""

    def tabela(self) -> int:
        if self._tab is None:
            c = _cache_ler("oficial-tabela")
            if not c:
                # O primeiro item da lista é sempre o mês corrente.
                t = _post("ConsultarTabelaDeReferencia", {})[0]
                c = {"codigo": t["Codigo"], "mes": str(t["Mes"]).strip()}
                _cache_gravar("oficial-tabela", c)
            self._tab, self._mes = c["codigo"], c["mes"]
        return self._tab

    def rotulo(self) -> str:
        return f"{self.nome} (tabela {self.tabela()}, {self._mes})"

    def marcas(self, tipo: str) -> list:
        d = _post(
            "ConsultarMarcas",
            {"codigoTabelaReferencia": self.tabela(), "codigoTipoVeiculo": COD_TIPO[tipo]},
        )
        return [{"codigo": str(m["Value"]), "nome": m["Label"]} for m in d]

    def modelos(self, tipo: str, cod_marca: str) -> list:
        d = _post(
            "ConsultarModelos",
            {
                "codigoTabelaReferencia": self.tabela(),
                "codigoTipoVeiculo": COD_TIPO[tipo],
                "codigoMarca": cod_marca,
            },
        )
        return [{"codigo": str(m["Value"]), "nome": m["Label"]} for m in d["Modelos"]]

    def anos(self, tipo: str, cod_marca: str, cod_modelo: str) -> list:
        d = _post(
            "ConsultarAnoModelo",
            {
                "codigoTabelaReferencia": self.tabela(),
                "codigoTipoVeiculo": COD_TIPO[tipo],
                "codigoMarca": cod_marca,
                "codigoModelo": cod_modelo,
            },
        )
        return [{"codigo": str(a["Value"]), "nome": a["Label"]} for a in d]

    def valor(self, tipo: str, cod_marca: str, cod_modelo: str, cod_ano: str) -> dict:
        # "2016-1": o 1 depois do traço é o código do combustível, não o mês.
        ano, comb = cod_ano.split("-")
        return _post(
            "ConsultarValorComTodosParametros",
            {
                "codigoTabelaReferencia": self.tabela(),
                "codigoTipoVeiculo": COD_TIPO[tipo],
                "codigoMarca": cod_marca,
                "codigoModelo": cod_modelo,
                "anoModelo": int(ano),
                "codigoTipoCombustivel": int(comb),
                "tipoVeiculo": NOME_TIPO[tipo],
                "tipoConsulta": "tradicional",
            },
        )


class Parallelum:
    nome = "parallelum"
    faz_preco = True

    def rotulo(self) -> str:
        return self.nome

    def marcas(self, tipo: str) -> list:
        return [
            {"codigo": str(m["codigo"]), "nome": m["nome"]}
            for m in _get(f"{PARALLELUM}/{tipo}/marcas")
        ]

    def modelos(self, tipo: str, cod_marca: str) -> list:
        d = _get(f"{PARALLELUM}/{tipo}/marcas/{cod_marca}/modelos")
        return [{"codigo": str(m["codigo"]), "nome": m["nome"]} for m in d["modelos"]]

    def anos(self, tipo: str, cod_marca: str, cod_modelo: str) -> list:
        d = _get(f"{PARALLELUM}/{tipo}/marcas/{cod_marca}/modelos/{cod_modelo}/anos")
        return [{"codigo": str(a["codigo"]), "nome": a["nome"]} for a in d]

    def valor(self, tipo: str, cod_marca: str, cod_modelo: str, cod_ano: str) -> dict:
        return _get(
            f"{PARALLELUM}/{tipo}/marcas/{cod_marca}/modelos/{cod_modelo}/anos/{cod_ano}"
        )


class BrasilApi:
    nome = "brasilapi"
    # Lista marca e modelo, mas o preço dela exige codigoFipe, que a listagem
    # de modelos não entrega. Então não fecha a cadeia: só serve de reserva
    # para LISTAR.
    faz_preco = False

    def rotulo(self) -> str:
        return self.nome

    def marcas(self, tipo: str) -> list:
        return [
            {"codigo": str(m["valor"]), "nome": m["nome"]}
            for m in _get(f"{BRASILAPI}/marcas/v1/{tipo}")
        ]

    def modelos(self, tipo: str, cod_marca: str) -> list:
        d = _get(f"{BRASILAPI}/veiculos/v1/{tipo}/{cod_marca}")
        return [{"codigo": str(m.get("valor", "")), "nome": m["modelo"]} for m in d]

    def anos(self, tipo, cod_marca, cod_modelo):
        raise RuntimeError("brasilapi não fecha preço (falta codigoFipe)")

    def valor(self, tipo, cod_marca, cod_modelo, cod_ano):
        raise RuntimeError("brasilapi não fecha preço (falta codigoFipe)")


def _provedores(para_preco: bool) -> list:
    p = [Oficial(), Parallelum(), BrasilApi()]
    return [x for x in p if x.faz_preco or not para_preco]


def _marcas_cache(prov, tipo: str) -> list:
    chave = f"{prov.nome}-{tipo}-marcas"
    c = _cache_ler(chave)
    if c:
        return c
    d = prov.marcas(tipo)
    _cache_gravar(chave, d)
    return d


def _modelos_cache(prov, tipo: str, cod_marca: str) -> list:
    chave = f"{prov.nome}-{tipo}-modelos-{cod_marca}"
    c = _cache_ler(chave)
    if c:
        return c
    d = prov.modelos(tipo, cod_marca)
    _cache_gravar(chave, d)
    return d


def marcas(tipo: str, filtro: str | None) -> None:
    erros = []
    for prov in _provedores(para_preco=False):
        try:
            lista = _marcas_cache(prov, tipo)
        except Exception as e:
            erros.append(f"{prov.nome}: {e}")
            continue
        _aviso(f"provedor: {prov.rotulo()}")
        for m in lista:
            if not filtro or _simples(filtro) in _simples(m["nome"]):
                print(f"{m['codigo']:>5}  {m['nome']}")
        return
    raise SystemExit("nenhum provedor da FIPE respondeu. " + " | ".join(erros))


def _anos_cache(prov, tipo: str, cod_marca: str, cod_modelo: str) -> list:
    chave = f"{prov.nome}-{tipo}-anos-{cod_marca}-{cod_modelo}"
    c = _cache_ler(chave)
    if c:
        return c
    d = prov.anos(tipo, cod_marca, cod_modelo)
    _cache_gravar(chave, d)
    return d


def _buscar(prov, tipo: str, palavras: list, filtro_marca: str | None, ano: str | None, limite: int):
    """Procura e JÁ resolve o ano, porque cortar em `limite` antes de olhar o
    ano jogava fora o modelo certo: "hb20s" tem 48 versões e só 6 existem em
    2016. O ano é parte da busca, não um filtro aplicado depois do corte.

    Devolve (resultados, sem_ano, varridas, falhas). Falha de provedor não é
    "não achei": os dois contadores voltam separados de propósito.
    """
    todas = _marcas_cache(prov, tipo)
    if filtro_marca:
        alvo = _simples(filtro_marca)
        todas = [m for m in todas if alvo in _simples(m["nome"])]
        if not todas:
            raise SystemExit(
                f"nenhuma marca com '{filtro_marca}'. Veja: fipe.py marcas --filtro {filtro_marca}"
            )

    resultados, sem_ano, falhas, varridas = [], [], 0, 0
    for marca in todas:
        try:
            modelos = _modelos_cache(prov, tipo, marca["codigo"])
        except Exception:
            falhas += 1
            continue
        varridas += 1
        for mod in modelos:
            if not all(p in _simples(mod["nome"]) for p in palavras):
                continue
            try:
                anos = _anos_cache(prov, tipo, marca["codigo"], mod["codigo"])
            except Exception:
                falhas += 1
                continue
            escolhidos = [a for a in anos if not ano or a["codigo"].startswith(str(ano))]
            if escolhidos:
                resultados.append((marca, mod, escolhidos[:3]))
                if len(resultados) >= limite:
                    return resultados, sem_ano, varridas, falhas
            elif len(sem_ano) < limite:
                sem_ano.append((marca, mod, anos))
    return resultados, sem_ano, varridas, falhas


def preco(termo: str, tipo: str, ano: str | None, limite: int, marca_filtro: str | None) -> None:
    palavras = [p for p in _simples(termo).split() if p]
    if not palavras:
        raise SystemExit("diga o que procurar, ex: \"amarok highline\"")

    # A primeira palavra costuma ser o modelo, não a marca ("amarok", "onix").
    # Então varre modelo de TODAS as marcas em vez de exigir que ele saiba a
    # marca. É mais lento e é o que torna o comando usável por gente. Quem
    # souber a marca passa --marca e corta a varredura.
    erros = []
    for prov in _provedores(para_preco=True):
        try:
            resultados, sem_ano, varridas, falhas = _buscar(
                prov, tipo, palavras, marca_filtro, ano, limite
            )
        except SystemExit:
            raise
        except Exception as e:
            erros.append(f"{prov.nome}: {e}")
            _aviso(f"{prov.nome} falhou ({e}), tentando o próximo")
            continue

        _aviso(f"provedor: {prov.rotulo()} | {varridas} marca(s) varrida(s), {falhas} falha(s)")

        if not resultados and not sem_ano:
            if falhas:
                # Distinção que faltava: catálogo incompleto não é ausência.
                raise SystemExit(
                    f"não deu para concluir: {prov.nome} falhou em {falhas} consulta(s) durante a "
                    f"varredura de {varridas} marca(s). Nada com '{termo}' no que respondeu, mas "
                    f"pode existir no que faltou. Tente de novo em alguns minutos."
                )
            raise SystemExit(
                f"nada com '{termo}' em {tipo}. {prov.nome} respondeu {varridas} marca(s) sem "
                f"erro, então é o termo que não casa. Tente menos palavras."
            )

        houve_valor = False
        for marca, mod, anos in resultados:
            for a in anos:
                try:
                    d = prov.valor(tipo, marca["codigo"], mod["codigo"], a["codigo"])
                except Exception as e:
                    print(f"{marca['nome']} {mod['nome']} {a['nome']}: provedor falhou no valor ({e})")
                    continue
                houve_valor = True
                print(f"{d['Valor']:>16}  {d['AnoModelo']}  {d['Marca']} {d['Modelo']}")
                print(f"{'':16}  tabela de {d['MesReferencia']}, código FIPE {d['CodigoFipe']}")

        if not resultados:
            # Achou o modelo, não naquele ano: diz o que existe, como antes.
            for marca, mod, anos in sem_ano[:limite]:
                disponiveis = ", ".join(a["nome"] for a in anos[:6])
                print(f"{marca['nome']} {mod['nome']}: não tem {ano}. Tem: {disponiveis}")
            return

        if houve_valor:
            return
        erros.append(f"{prov.nome}: achou o modelo e não fechou o valor")
        _aviso(f"{prov.nome} achou o modelo e não devolveu valor, tentando o próximo")
    raise SystemExit("nenhum provedor da FIPE fechou o preço. " + " | ".join(erros))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("marcas", help="lista as marcas")
    m.add_argument("--tipo", choices=TIPOS, default="carros")
    m.add_argument("--filtro")

    v = sub.add_parser("preco", help="acha o veículo pelo nome e mostra o valor")
    v.add_argument("termo", help='ex: "amarok highline"')
    v.add_argument("--tipo", choices=TIPOS, default="carros")
    v.add_argument("--ano")
    v.add_argument("--limite", type=int, default=3)
    v.add_argument("--marca", help="limita a varredura a uma marca, ex: --marca vw")

    a = p.parse_args()
    if a.cmd == "marcas":
        marcas(a.tipo, a.filtro)
    else:
        preco(a.termo, a.tipo, a.ano, a.limite, a.marca)


if __name__ == "__main__":
    main()
