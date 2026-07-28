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
from dataclasses import dataclass
from pathlib import Path

DADOS = Path(__file__).resolve().parent.parent / "data"
PADRAO = "*JCR_JournalResults*.csv"

_CABECALHO = "Journal name"

# A tela do JCR exporta no máximo 600 linhas. Uma categoria que chega exatamente
# nesse número quase certamente foi cortada — e aí N está errado, o que erra o
# percentil de TODAS as revistas dela. Melhor não ter o dado do que tê-lo torto.
TETO_DO_EXPORT = 600
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
    """O JCR grafa milhares com vírgula ("123,304") e ausências como "N/A"."""
    t = str(v or "").replace(",", "").strip()
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
    categoria = m.group(1).strip() if m else caminho.stem
    cab = linhas[i]
    dados = [
        dict(zip(cab, r))
        for r in linhas[i + 1 :]
        if r and r[0].strip() and "Copyright" not in r[0]
    ]
    return categoria, dados


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
    """ISSN normalizado -> revista com o MAIOR percentil entre suas categorias."""
    pasta = pasta or DADOS
    melhor: dict[str, Revista] = {}
    truncadas: list[tuple[str, int]] = []

    for caminho in sorted(pasta.glob(PADRAO)):
        categoria, linhas = _ler(caminho)
        validas = [(r, _numero(r.get("2025 JIF"))) for r in linhas]
        validas = [(r, j) for r, j in validas if j is not None]
        validas.sort(key=lambda rj: -rj[1])
        total = len(validas)
        if not total:
            continue
        if total >= TETO_DO_EXPORT:
            truncadas.append((categoria, total))
            continue

        for (linha, jif), posicao in zip(validas, _posicoes([j for _, j in validas])):
            pct = (total - posicao + 0.5) / total * 100
            issns = tuple(
                i
                for i in (
                    normalizar_issn(linha.get("ISSN")),
                    normalizar_issn(linha.get("eISSN")),
                )
                if i
            )
            if not issns:
                continue
            rev = Revista(
                titulo=(linha.get("Journal name") or "").strip(),
                percentil=round(pct, 1),
                categoria=categoria,
                jif=jif,
                posicao=posicao,
                total=total,
                issns=issns,
            )
            for i in issns:
                atual = melhor.get(i)
                if atual is None or rev.percentil > atual.percentil:
                    melhor[i] = rev

    for categoria, n in truncadas:
        print(
            f"  JCR: categoria {categoria!r} ignorada — {n} linhas, no teto de "
            f"{TETO_DO_EXPORT} do export. Reexporte em partes (por quartil ou "
            f"edição) para o percentil ficar correto."
        )
    return melhor


def buscar(issns: list[str], base: dict[str, Revista]) -> Revista | None:
    for i in issns or []:
        r = base.get(normalizar_issn(i))
        if r:
            return r
    return None
