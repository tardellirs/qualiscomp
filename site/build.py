#!/usr/bin/env python3
"""Gera o site estático a partir das bases locais.

    python site/build.py            # gera em site/dist/
    python site/build.py --servir   # gera e sobe um servidor local

Duas decisões de licenciamento estão codificadas aqui, e não são detalhe:

1. O site publica o **estrato derivado**, não os campos brutos do Scopus
   (CiteScore, SNIP, SJR, editora). O estrato é resultado de uma regra pública
   da CAPES; o percentil é dado da Elsevier obtido por assinatura institucional,
   e redistribuí-lo seria outra coisa. O percentil aparece arredondado como
   posição na régua, com link para a fonte.
2. O h5 exibido é sempre o do Google Scholar. Eventos sem h5 do Scholar entram
   como "não classificado", nunca com o número da planilha da SBC — que diverge
   em média ~4,6 pontos, cerca de um estrato inteiro.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from qualis import (  # noqa: E402
    apc, calendario, historico_oficial, jcr, oficial, rules, sbc,
    sbc_calendario, scopus_export,
)
from qualis.coleta import Cache, resolver  # noqa: E402

SAIDA = Path(__file__).resolve().parent / "dist"
APP = Path(__file__).resolve().parent / "app"
SNAPSHOT = date.today().isoformat()

# Domínio de produção. Entra no canonical, no sitemap e nas tags Open Graph —
# se ficar errado, o buscador indexa o endereço errado.
DOMINIO = "https://qualiscomp.com"


# --------------------------------------------------------------------------- #
# Modelo
# --------------------------------------------------------------------------- #


@dataclass
class Passo:
    """Uma linha do recibo: uma regra aplicada e o estrato resultante."""

    rotulo: str
    detalhe: str
    estrato: str | None
    fonte: str = ""
    alerta: str = ""


@dataclass
class Veiculo:
    slug: str
    nome: str
    tipo: str  # periodico | evento
    estrato: str | None
    situacao: str  # classificado | nao_classificavel | descartado
    confianca: str  # alto | medio | baixo | nenhum
    passos: list[Passo] = field(default_factory=list)
    sigla: str = ""
    percentil: float | None = None
    h5: int | None = None
    ce_sbc: str = ""
    ces: list[str] = field(default_factory=list)
    ambiguo: bool = False
    entradas: list[str] = field(default_factory=list)
    h5_sbc: int | None = None
    e_sbc: bool = False
    issns: list[str] = field(default_factory=list)
    e_computacao: bool = False
    editora: str = ""
    acesso_aberto: bool = False
    url_scopus: str = ""
    descontinuada: bool = False
    # [ano, percentil, estrato, ano_completo?] — só periódicos vindos da API.
    historico: list[list] = field(default_factory=list)
    percentil_wos: float | None = None
    qualis_ciclos: list[list] = field(default_factory=list)
    apc_capes: bool = False
    apc_editora: str = ""
    apc_licenca: str = ""
    apc_url: str = ""
    fronteira: str = ""
    nota: str = ""
    e_sbc_evento: bool = False
    edicoes: int | None = None
    # Base do simulador: o estrato que o INDICADOR sozinho dá, antes de
    # qualquer ajuste. Sem isso o simulador soma o bônus da CE-SBC de novo
    # sobre um estrato que já o inclui, e conta duas vezes.
    estrato_base: str | None = None
    oficial_estrato: str = ""
    oficial_original: str = ""

    apelidos: list[str] = field(default_factory=list)

    def para_indice(self) -> dict:
        """Só o necessário para buscar — a ficha completa vem à parte."""
        d = {
            "s": self.slug,
            "n": self.nome,
            "t": self.tipo[0],  # p | e
            "e": self.estrato or "",
            "g": self.sigla,
        }
        # O indicador é o que a pessoa filtra: percentil para periódico, h5
        # para evento. Sem ele na lista, não dá para procurar "acima de 80".
        ind = self.percentil if self.tipo == "periodico" else self.h5
        if ind is not None:
            d["i"] = round(ind, 1) if isinstance(ind, float) else ind
        if self.apelidos:
            d["a"] = " · ".join(self.apelidos)
        if self.issns:
            d["s2"] = self.issns
        if self.e_computacao:
            d["k"] = 1          # revista da área de Computação no ASJC
        if self.e_sbc_evento:
            d["br"] = 1         # evento promovido pela SBC
        if self.editora:
            d["ed"] = self.editora   # trocado por índice em `_compactar`
        if self.acesso_aberto:
            d["oa"] = 1
        if self.apc_capes:
            d["apc"] = 1        # taxa de publicação coberta por acordo da CAPES
        if self.ces:
            d["ce"] = self.ces      # trocado por índices em `main`
        return d


# Palavras que não entram na sigla derivada do título.
_MIUDAS = {"and", "of", "the", "for", "in", "a", "an", "de", "da", "do", "e", "em"}
_ORGS = {"acm", "ieee", "usenix", "ifip", "springer", "elsevier", "sbc", "the"}


def siglas_do_titulo(titulo: str) -> list[str]:
    """Siglas plausíveis a partir das iniciais do título.

    Periódicos não têm sigla na base do Scopus, mas todo mundo os chama pela
    sigla: ninguém procura "ACM Transactions on Software Engineering and
    Methodology", procura "TOSEM". Geramos algumas combinações plausíveis
    (com e sem o prefixo institucional, com e sem palavras miúdas) e indexamos
    todas — é barato e o custo de um falso positivo numa busca é baixo.
    """
    palavras = [p for p in re.findall(r"[A-Za-zÀ-ÿ]+", titulo)]
    if len(palavras) < 2:
        return []
    out: set[str] = set()
    for tirar_org in (False, True):
        base = palavras[1:] if (tirar_org and palavras[0].lower() in _ORGS) else palavras
        for tirar_miudas in (False, True):
            sel = [w for w in base if not (tirar_miudas and w.lower() in _MIUDAS)]
            if 2 <= len(sel) <= 9:
                out.add("".join(w[0] for w in sel).upper())
    return [s for s in out if 3 <= len(s) <= 8]


# A mesma editora aparece com grafias diferentes no Scopus ("IEEE" e "Institute
# of Electrical and Electronics Engineers Inc."). Sem normalizar, filtrar por
# uma delas perde metade das revistas.
_EDITORAS = (
    ("institute of electrical and electronics engineers", "IEEE"),
    ("ieee", "IEEE"),
    ("association for computing machinery", "ACM"),
    ("springer", "Springer Nature"),
    ("elsevier", "Elsevier"),
    ("john wiley", "Wiley"),
    ("wiley", "Wiley"),
    ("taylor & francis", "Taylor & Francis"),
    ("taylor and francis", "Taylor & Francis"),
    ("multidisciplinary digital publishing", "MDPI"),
    ("sage", "SAGE"),
    ("oxford university press", "Oxford University Press"),
    ("cambridge university press", "Cambridge University Press"),
    ("world scientific", "World Scientific"),
    ("igi global", "IGI Global"),
    ("inderscience", "Inderscience"),
    ("emerald", "Emerald"),
    ("frontiers media", "Frontiers"),
    ("public library of science", "PLOS"),
    ("nature publishing", "Springer Nature"),
    ("sociedade brasileira de computa", "SBC"),
    ("brazilian comput", "SBC"),
)


def normalizar_editora(nome: str | None) -> str:
    if not nome:
        return ""
    baixo = nome.lower()
    for chave, canonico in _EDITORAS:
        if chave in baixo:
            return canonico
    return nome.strip()


def slugificar(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:80] or "veiculo"


# --------------------------------------------------------------------------- #
# Fronteira: o aviso mais útil do site
# --------------------------------------------------------------------------- #


def _fronteira_percentil(p: float, estrato: str) -> str:
    """Avisa quando o percentil está a <=3 pontos de mudar de estrato."""
    i = rules.ESTRATOS.index(estrato)
    acima = rules.PERCENTIL_MINIMO.get(rules.ESTRATOS[i - 1]) if i > 0 else None
    abaixo = rules.PERCENTIL_MINIMO.get(estrato)
    if acima is not None and acima - p <= 3:
        return f"faltam {acima - p:.1f} pontos de percentil para {rules.ESTRATOS[i - 1]}"
    if abaixo is not None and p - abaixo <= 3:
        prox = rules.ESTRATOS[i + 1] if i + 1 < len(rules.ESTRATOS) else None
        if prox:
            return f"{p - abaixo:.1f} ponto(s) a menos e cai para {prox}"
    return ""


def _fronteira_h5(h5: int, estrato: str) -> str:
    """Idem para eventos, com tolerância de 2 pontos de h5."""
    i = rules.ESTRATOS.index(estrato)
    if i > 0:
        alvo = rules.H5_MINIMO[rules.ESTRATOS[i - 1]]
        if 0 < alvo - h5 <= 2:
            return f"faltam {alvo - h5} ponto(s) de h5 para {rules.ESTRATOS[i - 1]}"
    piso = rules.H5_MINIMO[estrato]
    if h5 - piso <= 1 and i + 1 < len(rules.ESTRATOS):
        return f"{h5 - piso + 1} ponto(s) a menos e cai para {rules.ESTRATOS[i + 1]}"
    return ""


# --------------------------------------------------------------------------- #
# Periódicos
# --------------------------------------------------------------------------- #


def montar_periodicos() -> list[Veiculo]:
    acordos = apc.carregar()
    ciclos = historico_oficial.carregar()
    wos = jcr.carregar()
    out: list[Veiculo] = []
    for fonte in scopus_export.carregar().values():
        if fonte.parece_evento:
            continue  # anais indexados no Scopus: vão pela regra de h5
        if fonte.tipo_scopus == "bookseries":
            # Séries de livros (Foundations and Trends, Synthesis Lectures,
            # Handbooks). O documento manda livros e capítulos pelo relatório do
            # GT de livros da CAPES, não pelo percentil — e esse caminho não é
            # modelado aqui. Classificá-las por percentil seria usar a regra
            # errada, então ficam de fora.
            continue
        # A regra manda usar "o percentil da WoS ou Scopus - o maior entre os
        # dois". Com só uma base, toda estimativa era um piso.
        no_wos = jcr.buscar(getattr(fonte, "issns", []) or [], wos)
        c = rules.classificar_periodico(
            fonte.titulo,
            percentil_scopus=fonte.percentil,
            percentil_wos=no_wos.percentil if no_wos else None,
            e_sbc=fonte.e_sbc,
            rotulo_scopus="Scopus",
        )
        venceu_wos = no_wos is not None and no_wos.percentil > fonte.percentil
        pct = no_wos.percentil if venceu_wos else fonte.percentil
        base = "no Web of Science" if venceu_wos else "no Scopus"
        passos = [
            Passo(
                rotulo=f"Percentil {pct:.0f} {base}",
                detalhe=(
                    f"corte de {c.estrato}: {rules.PERCENTIL_MINIMO[c.estrato]:.1f}"
                    if c.estrato in rules.PERCENTIL_MINIMO
                    else f"A8 é tudo abaixo de {rules.PERCENTIL_MINIMO['A7']:.1f}"
                ),
                estrato=c.estrato,
                fonte=(
                    f"Web of Science · categoria {no_wos.categoria.title()}"
                    if venceu_wos
                    else f"Scopus · categoria {fonte.categoria or '?'}"
                ),
            )
        ]
        if fonte.descontinuada:
            passos.append(
                Passo(
                    rotulo="Periódico descontinuado no Scopus",
                    detalhe=f"deixou de ser indexado em {fonte.ano_fim}; o "
                    f"percentil é retrato de um período encerrado",
                    estrato=c.estrato,
                    fonte="Scopus",
                    alerta="ausente",
                )
            )
        if fonte.e_sbc:
            passos.append(
                Passo(
                    rotulo="Periódico de sociedade científica (SBC)",
                    detalhe="elegível a subir até 2 níveis por análise qualitativa "
                    "da área — decisão da comissão, não aplicada aqui",
                    estrato=c.estrato,
                    fonte="Documento de Área, p. 22",
                    alerta="potencial",
                )
            )
        acordo = apc.buscar(getattr(fonte, "issns", []) or [], acordos)
        out.append(
            Veiculo(
                slug=f"p-{slugificar(fonte.titulo)}",
                nome=fonte.titulo,
                tipo="periodico",
                estrato=c.estrato,
                situacao="classificado",
                confianca="alto",
                passos=passos,
                percentil=fonte.percentil,
                e_sbc=fonte.e_sbc,
                issns=list(getattr(fonte, "issns", []) or []),
                e_computacao=fonte.e_computacao,
                editora=normalizar_editora(fonte.editora),
                acesso_aberto=fonte.acesso_aberto,
                url_scopus=fonte.url_scopus,
                descontinuada=fonte.descontinuada,
                historico=[
                    [ano, pct, rules.estrato_por_percentil(pct), completo]
                    for ano, pct, completo in fonte.historico
                ],
                percentil_wos=no_wos.percentil if no_wos else None,
                qualis_ciclos=historico_oficial.buscar(
                    getattr(fonte, "issns", []) or [], ciclos
                ),
                apc_capes=bool(acordo),
                apc_editora=acordo.editora if acordo else "",
                apc_licenca=acordo.licenca if acordo else "",
                apc_url=acordo.url if acordo else "",
                estrato_base=c.estrato,
                apelidos=siglas_do_titulo(fonte.titulo),
                fronteira=_fronteira_percentil(fonte.percentil, c.estrato),
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Eventos
# --------------------------------------------------------------------------- #


def montar_eventos() -> list[Veiculo]:
    cache = Cache()
    of = oficial.carregar()
    # A aba "Eventos SBC" da planilha traz o número de edições de cada evento
    # promovido pela SBC — é o que habilita o critério de indução do documento,
    # que até aqui não era aplicado por falta do dado.
    da_sbc = sbc.eventos_da_sbc()
    out: list[Veiculo] = []
    das_ces = sbc.ler()

    # A lista de eventos vinha SÓ das abas das Comissões Especiais. Mas a aba
    # "Eventos SBC" tem 35 eventos que CE nenhuma classificou — e o critério de
    # indução do documento não depende de CE: basta ser evento nacional da SBC
    # com tradição. O WGRS tem 28 edições e ficava de fora, quando a regra lhe
    # daria A4. Os demais entram sem estrato, visíveis, em vez de invisíveis.
    ja_listados = {e.sigla.upper() for e in das_ces}
    for chave, info in sorted(da_sbc.items()):
        if chave in ja_listados:
            continue
        das_ces.append(
            sbc.EventoSBC(
                sigla=info.sigla,
                nome=info.nome or info.sigla,
                classificacao="",       # nenhuma CE se manifestou (vira None na regra)
                h5_sbc=None,
                ces=[],
            )
        )

    for ev in das_ces:
        r = resolver(ev, cache)
        info_sbc = da_sbc.get(ev.sigla.upper())
        anos = info_sbc.anos_de_tradicao if info_sbc else None
        slug = f"e-{slugificar(r.sigla or r.nome)}"
        # Muitos eventos brasileiros têm nome oficial em inglês na planilha da
        # SBC e são procurados em português (e vice-versa). Indexamos todos os
        # nomes conhecidos, inclusive os que o Scholar usa.
        apelidos = [n for n in ev.todos_os_nomes[1:]]
        apelidos += [e.rsplit(" (h5=", 1)[0] for e in r.entradas]
        apelidos = list(dict.fromkeys(a for a in apelidos if a and a != r.nome))

        if r.h5_fonte != "scholar" or r.h5 is None:
            # Sem h5 do Google, a regra ainda pode classificar pela CE-SBC.
            c = rules.classificar_evento(
                r.sigla, h5=0, ce_sbc=r.ce_sbc or None,
                anos_tradicao_sbc=anos, promovido_por_sociedade=bool(info_sbc),
            )
            passos = [
                Passo(
                    rotulo="Sem h5-index no Google Scholar",
                    detalhe="o evento não tem entrada no Scholar Metrics",
                    estrato=None,
                    fonte="Google Scholar Metrics",
                ),
            ]
            if r.ce_sbc:
                passos.append(
                    Passo(
                        rotulo=f"CE-SBC classifica como \u201c{r.ce_sbc}\u201d",
                        detalhe="para evento sem h5, o documento define: "
                        "\u201cTop\u201d \u2192 A7, \u201crelevante\u201d \u2192 A8",
                        estrato=c.estrato,
                        fonte="Documento de Área, p. 22",
                    )
                )
            elif anos:
                passos.append(
                    Passo(
                        rotulo=f"Evento da SBC com {anos} edições",
                        detalhe="critério de indução: >=20 anos de tradição "
                        "\u2192 A4; >=10 anos \u2192 A5",
                        estrato=c.estrato,
                        fonte="Documento de Área, p. 22",
                    )
                )
            # O critério de indução (evento nacional da SBC com >=20 anos -> A4,
            # >=10 anos -> A5) exige o ano de fundação, que não temos de fonte
            # verificável. Não aplicamos — mas avisamos, porque a diferença é
            # grande: dos 126 eventos sem h5 que a CAPES classificou no ciclo
            # anterior, 82 receberam estrato melhor que o nosso.
            nota = (
                ""
                if info_sbc
                else "Se este evento for promovido pela SBC, o critério de "
                "indução pode elevá-lo. Ele não está na lista de eventos da "
                "SBC que usamos, então não aplicamos."
            )
            out.append(
                Veiculo(
                    slug=slug,
                    nome=r.nome,
                    sigla=r.sigla,
                    tipo="evento",
                    estrato=c.estrato,
                    situacao="classificado" if c.considerado else "nao_classificavel",
                    confianca="baixo",
                    passos=passos,
                    ce_sbc=r.ce_sbc,
                    ces=r.ces,
                    h5_sbc=r.h5_sbc,
                    nota=nota,
                    apelidos=apelidos,
                    e_sbc_evento=bool(info_sbc),
                    edicoes=anos,
                    estrato_base=None,
                    oficial_estrato=of[r.sigla.upper()].estrato
                    if r.sigla.upper() in of else "",
                    oficial_original=of[r.sigla.upper()].estrato_original
                    if r.sigla.upper() in of else "",
                )
            )
            continue

        c = rules.classificar_evento(
            r.sigla, h5=r.h5, ce_sbc=r.ce_sbc or None,
            anos_tradicao_sbc=anos, promovido_por_sociedade=bool(info_sbc),
        )
        base = rules.estrato_por_h5(r.h5)
        passos = [
            Passo(
                rotulo=f"h5 = {r.h5} no Google Scholar",
                detalhe=f"corte de {base}: h5 ≥ {rules.H5_MINIMO[base]}",
                estrato=base,
                fonte="Google Scholar Metrics · janela 2020-2024",
                alerta="ambiguo" if r.ambiguo else "",
            )
        ]
        rotulos = {"top10": "+2 níveis", "top20": "+1 nível", "relevante": "mantém"}
        teto = any("Saturação" in m for m in c.motivos)
        if r.ce_sbc:
            # Sem o teto, o bônus levaria a este estrato. Mostrar o valor SEM
            # teto aqui e o teto na linha seguinte é o que faz a conta fechar:
            # senão a linha da saturação apareceria como "sem mudança",
            # escondendo justamente a regra que decidiu o resultado.
            sem_teto = rules.classificar_evento(
                r.sigla, h5=r.h5, ce_sbc=r.ce_sbc or None, teto_qualitativo=False
            ).estrato
            # Sem a indução: senão a linha da CE já mostraria o resultado dela,
            # e a linha seguinte pareceria não ter feito nada.
            so_ce = rules.classificar_evento(
                r.sigla, h5=r.h5, ce_sbc=r.ce_sbc or None
            ).estrato
            passos.append(
                Passo(
                    rotulo=f"CE-SBC: \u201c{r.ce_sbc}\u201d",
                    detalhe=rotulos.get(r.ce_sbc, ""),
                    estrato=sem_teto if teto else so_ce,
                    fonte=f"CEs: {', '.join(r.ces)}" if r.ces else "planilha da SBC",
                )
            )
        if anos and any("indução" in m for m in c.motivos):
            passos.append(
                Passo(
                    rotulo="Critério de indução da área",
                    detalhe=f"evento nacional da SBC com {anos} edições; "
                    f"a partir de 20 anos de tradição pode ir a A4, "
                    f"a partir de 10 anos a A5",
                    estrato=c.estrato,
                    fonte="Documento de Área, p. 22-23",
                )
            )
        if teto:
            voltou = c.estrato == base
            passos.append(
                Passo(
                    rotulo=(
                        "Ganho anulado pela saturação"
                        if voltou
                        else "Saturação qualitativa em A3"
                    ),
                    detalhe=(
                        f"nenhum artigo passa de A3 só por critério qualitativo, "
                        f"então mantém o {base} que o h5 já dava"
                        if voltou
                        else "nenhum artigo passa de A3 só por critério qualitativo"
                    ),
                    estrato=c.estrato,
                    fonte="Documento de Área, p. 22",
                    alerta="ambiguo_regra",
                )
            )
        out.append(
            Veiculo(
                slug=slug,
                nome=r.nome,
                sigla=r.sigla,
                tipo="evento",
                estrato=c.estrato,
                situacao="classificado",
                confianca="medio" if r.ambiguo else "alto",
                passos=passos,
                h5=r.h5,
                ce_sbc=r.ce_sbc,
                ces=r.ces,
                ambiguo=r.ambiguo,
                entradas=r.entradas,
                h5_sbc=r.h5_sbc,
                fronteira=_fronteira_h5(r.h5, base),
                apelidos=apelidos,
                e_sbc_evento=bool(info_sbc),
                edicoes=anos,
                estrato_base=base,
                oficial_estrato=of[r.sigla.upper()].estrato
                if r.sigla.upper() in of else "",
                oficial_original=of[r.sigla.upper()].estrato_original
                if r.sigla.upper() in of else "",
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Distribuições (para a régua)
# --------------------------------------------------------------------------- #


def distribuicoes(vs: list[Veiculo]) -> dict:
    pcts = sorted(v.percentil for v in vs if v.percentil is not None)
    h5s = sorted(v.h5 for v in vs if v.h5 is not None)
    return {
        "percentis": pcts,
        "h5": h5s,
        "n_periodicos": len(pcts),
        "n_eventos_com_h5": len(h5s),
    }


def _agenda(saida: Path, veiculos: list[Veiculo], marcas: dict) -> None:
    """Página /agenda/: próximos eventos, com o estrato que já estimamos.

    Juntar as duas coisas é o que este site pode fazer e nenhum outro faz: o
    calendário da SBC não sabe o estrato, e quem publica estrato não sabe a
    data. O prazo de submissão vem de `calendario.py`, curado à mão.
    """
    from datetime import date
    import html as _html

    proximos, baixado_em = sbc_calendario.carregar()
    curados = calendario.carregar()
    prazos = {e.sigla.upper(): e for e in curados}
    if not proximos and not curados:
        return

    # O calendário da SBC não é completo: SBQS e SBMF de 2026 não estão lá,
    # embora tenham prazo aberto. Quem foi curado à mão com data própria entra
    # também — senão o prazo existiria no CSV e não apareceria na página.
    # O que foi conferido à mão vence o calendário da SBC. A entidade erra
    # cidade: o ENIAC 2026 aparece em Campo Grande/MS quando acontece em
    # Cuiabá/MT, junto com o BRACIS.
    por_chave = {(e.sigla, e.inicio): i for i, e in enumerate(proximos)}
    for c in curados:
        i = por_chave.get((c.sigla.upper(), c.inicio))
        if i is None:
            continue
        e = proximos[i]
        proximos[i] = replace(
            e,
            cidade=c.cidade or e.cidade,
            site=c.url or e.site,
            fim=c.fim or e.fim,
        )

    ja = {(e.sigla, e.inicio) for e in proximos}
    for c in curados:
        if (c.sigla.upper(), c.inicio) in ja or not c.inicio:
            continue
        proximos.append(
            sbc_calendario.Evento(
                sigla=c.sigla.upper(),
                titulo=f"{c.nome} ({c.sigla} {c.inicio.year})" if c.nome else c.sigla,
                inicio=c.inicio,
                fim=c.fim or c.inicio,
                cidade=c.cidade,
                url_sbc="",
                site=c.url,
                categorias=(),
            )
        )
    proximos.sort(key=lambda e: (e.inicio, e.sigla))

    # Casa com o catálogo para pegar o estrato. Pela sigla, e depois pelo nome
    # sem o numeral romano e sem o "(SIGLA ano)" do fim.
    por_sigla = {v.sigla.upper(): v for v in veiculos if v.tipo == "evento" and v.sigla}
    por_nome: dict[str, Veiculo] = {}
    for v in veiculos:
        if v.tipo != "evento":
            continue
        for n in [v.nome, *(v.apelidos or [])]:
            if n:
                por_nome.setdefault(_chave_nome(n), v)

    hoje = date.today()
    linhas = []
    for e in proximos:
        v = por_sigla.get(e.sigla)
        if v is None:
            t = re.sub(r"^[IVXLC]+\s+", "", e.titulo)
            t = re.sub(r"\s*\([^)]*\)\s*$", "", t)
            v = por_nome.get(_chave_nome(t))
        p = prazos.get(e.sigla)

        quando = e.inicio.strftime("%d/%m")
        if e.fim != e.inicio:
            quando += "&ndash;" + e.fim.strftime("%d/%m")
        quando += e.inicio.strftime("/%Y")

        estrato = (
            f'<a class="e" data-e="{v.estrato}" href="../?v={v.slug}"'
            f' title="Ver como chegamos a {v.estrato}">{v.estrato}</a>'
            if v is not None and v.estrato
            else '<span class="ag__sem" title="ainda não estimamos o estrato deste evento">&mdash;</span>'
        )
        alvo = e.site or e.url_sbc
        nome = _html.escape(e.titulo)
        # A data é fato estável; contagem regressiva e rótulo de "encerrada"
        # seriam calculados no build e ficariam errados no dia seguinte.
        prazo_html = ""
        if p and p.prazo:
            prazo_html = (
                f'<a class="ag__prazo" href="{_html.escape(p.url)}"'
                f' target="_blank" rel="noopener">submissão até'
                f' {p.prazo.strftime("%d/%m/%Y")}</a>'
            )
            if p.observacao:
                prazo_html += f'<span class="ag__obs">{_html.escape(p.observacao)}</span>'

        linhas.append(
            f'    <li class="ag__it">\n'
            f'      <time class="ag__quando" datetime="{e.inicio.isoformat()}">{quando}</time>\n'
            f'      <span class="ag__estrato">{estrato}</span>\n'
            f'      <span class="ag__nome">'
            f'<a href="{_html.escape(alvo)}" target="_blank" rel="noopener">{nome}</a>'
            f'<small>{_html.escape(e.cidade) or "local a confirmar"}</small></span>\n'
            f'      <span class="ag__praz">{prazo_html}</span>\n'
            f'    </li>'
        )

    corpo = (
        '  <section class="doc__sec">\n'
        '  <ol class="ag">\n' + "\n".join(linhas) + "\n  </ol>\n"
        f'  <p class="doc__nota">Última atualização {_data_br(baixado_em)}</p>\n'
        "  </section>"
    )

    dados = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Próximos eventos de Computação no Brasil",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i,
                "item": {
                    "@type": "Event",
                    "name": e.titulo,
                    "startDate": e.inicio.isoformat(),
                    "endDate": e.fim.isoformat(),
                    "eventAttendanceMode":
                        "https://schema.org/OfflineEventAttendanceMode",
                    "url": e.site or e.url_sbc,
                    **({"location": {"@type": "Place", "name": e.cidade}}
                       if e.cidade else {}),
                },
            }
            for i, e in enumerate(proximos, 1)
        ],
    }
    jsonld = ('<script type="application/ld+json">'
              + json.dumps(dados, ensure_ascii=False) + "</script>")

    destino = saida / "agenda"
    destino.mkdir(parents=True, exist_ok=True)
    texto = (APP / "agenda.html").read_text(encoding="utf-8")
    texto = texto.replace("{{AGENDA}}", corpo).replace("{{JSONLD}}", jsonld)
    for k, v in marcas.items():
        texto = texto.replace(k, v)
    (destino / "index.html").write_text(texto, encoding="utf-8")
    shutil.copy2(APP / "agenda.css", destino / "agenda.css")
    abertos = sum(
        1 for c in curados if c.prazo and (c.prazo - hoje).days >= 0
    )
    print(f"  agenda: {len(proximos)} eventos, {abertos} com prazo aberto")


def _chave_nome(t: str) -> str:
    """Compara nomes de evento ignorando acento, caixa e pontuação."""
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t)).strip()


def _data_br(iso: str) -> str:
    from datetime import date as _d
    try:
        return _d.fromisoformat(iso).strftime("%d/%m/%Y")
    except ValueError:
        return iso or "data desconhecida"


def _mil(n: int) -> str:
    """1234 -> "1.234" — separador de milhar do português."""
    return f"{n:,}".replace(",", ".")


def _sitemap(saida: Path, veiculos: list) -> None:
    """sitemap.xml e robots.txt — sem eles o buscador não acha as páginas."""
    urls = ["", "sobre/", "agenda/"]
    linhas = "".join(
        f"<url><loc>{DOMINIO}/{u}</loc>"
        f"<lastmod>{SNAPSHOT}</lastmod>"
        f"<priority>{'1.0' if u == '' else '0.8'}</priority>"
        f"<changefreq>{'weekly' if u == 'agenda/' else 'monthly'}</changefreq></url>"
        for u in urls
    )
    (saida / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{linhas}</urlset>",
        encoding="utf-8",
    )
    (saida / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n"
        f"Sitemap: {DOMINIO}/sitemap.xml\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--servir", action="store_true")
    ap.add_argument("--porta", type=int, default=8000)
    args = ap.parse_args()

    print("Montando periódicos...", flush=True)
    veiculos = montar_periodicos()
    print(f"  {len(veiculos)}")
    print("Montando eventos...", flush=True)
    eventos = montar_eventos()
    print(f"  {len(eventos)}")
    veiculos += eventos

    # Slugs precisam ser únicos: são URLs que serão citadas.
    vistos: dict[str, int] = {}
    for v in veiculos:
        if v.slug in vistos:
            vistos[v.slug] += 1
            v.slug = f"{v.slug}-{vistos[v.slug]}"
        else:
            vistos[v.slug] = 0

    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    (SAIDA / "dados" / "v").mkdir(parents=True, exist_ok=True)

    dist = distribuicoes(veiculos)

    # Índice leve: só o que a lista e a busca precisam. As fichas completas vão
    # em arquivos separados, buscados sob demanda — 3.100 fichas com recibo não
    # cabem num payload inicial.
    # Editora repetida em 2.800 entradas dobrava o índice; vira tabela e cada
    # veículo guarda só o número.
    indice = [v.para_indice() for v in veiculos]
    editoras: list[str] = []
    pos: dict[str, int] = {}
    for d in indice:
        nome = d.pop("ed", None)
        if nome:
            if nome not in pos:
                pos[nome] = len(editoras)
                editoras.append(nome)
            d["ed"] = pos[nome]

    # Comissões Especiais da SBC: são as subáreas da Computação brasileira, e
    # até aqui só apareciam como texto decorativo na ficha.
    # Sigla sem o prefixo "CE-" (redundante quando todas têm) e nome por
    # extenso para o tooltip: "GRAPI" não diz nada a quem não é da subárea.
    nomes_ce = sbc.nomes_das_ces()
    ces: list[list[str]] = []
    pos_ce: dict[str, int] = {}
    for d in indice:
        lista = d.pop("ce", None)
        if lista:
            ids = []
            for c in lista:
                if c not in pos_ce:
                    pos_ce[c] = len(ces)
                    curto = c[3:] if c.upper().startswith("CE-") else c
                    ces.append([curto, nomes_ce.get(c, "")])
                ids.append(pos_ce[c])
            d["ce"] = ids

    (SAIDA / "dados" / "indice.json").write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "dist": dist,
                "editoras": editoras,
                "ces": ces,
                "veiculos": indice,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    for v in veiculos:
        (SAIDA / "dados" / "v" / f"{v.slug}.json").write_text(
            json.dumps(asdict(v), ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    # API pública: mesmos dados, schema estável, CORS aberto pelo vercel.json.
    (SAIDA / "api" / "v1").mkdir(parents=True, exist_ok=True)
    (SAIDA / "api" / "v1" / "veiculos.json").write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "aviso": "Estimativa segundo o Documento de Área de Computação "
                "(Área 02) 2025-2028. A classificação oficial é da comissão.",
                "veiculos": [asdict(v) for v in veiculos],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Página única: a ferramenta em cima, o texto embaixo. A raiz é o que o
    # buscador indexa, e é a mesma coisa que a pessoa usa.
    # Números que aparecem no HTML saem dos dados de fato gerados. Cravados à
    # mão eles envelhecem calados: a descrição do Dataset ficou meses anunciando
    # 1.983 periódicos quando já eram 2.692.
    marcas = {
        "{{N_PERIODICOS}}": _mil(sum(1 for v in veiculos if v.tipo == "periodico")),
        "{{N_EVENTOS}}": _mil(sum(1 for v in veiculos if v.tipo == "evento")),
        "{{N_TOTAL}}": _mil(len(veiculos)),
    }
    for nome in ("index.html", "estilo.css", "pagina.css", "app.js", "tema.js"):
        destino = SAIDA / nome
        if nome.endswith(".html"):
            texto = (APP / nome).read_text(encoding="utf-8")
            for k, v in marcas.items():
                texto = texto.replace(k, v)
            destino.write_text(texto, encoding="utf-8")
        else:
            shutil.copy2(APP / nome, destino)
    # A explicação vive em /sobre/: quem chega vai direto para a busca, e quem
    # quer entender tem uma página própria — que é também a que carrega o FAQ
    # para o buscador.
    sobre = SAIDA / "sobre"
    sobre.mkdir(parents=True, exist_ok=True)
    texto = (APP / "sobre.html").read_text(encoding="utf-8")
    for k, v in marcas.items():
        texto = texto.replace(k, v)
    (sobre / "index.html").write_text(texto, encoding="utf-8")
    shutil.copy2(APP / "sobre.js", sobre / "sobre.js")

    _agenda(SAIDA, veiculos, marcas)
    _sitemap(SAIDA, veiculos)

    kb = sum(f.stat().st_size for f in SAIDA.rglob("*") if f.is_file()) / 1024
    idx = (SAIDA / "dados" / "indice.json").stat().st_size / 1024
    print(f"\nGerado em {SAIDA} — {len(veiculos)} veículos, {kb:.0f} KB no total")
    print(f"  índice (carga inicial): {idx:.0f} KB")

    if args.servir:
        import http.server
        import socketserver

        class H(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *a, **k):
                super().__init__(*a, directory=str(SAIDA), **k)

        with socketserver.TCPServer(("", args.porta), H) as s:
            print(f"\nhttp://localhost:{args.porta}  (Ctrl+C para parar)")
            s.serve_forever()
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main())
