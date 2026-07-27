"""Testes offline do módulo de validação e do parser do Scholar."""

import json

import pytest

from qualis import coleta, scholar, validacao


def test_fixture_de_referencia_carrega():
    ref = validacao.referencia()
    assert len(ref) == 20
    assert ref["ICSE"]["h5_index"] == 98
    assert ref["ICSE"]["type"] == "conference"


def test_divergencia_calcula_delta_e_conferencia():
    d = validacao.Divergencia("ICSE", "x", 98, 98, "scholar")
    assert d.confere and d.delta == 0
    d2 = validacao.Divergencia("ICSE", "x", 95, 98, "scholar")
    assert not d2.confere and d2.delta == -3
    d3 = validacao.Divergencia("ICSE", "x", None, 98, "ausente")
    assert not d3.confere and d3.delta is None


HTML = """
<table><tbody>
<tr><td>1.</td><td><a>Brazilian Symposium on Software Engineering</a></td>
    <td><a>23</a></td><td>32</td></tr>
<tr><td>2.</td><td><a>Simp&oacute;sio Brasileiro de Banco de Dados (SBBD)</a></td>
    <td><a>4</a></td><td>7</td></tr>
</tbody></table>
"""


def test_parser_do_scholar(monkeypatch):
    class FakeResp:
        def read(self):
            return HTML.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(scholar.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    vs = scholar.buscar("qualquer")
    assert [(v.nome, v.h5, v.h5_mediana) for v in vs] == [
        ("Brazilian Symposium on Software Engineering", 23, 32),
        ("Simpósio Brasileiro de Banco de Dados (SBBD)", 4, 7),
    ]


def test_parser_detecta_bloqueio(monkeypatch):
    class FakeResp:
        def read(self):
            return b"Our systems have detected unusual traffic"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(scholar.urllib.request, "urlopen", lambda *a, **k: FakeResp())
    with pytest.raises(scholar.ScholarBloqueado):
        scholar.buscar("qualquer")


@pytest.mark.parametrize(
    "sigla,nome,esperado",
    [
        ("SBBD", "Simpósio Brasileiro de Banco de Dados (SBBD)", True),
        ("SBBD", "Brazilian Symposium on Databases (SBBD)", True),
        # Siglas de até 3 letras só valem entre parênteses.
        ("CHI", "Computer Human Interaction (CHI)", True),
        ("CHI", "Journal of preventive medicine/Yebang Uihakhoe chi", False),
        ("CHI", "Tạp chí Nghiên cứu Kinh tế", False),
        ("ICSE", "ACM/IEEE International Conference on Software Engineering", False),
    ],
)
def test_sigla_no_nome(sigla, nome, esperado):
    assert coleta._sigla_no_nome(sigla, nome) is esperado


def test_similaridade_ignora_ruido():
    a = "International Conference on Software Engineering"
    assert coleta.similaridade(a, "Conference on Software Engineering") == 1.0
    # ICSE vs ASE: parecidos demais para um limiar fixo separar.
    assert 0.5 < coleta.similaridade(
        a, "International Conference on Automated Software Engineering"
    ) < 0.8


def test_tokens_removem_acentos_e_ruido():
    assert coleta.tokens("Simpósio Brasileiro de Informática") == {
        "brasileiro",
        "informatica",
    }
