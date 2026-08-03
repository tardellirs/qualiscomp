"""Percentil do Web of Science, a partir dos exports do Journal Citation Reports.

A regra da Área 02 manda usar "o percentil da WoS ou Scopus – o maior entre os
dois". Até aqui o site só tinha Scopus, o que tornava toda estimativa um piso:
nunca superestimávamos, mas subestimávamos toda vez que o WoS fosse maior.

Este módulo fecha essa metade. A fonte são os CSV exportados de
`jcr.clarivate.com`, uma exportação por categoria (a tela limita a 600 linhas
por vez, e as categorias de Computação cabem folgadamente nisso).

## O percentil é calculado, não lido

O export padrão do JCR **não traz a coluna JIF Percentile** — traz o JIF e o
quartil. Mas o percentil da Clarivate é posicional e reconstituível:

    percentil = (N - R + 0,5) / N × 100

com R = posição da revista por JIF decrescente na categoria e N = total de
revistas com JIF na categoria. Como o export traz a categoria inteira, N e R
são conhecidos.

Isso não é aproximação: foi conferido contra 16 valores de JIF Percentile
publicados pela própria Clarivate, e **os 16 batem na casa decimal, diferença
zero** — inclusive o caso de empate (iScience e Annals of the NYAS têm o mesmo
JIF 4,5 e o mesmo percentil 83,2). O teste está em `test_jcr.py`.

Empatados recebem a MENOR posição do grupo, o que reproduz esse comportamento.

## Uma revista, várias categorias

O JCR classifica a mesma revista em quantas categorias couber, com percentil
diferente em cada. Ficamos com o maior — é a mesma convenção da coluna "Highest
percentile" do Scopus, e a mesma que a regra usa ao mandar pegar o maior entre
as duas bases.

## Licença

Dado do JCR é licenciado pela Clarivate e chega via assinatura do Portal de
Periódicos da CAPES. Os CSV ficam em `data/` e fora do versionamento; o site
publica apenas o **estrato derivado**, resultado de regra pública da CAPES, e
nunca o JIF ou o percentil bruto.
"""

from __future__ import annotations

import csv
import re
from decimal import ROUND_HALF_UP, Decimal
from dataclasses import dataclass
from pathlib import Path

DADOS = Path(__file__).resolve().parent.parent / "data"
PADRAO = "*JCR_JournalResults*.csv"

_CABECALHO = "Journal name"

# A tela do JCR exporta no máximo 600 linhas. Uma categoria que chega exatamente
# nesse número quase certamente foi cortada — e aí N está errado, o que erra o
# percentil de TODAS as revistas dela. Melhor não ter o dado do que tê-lo torto.
TETO_DO_EXPORT = 600

# Quando o export traz esta coluna, o percentil é lido da Clarivate em vez de
# reconstituído. Vale sempre a pena pedi-la na tela do JCR.
COLUNA_PERCENTIL = "JIF Percentile"
_CATEGORIA = re.compile(r"Selected Categories:\s*(.*?)\s*Selected Editions")


@dataclass(frozen=True)
class Revista:
    titulo: str
    percentil: float
    categoria: str
    jif: float
    posicao: int
    total: int
    issns: tuple[str, ...]


def normalizar_issn(v: object) -> str:
    t = re.sub(r"[^0-9Xx]", "", str(v or "")).upper()
    return t if len(t) == 8 else ""


def _numero(v: object) -> float | None:
    """O JCR grafa milhares com vírgula ("123,304") e ausências como "N/A".

    Também grafa impacto muito baixo como **"<0.1"**. Essas revistas TÊM JIF e
    entram no ranking da categoria — descartá-las encolhe N e baixa o percentil
    de todas as outras. Em Education eram 16 de 760, e o erro resultante era de
    um ponto percentual em toda a categoria.

    Elas ficam no fim da fila, empatadas, que é como o próprio JCR as trata
    (as 16 receberam percentil 2,0 idêntico).
    """
    t = str(v or "").replace(",", "").strip()
    if t.startswith("<"):
        return 0.0
    try:
        return float(t)
    except ValueError:
        return None


def _ler(caminho: Path) -> tuple[str, list[dict]]:
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        linhas = list(csv.reader(fh))
    if not linhas:
        return "", []
    i = next(
        (j for j, r in enumerate(linhas) if r and r[0].strip() == _CABECALHO), None
    )
    if i is None:
        return "", []
    m = _CATEGORIA.search(linhas[0][0] if linhas[0] else "")
    # Sem "Selected Categories:" o export foi filtrado por outra coisa — o de
    # revistas brasileiras usa "Selected Country/region: BRAZIL" e traz 122
    # categorias misturadas. Aí não há categoria única, e ranquear as linhas
    # juntas daria percentil sem sentido.
    categoria = m.group(1).strip() if m else ""
    cab = linhas[i]
    dados = [
        dict(zip(cab, r))
        for r in linhas[i + 1 :]
        if r and r[0].strip() and "Copyright" not in r[0]
    ]
    return categoria, dados


def _uma_casa(x: float) -> float:
    """Arredonda para uma casa, meia para CIMA.

    O `round()` do Python arredonda meia para o par ("bancário"), e isso
    divergia do JCR em 39 das 760 revistas de Education. Meia para cima acerta
    as 760.
    """
    return float(Decimal(str(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _posicoes(ordenadas: list[float]) -> list[int]:
    """Ranking de competição: empatados recebem a MENOR posição do grupo.

    É o que a Clarivate faz — duas revistas com o mesmo JIF saem com o mesmo
    percentil publicado. Ver a conferência no cabeçalho do módulo.
    """
    out: list[int] = []
    i = 0
    while i < len(ordenadas):
        j = i
        while j + 1 < len(ordenadas) and ordenadas[j + 1] == ordenadas[i]:
            j += 1
        out.extend([i + 1] * (j - i + 1))
        i = j + 1
    return out


def carregar(pasta: Path | None = None) -> dict[str, Revista]:
    """ISSN normalizado -> revista com o MAIOR percentil entre suas categorias.

    Há dois caminhos, e o primeiro é sempre melhor:

    1. **O export traz a coluna `JIF Percentile`.** Lemos o valor da Clarivate,
       linha a linha, com a categoria da própria linha. Exato, e funciona mesmo
       quando o export não é de uma categoria — o de revistas brasileiras filtra
       por país e mistura 122 categorias.

    2. **Não traz.** Reconstituímos pela posição: (N - R + 0,5) / N sobre a
       categoria inteira, juntando os arquivos que a compõem (Education tem 775
       revistas e sai em duas partes). Isso exige saber qual é a categoria, e
       que ela esteja completa — por isso um export sem "Selected Categories:"
       no cabeçalho, ou cortado no teto de 600, é recusado em vez de virar
       número torto.
    """
    pasta = pasta or DADOS
    porcategoria: dict[str, dict[tuple[str, ...], tuple[dict, float]]] = {}
    truncadas: list[tuple[str, int]] = []
    sem_categoria: list[str] = []
    melhor: dict[str, Revista] = {}

    def guardar(rev: Revista, issns: tuple[str, ...]) -> None:
        for i in issns:
            atual = melhor.get(i)
            if atual is None or rev.percentil > atual.percentil:
                melhor[i] = rev

    def chave(linha: dict) -> tuple[str, ...]:
        return tuple(
            i
            for i in (
                normalizar_issn(linha.get("ISSN")),
                normalizar_issn(linha.get("eISSN")),
            )
            if i
        )

    for caminho in sorted(pasta.glob(PADRAO)):
        categoria, linhas = _ler(caminho)
        if not linhas:
            continue

        if COLUNA_PERCENTIL in linhas[0]:
            for linha in linhas:
                pct = _numero(linha.get(COLUNA_PERCENTIL))
                issns = chave(linha)
                if pct is None or not issns:
                    continue
                guardar(
                    Revista(
                        titulo=(linha.get("Journal name") or "").strip(),
                        percentil=pct,
                        categoria=(linha.get("Category") or categoria).strip(),
                        jif=_numero(linha.get("2025 JIF")) or 0.0,
                        posicao=0,
                        total=0,
                        issns=issns,
                    ),
                    issns,
                )
            continue

        if not categoria:
            sem_categoria.append(caminho.name)
            continue

        completas = [(r, _numero(r.get("2025 JIF"))) for r in linhas]
        completas = [(r, j) for r, j in completas if j is not None]
        # O teto vale sobre as LINHAS EXPORTADAS, não sobre as que têm JIF:
        # ECONOMICS veio com 601 linhas e 599 com JIF, e passava pela guarda
        # contando as 599 — quando na verdade tinha sido cortada em 600.
        if len(linhas) >= TETO_DO_EXPORT:
            truncadas.append((categoria, len(linhas)))
            porcategoria[categoria] = {}
            continue
        if porcategoria.get(categoria) == {}:
            continue  # já descartada por truncamento
        alvo = porcategoria.setdefault(categoria, {})
        for linha, jif in completas:
            issns = chave(linha)
            if issns:
                # Partes de uma mesma categoria se sobrepõem nas bordas; contar
                # a repetição duas vezes inflaria N e baixaria todo mundo.
                alvo[issns] = (linha, jif)

    for categoria, revistas in porcategoria.items():
        validas = sorted(revistas.items(), key=lambda kv: -kv[1][1])
        total = len(validas)
        if not total:
            continue
        posicoes = _posicoes([jif for _, (_, jif) in validas])
        for (issns, (linha, jif)), posicao in zip(validas, posicoes):
            guardar(
                Revista(
                    titulo=(linha.get("Journal name") or "").strip(),
                    percentil=_uma_casa((total - posicao + 0.5) / total * 100),
                    categoria=categoria,
                    jif=jif,
                    posicao=posicao,
                    total=total,
                    issns=issns,
                ),
                issns,
            )

    for categoria, n in truncadas:
        print(
            f"  JCR: categoria {categoria!r} ignorada — um arquivo com {n} "
            f"linhas, no teto de {TETO_DO_EXPORT} do export. Reexporte em "
            f"partes (por faixa de JIF) para o percentil ficar correto."
        )
    for nome in sem_categoria:
        print(
            f"  JCR: {nome} ignorado — o export não é de uma categoria e não "
            f"traz a coluna {COLUNA_PERCENTIL!r}. Sem os dois não há como saber "
            f"o percentil."
        )
    return melhor


def buscar(issns: list[str], base: dict[str, Revista]) -> Revista | None:
    for i in issns or []:
        r = base.get(normalizar_issn(i))
        if r:
            return r
    return None
