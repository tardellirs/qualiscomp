"""Próximas edições dos eventos, com data e prazo de submissão.

Quem consulta o estrato de um evento quase sempre quer a mesma coisa em
seguida: quando é, e até quando dá para submeter. Hoje isso exige achar o site
da edição do ano, que muda de endereço todo ano. Juntar as duas informações é o
que este site pode fazer e nenhum outro faz.

## Por que é um CSV curado, e não raspagem

Não existe fonte legível por máquina. A SBC não publica calendário em iCal, JSON
ou API, e cada evento tem site próprio, com layout próprio, que muda a cada
edição. Raspar 89 sites seria frágil de um jeito perigoso: um seletor quebrado
não daria erro, daria **prazo errado** — e prazo errado faz alguém perder uma
submissão. É a única informação deste site que tem consequência imediata e
irreversível.

Então o arquivo é curado à mão, cada linha com a URL de onde a data foi lida, e
o site mostra **quando foi conferido pela última vez**. Envelhecer é inevitável;
envelhecer em silêncio é que não pode.

## O que este módulo NÃO faz

Não inventa data. Sem `data_inicio` confirmada, a edição não entra. Um evento
que ainda não anunciou 2027 simplesmente não aparece, em vez de aparecer com
"provavelmente em outubro".
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "calendario_eventos.csv"


@dataclass(frozen=True)
class Edicao:
    sigla: str
    nome: str
    edicao: str
    inicio: date
    fim: date | None
    cidade: str
    prazo: date | None
    url: str
    conferido: date | None
    observacao: str = ""

    @property
    def dias_ate_o_prazo(self) -> int | None:
        return (self.prazo - date.today()).days if self.prazo else None

    @property
    def prazo_aberto(self) -> bool:
        d = self.dias_ate_o_prazo
        return d is not None and d >= 0

    @property
    def ja_passou(self) -> bool:
        return (self.fim or self.inicio) < date.today()

    def para_json(self) -> dict:
        d = {
            "sigla": self.sigla,
            "nome": self.nome,
            "edicao": self.edicao,
            "inicio": self.inicio.isoformat(),
            "cidade": self.cidade,
            "url": self.url,
        }
        if self.fim and self.fim != self.inicio:
            d["fim"] = self.fim.isoformat()
        if self.prazo:
            d["prazo"] = self.prazo.isoformat()
        if self.conferido:
            d["conferido"] = self.conferido.isoformat()
        if self.observacao:
            d["obs"] = self.observacao
        return d


def _data(v: str) -> date | None:
    v = (v or "").strip()
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def carregar(caminho: Path | None = None, *, hoje: date | None = None) -> list[Edicao]:
    """Edições ainda por acontecer, da mais próxima para a mais distante.

    Edição sem data de início é descartada: sem ela não há o que anunciar, e
    exibir "data a confirmar" ocuparia espaço sem informar nada.
    """
    caminho = caminho or ARQUIVO
    if not caminho.exists():
        return []
    hoje = hoje or date.today()

    with caminho.open(encoding="utf-8") as f:
        linhas = [ln for ln in f if not ln.lstrip().startswith("//")]

    out: list[Edicao] = []
    for r in csv.DictReader(linhas):
        inicio = _data(r.get("inicio", ""))
        sigla = (r.get("sigla") or "").strip()
        if not inicio or not sigla:
            continue
        fim = _data(r.get("fim", "")) or inicio
        if fim < hoje:
            continue  # já aconteceu
        out.append(
            Edicao(
                sigla=sigla,
                nome=(r.get("nome") or "").strip(),
                edicao=(r.get("edicao") or "").strip(),
                inicio=inicio,
                fim=fim,
                cidade=(r.get("cidade") or "").strip(),
                prazo=_data(r.get("prazo", "")),
                url=(r.get("url") or "").strip(),
                conferido=_data(r.get("conferido", "")),
                observacao=(r.get("observacao") or "").strip(),
            )
        )
    return sorted(out, key=lambda e: (e.inicio, e.sigla))
