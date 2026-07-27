"""Testes do parser dos exports da tela Scopus Sources."""

import pytest

from qualis import scopus_export as se


def _fonte(titulo, percentil=50.0, editora=None):
    return se.Fonte(
        titulo=titulo,
        percentil=percentil,
        citescore=None,
        rank=None,
        total=None,
        categoria=None,
        snip=None,
        sjr=None,
        editora=editora,
    )


@pytest.mark.parametrize(
    "celula,esperado",
    [
        ("99.0%\n1/1022\nComputer Science Applications", (99.0, 1, 1022, "Computer Science Applications")),
        ("49.0%\n124/245\nHardware and Architecture", (49.0, 124, 245, "Hardware and Architecture")),
        ("7%\n900/1000\nX", (7.0, 900, 1000, "X")),
        ("", (None, None, None, None)),
        (None, (None, None, None, None)),
        ("None", (None, None, None, None)),
    ],
)
def test_parse_da_celula_de_percentil(celula, esperado):
    assert se._parse_percentil(celula) == esperado


def test_parse_sem_categoria():
    # Só duas linhas: não há categoria a extrair.
    assert se._parse_percentil("88.0%\n10/100") == (88.0, 10, 100, None)


def test_normalizar():
    assert se.normalizar("  ACM  Trans. on Software-Engineering ") == (
        "acm trans on software engineering"
    )


def test_busca_exata_tem_prioridade():
    bd = {se.normalizar("Computer"): _fonte("Computer", 64.0)}
    assert se.buscar("computer", bd)[0].titulo == "Computer"


def test_busca_nao_casa_titulo_curto_contido_na_consulta():
    """O bug original: 'Journal of the Brazilian Computer Society' casava com
    a revista 'Computer' porque o título estava contido na consulta."""
    bd = {se.normalizar("Computer"): _fonte("Computer", 64.0)}
    assert se.buscar("Journal of the Brazilian Computer Society", bd) == []


def test_busca_por_substring_da_consulta_no_titulo():
    bd = {
        se.normalizar("IEEE Transactions on Software Engineering"): _fonte(
            "IEEE Transactions on Software Engineering", 92.0
        )
    }
    assert se.buscar("Transactions on Software Engineering", bd)[0].percentil == 92.0


def test_busca_por_tokens_ignora_palavras_genericas():
    bd = {
        se.normalizar("Empirical Software Engineering"): _fonte(
            "Empirical Software Engineering", 86.0
        )
    }
    # "journal of" é genérico; "empirical"/"software"/"engineering" sustentam o match.
    assert se.buscar("Journal of Empirical Software Engineering", bd)[0].percentil == 86.0


def test_busca_vazia():
    assert se.buscar("   ", {}) == []


@pytest.mark.parametrize(
    "titulo,esperado",
    [
        ("Brazilian Symposium on Computing System Engineering, SBESC", True),
        ("ICSE Workshop on Software Engineering", True),
        ("Lecture Notes in Computer Science", True),
        ("Journal of Machine Learning Research", False),
        ("ACM Computing Surveys", False),
        # Periódicos com nome de evento: são revistas, e o PACMPL é onde saem
        # POPL, OOPSLA, ICFP e PLDI — bloqueá-lo inviabilizaria a área toda.
        ("Proceedings of the ACM on Programming Languages", False),
        ("Proceedings of the IEEE", False),
        ("Proceedings of the VLDB Endowment", False),
    ],
)
def test_deteccao_de_evento(titulo, esperado):
    assert _fonte(titulo).parece_evento is esperado


@pytest.mark.parametrize(
    "editora,esperado",
    [
        ("Sociedade Brasileira de Computacao", True),
        # Grafia que o Scopus realmente usa para o JBCS.
        ("Brazilian Computing Society", True),
        ("Brazilian Computer Society", True),
        ("Springer", False),
        ("Associacao Brasileira de Engenharia de Producao", False),
        (None, False),
    ],
)
def test_deteccao_de_sbc(editora, esperado):
    assert _fonte("X", editora=editora).e_sbc is esperado
