"""h5-index calculado a partir do OpenAlex — um PISO, nunca uma estimativa.

A regra da Área 02 para eventos usa o h5-index do **Google Scholar**, que não
tem API e bloqueia scraping. Dá para calcular um h5 com os dados do OpenAlex,
mas ele sai sistematicamente MENOR que o do Scholar, porque o Scholar conta uma
base de citações maior (preprints, teses, literatura cinzenta, itens sem DOI).

Medições feitas contra o Scholar mostram que a diferença não é um fator estável:
o desconto varia de venue para venue conforme a qualidade da indexação. Portanto
este número **não serve como estimativa** do h5 real.

O que ele serve, e serve bem: como **limite inferior**. Se o h5 do OpenAlex já
passa de um corte, o do Scholar também passa — logo o estrato calculado aqui é
um piso garantido, e o estrato real é esse ou melhor. Isso responde com
segurança "este evento é seguramente A1?", mas nunca "este evento é A5 ou A6?".

Não use perto dos cortes, e não use para eventos brasileiros: a cobertura do
OpenAlex para eventos da SBC é fraca a inexistente (SBBD, SIBGRAPI e SBRC não
têm fonte; o SBES tem 62 trabalhos). Para esses, preencha data/eventos.csv à mão.
"""

from __future__ import annotations

from dataclasses import dataclass

from .openalex import _get
from .rules import ESTRATOS, H5_MINIMO, estrato_por_h5

# Janela do Google Scholar Metrics: os 5 anos completos mais recentes.
JANELA = (2020, 2024)

# Teto de trabalhos lidos por venue. O h5 nunca passa da raiz do número de
# trabalhos, e nenhum evento de Computação chega perto de h5 = 1200.
CAP_TRABALHOS = 1200


@dataclass
class ResultadoH5:
    consulta: str
    h5_piso: int
    trabalhos: int
    fontes: list[str]
    janela: tuple[int, int]

    @property
    def estrato_piso(self) -> str | None:
        return estrato_por_h5(self.h5_piso)

    @property
    def confiavel(self) -> bool:
        """Só confie quando o piso já garante o melhor estrato.

        Abaixo de A1 o número real pode estar vários níveis acima do piso, e o
        resultado não distingue "evento mediano" de "evento mal indexado".
        """
        return self.h5_piso >= H5_MINIMO["A1"]

    def resumo(self) -> str:
        if not self.fontes:
            return (
                f"'{self.consulta}': nenhuma fonte de conferência no OpenAlex. "
                f"Sem cobertura — preencha o h5 à mão em data/eventos.csv."
            )
        est = self.estrato_piso or "nenhum"
        cab = (
            f"'{self.consulta}': h5 >= {self.h5_piso} (piso via OpenAlex, "
            f"{self.trabalhos} trabalhos de {len(self.fontes)} fonte(s), "
            f"{self.janela[0]}-{self.janela[1]})"
        )
        if self.confiavel:
            return f"{cab}\n  -> seguramente A1 (o piso já passa do corte de {H5_MINIMO['A1']})."
        return (
            f"{cab}\n  -> piso {est}, mas o h5 real do Google Scholar é MAIOR "
            f"(quanto, não dá para saber). Não decida por este número: "
            f"consulte o Scholar Metrics."
        )


def _buscar_fontes(nome: str, email: str, limite: int = 40) -> list[tuple[str, str]]:
    """Fontes do tipo conferência cujo nome casa com a consulta.

    Eventos grandes aparecem fatiados por edição no OpenAlex (o CVPR tem uma
    fonte por ano), então agregamos todas as edições encontradas.
    """
    d = _get(
        "sources",
        {
            "filter": f"type:conference,display_name.search:{nome}",
            "per_page": str(limite),
            "select": "id,display_name,works_count",
        },
        email,
    )
    return [
        (r["id"].rsplit("/", 1)[-1], r["display_name"])
        for r in d["results"]
        if r.get("works_count")
    ]


def calcular(
    nome: str, email: str, *, janela: tuple[int, int] = JANELA, cap: int = CAP_TRABALHOS
) -> ResultadoH5:
    """Calcula o piso do h5 de um evento agregando suas edições no OpenAlex."""
    fontes = _buscar_fontes(nome, email)
    if not fontes:
        return ResultadoH5(nome, 0, 0, [], janela)

    ids = [i for i, _ in fontes]
    filtro = (
        f"primary_location.source.id:{'|'.join(ids)},"
        f"publication_year:{janela[0]}-{janela[1]}"
    )
    citacoes: list[int] = []
    cursor = "*"
    while cursor and len(citacoes) < cap:
        d = _get(
            "works",
            {
                "filter": filtro,
                "per_page": "200",
                "cursor": cursor,
                "select": "cited_by_count",
                "sort": "cited_by_count:desc",
            },
            email,
        )
        citacoes.extend(w["cited_by_count"] for w in d["results"])
        cursor = d["meta"].get("next_cursor")
        if not d["results"]:
            break

    return ResultadoH5(
        consulta=nome,
        h5_piso=indice_h(citacoes),
        trabalhos=len(citacoes),
        fontes=[n for _, n in fontes],
        janela=janela,
    )


def indice_h(citacoes: list[int]) -> int:
    """Maior h tal que h trabalhos tenham ao menos h citações cada."""
    h = 0
    for i, c in enumerate(sorted(citacoes, reverse=True), start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def estrato_minimo_garantido(h5_piso: int) -> str | None:
    """Pior estrato que o evento pode receber, dado o piso do h5."""
    del ESTRATOS  # a ordem vem de estrato_por_h5
    return estrato_por_h5(h5_piso)
