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


def _cache(ev, *venues):
    return CacheFalso({q: list(venues) for q in coleta._consultas(ev)})


def test_revista_nao_vence_conferencia():
    """O Scholar Metrics mistura revista e conferência na mesma lista, e
    revista de área grande tem h5 muito maior. 'Information Fusion' (143)
    engolia a 'International Conference on Information Fusion' (23)."""
    ev = _ev("FUSION", "International Conference on Information Fusion")
    r = coleta.resolver(ev, _cache(
        ev,
        scholar.Venue("Information Fusion", 143, 0),
        scholar.Venue("International Conference on Information Fusion", 23, 0),
    ))
    assert r.h5 == 23


def test_sem_candidato_de_evento_fica_sem_h5():
    """Melhor sem h5 do que com o h5 de outro veículo: o CASES (compiladores
    para embarcados) saía A1 com o h5 do 'World Journal of Clinical Cases'."""
    ev = _ev("CASES", "International Conference on Compilers, Architecture and Synthesis")
    r = coleta.resolver(ev, _cache(ev, scholar.Venue("World Journal of Clinical Cases", 48, 0)))
    assert r.h5 is None and r.h5_fonte == "nenhum"


def test_sigla_em_minuscula_nao_confirma_o_evento():
    """'Cases' no nome de uma revista não é a sigla CASES do evento."""
    assert not coleta._sigla_no_nome("CASES", "World Journal of Clinical Cases")
    assert coleta._sigla_no_nome("CENTERIS", "CENTERIS/ProjMAN/HCist")
    assert coleta._sigla_no_nome("SBBD", "Brazilian Symposium on Databases (SBBD)")


def test_serie_pacm_conta_como_revista():
    """'Proceedings of the ACM on ...' é periódico, apesar da palavra."""
    ev = _ev("HCII", "International Conference on Human-Computer Interaction")
    r = coleta.resolver(ev, _cache(
        ev,
        scholar.Venue("Proceedings of the ACM on Human-Computer Interaction", 88, 0),
        scholar.Venue("International Conference on Human-Computer Interaction", 14, 0),
    ))
    assert r.h5 == 14


def test_semelhanca_desempata_antes_do_h5():
    """Duas conferências da mesma área: só o nome distingue. O ECCV (262)
    vencia o ICCV (256) por h5."""
    ev = _ev("ICCV", "IEEE International Conference on Computer Vision",
             ["IEEE/CVF International Conference on Computer Vision"])
    r = coleta.resolver(ev, _cache(
        ev,
        scholar.Venue("European Conference on Computer Vision", 262, 0),
        scholar.Venue("IEEE/CVF International Conference on Computer Vision", 256, 0),
    ))
    assert r.h5 == 256


def test_ano_de_fundacao_vence_contagem_de_edicoes(tmp_path, monkeypatch):
    """Edições é piso, e o piso erra pela metade em evento bienal.

    O SBCM tem 18 edições registradas e existe desde 1994: 32 anos de tradição,
    que é a diferença entre A5 e A4 no critério de indução.
    """
    from datetime import date

    csv = tmp_path / "tradicao_eventos.csv"
    csv.write_text("sigla,desde,fonte\nSBCM,1994,https://exemplo\n", encoding="utf-8")
    monkeypatch.setattr(sbc, "TRADICAO", csv)
    evs = sbc.eventos_da_sbc()
    if "SBCM" not in evs:
        import pytest as _p
        _p.skip("planilha da SBC não está em data/")
    assert evs["SBCM"].ano_primeira == 1994
    assert evs["SBCM"].anos_de_tradicao == date.today().year - 1994
