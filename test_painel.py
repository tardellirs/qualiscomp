"""Monta o painel de detalhe de TODAS as fichas, fora do navegador.

Existe por causa de um bug real: dentro de `regua()` havia uma variável local
`const esc` (a escala da régua) que sombreava a função global `esc()` de escape
de HTML. A chamada `esc(d.fronteira)` acertava a string em vez da função e
lançava TypeError — mas só em fichas COM aviso de fronteira, e a falha era
silenciosa, então o clique simplesmente não abria nada.

Nenhum teste de `rules.py` pegaria isso: o bug estava no JS, e só em parte dos
dados. Este teste executa as funções de renderização contra as 3.108 fichas
geradas, o que cobre justamente a combinação de dados que quebrava.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent
SCRIPT = RAIZ / "site" / "testa_painel.mjs"
DIST = RAIZ / "site" / "dist" / "dados" / "indice.json"


@pytest.mark.skipif(shutil.which("node") is None, reason="node não instalado")
@pytest.mark.skipif(not DIST.exists(), reason="site ainda não foi gerado (site/build.py)")
def test_todas_as_fichas_montam_sem_erro():
    r = subprocess.run(
        ["node", str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True, timeout=180
    )
    assert r.returncode == 0, f"fichas quebraram ao montar:\n{r.stdout}\n{r.stderr}"
    assert "falharam: 0" in r.stdout, r.stdout
