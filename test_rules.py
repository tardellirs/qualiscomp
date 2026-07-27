"""Testes das regras da Área 02, com os exemplos-limite do Documento de Área."""

import pytest

from qualis import rules as r


@pytest.mark.parametrize(
    "percentil,esperado",
    [
        (100.0, "A1"),
        (87.5, "A1"),
        (87.4, "A2"),
        (75.0, "A2"),
        (62.5, "A3"),
        (50.0, "A4"),
        (37.5, "A5"),
        (25.0, "A6"),
        (12.5, "A7"),
        (12.4, "A8"),
        (0.0, "A8"),
    ],
)
def test_cortes_de_percentil(percentil, esperado):
    assert r.estrato_por_percentil(percentil) == esperado


@pytest.mark.parametrize(
    "h5,esperado",
    [
        (100, "A1"),
        (35, "A1"),
        (34, "A2"),
        (25, "A2"),
        (20, "A3"),
        (15, "A4"),
        (12, "A5"),
        (9, "A6"),
        (6, "A7"),
        (1, "A8"),
        (0, None),
    ],
)
def test_cortes_de_h5(h5, esperado):
    assert r.estrato_por_h5(h5) == esperado


def test_percentil_invalido():
    with pytest.raises(ValueError):
        r.estrato_por_percentil(101)


def test_usa_o_maior_percentil_entre_scopus_e_wos():
    c = r.classificar_periodico("X", percentil_scopus=40.0, percentil_wos=80.0)
    assert c.estrato == "A2"
    assert "WoS" in c.motivos[0]


def test_periodico_sem_percentil_nao_e_classificavel():
    with pytest.raises(r.RegraNaoAplicavel):
        r.classificar_periodico("X")


def test_bonus_sbc_sobe_no_maximo_dois_niveis():
    c = r.classificar_periodico("SBC J", percentil_scopus=40.0, e_sbc=True, bonus_sbc=2)
    assert c.estrato == "A3"  # A5 -> A3
    with pytest.raises(ValueError):
        r.classificar_periodico("SBC J", percentil_scopus=40.0, e_sbc=True, bonus_sbc=3)


def test_bonus_sbc_satura_em_a1():
    c = r.classificar_periodico("SBC J", percentil_scopus=80.0, e_sbc=True, bonus_sbc=2)
    assert c.estrato == "A1"


def test_bonus_sbc_exige_periodico_sbc():
    with pytest.raises(ValueError):
        r.classificar_periodico("X", percentil_scopus=40.0, bonus_sbc=1)


def test_ma_pratica_editorial_descarta():
    c = r.classificar_periodico("X", percentil_scopus=95.0, ma_pratica_editorial=True)
    assert not c.considerado and c.estrato is None


def test_sem_aderencia_descarta():
    c = r.classificar_periodico("X", percentil_scopus=95.0, aderencia_computacao=False)
    assert not c.considerado


def test_evento_top10_sobe_dois_niveis_ate_o_teto_a3():
    # A4 + 2 níveis seria A2, mas o ganho qualitativo satura em A3.
    assert r.classificar_evento("E", h5=15, ce_sbc="top10").estrato == "A3"


def test_evento_top20_sobe_um_nivel():
    assert r.classificar_evento("E", h5=15, ce_sbc="top20").estrato == "A3"


def test_teto_qualitativo_nao_rebaixa_quem_o_h5_ja_levou_acima_de_a3():
    """O h5 sozinho pode passar de A3; só o ganho qualitativo é que não pode."""
    assert r.classificar_evento("E", h5=40, ce_sbc="top10").estrato == "A1"
    assert r.classificar_evento("E", h5=25, ce_sbc="top10").estrato == "A2"


def test_teto_qualitativo_desligavel():
    c = r.classificar_evento("E", h5=15, ce_sbc="top10", teto_qualitativo=False)
    assert c.estrato == "A2"


def test_teto_qualitativo_registra_o_motivo():
    c = r.classificar_evento("E", h5=15, ce_sbc="top10")
    assert any("Saturação qualitativa" in m for m in c.motivos)


def test_evento_relevante_mantem():
    assert r.classificar_evento("E", h5=15, ce_sbc="relevante").estrato == "A4"


def test_evento_sem_h5_com_ce_top():
    assert r.classificar_evento("E", h5=0, ce_sbc="top10").estrato == "A7"
    assert r.classificar_evento("E", h5=0, ce_sbc="top20").estrato == "A7"


def test_evento_sem_h5_relevante():
    assert r.classificar_evento("E", h5=0, ce_sbc="relevante").estrato == "A8"


def test_evento_sem_h5_e_sem_ce_nao_e_considerado():
    c = r.classificar_evento("E", h5=None)
    assert not c.considerado and c.estrato is None


def test_evento_fora_do_gt_nao_e_considerado():
    c = r.classificar_evento("E", h5=40, segue_gt_capes=False)
    assert not c.considerado


def test_inducao_por_tradicao():
    ok = {"promovido_por_sociedade": True}
    assert r.classificar_evento("E", h5=None, anos_tradicao_sbc=25, **ok).estrato == "A4"
    assert r.classificar_evento("E", h5=None, anos_tradicao_sbc=12, **ok).estrato == "A5"
    assert not r.classificar_evento("E", h5=None, anos_tradicao_sbc=5, **ok).considerado


def test_inducao_exige_vinculo_com_sociedade_cientifica():
    """Tempo de existência sozinho não classifica: senão um workshop qualquer
    de 22 anos, sem h5 e sem CE-SBC, viraria A4."""
    c = r.classificar_evento("E", h5=None, anos_tradicao_sbc=22)
    assert not c.considerado and c.estrato is None


def test_inducao_nao_rebaixa_quem_ja_esta_melhor():
    c = r.classificar_evento("E", h5=40, anos_tradicao_sbc=25, promovido_por_sociedade=True)
    assert c.estrato == "A1"


def test_inducao_promove_quem_esta_pior():
    c = r.classificar_evento(
        "E", h5=7, anos_tradicao_sbc=25, promovido_por_sociedade=True
    )  # h5 -> A7
    assert c.estrato == "A4"


def test_saturacao_qualitativa_em_a3():
    c = r.Classificacao(estrato="A1", veiculo="E", tipo="evento")
    assert r.aplicar_saturacao_qualitativa(c).estrato == "A3"
    c2 = r.Classificacao(estrato="A5", veiculo="E", tipo="evento")
    assert r.aplicar_saturacao_qualitativa(c2).estrato == "A5"


def test_saturacao_ignora_nao_considerado():
    c = r.Classificacao(estrato=None, veiculo="E", tipo="evento", considerado=False)
    assert r.aplicar_saturacao_qualitativa(c).estrato is None


def test_fwci_sobe_um_nivel_apenas_abaixo_de_a3():
    cs = [
        r.classificar_periodico("alto-a2", percentil_scopus=80.0),  # A2
        r.classificar_periodico("baixo-1", percentil_scopus=40.0),  # A5
        r.classificar_periodico("baixo-2", percentil_scopus=30.0),  # A6
    ]
    r.aplicar_bonus_fwci(cs, [9.0, 8.0, 1.0], fracao=0.7)  # corte = 2 artigos
    assert cs[0].estrato == "A2"  # no top-5%, mas já em A2: não recebe bônus
    assert cs[1].estrato == "A4"  # no top-5% e abaixo de A3: +1
    assert cs[2].estrato == "A6"  # fora do corte


def test_fwci_corte_sai_do_conjunto_inteiro_nao_do_grupo_abaixo_de_a3():
    """O bug original: filtrar por <A3 antes de tirar os 5% promovia artigos
    que nem estão entre os 5% maiores FWCI do conjunto."""
    cs = [
        r.classificar_periodico("a1-fwci-altissimo", percentil_scopus=95.0),
        r.classificar_periodico("a2-fwci-alto", percentil_scopus=80.0),
        r.classificar_periodico("a6-fwci-medio", percentil_scopus=30.0),
        r.classificar_periodico("a6-fwci-baixo", percentil_scopus=30.0),
    ]
    # Corte de 50% = 2 artigos, e os dois maiores FWCI são A1 e A2.
    r.aplicar_bonus_fwci(cs, [100.0, 90.0, 5.0, 1.0], fracao=0.5)
    assert [c.estrato for c in cs] == ["A1", "A2", "A6", "A6"]


def test_fwci_nao_fabrica_promocao_quando_o_corte_arredonda_para_zero():
    """max(1, ...) promovia 1 artigo mesmo quando 5% dava 0."""
    cs = [r.classificar_periodico(f"p{i}", percentil_scopus=30.0) for i in range(10)]
    r.aplicar_bonus_fwci(cs, [float(i) for i in range(10)])  # 5% de 10 = 0
    assert all(c.estrato == "A6" for c in cs)


def test_fwci_exige_um_valor_por_artigo():
    cs = [r.classificar_periodico("x", percentil_scopus=30.0)]
    with pytest.raises(ValueError):
        r.aplicar_bonus_fwci(cs, [1.0, 2.0])


def test_fwci_lista_vazia():
    assert r.aplicar_bonus_fwci([], []) == []


def test_fwci_sem_elegiveis_e_noop():
    cs = [r.classificar_periodico("x", percentil_scopus=95.0)]
    r.aplicar_bonus_fwci(cs, [99.0], fracao=1.0)
    assert cs[0].estrato == "A1"
