"""Periódicos trazidos um a um por ISSN.

A varredura por área do ASJC não alcança revista classificada só em SOCI, ARTS
ou PSYC — e a regra da Área 02 não restringe o campo do periódico, só exige
aderência do ARTIGO. A "Education and Information Technologies" tem percentil
98 e é destino frequente da Informática na Educação brasileira; ficava fora.
"""

import csv
from pathlib import Path

import pytest

ARQUIVO = Path(__file__).resolve().parent / "data" / "periodicos_extra.csv"

pytestmark = pytest.mark.skipif(not ARQUIVO.exists(), reason="lista não versionada")


def _linhas():
    with ARQUIVO.open(encoding="utf-8") as f:
        return list(csv.DictReader(ln for ln in f if not ln.lstrip().startswith("//")))


def test_toda_linha_tem_issn_titulo_e_razao():
    for r in _linhas():
        assert (r.get("issn") or "").strip(), r
        assert (r.get("titulo") or "").strip(), r
        assert (r.get("porque") or "").strip(), f"sem razão: {r.get('titulo')}"


def test_issns_sao_validos_e_unicos():
    issns = [(r["issn"] or "").replace("-", "").strip().upper() for r in _linhas()]
    assert all(len(i) == 8 for i in issns), [i for i in issns if len(i) != 8]
    assert len(issns) == len(set(issns)), "ISSN repetido na lista"


def test_lista_ausente_nao_quebra(tmp_path):
    from qualis import elsevier

    assert elsevier.importar_issns(tmp_path / "nao-existe.csv", verbose=False) is not None
