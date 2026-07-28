"""O percentil do WoS é calculado, não lido — então tem que ser conferível.

O export padrão do JCR traz JIF e quartil, mas não o JIF Percentile. Nós o
reconstituímos pela posição na categoria. Estes testes fixam essa reconstituição
contra valores que a própria Clarivate publica, porque um erro aqui muda estrato
de gente de verdade.
"""

import csv
from pathlib import Path

import pytest

from qualis import jcr

# JIF Percentile publicado pela Clarivate (JCR 2025, MULTIDISCIPLINARY
# SCIENCES). iScience e Annals of the NYAS empatam em JIF 4,5 e recebem o
# MESMO percentil — é o caso que fixa o tratamento de empates.
PUBLICADO = {
    "NATURE": 99.6,
    "SCIENCE": 98.2,
    "Science Bulletin": 96.1,
    "Nature Communications": 94.6,
    "Science Advances": 91.8,
    "PROCEEDINGS OF THE NATIONAL ACADEMY OF SCIENCES OF THE UNITED STATES OF AMERICA": 90.4,  # noqa: E501
    "Scientific Data": 88.2,
    "Scientific Reports": 85.4,
    "iScience": 83.2,
    "ANNALS OF THE NEW YORK ACADEMY OF SCIENCES": 83.2,
    "PHILOSOPHICAL TRANSACTIONS OF THE ROYAL SOCIETY A-MATHEMATICAL PHYSICAL AND ENGINEERING SCIENCES": 77.5,  # noqa: E501
    "PeerJ": 68.9,
    "PLoS One": 66.1,
    "PROCEEDINGS OF THE ROYAL SOCIETY A-MATHEMATICAL PHYSICAL AND ENGINEERING SCIENCES": 65.4,  # noqa: E501
    "Symmetry-Basel": 57.5,
    "Jove-Journal of Visualized Experiments": 41.1,
}

CATEGORIA = "MULTIDISCIPLINARY SCIENCES"


def _percentis_da_categoria() -> dict[str, float]:
    for caminho in sorted(jcr.DADOS.glob(jcr.PADRAO)):
        cat, linhas = jcr._ler(caminho)
        if cat != CATEGORIA:
            continue
        val = [(r, jcr._numero(r.get("2025 JIF"))) for r in linhas]
        val = [(r, j) for r, j in val if j is not None]
        val.sort(key=lambda x: -x[1])
        n = len(val)
        pos = jcr._posicoes([j for _, j in val])
        return {
            (r.get("Journal name") or "").strip(): round((n - p + 0.5) / n * 100, 1)
            for (r, _), p in zip(val, pos)
        }
    return {}


tem_dados = pytest.mark.skipif(
    not any(jcr.DADOS.glob(jcr.PADRAO)),
    reason="exports do JCR não estão em data/ (licenciados, ver README)",
)


@tem_dados
@pytest.mark.parametrize("revista,esperado", sorted(PUBLICADO.items()))
def test_percentil_reproduz_o_publicado(revista, esperado):
    calculado = _percentis_da_categoria().get(revista)
    assert calculado is not None, f"{revista} sumiu do export"
    assert calculado == esperado


@tem_dados
def test_empate_recebe_o_mesmo_percentil():
    p = _percentis_da_categoria()
    assert p["iScience"] == p["ANNALS OF THE NEW YORK ACADEMY OF SCIENCES"]


def test_posicoes_empatadas_usam_a_menor():
    assert jcr._posicoes([9.0, 5.0, 5.0, 5.0, 2.0]) == [1, 2, 2, 2, 5]


def test_numero_aceita_milhar_com_virgula_e_recusa_na():
    assert jcr._numero("123,304") == 123304.0
    assert jcr._numero("20.4") == 20.4
    assert jcr._numero("N/A") is None and jcr._numero("") is None


def test_issn_invalido_e_descartado():
    assert jcr.normalizar_issn("0162-8828") == "01628828"
    assert jcr.normalizar_issn("N/A") == ""
    assert jcr.normalizar_issn("1234") == ""


def test_maior_percentil_entre_categorias(tmp_path):
    """A mesma revista em duas categorias fica com o melhor percentil — é o
    que a coluna "Highest percentile" do Scopus faz, e o que a regra pede."""

    def escrever(nome, categoria, linhas):
        p = tmp_path / f"x_JCR_JournalResults_{nome}.csv"
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow([f"Selected Categories: {categoria} Selected Editions: SCIE"])
            w.writerow([])
            w.writerow(["Journal name", "ISSN", "eISSN", "2025 JIF"])
            w.writerows(linhas)

    # Na categoria A é a melhor de 2; na B é a pior de 2.
    escrever("a", "CAT A", [["R", "1234-5678", "N/A", "9.0"], ["Z", "1111-1111", "N/A", "1.0"]])
    escrever("b", "CAT B", [["Y", "2222-2222", "N/A", "9.0"], ["R", "1234-5678", "N/A", "1.0"]])
    r = jcr.buscar(["1234-5678"], jcr.carregar(tmp_path))
    assert r.categoria == "CAT A" and r.percentil == 75.0


def test_pasta_vazia_nao_quebra_o_build(tmp_path):
    assert jcr.carregar(tmp_path) == {}
