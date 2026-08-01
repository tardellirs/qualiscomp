"""Escolher a entrada errada do Google Scholar publica estrato errado.

Dois defeitos motivaram estes testes, ambos inflando estrato:

1. Entre os candidatos, vencia o de MAIOR h5 — mesmo quando o evento já tinha
   entrada confirmada pela própria sigla. O SBIE perdia a sua (h5=15) para o
   ICCE (h5=16), que casou por uma palavra genérica.
2. A planilha da SBC registra nomes alternativos que pertencem a OUTRO evento
   de mesma sigla. O SoCC (System-on-Chip) trazia o Symposium on Cloud
   Computing, com h5=39, e saía A1.
"""

from qualis import coleta, sbc, scholar


class CacheFalso:
    def __init__(self, por_consulta):
        self.por_consulta = por_consulta

    def get(self, q):
        return self.por_consulta.get(q, [])


def _ev(sigla, nome, alternativos=()):
    return sbc.EventoSBC(
        sigla=sigla, nome=nome, classificacao="relevante", h5_sbc=None,
        ces=[], nomes_alternativos=list(alternativos),
    )


def test_entrada_confirmada_pela_sigla_vence_casamento_parcial():
    """O caso SBIE: a entrada própria tem h5 menor e ainda assim é a certa."""
    ev = _ev("SBIE", "Simpósio Brasileiro de Informática na Educação",
             ["Brazilian Symposium on Computers in Education"])
    cache = CacheFalso({
        q: [
            scholar.Venue("Simpósio Brasileiro de Informática na Educação (SBIE)", 15, 0),
            scholar.Venue("International Conference on Computers in Education", 16, 0),
        ]
        for q in coleta._consultas(ev)
    })
    assert coleta.resolver(ev, cache).h5 == 15


def test_nome_em_outro_idioma_do_mesmo_evento_continua_valendo():
    """O caso IHC: a entrada em inglês é o MESMO evento e tem h5 maior.

    Sem isto, a correção acima cortaria o h5 do IHC de 16 para 5.
    """
    ev = _ev("IHC", "Simpósio Brasileiro sobre Fatores Humanos em Sistemas Computacionais",
             ["Brazilian Symposium on Human Factors in Computing Systems"])
    cache = CacheFalso({
        q: [
            scholar.Venue("Simpósio Brasileiro sobre Fatores Humanos em Sistemas Computacionais (IHC)", 5, 0),
            scholar.Venue("Brazilian Symposium on Human Factors in Computing Systems", 16, 0),
        ]
        for q in coleta._consultas(ev)
    })
    assert coleta.resolver(ev, cache).h5 == 16


def test_sem_entrada_por_sigla_o_maior_h5_ainda_vale():
    """Sem confirmação por sigla, o comportamento antigo continua: entre nomes
    que casam igualmente bem, fica o maior h5 — são o mesmo evento partido em
    duas entradas do Scholar."""
    ev = _ev("XPTO", "International Conference on Something Specific",
             ["Conferencia Internacional sobre Something Specific"])
    cache = CacheFalso({
        q: [
            scholar.Venue("International Conference on Something Specific", 30, 0),
            scholar.Venue("Conferencia Internacional sobre Something Specific", 40, 0),
        ]
        for q in coleta._consultas(ev)
    })
    assert coleta.resolver(ev, cache).h5 == 40


def test_apelido_recusado_sai_das_consultas():
    recusados = sbc.apelidos_recusados()
    assert ("SOCC", "acm symposium on cloud computing") in recusados
    porsigla = {e.sigla.upper(): e for e in sbc.ler()}
    if "SOCC" in porsigla:
        assert "ACM Symposium on Cloud Computing" not in porsigla["SOCC"].nomes_alternativos


def test_arquivo_de_recusados_ausente_nao_quebra(tmp_path):
    assert sbc.apelidos_recusados(tmp_path / "nao-existe.csv") == set()
