"""O recibo tem que terminar no estrato que a ficha mostra.

O BSB não tem entrada no Scholar, é Top20 na CE (A7) e tem 16 edições (A5 pela
indução). O recibo mostrava só a CE e terminava em A7, com A5 no topo da ficha —
quem lia não fechava a conta.
"""

import json
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent / "site" / "dist" / "dados" / "v"

pytestmark = pytest.mark.skipif(
    not DIST.exists(), reason="rode site/build.py antes"
)


def _fichas():
    for f in DIST.glob("e-*.json"):
        yield json.loads(f.read_text(encoding="utf-8"))


def test_ultimo_passo_bate_com_o_estrato():
    """Vale para todos os eventos, não só o BSB."""
    falham = []
    for d in _fichas():
        passos = [p for p in d["passos"] if p.get("estrato")]
        if not passos or not d.get("estrato"):
            continue
        if passos[-1]["estrato"] != d["estrato"]:
            falham.append((d["sigla"], passos[-1]["estrato"], d["estrato"]))
    assert not falham, f"{len(falham)} recibos não fecham: {falham[:5]}"


def test_bsb_mostra_ce_e_inducao():
    d = json.loads((DIST / "e-bsb.json").read_text(encoding="utf-8"))
    rotulos = [p["rotulo"] for p in d["passos"]]
    assert any("CE-SBC" in r for r in rotulos)
    assert any("edições" in r for r in rotulos)
    assert d["estrato"] == "A5"


def test_passo_da_ce_mostra_o_que_a_ce_da_sozinha():
    """Não o estrato final: 'Top' sem h5 dá A7, e é isso que o passo diz."""
    d = json.loads((DIST / "e-bsb.json").read_text(encoding="utf-8"))
    ce = next(p for p in d["passos"] if "CE-SBC" in p["rotulo"])
    assert ce["estrato"] == "A7"
