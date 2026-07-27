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
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from qualis import oficial, rules, sbc, scopus_export  # noqa: E402
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
    fronteira: str = ""
    nota: str = ""
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
    out: list[Veiculo] = []
    for fonte in scopus_export.carregar().values():
        if fonte.parece_evento:
            continue  # anais indexados no Scopus: vão pela regra de h5
        c = rules.classificar_periodico(
            fonte.titulo,
            percentil_scopus=fonte.percentil,
            e_sbc=fonte.e_sbc,
            rotulo_scopus="Scopus",
        )
        passos = [
            Passo(
                rotulo=f"Percentil {fonte.percentil:.0f} no Scopus",
                detalhe=(
                    f"corte de {c.estrato}: {rules.PERCENTIL_MINIMO[c.estrato]:.1f}"
                    if c.estrato in rules.PERCENTIL_MINIMO
                    else f"A8 é tudo abaixo de {rules.PERCENTIL_MINIMO['A7']:.1f}"
                ),
                estrato=c.estrato,
                fonte=f"Scopus · categoria {fonte.categoria or '?'}",
            )
        ]
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
    out: list[Veiculo] = []
    for ev in sbc.ler():
        r = resolver(ev, cache)
        slug = f"e-{slugificar(r.sigla or r.nome)}"
        # Muitos eventos brasileiros têm nome oficial em inglês na planilha da
        # SBC e são procurados em português (e vice-versa). Indexamos todos os
        # nomes conhecidos, inclusive os que o Scholar usa.
        apelidos = [n for n in ev.todos_os_nomes[1:]]
        apelidos += [e.rsplit(" (h5=", 1)[0] for e in r.entradas]
        apelidos = list(dict.fromkeys(a for a in apelidos if a and a != r.nome))

        if r.h5_fonte != "scholar" or r.h5 is None:
            # Sem h5 do Google, a regra ainda pode classificar pela CE-SBC.
            c = rules.classificar_evento(r.sigla, h5=0, ce_sbc=r.ce_sbc)
            passos = [
                Passo(
                    rotulo="Sem h5-index no Google Scholar",
                    detalhe="o evento não tem entrada no Scholar Metrics",
                    estrato=None,
                    fonte="Google Scholar Metrics",
                ),
                Passo(
                    rotulo=f"CE-SBC classifica como \u201c{r.ce_sbc}\u201d",
                    detalhe="para evento sem h5, o documento define: "
                    "\u201cTop\u201d \u2192 A7, \u201crelevante\u201d \u2192 A8",
                    estrato=c.estrato,
                    fonte="Documento de Área, p. 22",
                ),
            ]
            # O critério de indução (evento nacional da SBC com >=20 anos -> A4,
            # >=10 anos -> A5) exige o ano de fundação, que não temos de fonte
            # verificável. Não aplicamos — mas avisamos, porque a diferença é
            # grande: dos 126 eventos sem h5 que a CAPES classificou no ciclo
            # anterior, 82 receberam estrato melhor que o nosso.
            nota = (
                "Se este evento for um dos principais eventos nacionais "
                "promovidos pela SBC, o critério de indução pode elevá-lo a A4 "
                "(20+ anos de tradição) ou A5 (10+ anos). Não aplicamos porque "
                "não temos o ano de fundação verificado."
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
                    estrato_base=None,
                    oficial_estrato=of[r.sigla.upper()].estrato
                    if r.sigla.upper() in of else "",
                    oficial_original=of[r.sigla.upper()].estrato_original
                    if r.sigla.upper() in of else "",
                )
            )
            continue

        c = rules.classificar_evento(r.sigla, h5=r.h5, ce_sbc=r.ce_sbc)
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
                r.sigla, h5=r.h5, ce_sbc=r.ce_sbc, teto_qualitativo=False
            ).estrato
            passos.append(
                Passo(
                    rotulo=f"CE-SBC: \u201c{r.ce_sbc}\u201d",
                    detalhe=rotulos.get(r.ce_sbc, ""),
                    estrato=sem_teto if teto else c.estrato,
                    fonte=f"CEs: {', '.join(r.ces)}" if r.ces else "planilha da SBC",
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


def _sitemap(saida: Path, veiculos: list) -> None:
    """sitemap.xml e robots.txt — sem eles o buscador não acha as páginas."""
    urls = ["", "sobre/"]
    linhas = "".join(
        f"<url><loc>{DOMINIO}/{u}</loc>"
        f"<lastmod>{SNAPSHOT}</lastmod>"
        f"<priority>{'1.0' if u == '' else '0.8'}</priority></url>"
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
    (SAIDA / "dados" / "indice.json").write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "dist": dist,
                "veiculos": [v.para_indice() for v in veiculos],
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
    for nome in ("index.html", "estilo.css", "pagina.css", "app.js"):
        shutil.copy2(APP / nome, SAIDA / nome)
    # A explicação vive em /sobre/: quem chega vai direto para a busca, e quem
    # quer entender tem uma página própria — que é também a que carrega o FAQ
    # para o buscador.
    sobre = SAIDA / "sobre"
    sobre.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APP / "sobre.html", sobre / "index.html")
    shutil.copy2(APP / "sobre.js", sobre / "sobre.js")

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
