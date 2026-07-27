"""Percentil do Scopus pela API da Elsevier, em vez de export manual.

    export ELSEVIER_API_KEY=...           # dev.elsevier.com/apikey/manage
    python -m qualis importar-api --areas COMP

A API `serial/title` com `view=CITESCORE` devolve `citeScoreYearInfoList`, que
traz o CiteScore e o **percentil por área ASJC** de cada revista. É o mesmo dado
da coluna "Highest percentile" do export da tela Scopus Sources — conferido em
JMLR (98), IEEE Access (91) e ACM Computing Surveys (99), todos idênticos.

Três ganhos sobre o export manual:

1. **Cobertura.** COMP sozinho tem ~3.500 revistas, contra as ~2.200 que uma
   sessão de export rende. E a regra da Área 02 não restringe o campo do
   periódico — artigo de Computação publicado em revista de engenharia,
   medicina ou educação conta igual —, então dá para varrer outras áreas.
2. **ISSN**, que o export não traz e sem o qual não há busca por ISSN.
3. Repetível, sem clicar em tela.

Sobre licença: a chave gratuita é para uso acadêmico não comercial, e os termos
restringem construir base derivada redistribuível. Por isso este módulo grava
localmente e o site publica apenas o **estrato derivado** — resultado de regra
pública da CAPES —, nunca CiteScore, SJR ou SNIP.

A chave vem sempre de variável de ambiente. Nunca escreva chave em arquivo do
repositório.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .scopus_export import BD, Fonte, carregar, normalizar

API = "https://api.elsevier.com/content/serial/title"
POR_PAGINA = 200  # máximo aceito pela API
PAUSA = 0.25  # respeita o throttling; a cota semanal é de 20.000 requisições

# Áreas de topo do ASJC. COMP é o núcleo; as demais existem porque a regra não
# restringe o campo da revista — só exige aderência do ARTIGO à Computação.
AREAS = {
    "COMP": "Computer Science",
    "ENGI": "Engineering",
    "MATH": "Mathematics",
    "DECI": "Decision Sciences",
    "MULT": "Multidisciplinary",
    "HEAL": "Health Professions",
    "SOCI": "Social Sciences",
    "MEDI": "Medicine",
    "BUSI": "Business and Management",
    "PSYC": "Psychology",
}


class SemChave(RuntimeError):
    pass


class CotaEsgotada(RuntimeError):
    pass


@dataclass
class Resposta:
    fontes: list[Fonte]
    total: int
    restante: int | None


def _chave() -> str:
    k = os.environ.get("ELSEVIER_API_KEY", "").strip()
    if not k:
        raise SemChave(
            "defina ELSEVIER_API_KEY (pegue em dev.elsevier.com/apikey/manage).\n"
            "Nunca coloque a chave em arquivo do repositório."
        )
    return k


def _cabecalhos() -> dict[str, str]:
    h = {"X-ELS-APIKey": _chave(), "Accept": "application/json"}
    # Alguns campos podem exigir vínculo institucional; se a instituição
    # forneceu um insttoken, ele entra aqui.
    tok = os.environ.get("ELSEVIER_INSTTOKEN", "").strip()
    if tok:
        h["X-ELS-Insttoken"] = tok
    return h


def _pedir(params: dict) -> tuple[dict, int | None]:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_cabecalhos())
    for tentativa in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                restante = r.headers.get("X-RateLimit-Remaining")
                return json.loads(r.read()), (
                    int(restante) if restante and restante.isdigit() else None
                )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise CotaEsgotada("cota da API esgotada; ela reinicia a cada 7 dias")
            if e.code in (401, 403):
                raise SemChave(
                    f"HTTP {e.code}: chave inválida, ou o campo pedido exige "
                    f"vínculo institucional (tente de dentro da rede da "
                    f"instituição, ou defina ELSEVIER_INSTTOKEN)."
                )
            if tentativa == 3:
                raise
            time.sleep(2**tentativa)
        except Exception:
            if tentativa == 3:
                raise
            time.sleep(2**tentativa)
    raise AssertionError("unreachable")


def _maior_percentil(entrada: dict) -> tuple[float | None, str | None, int | None, int | None]:
    """Maior percentil entre as áreas da revista — é o que a regra manda usar.

    Prefere o ano mais recente marcado como completo; o "In-Progress" muda ao
    longo do ano e não serve para classificar.
    """
    cs = entrada.get("citeScoreYearInfoList") or {}
    anos = cs.get("citeScoreYearInfo") or []
    completos = [a for a in anos if a.get("@status") == "Complete"]
    for ano in completos or anos:
        for lista in ano.get("citeScoreInformationList") or []:
            for info in lista.get("citeScoreInfo") or []:
                if info.get("docType") not in (None, "all"):
                    continue
                ranks = info.get("citeScoreSubjectRank") or []
                pcts = [
                    (int(r["percentile"]), r.get("subjectCode"), r.get("rank"))
                    for r in ranks
                    if str(r.get("percentile", "")).isdigit()
                ]
                if pcts:
                    p, cod, rank = max(pcts, key=lambda x: x[0])
                    return (
                        float(p),
                        str(cod) if cod else None,
                        int(rank) if str(rank).isdigit() else None,
                        int(ano.get("@year")) if str(ano.get("@year")).isdigit() else None,
                    )
    return None, None, None, None


def _para_fonte(e: dict) -> Fonte | None:
    pct, cod, rank, ano = _maior_percentil(e)
    if pct is None:
        return None
    titulo = (e.get("dc:title") or "").strip()
    if not titulo:
        return None
    areas = e.get("subject-area") or []
    nomes = [a.get("$") for a in areas if a.get("@code") == cod] or [
        a.get("$") for a in areas
    ]
    cs = e.get("citeScoreYearInfoList") or {}
    try:
        citescore = float(cs.get("citeScoreCurrentMetric"))
    except (TypeError, ValueError):
        citescore = None
    issns = [
        (e.get(k) or "").replace("-", "").strip()
        for k in ("prism:issn", "prism:eIssn")
    ]
    f = Fonte(
        titulo=titulo,
        percentil=pct,
        citescore=citescore,
        rank=rank,
        total=None,
        categoria=(nomes[0] if nomes else None),
        snip=None,
        sjr=None,
        editora=(e.get("dc:publisher") or "").strip() or None,
    )
    # Campos extras que o export manual não tinha. `issns` habilita busca por
    # ISSN, que o site prometia no campo e não entregava.
    f.issns = [i for i in issns if i]  # type: ignore[attr-defined]
    f.ano_citescore = ano  # type: ignore[attr-defined]
    return f


def buscar_area(
    abbrev: str, *, inicio: int = 0, limite: int | None = None, verbose: bool = True
) -> list[Fonte]:
    """Percorre todas as revistas de uma área de topo do ASJC."""
    out: list[Fonte] = []
    start = inicio
    while True:
        d, restante = _pedir(
            {"subj": abbrev, "count": POR_PAGINA, "start": start, "view": "CITESCORE"}
        )
        entradas = (d.get("serial-metadata-response") or {}).get("entry") or []
        if not entradas or "error" in entradas[0]:
            break
        for e in entradas:
            f = _para_fonte(e)
            if f:
                out.append(f)
        start += len(entradas)
        if verbose:
            print(
                f"  {abbrev}: {start} lidas, {len(out)} com percentil"
                + (f" | cota restante {restante}" if restante is not None else ""),
                flush=True,
            )
        if len(entradas) < POR_PAGINA or (limite and start >= limite):
            break
        time.sleep(PAUSA)
    return out


def por_issn(issn: str) -> Fonte | None:
    d, _ = _pedir({"issn": issn.replace("-", ""), "view": "CITESCORE"})
    entradas = (d.get("serial-metadata-response") or {}).get("entry") or []
    return _para_fonte(entradas[0]) if entradas else None


def importar(areas: list[str], *, verbose: bool = True) -> dict[str, Fonte]:
    """Busca as áreas pedidas e mescla na base local, ficando com o maior
    percentil em caso de duplicata — a mesma convenção da regra."""
    bd = carregar()
    antes = len(bd)
    novos = atualizados = 0

    for a in areas:
        for f in buscar_area(a, verbose=verbose):
            k = normalizar(f.titulo)
            atual = bd.get(k)
            if atual is None:
                bd[k] = f
                novos += 1
            elif f.percentil > atual.percentil:
                bd[k] = f
                atualizados += 1
            elif getattr(f, "issns", None) and not getattr(atual, "issns", None):
                atual.issns = f.issns  # type: ignore[attr-defined]

    import gzip
    from dataclasses import asdict

    BD.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(BD, "wt", encoding="utf-8") as fh:
        json.dump(
            {
                k: {**asdict(v), "issns": getattr(v, "issns", [])}
                for k, v in bd.items()
            },
            fh,
            ensure_ascii=False,
        )
    if verbose:
        print(
            f"\nbase: {antes} -> {len(bd)} periódicos "
            f"({novos} novos, {atualizados} com percentil maior)"
        )
    return bd
