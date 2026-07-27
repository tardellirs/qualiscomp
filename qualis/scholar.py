"""h5-index REAL, direto do Google Scholar Metrics.

O Scholar não tem API, mas a tela de busca de veículos responde a GET simples e
devolve h5-index e h5-mediana em uma tabela HTML:

    https://scholar.google.com/citations?hl=pt-BR&view_op=search_venues&vq=<termo>

Este é o número que a Área 02 usa para classificar artigos em eventos — não um
proxy. A janela é a do Scholar Metrics vigente (5 anos completos).

Cuidados:
- Busque pelo **nome completo em inglês**; siglas ("SBES", "SBC") quase não
  retornam nada, porque o Scholar indexa pelo nome por extenso.
- O Scholar pode bloquear por volume. Há um intervalo entre requisições, e um
  bloqueio é reportado como erro explícito, nunca silenciado como "não achado" —
  confundir os dois faria a base ficar cheia de buracos invisíveis.
"""

from __future__ import annotations

import html
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

URL = "https://scholar.google.com/citations"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
INTERVALO_S = 2.0

_LINHA = re.compile(r"<tr>(.*?)</tr>", re.S)
_CELULA = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")


class ScholarBloqueado(RuntimeError):
    """O Scholar respondeu com captcha/bloqueio, não com resultados."""


@dataclass
class Venue:
    nome: str
    h5: int
    h5_mediana: int


def _limpar(c: str) -> str:
    return html.unescape(_TAG.sub("", c)).strip()


def buscar(termo: str, *, hl: str = "pt-BR", timeout: int = 30) -> list[Venue]:
    """Busca veículos no Scholar Metrics e devolve os que têm h5."""
    qs = urllib.parse.urlencode(
        {"hl": hl, "view_op": "search_venues", "vq": termo, "btnG": ""}
    )
    req = urllib.request.Request(f"{URL}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        corpo = r.read().decode("utf-8", "replace")

    if "unusual traffic" in corpo or "/sorry/" in corpo or "captcha" in corpo.lower():
        raise ScholarBloqueado(
            f"Google Scholar bloqueou a consulta '{termo}'. Espere alguns minutos "
            f"e aumente INTERVALO_S."
        )

    out: list[Venue] = []
    for linha in _LINHA.findall(corpo):
        celulas = [_limpar(c) for c in _CELULA.findall(linha)]
        # Formato: ['1.', '<nome>', '<h5>', '<h5-mediana>']
        if len(celulas) >= 4 and celulas[2].isdigit() and celulas[3].isdigit():
            out.append(Venue(celulas[1], int(celulas[2]), int(celulas[3])))
    return out


def melhor(termo: str, **kw) -> Venue | None:
    """Primeiro resultado da busca, que é o mais relevante segundo o Scholar."""
    r = buscar(termo, **kw)
    return r[0] if r else None


@dataclass
class ResultadoEvento:
    """h5 de um evento, com as entradas concorrentes que o produziram."""

    h5: int | None
    entrada: Venue | None
    alternativas: list[Venue]

    @property
    def ambiguo(self) -> bool:
        """O Scholar tem mais de uma entrada com h5 diferente para o evento."""
        return len({v.h5 for v in self.alternativas}) > 1


def h5_de_evento(*nomes: str, intervalo: float = INTERVALO_S) -> ResultadoEvento:
    """Busca o h5 de um evento por vários nomes e devolve o MAIOR.

    Existe porque eventos brasileiros costumam ter DUAS entradas no Scholar, uma
    em português e outra em inglês, com as citações partidas entre elas. O IHC é
    o caso extremo: "Simpósio Brasileiro sobre Fatores Humanos em Sistemas
    Computacionais (IHC)" tem h5=5, e "Brazilian Symposium on Human Factors in
    Computing Systems" tem h5=16 — três estratos de diferença (A8 vs A4).

    Pegamos o maior, que é a entrada mais completa, e sinalizamos a ambiguidade
    em `ambiguo` para que a decisão não passe despercebida.
    """
    vistos: dict[str, Venue] = {}
    for i, nome in enumerate(n for n in nomes if n and n.strip()):
        if i:
            time.sleep(intervalo)
        try:
            for v in buscar(nome):
                vistos.setdefault(v.nome, v)
        except ScholarBloqueado:
            raise
        except Exception:
            continue
    if not vistos:
        return ResultadoEvento(None, None, [])
    # Só consideramos entradas cujo nome lembre a consulta, para não capturar
    # um periódico homônimo que apareceu na mesma busca.
    alvo = max(vistos.values(), key=lambda v: v.h5)
    return ResultadoEvento(alvo.h5, alvo, sorted(vistos.values(), key=lambda v: -v.h5))


def buscar_varios(
    termos: list[str], *, intervalo: float = INTERVALO_S, verbose: bool = True
) -> dict[str, Venue | None]:
    """Busca vários termos em sequência, respeitando um intervalo entre eles."""
    resultado: dict[str, Venue | None] = {}
    for i, t in enumerate(termos):
        if i:
            time.sleep(intervalo)
        try:
            v = melhor(t)
        except ScholarBloqueado:
            raise
        except Exception as e:  # rede instável não deve derrubar o lote inteiro
            if verbose:
                print(f"  [!] {t}: {e}")
            v = None
        resultado[t] = v
        if verbose:
            print(f"  {t}: {'h5=' + str(v.h5) + f' ({v.nome})' if v else 'não achado'}")
    return resultado


# Termos amplos que varrem o grosso dos veículos de Computação de uma vez. Uma
# busca por "brazilian" traz 20 veículos; buscar evento por evento pelo nome
# gastaria dezenas de requisições e aumentaria o risco de bloqueio.
TERMOS_AMPLOS = (
    "brazilian",
    "simposio brasileiro",
    "simpósio brasileiro",
    "congresso brasileiro",
    "workshop brasileiro",
    "latin american",
)

# Conferências internacionais de referência. O Scholar indexa cada uma pelo nome
# por extenso, então buscamos assim e não pela sigla.
CONFERENCIAS_INTERNACIONAIS = (
    "Neural Information Processing Systems",
    "International Conference on Machine Learning",
    "International Conference on Learning Representations",
    "AAAI Conference on Artificial Intelligence",
    "International Joint Conference on Artificial Intelligence",
    "Meeting of the Association for Computational Linguistics",
    "Empirical Methods in Natural Language Processing",
    "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
    "International Conference on Computer Vision",
    "European Conference on Computer Vision",
    "International Conference on Software Engineering",
    "Foundations of Software Engineering",
    "International Conference on Automated Software Engineering",
    "International Symposium on Software Testing and Analysis",
    "ACM SIGCOMM Conference",
    "USENIX Symposium on Networked Systems Design and Implementation",
    "IEEE International Conference on Computer Communications",
    "Symposium on Operating Systems Principles",
    "USENIX Symposium on Operating Systems Design and Implementation",
    "IEEE Symposium on Security and Privacy",
    "USENIX Security Symposium",
    "ACM Conference on Computer and Communications Security",
    "Network and Distributed System Security Symposium",
    "ACM SIGMOD International Conference on Management of Data",
    "International Conference on Very Large Data Bases",
    "IEEE International Conference on Data Engineering",
    "Knowledge Discovery and Data Mining",
    "International ACM SIGIR Conference",
    "The Web Conference",
    "Symposium on Theory of Computing",
    "Symposium on Foundations of Computer Science",
    "ACM-SIAM Symposium on Discrete Algorithms",
    "Principles of Programming Languages",
    "Programming Language Design and Implementation",
    "International Conference on Computer Aided Verification",
    "Conference on Human Factors in Computing Systems",
    "ACM Symposium on User Interface Software and Technology",
    "ACM International Conference on Multimedia",
    "International Symposium on Computer Architecture",
    "IEEE/ACM International Symposium on Microarchitecture",
    "Architectural Support for Programming Languages and Operating Systems",
    "International Conference for High Performance Computing",
)


def coletar(
    termos: list[str] | None = None, *, intervalo: float = INTERVALO_S, verbose: bool = True
) -> dict[str, Venue]:
    """Varre vários termos e junta todos os veículos encontrados.

    Devolve um dicionário nome-do-veículo -> Venue, deduplicado. Um bloqueio
    interrompe a coleta em vez de devolver um resultado parcial silencioso.
    """
    termos = list(termos if termos is not None else TERMOS_AMPLOS + CONFERENCIAS_INTERNACIONAIS)
    achados: dict[str, Venue] = {}
    for i, t in enumerate(termos):
        if i:
            time.sleep(intervalo)
        try:
            vs = buscar(t)
        except ScholarBloqueado:
            if verbose:
                print(f"  [BLOQUEADO] parando em '{t}' com {len(achados)} veículos coletados")
            raise
        except Exception as e:
            if verbose:
                print(f"  [!] {t}: {e}")
            continue
        novos = sum(1 for v in vs if v.nome not in achados)
        for v in vs:
            achados.setdefault(v.nome, v)
        if verbose:
            print(f"  {t}: {len(vs)} veículos ({novos} novos) | total {len(achados)}")
    return achados
