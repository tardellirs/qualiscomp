"""Trava a decisão sobre a saturação em A3 usando os resultados oficiais da CAPES.

O Documento de Área diz apenas: "Para a avaliação qualitativa haverá uma
saturação no nível A3, ou seja, nenhum artigo será avaliado acima do nível A3
somente por meio desses critérios qualitativos." A frase admite duas leituras:

  (a) o teto limita o GANHO qualitativo (a reclassificação por CE-SBC), mas o
      h5 sozinho pode passar de A3;
  (b) o teto não se aplica ao bônus, e a frase vira letra morta — porque os
      outros caminhos qualitativos (CE-SBC sem h5, indução por tradição) já
      produzem A4-A8, sempre abaixo de A3.

O Qualis Eventos oficial do ciclo 2021-2024 (mesma comissão, mesmo método,
mesmos cortes de h5) resolve isso empiricamente: se (a) vale, eventos Top10 com
h5 baixo têm de parar em A3; se (b) valesse, iriam para A1/A2.

Estes testes falham se alguém inverter a implementação sem evidência nova.
"""

from __future__ import annotations

import pytest

from qualis import oficial, rules, sbc
from qualis.coleta import Cache, resolver

idx = rules.ESTRATOS.index


@pytest.fixture(scope="module")
def dados():
    of = oficial.carregar()
    if not of:
        pytest.skip("lista oficial ausente (data/qualis_eventos_oficial_2021_2024.xlsx)")
    cache = Cache()
    meus = {}
    for e in sbc.ler():
        r = resolver(e, cache)
        if r.h5_fonte == "scholar" and r.h5:
            meus[e.sigla.upper()] = (r.h5, r.ce_sbc)
    comuns = sorted(set(of) & set(meus))
    if len(comuns) < 100:
        pytest.skip(f"poucos eventos em comum ({len(comuns)}) — coleta incompleta")
    return of, meus, comuns


def _grupo_teste(of, meus, comuns):
    """Top10/Top20 cujo h5 sozinho daria PIOR que A3.

    Sem teto, o bônus levaria todos a A1 ou A2.
    """
    return [
        (s, *meus[s], of[s].estrato)
        for s in comuns
        if meus[s][1] in ("top10", "top20")
        and idx(rules.estrato_por_h5(meus[s][0])) > idx("A3")
    ]


def _grupo_controle(of, meus, comuns):
    """Top10/Top20 cujo h5 sozinho já daria A1 ou A2 — podem passar de A3."""
    return [
        (s, *meus[s], of[s].estrato)
        for s in comuns
        if meus[s][1] in ("top10", "top20")
        and idx(rules.estrato_por_h5(meus[s][0])) <= idx("A2")
    ]


def test_bonus_qualitativo_nao_ultrapassa_a3_na_pratica(dados):
    """A evidência: quase nenhum evento sobe acima de A3 só pelo bônus."""
    grupo = _grupo_teste(*dados)
    assert len(grupo) >= 50, "amostra pequena demais para concluir"
    acima = [g for g in grupo if idx(g[3]) < idx("A3")]
    fracao = len(acima) / len(grupo)
    assert fracao <= 0.10, (
        f"{len(acima)} de {len(grupo)} ({fracao:.0%}) passaram de A3 só pelo bônus "
        f"— isso contradiz a saturação: {[g[0] for g in acima][:8]}"
    )


def test_h5_sozinho_passa_de_a3_sem_problema(dados):
    """Controle: a comissão não é tímida — quando o h5 justifica, ela sobe.

    Sem este contraste, o teste acima poderia estar medindo só conservadorismo
    geral da comissão em vez do teto.
    """
    grupo = _grupo_controle(*dados)
    assert len(grupo) >= 50
    acima = [g for g in grupo if idx(g[3]) < idx("A3")]
    assert len(acima) / len(grupo) >= 0.60, (
        "se nem os eventos com h5 alto passam de A3, o teste anterior não "
        "distingue o teto de conservadorismo geral"
    )


def test_implementacao_segue_a_leitura_confirmada(dados):
    """h5=15 (A4) + Top10 para em A3, e h5=40 (A1) + Top10 continua A1."""
    assert rules.classificar_evento("X", h5=15, ce_sbc="top10").estrato == "A3"
    assert rules.classificar_evento("X", h5=40, ce_sbc="top10").estrato == "A1"
    sem = rules.classificar_evento("X", h5=15, ce_sbc="top10", teto_qualitativo=False)
    assert sem.estrato == "A2", "a leitura alternativa precisa continuar acessível"


def test_escala_antiga_mapeia_para_a_nova(dados):
    """B1..B4 são A5..A8: os cortes de h5 são os mesmos nos dois ciclos."""
    of, _, _ = dados
    assert oficial.ESCALA["B1"] == "A5" and oficial.ESCALA["B4"] == "A8"
    assert all(e.estrato in rules.ESTRATOS for e in of.values())


def test_concordancia_geral_com_o_oficial_e_razoavel(dados):
    """Sanidade da nossa conta: a maioria deve cair a no máximo 1 estrato do
    oficial. Divergência maior indicaria erro de regra, não de janela de h5."""
    of, meus, comuns = dados
    difs = []
    for s in comuns:
        h5, ce = meus[s]
        nosso = rules.classificar_evento(s, h5=h5, ce_sbc=ce or None).estrato
        difs.append(abs(idx(nosso) - idx(of[s].estrato)))
    perto = sum(1 for d in difs if d <= 1) / len(difs)
    assert perto >= 0.50, f"só {perto:.0%} a um estrato de distância do oficial"
