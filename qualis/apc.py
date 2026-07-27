"""Periódicos com acordo de isenção de APC negociado pela CAPES.

APC é a *article processing charge* — a taxa que revistas de acesso aberto
cobram do autor para publicar. A CAPES mantém acordos transformativos com
algumas editoras nos quais a taxa é coberta para autores de instituições
participantes. Na prática, é a diferença entre publicar de graça e pagar de
mil a cinco mil dólares.

Para quem decide onde submeter isso pesa tanto quanto o estrato, e as duas
informações nunca aparecem juntas em lugar nenhum.

A base vem do projeto `acordos-capes` (SQLite), que reúne as listas publicadas
por ACM, ACS, Elsevier, IEEE, Royal Society, Springer Nature e Wiley. O
casamento é por **ISSN**, não por nome: nome de revista tem variação demais, e
um falso positivo aqui faria alguém contar com isenção que não existe.

O arquivo é lido em modo somente leitura e não é versionado neste repositório —
ele pertence ao outro projeto, e é lá que deve ser atualizado.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

BASE = Path("/Users/tardelli/Workplace/acordos-capes/acordos.db")

# Editoras cobertas pelos acordos, como aparecem na base de origem.
EDITORAS = (
    "ACM", "ACS", "Elsevier", "IEEE", "Royal Society", "Springer Nature", "Wiley",
)


@dataclass(frozen=True)
class Acordo:
    titulo: str
    editora: str
    tipo_oa: str
    licenca: str
    url: str


def normalizar_issn(v: object) -> str:
    """Só dígitos e o X final; a base de origem e a API grafam diferente."""
    return re.sub(r"[^0-9Xx]", "", str(v or "")).upper()


def carregar(caminho: Path | None = None) -> dict[str, Acordo]:
    """Mapa ISSN (normalizado) -> acordo. Um periódico costuma ter dois ISSNs."""
    caminho = caminho or BASE
    if not caminho.exists():
        return {}

    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    try:
        linhas = con.execute(
            "select title, publisher, issn, eissn, open_access_type, license, url "
            "from journals"
        ).fetchall()
    finally:
        con.close()

    out: dict[str, Acordo] = {}
    for titulo, editora, issn, eissn, tipo, licenca, url in linhas:
        acordo = Acordo(
            titulo=(titulo or "").strip(),
            editora=(editora or "").strip(),
            tipo_oa=(tipo or "").strip(),
            licenca=(licenca or "").strip(),
            url=(url or "").strip(),
        )
        for bruto in (issn, eissn):
            chave = normalizar_issn(bruto)
            if len(chave) == 8:
                out.setdefault(chave, acordo)
    return out


def buscar(issns: list[str], acordos: dict[str, Acordo] | None = None) -> Acordo | None:
    """Acordo de um periódico, a partir dos ISSNs que conhecemos dele."""
    acordos = acordos if acordos is not None else carregar()
    for i in issns or []:
        a = acordos.get(normalizar_issn(i))
        if a:
            return a
    return None
