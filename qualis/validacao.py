"""Confere o h5 coletado contra uma transcrição independente do Google Scholar.

Fonte: https://github.com/ASSERT-KTH/open-h5 — arquivo
`data/software_systems_google_scholar_h5.json`, transcrito de um snapshot do
Google Scholar Metrics de 30/06/2026 (categoria "Software Systems", top 20).

Vale a distinção, porque o repositório publica DUAS séries:

  - `software_systems_google_scholar_h5.json` — os valores **do Google**,
    transcritos de um snapshot. É isto que usamos: o Documento de Área manda
    usar "H5 do Google".
  - `software_systems_h5_median*.{csv,json}` — um h5 **recomputado** a partir
    do Semantic Scholar, proposto como alternativa aberta ao número fechado do
    Google. Correlaciona bem (Pearson 0,93) mas fica em média 3,86 pontos
    ABAIXO do Google. Não serve para a regra da CAPES: com cortes fixos a cada
    poucos pontos, um viés desses muda estrato.

São só 20 veículos, então isto não é uma base — é um teste de sanidade do
coletor, e é offline (nenhuma consulta ao Scholar).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "data" / "validacao_open_h5.json"


@dataclass
class Divergencia:
    sigla: str
    nome: str
    h5_nosso: int | None
    h5_referencia: int
    fonte: str

    @property
    def delta(self) -> int | None:
        return None if self.h5_nosso is None else self.h5_nosso - self.h5_referencia

    @property
    def confere(self) -> bool:
        return self.h5_nosso == self.h5_referencia


def referencia(caminho: Path | None = None) -> dict[str, dict]:
    """Mapa sigla -> registro do snapshot do Google Scholar."""
    with (caminho or FIXTURE).open(encoding="utf-8") as f:
        return {r["venue"].upper(): r for r in json.load(f)}


def comparar(caminho_fixture: Path | None = None) -> list[Divergencia]:
    """Compara a base local de eventos com o snapshot de referência."""
    from .eventos import carregar

    ref = referencia(caminho_fixture)
    nossos = {e.sigla.upper(): e for e in carregar()}

    out: list[Divergencia] = []
    for sigla, r in sorted(ref.items()):
        e = nossos.get(sigla)
        out.append(
            Divergencia(
                sigla=sigla,
                nome=r["venue_name"],
                h5_nosso=e.h5 if e else None,
                h5_referencia=int(r["h5_index"]),
                fonte=(e.h5_fonte if e else "ausente"),
            )
        )
    return out
