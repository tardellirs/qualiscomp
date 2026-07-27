"""Camada de dados via OpenAlex (gratuito, sem chave de API).

ATENÇÃO — isto é um PROXY, não o dado oficial.

A CAPES/Área 02 usa o *percentil* do Scopus (CiteScore Percentile) ou do WoS
(JIF Percentile), o maior entre os dois. Nenhuma das duas bases publica esses
percentis em massa de graça. Este módulo estima o percentil ranqueando os
periódicos de Computação do OpenAlex pelo `2yr_mean_citedness` (a métrica do
OpenAlex mais próxima de um fator de impacto de 2 anos).

Use `qualis.scopus` com o Scopus Source List oficial quando quiser o número que
a CAPES realmente vai olhar. Este módulo serve para triagem e comparação.
"""

from __future__ import annotations

import bisect
import gzip
import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API = "https://api.openalex.org"
CACHE = Path(__file__).resolve().parent.parent / "data" / "openalex_cs_journals.json.gz"

# Campo "Computer Science" na taxonomia de tópicos do OpenAlex.
CS_FIELD = "Computer Science"

_SELECT = ",".join(
    [
        "id",
        "display_name",
        "alternate_titles",
        "abbreviated_title",
        "issn",
        "issn_l",
        "works_count",
        "summary_stats",
        "host_organization_name",
        "societies",
        "is_in_doaj",
        "is_core",
        "topics",
        "first_publication_year",
        "last_publication_year",
    ]
)

# Um periódico só entra na distribuição de referência se ainda estiver ativo.
# Revistas extintas ou renomeadas (IEEE Transactions on Neural Networks, ACM
# SIGPLAN Notices...) têm 2yr_mean_citedness = 0 legitimamente, e se entrarem na
# distribuição empurram o percentil de todo mundo para cima.
ANO_ATIVIDADE_MINIMO = 2024


@dataclass
class Periodico:
    nome: str
    issn_l: str | None
    issns: list[str]
    editora: str | None
    citedness_2y: float
    h_index: int
    works_count: int
    doaj: bool
    campo_primario: str | None
    ultimo_ano: int | None = None

    @property
    def tem_dado_de_citacao(self) -> bool:
        """False quando o OpenAlex não tem citedness utilizável.

        Duas causas distintas, ambas exigindo cautela: a revista está extinta
        (não publica mais, logo citedness 0 é correto) ou a cobertura do
        OpenAlex é falha (o JMLR, por exemplo, publicou anos sem DOI, e aparece
        com citedness 0 apesar de h-index 132).
        """
        return self.citedness_2y > 0.0

    @property
    def ativo(self) -> bool:
        return self.ultimo_ano is not None and self.ultimo_ano >= ANO_ATIVIDADE_MINIMO

    @property
    def e_sbc(self) -> bool:
        """Heurística: periódico editado pela Sociedade Brasileira de Computação."""
        alvo = (self.editora or "").lower()
        return "sociedade brasileira de computa" in alvo or "sbc" == alvo.strip()

    @classmethod
    def from_api(cls, d: dict) -> Periodico:
        stats = d.get("summary_stats") or {}
        topics = d.get("topics") or []
        campo = None
        if topics:
            campo = (topics[0].get("field") or {}).get("display_name")
        return cls(
            nome=d.get("display_name") or "?",
            issn_l=d.get("issn_l"),
            issns=d.get("issn") or [],
            editora=d.get("host_organization_name"),
            citedness_2y=float(stats.get("2yr_mean_citedness") or 0.0),
            h_index=int(stats.get("h_index") or 0),
            works_count=int(d.get("works_count") or 0),
            doaj=bool(d.get("is_in_doaj")),
            campo_primario=campo,
            ultimo_ano=d.get("last_publication_year"),
        )

    def to_json(self) -> dict:
        return {
            "nome": self.nome,
            "issn_l": self.issn_l,
            "issns": self.issns,
            "editora": self.editora,
            "citedness_2y": self.citedness_2y,
            "h_index": self.h_index,
            "works_count": self.works_count,
            "doaj": self.doaj,
            "campo_primario": self.campo_primario,
            "ultimo_ano": self.ultimo_ano,
        }


def _get(path: str, params: dict, email: str) -> dict:
    params = {**params, "mailto": email}
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"qualis-capes ({email})"})
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception:
            if tentativa == 3:
                raise
            time.sleep(2**tentativa)
    raise AssertionError("unreachable")


def construir_referencia(
    email: str, *, min_works: int = 50, verbose: bool = True
) -> list[Periodico]:
    """Baixa os periódicos "core" do OpenAlex e mantém os de Computação.

    Percorre ~34k periódicos em páginas de 200 via cursor. Leva alguns minutos.
    O resultado é gravado em `CACHE`.
    """
    cursor = "*"
    todos: list[Periodico] = []
    pagina = 0
    while cursor:
        d = _get(
            "sources",
            {
                "filter": "type:journal,is_core:true",
                "per_page": "200",
                "cursor": cursor,
                "select": _SELECT,
            },
            email,
        )
        for item in d["results"]:
            p = Periodico.from_api(item)
            if p.campo_primario == CS_FIELD and p.works_count >= min_works:
                todos.append(p)
        cursor = d["meta"].get("next_cursor")
        pagina += 1
        if verbose:
            print(
                f"  página {pagina}: {len(todos)} periódicos de Computação até agora",
                flush=True,
            )
        if not d["results"]:
            break

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(CACHE, "wt", encoding="utf-8") as f:
        json.dump([p.to_json() for p in todos], f, ensure_ascii=False)
    if verbose:
        print(f"Gravado: {CACHE} ({len(todos)} periódicos)")
    return todos


def carregar_referencia() -> list[Periodico]:
    if not CACHE.exists():
        raise FileNotFoundError(
            f"Base de referência ausente ({CACHE}). Rode primeiro:\n"
            f"  python -m qualis atualizar --email seu@email"
        )
    with gzip.open(CACHE, "rt", encoding="utf-8") as f:
        return [Periodico(**d) for d in json.load(f)]


class Referencia:
    """Base de referência de Computação com cálculo de percentil e busca."""

    def __init__(self, periodicos: list[Periodico]):
        self.periodicos = periodicos
        # A distribuição do percentil usa só periódicos ativos e com dado de
        # citação. Os demais continuam buscáveis, mas não distorcem o ranking.
        self.distribuicao = [p for p in periodicos if p.ativo and p.tem_dado_de_citacao]
        self._ordenado = sorted(p.citedness_2y for p in self.distribuicao)

    @classmethod
    def carregar(cls) -> Referencia:
        return cls(carregar_referencia())

    def __len__(self) -> int:
        return len(self.periodicos)

    def percentil(self, citedness: float) -> float:
        """Percentil de `citedness` dentro dos periódicos de Computação.

        Usa a mesma convenção do CiteScore Percentile: fração de periódicos da
        área com valor estritamente menor.
        """
        n = len(self._ordenado)
        if n == 0:
            raise ValueError("base de referência vazia")
        return 100.0 * bisect.bisect_left(self._ordenado, citedness) / n

    def buscar_online(self, consulta: str, email: str) -> Periodico | None:
        """Consulta o OpenAlex ao vivo, para periódicos fora da base local.

        Útil para revistas cujo campo primário no OpenAlex não é Computação
        (IEEE Access, Expert Systems with Applications...) mas que a área de
        Computação considera. O percentil segue sendo calculado contra a
        distribuição dos periódicos de Computação.
        """
        filtro = (
            f"issn:{consulta}"
            if consulta.replace("-", "").isdigit()
            else f"display_name.search:{consulta}"
        )
        d = _get(
            "sources",
            {"filter": f"type:journal,{filtro}", "per_page": "5", "select": _SELECT},
            email,
        )
        if not d["results"]:
            return None
        cands = [Periodico.from_api(x) for x in d["results"]]
        exato = [p for p in cands if p.nome.lower() == consulta.strip().lower()]
        return (exato or cands)[0]

    def buscar(self, consulta: str, limite: int = 10) -> list[Periodico]:
        """Busca por nome (substring, sem acento-sensibilidade) ou por ISSN."""
        q = consulta.strip().lower()
        issn_q = q.replace(" ", "")
        exatos, parciais = [], []
        for p in self.periodicos:
            if issn_q in {(p.issn_l or "").lower(), *(i.lower() for i in p.issns)}:
                exatos.append(p)
                continue
            nome = p.nome.lower()
            if nome == q:
                exatos.append(p)
            elif q in nome:
                parciais.append(p)
        parciais.sort(key=lambda p: (len(p.nome), -p.citedness_2y))
        return (exatos + parciais)[:limite]
