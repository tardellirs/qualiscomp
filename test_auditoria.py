"""Invariantes do catálogo publicado.

Cada um destes nasceu de um defeito encontrado numa varredura geral:
941 revistas ativas marcadas como descontinuadas, e o mesmo evento listado
duas vezes com estratos diferentes.
"""

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parent / "site" / "dist" / "dados" / "v"

pytestmark = pytest.mark.skipif(not DIST.exists(), reason="rode site/build.py antes")


def _ler(prefixo):
    return [json.loads(f.read_text(encoding="utf-8")) for f in DIST.glob(f"{prefixo}-*.json")]


def _chave(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]", "", t)


def test_nenhum_evento_listado_duas_vezes():
    por = defaultdict(list)
    for d in _ler("e"):
        por[_chave(d["nome"])].append(d.get("sigla") or d["slug"])
    dup = {k: v for k, v in por.items() if len(v) > 1}
    assert not dup, f"{len(dup)} eventos repetidos: {list(dup.values())[:4]}"


def test_descontinuado_nao_tem_percentil_recente():
    """`coverageEndYear` do Scopus marca o fim do primeiro TRECHO de cobertura,
    não o da revista — a Science aparece com fim em 1881. Revista com percentil
    nos últimos anos está viva, diga o que disser aquele campo."""
    vivos = [
        d["nome"]
        for d in _ler("p")
        if d.get("descontinuada")
        and any(a >= 2024 for a, *_ in (d.get("historico") or []))
    ]
    assert not vivos, f"{len(vivos)} marcados como mortos mas com dado recente: {vivos[:5]}"


def test_todo_periodico_publicado_tem_percentil():
    """Sem percentil a regra não se aplica, e o veículo não deve ser listado."""
    assert not [d["nome"] for d in _ler("p") if d.get("percentil") is None]


def test_todo_veiculo_tem_recibo():
    assert not [d["slug"] for d in _ler("p") + _ler("e") if not d.get("passos")]


def test_slug_omitido_e_derivavel_do_nome():
    """O índice omite o slug quando ele sai do nome — 96% dos casos, e com 30
    mil veículos isso é 1,2 MB a menos na abertura. A derivação em app.js
    precisa bater byte a byte com `slugificar` do build; um descasamento faria
    a ficha não abrir, sem erro visível."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent / "site"))
    from build import slugificar

    indice = json.loads(
        (DIST.parent / "indice.json").read_text(encoding="utf-8")
    )["veiculos"]
    for v in indice:
        if "s" in v:
            continue  # exceção guardada de propósito
        derivado = f"{v['t']}-{slugificar(v['n'])}"
        assert (DIST / f"{derivado}.json").exists(), f"ficha ausente: {derivado}"


def test_toda_ficha_do_indice_existe():
    """Uma amostra ampla: slug guardado ou derivado, o arquivo tem que estar lá."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent / "site"))
    from build import slugificar

    indice = json.loads(
        (DIST.parent / "indice.json").read_text(encoding="utf-8")
    )["veiculos"]
    faltam = [
        v["n"]
        for v in indice[::37]
        if not (DIST / f"{v.get('s') or f'{v[chr(116)]}-{slugificar(v[chr(110)])}'}.json").exists()
    ]
    assert not faltam, faltam[:5]
