"""Regras de classificação de artigos da Área 02 (Computação) da CAPES.

Fonte: Documento de Área — Computação (Área 02), ciclo 2025-2028, seção 2.2
"Perspectivas na avaliação da produção intelectual", págs. 20-23.
https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/
sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/
colegio-de-ciencias-exatas-tecnologicas-e-multidisciplinar/ciencias-exatas-e-da-terra/
ciencia-da-computacao/computacao-docarea.pdf/@@download/file

A área adotou o Procedimento 2 da CAPES: indicadores quantitativos e qualitativos
do veículo, seguidos de indicadores quantitativos e qualitativos do artigo.

Este módulo é puro: sem I/O, sem rede. Todas as decisões são rastreáveis via a
lista `motivos` retornada em cada classificação.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Estratos, do melhor para o pior. A área usa "níveis A1..A8" para artigos.
ESTRATOS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8")

# Periódicos: percentil mínimo (WoS ou Scopus, o MAIOR entre os dois),
# em faixas iguais de 12,5%.
PERCENTIL_MINIMO = {
    "A1": 87.5,
    "A2": 75.0,
    "A3": 62.5,
    "A4": 50.0,
    "A5": 37.5,
    "A6": 25.0,
    "A7": 12.5,
    # A8: valor máximo do 8º estrato é inferior a 12,5
}

# Eventos: h5-index do Google Scholar.
H5_MINIMO = {
    "A1": 35,
    "A2": 25,
    "A3": 20,
    "A4": 15,
    "A5": 12,
    "A6": 9,
    "A7": 6,
    "A8": 1,  # "A8: H5 > 0"
}

# Saturação da avaliação puramente qualitativa de eventos: nenhum artigo passa
# de A3 apenas por critérios qualitativos.
SATURACAO_QUALITATIVA = "A3"

# Camadas de relevância atribuídas pelas Comissões Especiais da SBC.
CE_SBC_TIERS = ("top10", "top20", "relevante")


class RegraNaoAplicavel(Exception):
    """O veículo não é classificável pela área (não entra na avaliação)."""


@dataclass
class Classificacao:
    """Resultado de uma classificação, com a trilha de decisão."""

    estrato: str | None
    veiculo: str
    tipo: str  # "periodico" | "evento"
    motivos: list[str] = field(default_factory=list)
    considerado: bool = True

    @property
    def nivel(self) -> int | None:
        """Índice 0-based do estrato (0 = A1). None se não considerado."""
        return ESTRATOS.index(self.estrato) if self.estrato else None

    def __str__(self) -> str:
        rotulo = self.estrato or "NÃO CONSIDERADO"
        return f"{self.veiculo} [{self.tipo}] -> {rotulo}"


def _mover(estrato: str, niveis_acima: int) -> str:
    """Sobe `niveis_acima` estratos, saturando em A1."""
    i = ESTRATOS.index(estrato)
    return ESTRATOS[max(0, i - niveis_acima)]


def _limitar(estrato: str, teto: str) -> str:
    """Impede que `estrato` seja melhor que `teto`."""
    return estrato if ESTRATOS.index(estrato) >= ESTRATOS.index(teto) else teto


def estrato_por_percentil(percentil: float) -> str:
    """Mapeia um percentil (0-100) para o estrato base de periódico."""
    if not 0 <= percentil <= 100:
        raise ValueError(f"percentil fora de [0, 100]: {percentil}")
    for estrato in ESTRATOS[:-1]:
        if percentil >= PERCENTIL_MINIMO[estrato]:
            return estrato
    return "A8"


def estrato_por_h5(h5: int) -> str | None:
    """Mapeia um h5-index para o estrato base de evento. None se h5 == 0."""
    if h5 < 0:
        raise ValueError(f"h5 negativo: {h5}")
    for estrato in ESTRATOS:
        if h5 >= H5_MINIMO[estrato]:
            return estrato
    return None


def classificar_periodico(
    nome: str,
    percentil_scopus: float | None = None,
    percentil_wos: float | None = None,
    *,
    e_sbc: bool = False,
    bonus_sbc: int = 0,
    ma_pratica_editorial: bool = False,
    aderencia_computacao: bool = True,
    rotulo_scopus: str = "Scopus",
) -> Classificacao:
    """Classifica um artigo pelo periódico em que foi publicado.

    percentil_scopus / percentil_wos: a área usa o MAIOR entre os dois.
    e_sbc: periódico editado pela SBC (ou por sociedade científica).
    bonus_sbc: níveis que a análise qualitativa concedeu (0..2). A área permite
        "até no máximo dois níveis acima" para periódicos da SBC.
    ma_pratica_editorial: editora que usa más práticas (critérios COPE) — a área
        não considera esses artigos.
    """
    c = Classificacao(estrato=None, veiculo=nome, tipo="periodico")

    if ma_pratica_editorial:
        c.considerado = False
        c.motivos.append(
            "Descartado: editora com más práticas editoriais (COPE). "
            "A área só considera artigos em editoras sem más práticas."
        )
        return c

    if not aderencia_computacao:
        c.considerado = False
        c.motivos.append(
            "Descartado: sem aderência à Computação (a área faz análise "
            "qualitativa e não considera artigos fora da área)."
        )
        return c

    percentis = {
        rotulo_scopus: percentil_scopus,
        "WoS": percentil_wos,
    }
    disponiveis = {k: v for k, v in percentis.items() if v is not None}
    if not disponiveis:
        raise RegraNaoAplicavel(
            f"{nome}: sem percentil Scopus nem WoS — a área classifica periódicos "
            "pelo percentil dessas bases."
        )

    base_nome, percentil = max(disponiveis.items(), key=lambda kv: kv[1])
    c.estrato = estrato_por_percentil(percentil)
    outros = ", ".join(f"{k}={v:.1f}" for k, v in disponiveis.items())
    corte = (
        f"corte {PERCENTIL_MINIMO[c.estrato]}"
        if c.estrato in PERCENTIL_MINIMO
        else f"abaixo de {PERCENTIL_MINIMO['A7']}"  # A8 não tem piso, só teto
    )
    c.motivos.append(
        f"Percentil usado: {percentil:.1f} ({base_nome}, o maior entre os "
        f"disponíveis: {outros}) -> {c.estrato} ({corte})"
    )

    if bonus_sbc:
        if not e_sbc:
            raise ValueError("bonus_sbc só se aplica a periódicos da SBC")
        if not 0 <= bonus_sbc <= 2:
            raise ValueError("bonus_sbc deve estar em 0..2 (a área permite até 2)")
        antes = c.estrato
        c.estrato = _mover(c.estrato, bonus_sbc)
        c.motivos.append(
            f"Periódico da SBC: análise qualitativa subiu {bonus_sbc} nível(is) "
            f"({antes} -> {c.estrato}; máximo permitido pela área: 2)"
        )
    elif e_sbc:
        c.motivos.append(
            "Periódico da SBC: elegível a subir até 2 níveis por análise "
            "qualitativa da área (não aplicado aqui)."
        )

    return c


def classificar_evento(
    nome: str,
    h5: int | None = None,
    *,
    ce_sbc: str | None = None,
    segue_gt_capes: bool = True,
    anos_tradicao_sbc: int | None = None,
    promovido_por_sociedade: bool = False,
    teto_qualitativo: bool = True,
) -> Classificacao:
    """Classifica um artigo pelo evento em que foi publicado.

    h5: h5-index do Google Scholar do evento (None ou 0 = sem h5).
    ce_sbc: relevância atribuída pela Comissão Especial da SBC —
        "top10", "top20", "relevante" ou None.
    segue_gt_capes: o evento segue o padrão do relatório do GT da CAPES para
        classificação de eventos. Se não segue, a área não considera o artigo.
    anos_tradicao_sbc: anos de tradição, para eventos nacionais promovidos pela
        SBC (critério de indução: >=20 anos -> A4; >=10 anos -> A5).
    promovido_por_sociedade: o evento é um dos principais eventos nacionais
        promovidos pela SBC, ou de outra sociedade científica com aderência à
        área. É PRÉ-REQUISITO do critério de indução: sem isso, os anos de
        tradição sozinhos não classificam nada.
    teto_qualitativo: aplica a saturação em A3 sobre o ganho vindo de critérios
        qualitativos (a reclassificação por CE-SBC). Veja SATURACAO_QUALITATIVA.
    """
    c = Classificacao(estrato=None, veiculo=nome, tipo="evento")

    if ce_sbc is not None and ce_sbc not in CE_SBC_TIERS:
        raise ValueError(f"ce_sbc deve ser um de {CE_SBC_TIERS} ou None")

    if not segue_gt_capes:
        c.considerado = False
        c.motivos.append(
            "Descartado: evento não segue o padrão do relatório do GT da CAPES "
            "para classificação de eventos."
        )
        return c

    h5 = h5 or 0
    base = estrato_por_h5(h5)

    if base is None and ce_sbc is None:
        # Sem h5 e sem recomendação de CE-SBC: pode ainda entrar pelo critério
        # de indução (tradição), senão não é considerado.
        induzido = _estrato_por_tradicao(anos_tradicao_sbc, promovido_por_sociedade)
        if induzido is None:
            c.considerado = False
            c.motivos.append(
                "Descartado: sem h5-index e sem recomendação de CE-SBC "
                "(a área não considera esses artigos)."
            )
            return c
        c.estrato = induzido
        c.motivos.append(
            f"Critério de indução: evento com {anos_tradicao_sbc} anos de "
            f"tradição -> {induzido}"
        )
        return c

    if base is None:
        # Sem h5, mas com recomendação da CE-SBC.
        c.estrato = "A7" if ce_sbc in ("top10", "top20") else "A8"
        c.motivos.append(
            f"Sem h5-index; CE-SBC indicou como '{ce_sbc}' -> {c.estrato} "
            "(regra: 'Top' -> A7, 'relevante' -> A8)"
        )
    else:
        c.estrato = base
        c.motivos.append(f"h5={h5} -> {base} (corte {H5_MINIMO[base]})")

        if ce_sbc in ("top10", "top20"):
            niveis = 2 if ce_sbc == "top10" else 1
            promovido = _mover(base, niveis)
            rotulo = "Top10" if ce_sbc == "top10" else "Top20"
            if teto_qualitativo:
                # O ganho qualitativo não pode ultrapassar A3; o h5 sozinho pode.
                promovido = max(
                    (base, _limitar(promovido, SATURACAO_QUALITATIVA)),
                    key=lambda e: -ESTRATOS.index(e),
                )
            c.estrato = promovido
            c.motivos.append(
                f"CE-SBC '{rotulo}': +{niveis} nível(is) ({base} -> {c.estrato})"
            )
            teto = _mover(base, niveis)
            if teto_qualitativo and c.estrato != teto:
                c.motivos.append(
                    f"Saturação qualitativa: o ganho por CE-SBC pararia em "
                    f"{SATURACAO_QUALITATIVA}, não em {teto} "
                    f"(nenhum artigo passa de {SATURACAO_QUALITATIVA} só por "
                    f"critério qualitativo)"
                )
        elif ce_sbc == "relevante":
            c.motivos.append("CE-SBC 'relevante': mantém a classificação do h5")

    # Critério de indução pode ser mais favorável que o resultado acima.
    induzido = _estrato_por_tradicao(anos_tradicao_sbc, promovido_por_sociedade)
    if induzido and ESTRATOS.index(induzido) < ESTRATOS.index(c.estrato):
        c.motivos.append(
            f"Critério de indução ({anos_tradicao_sbc} anos de tradição) é mais "
            f"favorável: {c.estrato} -> {induzido}"
        )
        c.estrato = induzido

    return c


def _estrato_por_tradicao(anos: int | None, promovido_por_sociedade: bool) -> str | None:
    """Critério de indução: >=20 anos -> A4, >=10 anos -> A5.

    Só vale para "os principais eventos nacionais promovidos pela SBC" e para
    "eventos de outras sociedades científicas que tenham aderência à área".
    Sem esse vínculo, tempo de existência não classifica nada — do contrário um
    workshop qualquer de 22 anos, sem h5 e sem CE-SBC, viraria A4 justamente
    quando a regra manda não considerar o artigo.
    """
    if anos is None or not promovido_por_sociedade:
        return None
    if anos >= 20:
        return "A4"
    if anos >= 10:
        return "A5"
    return None


def aplicar_saturacao_qualitativa(c: Classificacao) -> Classificacao:
    """Aplica a saturação em A3 quando o estrato veio SÓ de critérios qualitativos.

    "Para a avaliação qualitativa haverá uma saturação no nível A3, ou seja,
    nenhum artigo será avaliado acima do nível A3 somente por meio desses
    critérios qualitativos."
    """
    if not c.considerado or c.estrato is None:
        return c
    limitado = _limitar(c.estrato, SATURACAO_QUALITATIVA)
    if limitado != c.estrato:
        c.motivos.append(
            f"Saturação qualitativa: {c.estrato} -> {limitado} "
            "(nada passa de A3 só por critério qualitativo)"
        )
        c.estrato = limitado
    return c


def aplicar_bonus_fwci(
    classificacoes: list[Classificacao], fwci: list[float], *, fracao: float = 0.05
) -> list[Classificacao]:
    """Aplica o bônus de FWCI do documento:

    "5% dos artigos com maior FWCI, dentre TODOS os artigos selecionados pelo
    conjunto dos programas, E que foram classificados inicialmente em estratos
    inferiores a A3, terão seu estrato aumentado em 1 nível."

    A ordem importa e é fácil errar: o corte dos 5% é tirado sobre o conjunto
    INTEIRO, e só depois se filtra quem está abaixo de A3. Tirar 5% já dentro do
    grupo abaixo de A3 promoveria muito mais artigos, e os errados — um A6 com
    FWCI medíocre entraria só por ser o melhor entre os fracos.

    `fwci` é posicional: `fwci[i]` é o FWCI do artigo de `classificacoes[i]`.
    FWCI é indicador DO ARTIGO, então dois artigos no mesmo periódico têm
    valores diferentes — não dá para indexar por veículo. O valor oficial é o
    fornecido pela CAPES.

    Atenção: é um efeito de CONJUNTO. O corte real é calculado sobre todos os
    artigos de todos os programas da área; rodar isto na lista de um único
    programa é simulação indicativa, não previsão.
    """
    if not 0 < fracao <= 1:
        raise ValueError("fracao deve estar em (0, 1]")
    if len(fwci) != len(classificacoes):
        raise ValueError(
            f"fwci tem {len(fwci)} valores para {len(classificacoes)} classificações; "
            "o FWCI é por artigo e a lista é posicional"
        )
    if not classificacoes:
        return classificacoes

    # 1) corte dos 5% sobre TODOS os artigos, não só os abaixo de A3.
    n_corte = int(len(classificacoes) * fracao)  # trunca: 5% de 10 é 0, não 1
    if n_corte == 0:
        return classificacoes
    ordem = sorted(range(len(classificacoes)), key=lambda i: fwci[i], reverse=True)
    top = ordem[:n_corte]

    # 2) dentre esses, promove quem está estritamente abaixo de A3.
    for i in top:
        c = classificacoes[i]
        if (
            not c.considerado
            or c.estrato is None
            or ESTRATOS.index(c.estrato) <= ESTRATOS.index("A3")
        ):
            continue
        antes = c.estrato
        c.estrato = _mover(c.estrato, 1)
        c.motivos.append(
            f"Bônus FWCI ({fwci[i]:.2f}): está entre os {fracao:.0%} maiores FWCI "
            f"do conjunto e abaixo de A3, +1 nível ({antes} -> {c.estrato})"
        )
    return classificacoes
