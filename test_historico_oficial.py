"""O histórico é dado oficial da CAPES e aparece ao lado da nossa estimativa.
Confundir os dois — ou traduzir escala antiga para a nova — seria atribuir à
comissão uma classificação que ela não publicou.
"""

import csv

import pytest

from qualis import historico_oficial as h


def _planilhas(tmp_path, linhas_por_ciclo):
    """Escreve os TSV disfarçados de .xls, como a Sucupira entrega."""
    for ciclo, linhas in linhas_por_ciclo.items():
        p = tmp_path / f"classificacoes_avaliacao{ciclo}.xls"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t", quotechar='"')
            w.writerow(["ISSN", "Título", "Área de Avaliação", "Estrato"])
            w.writerows(linhas)
    return tmp_path


def test_le_ciclos_em_ordem_cronologica(tmp_path):
    b = h.carregar(_planilhas(tmp_path, {
        "2021-2024": [["1234-5678", "R", "COMPUTAÇÃO", "A2"]],
        "2010-2012": [["1234-5678", "R", "CIÊNCIA DA COMPUTAÇÃO", "B1"]],
    }))
    assert h.buscar(["12345678"], b) == [["2010-2012", "B1"], ["2021-2024", "A2"]]


def test_ignora_outras_areas(tmp_path):
    """A planilha traz as ~50 áreas; só a Computação classifica para nós."""
    b = h.carregar(_planilhas(tmp_path, {
        "2021-2024": [
            ["1234-5678", "R", "MEDICINA I", "A1"],
            ["8765-4321", "S", "COMPUTAÇÃO", "B2"],
        ],
    }))
    assert h.buscar(["1234-5678"], b) == []
    assert h.buscar(["8765-4321"], b) == [["2021-2024", "B2"]]


def test_impresso_e_eletronico_no_mesmo_ciclo_fica_o_melhor(tmp_path):
    b = h.carregar(_planilhas(tmp_path, {
        "2017-2020": [
            ["1111-1111", "R (impresso)", "CIÊNCIA DA COMPUTAÇÃO", "B1"],
            ["2222-2222", "R (online)", "CIÊNCIA DA COMPUTAÇÃO", "A3"],
        ],
    }))
    assert h.buscar(["1111-1111", "2222-2222"], b) == [["2017-2020", "A3"]]


@pytest.mark.parametrize(
    "melhor,pior", [("A1", "A2"), ("A2", "B1"), ("B4", "B5"), ("B5", "C"), ("A4", "B1")]
)
def test_ordem_dos_estratos_antigos(melhor, pior):
    assert h._ordem(melhor) < h._ordem(pior)


def test_sem_planilhas_nao_quebra_o_build(tmp_path):
    b = h.carregar(tmp_path)
    assert b == {} and h.buscar(["1234-5678"], b) == []


def test_nao_traduz_escala_antiga():
    """B5 e C não existem em 2025-2028; devem sair como vieram.

    Converter "B1 de 2013" para algum A-de-2025 inventaria uma equivalência
    que a CAPES nunca publicou — as escalas mudaram duas vezes.
    """
    fonte = {"12345678": {"2013-2016": "B5", "2021-2024": "C"}}
    assert h.buscar(["1234-5678"], fonte) == [["2013-2016", "B5"], ["2021-2024", "C"]]
