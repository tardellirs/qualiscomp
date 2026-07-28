"""O que o buscador lê sobre o site.

Dois defeitos motivaram estes testes, ambos silenciosos — o site funcionava
perfeitamente enquanto anunciava coisa errada ao Google:

1. Faltava `creator` no Dataset (o Search Console avisou).
2. As contagens estavam cravadas no HTML e envelheceram: a descrição anunciava
   1.983 periódicos quando já eram 2.692.
"""

import json
import re
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent / "site" / "dist"
PAGINAS = [DIST / "index.html", DIST / "sobre" / "index.html"]

pytestmark = pytest.mark.skipif(
    not (DIST / "index.html").exists(), reason="rode site/build.py antes"
)


def _blocos(p: Path) -> list[dict]:
    s = p.read_text(encoding="utf-8")
    out = []
    for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        d = json.loads(b)
        out.extend(d.get("@graph", [d]))
    return out


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p.parent.name or "raiz")
def test_json_ld_e_valido(pagina):
    assert _blocos(pagina), f"{pagina} não tem JSON-LD"


def test_dataset_tem_creator():
    """Sem `creator` o Google não sabe a quem atribuir o conjunto de dados."""
    ds = next(b for b in _blocos(DIST / "index.html") if b.get("@type") == "Dataset")
    assert ds.get("creator", {}).get("name")


@pytest.mark.parametrize("pagina", PAGINAS, ids=lambda p: p.parent.name or "raiz")
def test_sem_marcador_por_substituir(pagina):
    """Um {{N_PERIODICOS}} vazado apareceria na busca do Google."""
    assert not re.findall(r"\{\{[A-Z_]+\}\}", pagina.read_text(encoding="utf-8"))


def test_contagens_batem_com_os_dados():
    """A descrição que o buscador lê tem que ser o número que o site tem."""
    veiculos = json.loads((DIST / "dados" / "indice.json").read_text())["veiculos"]
    real = {
        "p": sum(1 for v in veiculos if v.get("t") == "p"),
        "e": sum(1 for v in veiculos if v.get("t") == "e"),
    }
    fmt = lambda n: f"{n:,}".replace(",", ".")  # noqa: E731
    for pagina in PAGINAS:
        s = pagina.read_text(encoding="utf-8")
        for achado in re.findall(r"([\d.]+) periódicos", s):
            assert achado == fmt(real["p"]), f"{pagina.name}: {achado} periódicos"
        for achado in re.findall(r"([\d.]+) (?:eventos|conferências)", s):
            assert achado == fmt(real["e"]), f"{pagina.name}: {achado} eventos"
