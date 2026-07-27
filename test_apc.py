"""O casamento de APC é por ISSN, e um falso positivo aqui custa caro:
alguém contaria com isenção que não existe e receberia a fatura da editora.
"""

import sqlite3

from qualis import apc


def _base(tmp_path, linhas):
    p = tmp_path / "acordos.db"
    con = sqlite3.connect(p)
    con.execute(
        "create table journals (title, publisher, issn, eissn, "
        "open_access_type, license, url)"
    )
    con.executemany("insert into journals values (?,?,?,?,?,?,?)", linhas)
    con.commit()
    con.close()
    return p


def test_casa_pelos_dois_issns(tmp_path):
    b = _base(tmp_path, [("Revista", "Wiley", "1234-5678", "8765-4321", "hybrid", "CC BY", "u")])
    a = apc.carregar(b)
    assert apc.buscar(["12345678"], a).editora == "Wiley"
    assert apc.buscar(["8765-4321"], a).editora == "Wiley"


def test_issn_com_x_final(tmp_path):
    b = _base(tmp_path, [("R", "Elsevier", "0022-247x", "", "", "", "")])
    assert apc.buscar(["0022247X"], apc.carregar(b)) is not None


def test_sem_acordo_devolve_nada(tmp_path):
    b = _base(tmp_path, [("R", "Wiley", "1234-5678", "", "", "", "")])
    a = apc.carregar(b)
    assert apc.buscar(["9999-9999"], a) is None
    assert apc.buscar([], a) is None


def test_issn_truncado_nao_casa(tmp_path):
    """Um ISSN incompleto casaria com muita coisa se virasse prefixo."""
    b = _base(tmp_path, [("R", "Wiley", "1234-5678", "", "", "", "")])
    assert apc.buscar(["1234"], apc.carregar(b)) is None


def test_base_ausente_nao_quebra_o_build(tmp_path):
    """A base vive noutro projeto; sem ela o site continua gerando."""
    assert apc.carregar(tmp_path / "nao-existe.db") == {}
