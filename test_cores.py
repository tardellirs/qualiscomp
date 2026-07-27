"""Verifica a rampa de cores dos 8 estratos lendo o CSS de verdade.

Existe porque eu afirmei "contraste >= 7:1" no plano sem medir, e três dos oito
chips não cumpriam — o A3 ficava em 4,25:1, abaixo até do mínimo AA. Alegação de
acessibilidade sem teste é só alegação.

As três propriedades verificadas:
  1. contraste do texto sobre o chip >= 7:1 (WCAG AAA para texto normal);
  2. luminância monotônica — a ordem A1..A8 sobrevive em escala de cinza;
  3. separação mínima entre vizinhos, para os degraus serem distinguíveis.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

CSS = Path(__file__).resolve().parent / "site" / "app" / "estilo.css"

CONTRASTE_MINIMO = 7.0
SEPARACAO_MINIMA = 0.02  # luminância relativa entre estratos vizinhos


def oklch_para_srgb(L: float, C: float, h: float) -> tuple[float, float, float]:
    a = C * math.cos(math.radians(h))
    b = C * math.sin(math.radians(h))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )

    def gama(x: float) -> float:
        x = max(0.0, min(1.0, x))
        return 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055

    return tuple(gama(x) for x in lin)  # type: ignore[return-value]


def luminancia(rgb: tuple[float, float, float]) -> float:
    def f(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: tuple, b: tuple) -> float:
    la, lb = luminancia(a), luminancia(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


_TOKEN = re.compile(
    r"--e(\d)(t?):\s*oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)", re.I
)


def ler_rampa() -> dict[int, dict[str, tuple[float, float, float]]]:
    """Extrai --e1..--e8 e --e1t..--e8t direto do CSS servido."""
    texto = CSS.read_text(encoding="utf-8")
    out: dict[int, dict[str, tuple[float, float, float]]] = {}
    for n, tinta, L, C, h in _TOKEN.findall(texto):
        out.setdefault(int(n), {})["tinta" if tinta else "fundo"] = (
            float(L),
            float(C),
            float(h),
        )
    return out


@pytest.fixture(scope="module")
def rampa():
    r = ler_rampa()
    assert set(r) == set(range(1, 9)), f"esperava 8 estratos, achei {sorted(r)}"
    return r


@pytest.mark.parametrize("n", range(1, 9))
def test_contraste_do_texto_sobre_o_chip(rampa, n):
    fundo = oklch_para_srgb(*rampa[n]["fundo"])
    tinta = oklch_para_srgb(*rampa[n]["tinta"])
    r = contraste(fundo, tinta)
    assert r >= CONTRASTE_MINIMO, f"A{n}: {r:.2f}:1, abaixo de {CONTRASTE_MINIMO}:1"


def test_luminancia_monotonica(rampa):
    """A1 é o mais escuro e A8 o mais claro, sem inversão no meio.

    É isso que faz a ordem sobreviver em preto e branco e em daltonismo — a
    matiz é só reforço redundante.
    """
    lums = [luminancia(oklch_para_srgb(*rampa[n]["fundo"])) for n in range(1, 9)]
    for i in range(7):
        assert lums[i] < lums[i + 1], (
            f"A{i + 1} ({lums[i]:.3f}) não é mais escuro que A{i + 2} ({lums[i + 1]:.3f})"
        )


def test_estratos_vizinhos_sao_distinguiveis(rampa):
    lums = [luminancia(oklch_para_srgb(*rampa[n]["fundo"])) for n in range(1, 9)]
    for i in range(7):
        d = lums[i + 1] - lums[i]
        assert d >= SEPARACAO_MINIMA, f"A{i + 1}/A{i + 2} diferem só {d:.4f}"


def test_cores_dentro_do_gamut_srgb(rampa):
    """oklch permite cores fora do sRGB, que o navegador recorta de forma
    imprevisível — e um recorte muda o contraste medido."""
    for n in range(1, 9):
        for papel in ("fundo", "tinta"):
            rgb = oklch_para_srgb(*rampa[n][papel])
            for c in rgb:
                assert 0.0 <= c <= 1.0, f"A{n} {papel} fora do gamut: {rgb}"


def test_funcoes_de_cor_conferem_com_valores_conhecidos():
    """Guarda contra erro na própria matemática do teste."""
    branco = oklch_para_srgb(1.0, 0.0, 0.0)
    preto = oklch_para_srgb(0.0, 0.0, 0.0)
    assert contraste(branco, preto) == pytest.approx(21.0, abs=0.1)
    assert luminancia(branco) == pytest.approx(1.0, abs=0.01)
