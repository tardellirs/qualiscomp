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
def test_calculo_reproduz_o_percentil_publicado_de_education():
    """Confere o CÁLCULO contra as 760 revistas de Education.

    O carregador hoje lê a coluna `JIF Percentile` quando ela existe, então
    comparar a saída dele com o publicado seria tautológico. Aqui a coluna é
    removida de propósito, forçando o caminho de reconstituição — que é o que
    vale para todo export que não a traga.

    É o caso mais difícil: categoria repartida em dois arquivos, unida por ISSN
    e ranqueada inteira.
    """
    publicado, linhas_por_arquivo = {}, []
    for caminho in sorted(jcr.DADOS.glob(jcr.PADRAO)):
        cat, linhas = jcr._ler(caminho)
        if cat != "EDUCATION & EDUCATIONAL RESEARCH":
            continue
        linhas_por_arquivo.append(linhas)
        for r in linhas:
            p = jcr._numero(r.get(jcr.COLUNA_PERCENTIL))
            if p is not None:
                publicado[(r.get("Journal name") or "").strip()] = p
    if not publicado:
        pytest.skip("export de Education sem a coluna JIF Percentile")

    # Reconstitui do zero, sem olhar a coluna de percentil.
    revistas = {}
    for linhas in linhas_por_arquivo:
        for r in linhas:
            jif = jcr._numero(r.get("2025 JIF"))
            k = tuple(
                i
                for i in (
                    jcr.normalizar_issn(r.get("ISSN")),
                    jcr.normalizar_issn(r.get("eISSN")),
                )
                if i
            )
            if jif is not None and k:
                revistas[k] = (r, jif)
    validas = sorted(revistas.values(), key=lambda rj: -rj[1])
    n = len(validas)
    pos = jcr._posicoes([j for _, j in validas])
    calculado = {
        (r.get("Journal name") or "").strip(): jcr._uma_casa((n - p + 0.5) / n * 100)
        for (r, _), p in zip(validas, pos)
    }
    divergem = {
        t: (p, calculado[t])
        for t, p in publicado.items()
        if t in calculado and abs(calculado[t] - p) >= 0.05
    }
    assert n == len(publicado), f"N calculado {n} != {len(publicado)} publicados"
    assert not divergem, f"{len(divergem)} de {len(publicado)} divergem"


def test_export_por_pais_usa_a_coluna_e_nao_ranqueia(tmp_path):
    """O export de revistas brasileiras filtra por país, não por categoria.

    São 440 linhas de 122 categorias diferentes. Ranqueá-las juntas daria
    percentil sem sentido — mas o arquivo traz `JIF Percentile`, então o valor
    é lido, com a categoria de cada linha.
    """
    p = tmp_path / "x_JCR_JournalResults_br.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Selected Country/region: BRAZIL Selected Editions: SCIE"])
        w.writerow([])
        w.writerow(["Journal name", "ISSN", "eISSN", "Category", "2025 JIF",
                    jcr.COLUNA_PERCENTIL])
        w.writerow(["A", "1111-1111", "N/A", "HISTORY", "0.4", "12.5"])
        w.writerow(["B", "2222-2222", "N/A", "LAW", "0.9", "88.0"])
    base = jcr.carregar(tmp_path)
    assert jcr.buscar(["1111-1111"], base).percentil == 12.5
    assert jcr.buscar(["1111-1111"], base).categoria == "HISTORY"
    assert jcr.buscar(["2222-2222"], base).percentil == 88.0


def test_export_sem_categoria_e_sem_percentil_e_recusado(tmp_path, capsys):
    """Sem categoria não dá para ranquear, e sem a coluna não dá para ler."""
    p = tmp_path / "x_JCR_JournalResults_br.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Selected Country/region: BRAZIL Selected Editions: SCIE"])
        w.writerow([])
        w.writerow(["Journal name", "ISSN", "eISSN", "Category", "2025 JIF"])
        w.writerow(["A", "1111-1111", "N/A", "HISTORY", "0.4"])
    assert jcr.carregar(tmp_path) == {}
    assert "ignorado" in capsys.readouterr().out


def test_teto_conta_linhas_exportadas_nao_as_com_jif(tmp_path, capsys):
    """ECONOMICS veio com 601 linhas e 599 com JIF. Contar as 599 deixava
    passar uma categoria cortada em 600 — e aí o N do ranking sai errado."""
    p = tmp_path / "x_JCR_JournalResults_econ.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Selected Categories: CORTADA Selected Editions: SCIE"])
        w.writerow([])
        w.writerow(["Journal name", "ISSN", "eISSN", "2025 JIF"])
        for i in range(jcr.TETO_DO_EXPORT - 1):
            w.writerow([f"R{i}", f"{1000 + i:04d}-0000", "N/A", str(600 - i)])
        w.writerow(["SemJIF", "9999-0000", "N/A", "N/A"])  # 600ª linha, sem JIF
    assert jcr.carregar(tmp_path) == {}
    assert "no teto" in capsys.readouterr().out


def test_com_a_coluna_de_percentil_o_teto_nao_importa(tmp_path):
    """Lendo o percentil publicado, não precisamos da categoria inteira — cada
    revista já traz o seu. É por isso que vale pedir a coluna no JCR."""
    p = tmp_path / "x_JCR_JournalResults_big.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Selected Categories: GRANDE Selected Editions: SCIE"])
        w.writerow([])
        w.writerow(["Journal name", "ISSN", "eISSN", "2025 JIF",
                    jcr.COLUNA_PERCENTIL])
        for i in range(jcr.TETO_DO_EXPORT + 1):
            w.writerow([f"R{i}", f"{1000 + i:04d}-0000", "N/A", "1.0", "42.0"])
    base = jcr.carregar(tmp_path)
    assert base and jcr.buscar(["1000-0000"], base).percentil == 42.0
