"""Impede que chave de API entre no repositório.

Existe porque a resposta da API da Elsevier **embute a chave nas URLs de
paginação** que ela devolve (`...&apiKey=...`). Basta serializar uma resposta
crua para vazar a credencial sem perceber — e um repositório público não
esquece. A chave sempre vem de variável de ambiente.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent

# Chave da Elsevier: 32 caracteres hexadecimais. O padrão é largo de propósito;
# preferimos um falso positivo a uma credencial publicada.
_HEX32 = re.compile(r"\b[0-9a-f]{32}\b")
_ATRIBUICAO = re.compile(
    r"""(?ix)
    (api[_-]?key|apikey|insttoken|secret|token)
    \s* [:=] \s*
    ['"]? [A-Za-z0-9_\-]{20,} ['"]?
    """
)

# Onde é legítimo aparecer: os próprios testes e a documentação do padrão.
_ISENTOS = {"test_segredos.py"}


def _versionados() -> list[Path]:
    r = subprocess.run(
        ["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        pytest.skip("não é um repositório git")
    return [
        RAIZ / p
        for p in r.stdout.split("\n")
        if p and Path(p).name not in _ISENTOS
    ]


def _texto(p: Path) -> str | None:
    if not p.is_file() or p.stat().st_size > 4_000_000:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None  # binário: gz, xlsx, png, pdf


def test_nenhuma_chave_hexadecimal_nos_arquivos_versionados():
    achados = []
    for p in _versionados():
        t = _texto(p)
        if t is None:
            continue
        for m in _HEX32.finditer(t):
            achados.append(f"{p.relative_to(RAIZ)}: {m.group()[:8]}…")
    assert not achados, "possível chave de API versionada:\n  " + "\n  ".join(achados)


def test_nenhuma_atribuicao_de_credencial():
    achados = []
    for p in _versionados():
        t = _texto(p)
        if t is None:
            continue
        for m in _ATRIBUICAO.finditer(t):
            trecho = m.group().strip()
            # `os.environ.get("ELSEVIER_API_KEY", "")` e afins são o jeito certo.
            if "environ" in t[max(0, m.start() - 60) : m.end()]:
                continue
            achados.append(f"{p.relative_to(RAIZ)}: {trecho[:60]}")
    assert not achados, "credencial embutida no código:\n  " + "\n  ".join(achados)


def test_a_chave_so_vem_do_ambiente():
    fonte = (RAIZ / "qualis" / "elsevier.py").read_text(encoding="utf-8")
    assert 'os.environ.get("ELSEVIER_API_KEY"' in fonte
    assert not _HEX32.search(fonte)


def test_os_dados_de_origem_ficam_fora_do_versionamento():
    """A resposta da API traz a chave nas URLs de paginação; se algum cache
    cru for versionado por engano, a credencial vai junto."""
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8")
    for alvo in ("data/scopus_percentis.json.gz", "data/*.xlsx"):
        assert alvo in ignorados, f"{alvo} deveria estar no .gitignore"
