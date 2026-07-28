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


def test_categoria_no_teto_do_export_e_recusada(tmp_path, capsys):
    """600 linhas é o limite da tela do JCR: a categoria veio cortada.

    Com N errado, o percentil de TODAS as revistas da categoria sai errado.
    Publicar número torto é pior que não ter o dado — foi o que aconteceu com
    EDUCATION & EDUCATIONAL RESEARCH, que exportou exatamente 600.
    """
    p = tmp_path / "x_JCR_JournalResults_edu.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Selected Categories: CHEIA Selected Editions: SCIE"])
        w.writerow([])
        w.writerow(["Journal name", "ISSN", "eISSN", "2025 JIF"])
        for i in range(jcr.TETO_DO_EXPORT):
            w.writerow([f"R{i}", f"{1000 + i:04d}-0000", "N/A", str(600 - i)])
    assert jcr.carregar(tmp_path) == {}
    assert "no teto" in capsys.readouterr().out


def _parte(pasta, nome, categoria, linhas):
    p = pasta / f"x_JCR_JournalResults_{nome}.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"Selected Categories: {categoria} Selected Editions: SCIE"])
        w.writerow([])
        w.writerow(["Journal name", "ISSN", "eISSN", "2025 JIF"])
        w.writerows(linhas)


def test_categoria_partida_e_ranqueada_inteira(tmp_path):
    """Categoria grande sai em partes (por faixa de JIF) e tem que ser unida.

    Ranquear cada parte isolada daria N errado nas duas: a pior revista da
    metade de baixo apareceria como topo de uma categoria que não existe.
    """
    _parte(tmp_path, "alta", "CAT", [["A", "1111-1111", "N/A", "9.0"],
                                     ["B", "2222-2222", "N/A", "5.0"]])
    _parte(tmp_path, "baixa", "CAT", [["C", "3333-3333", "N/A", "1.0"],
                                      ["D", "4444-4444", "N/A", "0.5"]])
    base = jcr.carregar(tmp_path)
    assert jcr.buscar(["1111-1111"], base).total == 4          # N da categoria inteira
    assert jcr.buscar(["1111-1111"], base).percentil == 87.5   # 1ª de 4
    assert jcr.buscar(["3333-3333"], base).percentil == 37.5   # 3ª de 4, não 1ª de 2


def test_revista_repetida_entre_as_partes_conta_uma_vez(tmp_path):
    """As partes se sobrepõem nas bordas — contar duas vezes inflaria N."""
    _parte(tmp_path, "a", "CAT", [["A", "1111-1111", "N/A", "9.0"],
                                  ["B", "2222-2222", "N/A", "5.0"]])
    _parte(tmp_path, "b", "CAT", [["B", "2222-2222", "N/A", "5.0"],
                                  ["C", "3333-3333", "N/A", "1.0"]])
    assert jcr.buscar(["1111-1111"], jcr.carregar(tmp_path)).total == 3


def test_jif_abaixo_de_zero_ponto_um_conta_no_ranking():
    """O JCR grafa impacto muito baixo como "<0.1" — são revistas com JIF.

    Descartá-las encolhia N e baixava o percentil de TODA a categoria. Em
    Education eram 16 de 760, e o erro dava um ponto percentual em todas.
    """
    assert jcr._numero("<0.1") == 0.0
    assert jcr._numero("N/A") is None


def test_arredonda_meia_para_cima():
    """O round() do Python arredonda meia para o par e divergia do JCR em 39
    das 760 revistas de Education. Meia para cima acerta as 760."""
    assert jcr._uma_casa(2.25) == 2.3
    assert jcr._uma_casa(2.35) == 2.4
    assert round(2.25, 1) == 2.2  # o que NÃO queremos


@tem_dados
def test_education_reproduz_o_percentil_publicado():
    """Education vem em duas partes e traz a coluna JIF Percentile, o que
    permite conferir o caso difícil: categoria repartida, unida e ranqueada.

    Confere as 760 de uma vez, em vez de uma amostra."""
    publicado, calculado = {}, {}
    for caminho in sorted(jcr.DADOS.glob(jcr.PADRAO)):
        cat, linhas = jcr._ler(caminho)
        if cat != "EDUCATION & EDUCATIONAL RESEARCH":
            continue
        for r in linhas:
            p = jcr._numero(r.get("JIF Percentile"))
            if p is not None:
                publicado[(r.get("Journal name") or "").strip()] = p
    if not publicado:
        pytest.skip("export de Education sem a coluna JIF Percentile")
    for r in jcr.carregar().values():
        if r.categoria == "EDUCATION & EDUCATIONAL RESEARCH":
            calculado[r.titulo] = r.percentil
    divergem = {
        t: (p, calculado[t])
        for t, p in publicado.items()
        if t in calculado and abs(calculado[t] - p) >= 0.05
    }
    assert not divergem, f"{len(divergem)} de {len(publicado)} divergem: {list(divergem.items())[:5]}"  # noqa: E501
