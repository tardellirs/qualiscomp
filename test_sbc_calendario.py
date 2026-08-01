"""O calendário da SBC tem registros duplicados e conflitantes. Deduplicar
errado apagaria eventos reais: BRACIS, STIL e ENIAC compartilham um site
porque acontecem juntos.
"""

from datetime import date

from qualis import sbc_calendario as sc

HOJE = date(2026, 8, 1)


def _ev(titulo, inicio, cidade="X/XX", site="https://s", fim=None, mod="2026-01-01"):
    return {
        "title": titulo,
        "start_date": f"{inicio} 09:00:00",
        "end_date": f"{fim or inicio} 18:00:00",
        "venue": {"venue": cidade},
        "website": site,
        "url": "https://sbc/e",
        "categories": [],
        "modified_utc": mod,
    }


def test_eventos_no_mesmo_site_nao_sao_fundidos():
    """BRACIS, STIL e ENIAC 2026 apontam para sbc.org.br/bracis2026 porque
    acontecem juntos. São três eventos, com estratos distintos."""
    brutos = [
        _ev("XXXVI Brazilian Conference on Intelligent Systems (BRACIS 2026)", "2026-10-19"),
        _ev("18th Brazilian Symposium in Information and Human Language Technology (STIL 2026)", "2026-10-19"),
        _ev("23° Encontro Nacional de Inteligência Artificial e Computacional (ENIAC 2026)", "2026-10-19"),
    ]
    assert {e.sigla for e in sc.interpretar(brutos, hoje=HOJE)} == {"BRACIS", "STIL", "ENIAC"}


def test_registro_repetido_fica_com_o_mais_recente():
    """O SBBD 2026 aparece duas vezes com cidades divergentes."""
    brutos = [
        _ev("41° Simpósio Brasileiro de Banco de Dados (SBBD 2026)", "2026-09-08",
            "São Paulo/SP", mod="2026-01-01"),
        _ev("XLI Simpósio Brasileiro de Banco de Dados (SBBD 2026)", "2026-09-08",
            "São Carlos/SP", mod="2026-06-01"),
    ]
    r = sc.interpretar(brutos, hoje=HOJE)
    assert len(r) == 1 and r[0].cidade == "São Carlos/SP"


def test_mesma_sigla_em_anos_diferentes_coexiste():
    brutos = [
        _ev("XXIII Simpósio Brasileiro de Sistemas de Informação (SBSI 2027)", "2027-05-17"),
        _ev("XXIV Simpósio Brasileiro de Sistemas de Informação (SBSI 2028)", "2028-05-22"),
    ]
    assert len(sc.interpretar(brutos, hoje=HOJE)) == 2


def test_evento_encerrado_some():
    assert sc.interpretar([_ev("Velho (X 2026)", "2026-07-01")], hoje=HOJE) == []


def test_sigla_do_titulo():
    assert sc.sigla_do_titulo("XLI Simpósio Brasileiro (SBBD 2026)") == "SBBD"
    assert sc.sigla_do_titulo("Conferência (CONNECTech 2026)") == "CONNECTECH"
    # Sem parêntese de sigla, cai para o título — não inventa.
    assert sc.sigla_do_titulo("NetMob 2026").startswith("NETMOB")


def test_entidades_html_do_wordpress_sao_desfeitas():
    r = sc.interpretar([_ev("Congresso &#8211; Campus (CINFO 2026)", "2026-08-26")], hoje=HOJE)
    assert "–" in r[0].titulo and "&#8211;" not in r[0].titulo


def test_cache_ausente_nao_quebra_o_build(tmp_path):
    assert sc.carregar(tmp_path / "nao-existe.json.gz") == ([], "")
