"""Prazo de submissão é a única informação deste site com consequência
imediata e irreversível: quem confia num prazo errado perde a submissão.
Estes testes existem para que o calendário erre para o lado seguro.
"""

from datetime import date

from qualis import calendario

CABECALHO = "sigla,nome,edicao,inicio,fim,cidade,prazo,url,conferido,observacao\n"
HOJE = date(2026, 8, 1)


def _csv(tmp_path, *linhas):
    p = tmp_path / "calendario_eventos.csv"
    p.write_text(CABECALHO + "".join(l + "\n" for l in linhas), encoding="utf-8")
    return p


def test_edicao_ja_encerrada_some(tmp_path):
    p = _csv(
        tmp_path,
        "VELHO,Antigo,10,2026-07-01,2026-07-03,Recife,,https://x,2026-06-01,",
        "NOVO,Futuro,3,2026-09-10,2026-09-12,Natal,,https://y,2026-06-01,",
    )
    assert [e.sigla for e in calendario.carregar(p, hoje=HOJE)] == ["NOVO"]


def test_evento_em_curso_continua_aparecendo(tmp_path):
    """Começou ontem e termina amanhã: ainda é 'próximo evento' para quem vai."""
    p = _csv(tmp_path, "AGORA,Em curso,1,2026-07-31,2026-08-02,Belém,,https://x,,")
    assert len(calendario.carregar(p, hoje=HOJE)) == 1


def test_sem_data_de_inicio_nao_entra(tmp_path):
    """'Data a confirmar' ocupa espaço sem informar. Fora."""
    p = _csv(
        tmp_path,
        "SEMDATA,Indefinido,5,,,,2026-09-01,https://x,,",
        "OK,Definido,5,2026-10-01,,Curitiba,,https://y,,",
    )
    assert [e.sigla for e in calendario.carregar(p, hoje=HOJE)] == ["OK"]


def test_data_malformada_nao_quebra_o_build(tmp_path):
    p = _csv(tmp_path, "RUIM,Torto,1,31/12/2026,,Recife,,https://x,,")
    assert calendario.carregar(p, hoje=HOJE) == []


def test_ordena_pela_data_mais_proxima(tmp_path):
    p = _csv(
        tmp_path,
        "C,Terceiro,1,2026-12-01,,X,,https://c,,",
        "A,Primeiro,1,2026-08-15,,X,,https://a,,",
        "B,Segundo,1,2026-10-05,,X,,https://b,,",
    )
    assert [e.sigla for e in calendario.carregar(p, hoje=HOJE)] == ["A", "B", "C"]


def test_prazo_aberto_e_contagem(tmp_path):
    p = _csv(tmp_path, "X,Evento,1,2026-11-01,,Recife,2026-08-20,https://x,,")
    e = calendario.carregar(p, hoje=HOJE)[0]
    assert e.prazo == date(2026, 8, 20)
    assert e.dias_ate_o_prazo == (date(2026, 8, 20) - date.today()).days


def test_sem_prazo_nao_finge_que_tem(tmp_path):
    """Prazo em branco é 'não sabemos', nunca 'já fechou'."""
    p = _csv(tmp_path, "X,Evento,1,2026-11-01,,Recife,,https://x,,")
    e = calendario.carregar(p, hoje=HOJE)[0]
    assert e.prazo is None and e.dias_ate_o_prazo is None and not e.prazo_aberto


def test_arquivo_ausente_nao_quebra_o_build(tmp_path):
    assert calendario.carregar(tmp_path / "nao-existe.csv") == []


def test_comentarios_sao_ignorados(tmp_path):
    p = tmp_path / "calendario_eventos.csv"
    p.write_text(
        "// fonte: conferido à mão, ver URL de cada linha\n"
        + CABECALHO
        + "X,Evento,1,2026-11-01,,Recife,,https://x,,\n",
        encoding="utf-8",
    )
    assert len(calendario.carregar(p, hoje=HOJE)) == 1


def test_prazo_urgente_e_encerrado_se_distinguem(tmp_path):
    """A página pinta prazo de <=7 dias de outra cor; encerrado é cinza.
    A distinção depende só de `dias_ate_o_prazo`, então ela é fixada aqui."""
    from datetime import timedelta

    hoje = date.today()
    p = _csv(
        tmp_path,
        f"PERTO,Urgente,1,2026-12-01,,X,{hoje + timedelta(days=3)},https://a,,",
        f"LONGE,Tranquilo,1,2026-12-01,,X,{hoje + timedelta(days=60)},https://b,,",
        f"FIM,Encerrado,1,2026-12-01,,X,{hoje - timedelta(days=1)},https://c,,",
    )
    por = {e.sigla: e for e in calendario.carregar(p, hoje=date(2026, 1, 1))}
    assert por["PERTO"].dias_ate_o_prazo == 3 and por["PERTO"].prazo_aberto
    assert por["LONGE"].dias_ate_o_prazo == 60 and por["LONGE"].prazo_aberto
    assert por["FIM"].dias_ate_o_prazo == -1 and not por["FIM"].prazo_aberto
