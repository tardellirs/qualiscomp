"""Coleta o h5 real do Scholar para os eventos da planilha das CEs da SBC.

Junta as duas fontes que a Área 02 usa, cada uma no seu papel:
  - planilha das CEs da SBC -> rótulo Top10 / Top20 / relevante
  - Google Scholar Metrics  -> h5-index (o documento é explícito: "H5 do Google")

O ponto delicado é o casamento de nomes. O Scholar indexa o mesmo evento sob
mais de uma entrada — em português e em inglês, com as citações partidas entre
elas (o IHC tem h5=5 em português e 16 em inglês). Então, para cada evento,
agrupamos todas as entradas parecidas e ficamos com o MAIOR h5, marcando o caso
como ambíguo para você poder revisar.

A coleta é cacheada em disco e retomável: são ~1100 consultas com intervalo
entre elas, e um bloqueio no meio não pode custar o trabalho já feito.
"""

from __future__ import annotations

import gzip
import json
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import sbc, scholar

CACHE = Path(__file__).resolve().parent.parent / "data" / "scholar_cache.json.gz"

# Palavras que não ajudam a distinguir um evento de outro.
_RUIDO = frozenset(
    """de da do das dos e em on of the and for a an at
    international conference symposium workshop congress simposio simpósio
    congresso encontro anais proceedings annual ieee acm sbc""".split()
)


def _sem_acento(t: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn"
    )


def normalizar(t: str) -> str:
    t = _sem_acento(t.lower())
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokens(t: str) -> set[str]:
    return {p for p in normalizar(t).split() if p not in _RUIDO and len(p) > 2}


def similaridade(a: str, b: str) -> float:
    """Jaccard entre os tokens significativos de dois nomes."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _sigla_no_nome(sigla: str, nome: str) -> bool:
    """A sigla do evento aparece como identificador dentro do nome da entrada.

    Siglas curtas são palavras comuns em outras línguas: "CHI" casava com
    "Yebang Uihakhoe chi" e "Tạp chí Nghiên cứu...". Por isso, até 3 letras só
    vale entre parênteses — "Computer Human Interaction (CHI)" conta, "chi"
    solto no meio de um título não.
    """
    s = normalizar(sigla)
    if not s:
        return False
    if f"({s})" in normalizar(nome).replace(" (", "(").replace("( ", "("):
        return True
    # Reconstrói os parênteses, que `normalizar` remove.
    if re.search(rf"\(\s*{re.escape(sigla)}\s*\)", nome, re.IGNORECASE):
        return True
    return len(s) >= 4 and s in normalizar(nome).split()


@dataclass
class EventoResolvido:
    sigla: str
    nome: str
    ce_sbc: str
    ces: list[str]
    h5: int | None
    h5_fonte: str  # scholar | sbc-2024 | nenhum
    h5_sbc: int | None
    entradas: list[str] = field(default_factory=list)
    ambiguo: bool = False

    @property
    def divergencia_sbc(self) -> int | None:
        if self.h5 is None or self.h5_sbc is None:
            return None
        return self.h5 - self.h5_sbc


class Cache:
    """Consultas já feitas ao Scholar, para tornar a coleta retomável."""

    def __init__(self, caminho: Path = CACHE):
        self.caminho = caminho
        self.dados: dict[str, list[dict]] = {}
        if caminho.exists():
            with gzip.open(caminho, "rt", encoding="utf-8") as f:
                self.dados = json.load(f)

    def __contains__(self, k: str) -> bool:
        return k in self.dados

    def get(self, k: str) -> list[scholar.Venue]:
        return [scholar.Venue(**v) for v in self.dados.get(k, [])]

    def set(self, k: str, vs: list[scholar.Venue]) -> None:
        self.dados[k] = [asdict(v) for v in vs]

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        with gzip.open(tmp, "wt", encoding="utf-8") as f:
            json.dump(self.dados, f, ensure_ascii=False)
        tmp.replace(self.caminho)  # troca atômica: nunca deixa cache truncado


# Prefixos institucionais que o Scholar frequentemente não usa no nome do
# veículo. "ACM Conference on Human Factors in Computing Systems" devolve zero;
# "Human Factors in Computing Systems" acha.
_PREFIXOS = re.compile(
    r"^(?:(?:the|acm|ieee|ifip|usenix|sbc|sbmicro|siam|eurographics|springer)"
    r"[\s/\-]*)+",
    re.IGNORECASE,
)
# Preâmbulos genéricos: o miolo depois de "... on" costuma ser o nome indexado.
_PREAMBULO = re.compile(
    r"^.*?\b(?:conference|symposium|workshop|congress|conferencia|congresso|"
    r"simp[oó]sio|encontro|escola)\b\s+(?:on|of|em|de|sobre|do|da)\s+",
    re.IGNORECASE,
)


def _variantes(nome: str) -> list[str]:
    """Formas alternativas de um nome, para vencer a busca literal do Scholar.

    A busca de veículos do Scholar casa por substring, não por relevância: a
    grafia da SBC "Simpósio Brasileiro de Bancos de Dados" devolve zero porque o
    Scholar indexa "Banco de Dados", no singular. Então tentamos o nome inteiro,
    sem o prefixo institucional, e só o miolo temático.
    """
    out = [nome]
    sem_paren = re.sub(r"\s*\([^)]*\)\s*", " ", nome).strip()
    if sem_paren and sem_paren != nome:
        out.append(sem_paren)
    for base in list(out):
        curto = _PREFIXOS.sub("", base).strip()
        if curto and curto not in out:
            out.append(curto)
        miolo = _PREAMBULO.sub("", base).strip()
        if len(miolo) > 12 and miolo not in out:
            out.append(miolo)
    return out


def _consultas(ev: sbc.EventoSBC) -> list[str]:
    """Termos de busca para um evento, do mais específico ao mais genérico."""
    qs: list[str] = []
    for nome in ev.todos_os_nomes:
        for v in _variantes(nome):
            if v not in qs:
                qs.append(v)
    # A sigla sozinha raramente acha (o Scholar indexa por extenso), mas é a
    # única forma de alguns eventos: SBGames, WSCAD indexado como SSCAD.
    if len(ev.sigla) >= 3 and ev.sigla not in qs:
        qs.append(ev.sigla)
    return [q for q in qs if q and q.strip()]


def _pontuar(ev: sbc.EventoSBC, v: scholar.Venue) -> float:
    """Quão bem a entrada do Scholar corresponde ao evento (0 a ~1.4)."""
    base = max(similaridade(n, v.nome) for n in ev.todos_os_nomes)
    return base + (0.4 if _sigla_no_nome(ev.sigla, v.nome) else 0.0)


# Com a sigla já confirmando o evento, um casamento textual precisa ser quase
# perfeito para acrescentar alguma coisa.
_QUASE_EXATO = 0.95


def resolver(
    ev: sbc.EventoSBC, cache: Cache, *, limiar: float = 0.45, margem: float = 0.12
) -> EventoResolvido:
    """Casa um evento da SBC com as entradas do Scholar e escolhe o h5.

    Só ficam as entradas no topo do ranking de similaridade (`margem`). Sem
    isso, "International Conference on Software Engineering" arrastava junto
    "...on Automated Software Engineering" (o ASE, outro evento) — os tokens se
    sobrepõem demais para um limiar fixo separar os dois.
    """
    por_similaridade: dict[str, tuple[scholar.Venue, float]] = {}
    por_sigla: dict[str, scholar.Venue] = {}
    for q in _consultas(ev):
        for v in cache.get(q):
            if _sigla_no_nome(ev.sigla, v.nome):
                # A sigla do evento aparece como palavra no nome da entrada:
                # é o mesmo evento, mesmo que o idioma diferente zere a
                # similaridade textual. É assim que "Brazilian Symposium on
                # Databases (SBBD)" (h5=8) se junta a "Simpósio Brasileiro de
                # Banco de Dados (SBBD)" (h5=4), que são a mesma conferência
                # com as citações partidas em duas entradas.
                por_sigla.setdefault(v.nome, v)
                continue
            p = _pontuar(ev, v)
            if p >= limiar:
                por_similaridade.setdefault(v.nome, (v, p))

    selecionados: dict[str, scholar.Venue] = dict(por_sigla)
    if por_similaridade:
        melhor_p = max(p for _, p in por_similaridade.values())
        # Com uma entrada já confirmada pela sigla, a identidade do evento não
        # está em dúvida — e aí casamento PARCIAL passa a ser mais perigoso que
        # útil, porque só pode trazer outro evento. O SBIE tinha a sua entrada
        # ("Simpósio Brasileiro de Informática na Educação (SBIE)", h5=15) e
        # perdia para a do ICCE ("International Conference on Computers in
        # Education", h5=16), que casou a 0,67 pela palavra genérica que
        # sobrou ao tirar o preâmbulo. Só entra quem casar quase inteiro — é
        # o caso do IHC, cujo nome em inglês casa a 1,00 e é o mesmo evento.
        corte = _QUASE_EXATO if por_sigla else melhor_p - margem
        for v, p in por_similaridade.values():
            if p >= corte:
                selecionados.setdefault(v.nome, v)

    if selecionados:
        melhores = sorted(selecionados.values(), key=lambda v: -v.h5)
        return EventoResolvido(
            sigla=ev.sigla,
            nome=ev.nome,
            ce_sbc=ev.classificacao,
            ces=ev.ces,
            h5=melhores[0].h5,
            h5_fonte="scholar",
            h5_sbc=ev.h5_sbc,
            entradas=[f"{v.nome} (h5={v.h5})" for v in melhores],
            ambiguo=len({v.h5 for v in melhores}) > 1,
        )

    # Sem entrada no Scholar: h5 fica VAZIO. Rotular a origem não basta — se o
    # número da planilha da SBC ocupar o campo `h5`, ele alimenta
    # `estrato_por_h5` e vira estrato publicado. E ele é sistematicamente
    # diferente do Google (delta médio ~+4,6 pontos nos casos verificados, com
    # cortes espaçados de 3 a 5: cerca de um estrato inteiro de erro).
    # O valor da SBC continua disponível em `h5_sbc`, só como referência.
    return EventoResolvido(
        sigla=ev.sigla,
        nome=ev.nome,
        ce_sbc=ev.classificacao,
        ces=ev.ces,
        h5=None,
        h5_fonte="nenhum",
        h5_sbc=ev.h5_sbc,
    )


def coletar(
    eventos: list[sbc.EventoSBC] | None = None,
    *,
    intervalo: float = 2.0,
    verbose: bool = True,
    salvar_a_cada: int = 25,
) -> list[EventoResolvido]:
    """Consulta o Scholar para todos os eventos, com cache e retomada.

    Todas as variantes de NOME são consultadas, mesmo depois de uma achar algo:
    é assim que se descobre que o IHC tem duas entradas (PT h5=5, EN h5=16). Parar
    na primeira devolveria só a portuguesa e esconderia três estratos de
    diferença — e expor essa ambiguidade é o ponto central do produto.
    A SIGLA, essa sim, só é tentada se nenhum nome achou nada.
    """
    eventos = eventos if eventos is not None else sbc.ler()
    cache = Cache()
    feitas = novas = 0

    try:
        for n, ev in enumerate(eventos, 1):
            nomes = [q for nome in ev.todos_os_nomes for q in _variantes(nome)]
            sigla = [ev.sigla] if len(ev.sigla) >= 3 else []
            achou_algo = False
            for q in dict.fromkeys(nomes + sigla):
                # A sigla é o último recurso: só consulta se nenhum nome achou.
                if q in sigla and q not in nomes and achou_algo:
                    break
                if q in cache:
                    achou_algo = achou_algo or bool(cache.get(q))
                    continue
                try:
                    vs = scholar.buscar(q)
                except scholar.ScholarBloqueado:
                    cache.salvar()
                    if verbose:
                        print(f"  [BLOQUEADO] em {n}/{len(eventos)}. Cache salvo; "
                              f"rode de novo mais tarde.", flush=True)
                    raise
                except Exception as e:
                    # Falha de rede NÃO vira "não existe": fica fora do cache.
                    if verbose:
                        print(f"  [!] {q[:48]}: {e}", flush=True)
                    continue
                cache.set(q, vs)
                novas += 1
                achou_algo = achou_algo or bool(vs)
                time.sleep(intervalo)
            feitas += 1
            if novas and feitas % salvar_a_cada == 0:
                cache.salvar()
                if verbose:
                    print(f"  {n}/{len(eventos)} eventos | {novas} consultas novas",
                          flush=True)
    finally:
        cache.salvar()

    return [resolver(ev, cache) for ev in eventos]


CSV_COLUNAS = (
    "sigla", "nome", "h5", "ce_sbc", "anos_tradicao", "segue_gt_capes",
    "h5_fonte", "h5_sbc", "ambiguo", "ces", "entradas_scholar",
)


def exportar_csv(
    resolvidos: list[EventoResolvido], caminho: Path | str | None = None
) -> Path:
    """Grava a base de eventos que o comando `qualis evento` consome."""
    import csv

    from .eventos import ARQUIVO

    caminho = Path(caminho) if caminho else ARQUIVO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as f:
        f.write(
            "// Gerado por `qualis coletar-eventos`. Edite à mão se precisar:\n"
            "// linhas iniciadas por // são ignoradas, e a coluna h5 vence.\n"
            "// h5_fonte=scholar é o dado que o Documento de Área manda usar;\n"
            "// h5_fonte=sbc-2024 é a coluna da planilha da SBC, que está\n"
            "// desatualizada e serve só como referência.\n"
            "// ambiguo=1: o Scholar tem mais de uma entrada para o evento,\n"
            "// com h5 diferentes; ficamos com o maior. Confira esses casos.\n"
            "// anos_tradicao fica vazio: não há fonte verificável em massa.\n"
        )
        w = csv.DictWriter(f, fieldnames=list(CSV_COLUNAS))
        w.writeheader()
        for r in sorted(resolvidos, key=lambda r: r.sigla.upper()):
            w.writerow(
                {
                    "sigla": r.sigla,
                    "nome": r.nome,
                    "h5": r.h5 if r.h5 is not None else "",
                    "ce_sbc": r.ce_sbc,
                    "anos_tradicao": "",
                    "segue_gt_capes": 1,
                    "h5_fonte": r.h5_fonte,
                    "h5_sbc": r.h5_sbc if r.h5_sbc is not None else "",
                    "ambiguo": 1 if r.ambiguo else 0,
                    "ces": "|".join(r.ces),
                    "entradas_scholar": " || ".join(r.entradas),
                }
            )
    return caminho


def grupos_ambiguos(resolvidos: list[EventoResolvido]) -> list[EventoResolvido]:
    """Eventos com mais de uma entrada no Scholar, do maior desacordo ao menor."""

    def desacordo(r: EventoResolvido) -> int:
        h5s = [int(e.rsplit("h5=", 1)[1].rstrip(")")) for e in r.entradas if "h5=" in e]
        return max(h5s) - min(h5s) if len(h5s) > 1 else 0

    return sorted(
        (r for r in resolvidos if r.ambiguo), key=desacordo, reverse=True
    )
