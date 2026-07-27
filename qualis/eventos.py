"""Base local de eventos (h5 do Google Scholar + relevância das CE-SBC)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "eventos.csv"


@dataclass
class Evento:
    sigla: str
    nome: str
    h5: int | None
    ce_sbc: str | None
    anos_tradicao: int | None
    segue_gt_capes: bool
    h5_fonte: str = ""
    h5_sbc: int | None = None
    ambiguo: bool = False
    ces: list[str] = field(default_factory=list)
    entradas_scholar: list[str] = field(default_factory=list)

    @property
    def h5_confiavel(self) -> bool:
        """O h5 veio do Google Scholar, que é o que o Documento de Área manda
        usar, e sem entradas concorrentes no índice."""
        return self.h5_fonte == "scholar" and not self.ambiguo


def _int(v: str) -> int | None:
    v = (v or "").strip()
    return int(v) if v else None


def carregar(caminho: Path | None = None) -> list[Evento]:
    caminho = caminho or ARQUIVO
    if not caminho.exists():
        return []
    with caminho.open(encoding="utf-8") as f:
        linhas = [l for l in f if not l.lstrip().startswith("//")]
    out = []
    for row in csv.DictReader(linhas):
        if not (row.get("sigla") or "").strip():
            continue
        out.append(
            Evento(
                sigla=row["sigla"].strip(),
                nome=(row.get("nome") or "").strip(),
                h5=_int(row.get("h5", "")),
                ce_sbc=(row.get("ce_sbc") or "").strip().lower() or None,
                anos_tradicao=_int(row.get("anos_tradicao", "")),
                segue_gt_capes=(row.get("segue_gt_capes") or "1").strip() != "0",
                h5_fonte=(row.get("h5_fonte") or "").strip(),
                h5_sbc=_int(row.get("h5_sbc", "")),
                ambiguo=(row.get("ambiguo") or "0").strip() == "1",
                ces=[c for c in (row.get("ces") or "").split("|") if c],
                entradas_scholar=[
                    e.strip()
                    for e in (row.get("entradas_scholar") or "").split("||")
                    if e.strip()
                ],
            )
        )
    return out


def buscar(consulta: str, caminho: Path | None = None) -> Evento | None:
    q = consulta.strip().lower()
    eventos = carregar(caminho)
    for e in eventos:
        if e.sigla.lower() == q:
            return e
    for e in eventos:
        if q in e.sigla.lower() or q in e.nome.lower():
            return e
    return None
