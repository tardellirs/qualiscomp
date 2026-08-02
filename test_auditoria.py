"""Invariantes do catálogo publicado.

Cada um destes nasceu de um defeito encontrado numa varredura geral:
941 revistas ativas marcadas como descontinuadas, e o mesmo evento listado
duas vezes com estratos diferentes.
"""

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent / "site" / "dist" / "dados" / "v"

pytestmark = pytest.mark.skipif(not DIST.exists(), reason="rode site/build.py antes")


def _ler(prefixo):
    return [json.loads(f.read_text(encoding="utf-8")) for f in DIST.glob(f"{prefixo}-*.json")]


def _chave(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t)


def test_nenhum_evento_listado_duas_vezes():
    por = defaultdict(list)
    for d in _ler("e"):
        por[_chave(d["nome"])].append(d.get("sigla") or d["slug"])
    dup = {k: v for k, v in por.items() if len(v) > 1}
    assert not dup, f"{len(dup)} eventos repetidos: {list(dup.values())[:4]}"


def test_descontinuado_nao_tem_percentil_recente():
    """`coverageEndYear` do Scopus marca o fim do primeiro TRECHO de cobertura,
    não o da revista — a Science aparece com fim em 1881. Revista com percentil
    nos últimos anos está viva, diga o que disser aquele campo."""
    vivos = [
        d["nome"]
        for d in _ler("p")
        if d.get("descontinuada")
        and any(a >= 2024 for a, *_ in (d.get("historico") or []))
    ]
    assert not vivos, f"{len(vivos)} marcados como mortos mas com dado recente: {vivos[:5]}"


def test_todo_periodico_publicado_tem_percentil():
    """Sem percentil a regra não se aplica, e o veículo não deve ser listado."""
    assert not [d["nome"] for d in _ler("p") if d.get("percentil") is None]


def test_todo_veiculo_tem_recibo():
    assert not [d["slug"] for d in _ler("p") + _ler("e") if not d.get("passos")]
