"""Próximas edições dos eventos, pelo calendário oficial da SBC.

O site da SBC roda WordPress com o plugin The Events Calendar, que expõe uma API
REST pública:

    https://www.sbc.org.br/wp-json/tribe/events/v1/events?start_date=...

De lá vêm data, cidade/UF, link do site da edição e as categorias (`apoiado`,
`internacional`...). É fonte oficial e legível por máquina — bem melhor do que
raspar 89 sites de evento, cada um com layout próprio.

## O que a API NÃO tem

**Prazo de submissão.** Verificado: `custom_fields` vem vazio e `description`
também. Deadline só existe no site de cada evento. Como prazo é a única
informação com consequência irreversível — quem confia num prazo errado perde a
submissão —, ele fica em `calendario.py`, curado à mão, com a URL de onde foi
lido e a data em que foi conferido.

## Duplicatas: por sigla, nunca por site

A base da SBC tem registros repetidos. O SBBD 2026 aparece duas vezes, com o
mesmo site e as mesmas datas, mas uma diz São Paulo/SP e a outra São Carlos/SP.

Mas deduplicar pelo **site** seria pior que o problema: BRACIS, STIL e ENIAC de
2026 apontam todos para `sbc.org.br/bracis2026` porque acontecem juntos, no
mesmo local e nas mesmas datas. São três eventos distintos, com estratos
distintos. Fundi-los apagaria dois.

A chave é **sigla + data de início**. A sigla vem do parêntese no título, que é
como a SBC padroniza ("41° Simpósio Brasileiro de Banco de Dados (SBBD 2026)").

Quando dois registros disputam, fica o **mais recentemente modificado** — a
cidade é o campo menos confiável da base, e a edição mais nova costuma ser a
correção.
"""

from __future__ import annotations

import gzip
import html
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

API = "https://www.sbc.org.br/wp-json/tribe/events/v1/events"
CACHE = Path(__file__).resolve().parent.parent / "data" / "sbc_calendario.json.gz"

# "XLI Simpósio Brasileiro de Banco de Dados (SBBD 2026)" -> SBBD
_SIGLA = re.compile(r"\(([A-Za-zÀ-ÿ0-9+\-/&\. ]{2,24}?)\s*(?:20\d\d)?\)\s*$")


@dataclass(frozen=True)
class Evento:
    sigla: str
    titulo: str
    inicio: date
    fim: date
    cidade: str
    url_sbc: str
    site: str
    categorias: tuple[str, ...]
    modificado: str = ""

    @property
    def internacional(self) -> bool:
        return "internacional" in self.categorias

    def para_json(self) -> dict:
        d = {
            "sigla": self.sigla,
            "titulo": self.titulo,
            "inicio": self.inicio.isoformat(),
            "cidade": self.cidade,
            "url": self.site or self.url_sbc,
        }
        if self.fim != self.inicio:
            d["fim"] = self.fim.isoformat()
        return d


def sigla_do_titulo(titulo: str) -> str:
    """Sigla entre parênteses no fim do título; senão, o título encurtado."""
    m = _SIGLA.search((titulo or "").strip())
    if m:
        s = m.group(1).strip()
        # Evita capturar parênteses explicativos ("(presencial)", "(online)").
        if s and not s.islower():
            return s.upper()
    return (titulo or "").strip()[:28].upper()


def _dia(v: str) -> date | None:
    try:
        return datetime.fromisoformat(str(v).replace(" ", "T")).date()
    except (TypeError, ValueError):
        return None


def baixar(*, desde: date | None = None, timeout: int = 45) -> list[dict]:
    """Eventos futuros crus da API. Erro de rede propaga — quem chama decide."""
    desde = desde or date.today()
    url = f"{API}?per_page=50&start_date={desde.isoformat()}"
    req = urllib.request.Request(url, headers={"User-Agent": "QualisComp/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (json.loads(r.read()) or {}).get("events") or []


def gravar_cache(brutos: list[dict], caminho: Path | None = None) -> Path:
    caminho = caminho or CACHE
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(caminho, "wt", encoding="utf-8") as f:
        json.dump({"baixado_em": date.today().isoformat(), "eventos": brutos}, f,
                  ensure_ascii=False)
    return caminho


def ler_cache(caminho: Path | None = None) -> tuple[list[dict], str]:
    caminho = caminho or CACHE
    if not caminho.exists():
        return [], ""
    with gzip.open(caminho, "rt", encoding="utf-8") as f:
        d = json.load(f)
    return d.get("eventos") or [], d.get("baixado_em") or ""


def interpretar(brutos: list[dict], *, hoje: date | None = None) -> list[Evento]:
    """Converte a resposta crua, deduplica e ordena pela data mais próxima."""
    hoje = hoje or date.today()
    melhor: dict[tuple[str, date], Evento] = {}

    for e in brutos:
        inicio = _dia(e.get("start_date"))
        if not inicio:
            continue
        fim = _dia(e.get("end_date")) or inicio
        if fim < hoje:
            continue
        # O WordPress devolve o título com entidades ("&#8211;").
        titulo = html.unescape((e.get("title") or "").strip())
        ev = Evento(
            sigla=sigla_do_titulo(titulo),
            titulo=titulo,
            inicio=inicio,
            fim=fim,
            cidade=((e.get("venue") or {}).get("venue") or "").strip(),
            url_sbc=(e.get("url") or "").strip(),
            site=(e.get("website") or "").strip(),
            categorias=tuple(
                (c.get("slug") or "") for c in (e.get("categories") or [])
            ),
            modificado=str(e.get("modified_utc") or ""),
        )
        chave = (ev.sigla, ev.inicio)
        atual = melhor.get(chave)
        # Empate: fica o registro corrigido mais recentemente.
        if atual is None or ev.modificado > atual.modificado:
            melhor[chave] = ev

    return sorted(melhor.values(), key=lambda x: (x.inicio, x.sigla))


def carregar(caminho: Path | None = None, *, hoje: date | None = None
             ) -> tuple[list[Evento], str]:
    """Do cache local. Devolve (eventos, data do download)."""
    brutos, quando = ler_cache(caminho)
    return interpretar(brutos, hoje=hoje), quando
