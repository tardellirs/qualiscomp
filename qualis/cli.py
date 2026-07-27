"""CLI: em qual veículo publicar, segundo as regras da Área 02 (Computação).

    python -m qualis atualizar --email seu@email
    python -m qualis periodico "IEEE Transactions on Software Engineering"
    python -m qualis comparar "TOSEM" "Information and Software Technology" "SBC JBCS"
    python -m qualis evento SBES --h5 18 --ce-sbc top20
    python -m qualis tabela
"""

from __future__ import annotations

import argparse
import sys

from . import eventos as ev
from . import h5 as h5mod
from . import coleta, openalex, rules, scopus, scopus_export, validacao

AVISO_PROXY = (
    "percentil ESTIMADO via OpenAlex (2yr_mean_citedness ranqueado entre os "
    "periódicos de Computação) — não é o CiteScore/JIF Percentile oficial"
)


# Categorias ASJC de Computação, como aparecem no export do Scopus.
_CATEGORIAS_COMPUTACAO = (
    "computer", "computation", "software", "information systems",
    "artificial intelligence", "human-computer", "signal processing",
    "hardware", "networks and communications", "computer vision",
    "computer graphics", "theoretical computer",
)


def _categoria_de_computacao(categoria: str | None) -> bool:
    if not categoria:
        return True  # sem categoria não dá para julgar; não alarma à toa
    c = categoria.lower()
    return any(m in c for m in _CATEGORIAS_COMPUTACAO)


def _fmt(c: rules.Classificacao, *, motivos: bool = True) -> str:
    rotulo = c.estrato or "NÃO CONSIDERADO"
    out = [f"{rotulo:<16} {c.veiculo}"]
    if motivos:
        out += [f"                 · {m}" for m in c.motivos]
    return "\n".join(out)


def _percentil_de(
    nome: str, args: argparse.Namespace
) -> tuple[float, str, str, openalex.Periodico | None, bool]:
    """Devolve (percentil, rotulo, descricao_da_fonte, periodico, e_sbc)."""
    if args.percentil is not None:
        return args.percentil, "informado", "informado por você", None, False

    if args.scopus_xlsx:
        linhas = scopus.carregar(args.scopus_xlsx)
        achado = scopus.melhor_percentil(linhas, nome)
        if achado:
            p, linha = achado
            fonte = f"CiteScore Percentile oficial (Scopus, {linha.nome})"
            return p, "Scopus", fonte, None, False
        print(f"  [!] '{nome}' não achado no Scopus Source List; caindo no proxy.")

    # Base local vinda dos exports do Scopus Sources: é o dado oficial, e a
    # coluna "Highest percentile" já é o maior percentil entre as categorias.
    if not args.sem_scopus_local:
        achados = scopus_export.buscar(nome)
        if achados:
            f = achados[0]
            if f.parece_evento and not args.tratar_como_periodico:
                raise SystemExit(
                    f"'{f.titulo}' parece ser anais de EVENTO, não periódico.\n"
                    f"A Área 02 classifica evento pelo h5 do Google Scholar, não "
                    f"pelo percentil Scopus ({f.percentil:.0f}%). Use:\n"
                    f'  python -m qualis evento "{nome}" --h5 N [--ce-sbc top10]\n'
                    f"Se for mesmo um periódico (o título só parece de evento), "
                    f"repita com --tratar-como-periodico."
                )
            if not _categoria_de_computacao(f.categoria):
                print(
                    f"  [!] o percentil {f.percentil:.0f}% de '{f.titulo}' vem da "
                    f"categoria '{f.categoria}', que não é de Computação.\n"
                    f"      O documento diz só 'o maior', sem restringir "
                    f"categoria, mas a comissão pode divergir."
                )
            det = f"{f.rank}/{f.total} em {f.categoria}" if f.rank else f.categoria or "?"
            fonte = (
                f"Scopus Highest percentile OFICIAL — {f.titulo} "
                f"(CiteScore {f.citescore}, {det})"
            )
            return f.percentil, "Scopus", fonte, None, f.e_sbc

    ref = openalex.Referencia.carregar()
    achados = ref.buscar(nome, limite=1)
    p = achados[0] if achados else None
    aviso = AVISO_PROXY
    if p is None and args.email:
        p = ref.buscar_online(nome, args.email)
        if p is not None:
            aviso = f"{AVISO_PROXY}; periódico obtido ao vivo (fora da base local)"
    if p is None:
        raise SystemExit(
            f"Periódico '{nome}' não encontrado na base de referência "
            f"({len(ref)} periódicos de Computação). Tente outro nome/ISSN, "
            f"passe --email para buscar ao vivo no OpenAlex, ou --percentil N."
        )
    if not p.tem_dado_de_citacao:
        # Nunca inventar percentil 0 aqui: A8 por falta de dado seria uma
        # mentira grave. O JMLR é o caso emblemático (h-index 132, citedness 0).
        motivo = (
            "revista extinta/renomeada"
            if not p.ativo
            else f"lacuna de cobertura do OpenAlex (h-index {p.h_index}, "
            f"{p.works_count} trabalhos, mas citedness 0)"
        )
        raise SystemExit(
            f"'{p.nome}': o OpenAlex não tem citedness utilizável — {motivo}.\n"
            f"O proxy não se aplica. Pegue o percentil real e passe "
            f"--percentil N, ou use --scopus-xlsx.\n"
            f"  Scopus: https://www.scopus.com/sources.uri (busque a revista, "
            f"veja 'CiteScore Percentile')"
        )
    return ref.percentil(p.citedness_2y), "proxy OpenAlex", aviso, p, p.e_sbc


def cmd_atualizar(args: argparse.Namespace) -> int:
    print("Baixando periódicos do OpenAlex e filtrando Computação...")
    periodicos = openalex.construir_referencia(args.email, min_works=args.min_works)
    print(f"Pronto: {len(periodicos)} periódicos de Computação na base de referência.")
    return 0


def cmd_periodico(args: argparse.Namespace) -> int:
    percentil, rotulo, fonte, p, sbc_detectado = _percentil_de(args.nome, args)
    e_sbc = args.sbc or sbc_detectado
    c = rules.classificar_periodico(
        p.nome if p else args.nome,
        percentil_scopus=percentil,
        rotulo_scopus=rotulo,
        percentil_wos=args.percentil_wos,
        e_sbc=e_sbc,
        bonus_sbc=args.bonus_sbc,
    )
    print(f"\nFonte do percentil: {fonte}")
    if p:
        print(
            f"OpenAlex: 2yr_mean_citedness={p.citedness_2y:.2f}  h-index={p.h_index}  "
            f"editora={p.editora or '?'}  DOAJ={'sim' if p.doaj else 'não'}"
        )
    print()
    print(_fmt(c))
    print()
    return 0


def cmd_comparar(args: argparse.Namespace) -> int:
    resultados = []
    for nome in args.nomes:
        try:
            percentil, rotulo, fonte, p, sbc_detectado = _percentil_de(nome, args)
        except SystemExit as e:
            print(f"  [!] {e}")
            continue
        c = rules.classificar_periodico(
            p.nome if p else nome,
            percentil_scopus=percentil,
            rotulo_scopus=rotulo,
            percentil_wos=args.percentil_wos,
            e_sbc=args.sbc or sbc_detectado,
            bonus_sbc=args.bonus_sbc if (args.sbc or sbc_detectado) else 0,
        )
        resultados.append((c, percentil, fonte))

    resultados.sort(key=lambda t: (t[0].nivel if t[0].nivel is not None else 99, -t[1]))
    print()
    print(f"{'ESTRATO':<9}{'PERCENTIL':<11}VEÍCULO")
    print("-" * 72)
    for c, percentil, _ in resultados:
        print(f"{c.estrato or '-':<9}{percentil:<11.1f}{c.veiculo}")
    print()
    if resultados and "OpenAlex" in resultados[0][2]:
        print(f"Nota: {AVISO_PROXY}.")
    return 0


def cmd_evento(args: argparse.Namespace) -> int:
    reg = ev.buscar(args.nome)
    h5 = args.h5 if args.h5 is not None else (reg.h5 if reg else None)
    ce = args.ce_sbc or (reg.ce_sbc if reg else None)
    anos = args.anos_tradicao if args.anos_tradicao is not None else (
        reg.anos_tradicao if reg else None
    )
    if reg is None and args.h5 is None:
        print(
            f"'{args.nome}' não está em data/eventos.csv e você não passou --h5.\n"
            "Pegue o h5-index em https://scholar.google.com/citations?view_op=top_venues"
            " e adicione a linha no CSV (ou use --h5)."
        )
        return 1
    c = rules.classificar_evento(
        reg.sigla if reg else args.nome,
        h5=h5,
        ce_sbc=ce,
        segue_gt_capes=(reg.segue_gt_capes if reg else True) and not args.fora_do_gt,
        anos_tradicao_sbc=anos,
        promovido_por_sociedade=args.sociedade,
        teto_qualitativo=not args.sem_teto_qualitativo,
    )
    print()
    print(_fmt(c))
    print()
    return 0


def cmd_h5(args: argparse.Namespace) -> int:
    r = h5mod.calcular(args.nome, args.email)
    print()
    print(r.resumo())
    if r.fontes:
        print(f"  fontes agregadas: {', '.join(r.fontes[:6])}"
              + (f" (+{len(r.fontes)-6})" if len(r.fontes) > 6 else ""))
    print()
    return 0


def cmd_coletar_eventos(args: argparse.Namespace) -> int:
    resolvidos = coleta.coletar(intervalo=args.intervalo)
    destino = coleta.exportar_csv(resolvidos)
    com_scholar = sum(1 for r in resolvidos if r.h5_fonte == "scholar")
    ambiguos = coleta.grupos_ambiguos(resolvidos)
    print(f"\n{len(resolvidos)} eventos gravados em {destino}")
    print(f"  h5 do Google Scholar: {com_scholar}")
    print(f"  h5 só da planilha SBC (desatualizado): "
          f"{sum(1 for r in resolvidos if r.h5_fonte == 'sbc-2024')}")
    print(f"  sem h5 nenhum: {sum(1 for r in resolvidos if r.h5 is None)}")
    print(f"  ambíguos (>1 entrada no Scholar): {len(ambiguos)}")
    for r in ambiguos[:15]:
        print(f"    {r.sigla:<12} h5={r.h5}")
        for e in r.entradas[:3]:
            print(f"        {e}")
    return 0


def cmd_validar(args: argparse.Namespace) -> int:
    ds = validacao.comparar()
    ok = [d for d in ds if d.confere]
    ausentes = [d for d in ds if d.h5_nosso is None]
    difere = [d for d in ds if not d.confere and d.h5_nosso is not None]
    print(f"\nReferência: snapshot do Google Scholar de 30/06/2026 (ASSERT-KTH/open-h5)")
    print(f"{len(ds)} veículos | confere: {len(ok)} | diverge: {len(difere)} | "
          f"ausente na base: {len(ausentes)}\n")
    print(f"{'SIGLA':<10}{'NOSSO':>7}{'REF':>7}{'DELTA':>8}  FONTE")
    print("-" * 60)
    for d in ds:
        nosso = "-" if d.h5_nosso is None else str(d.h5_nosso)
        delta = "-" if d.delta is None else f"{d.delta:+d}"
        print(f"{d.sigla:<10}{nosso:>7}{d.h5_referencia:>7}{delta:>8}  {d.fonte}")
    print()
    if difere:
        print("Divergências podem ser legítimas: o snapshot é de 30/06/2026 e o "
              "Scholar atualiza.\nO que NÃO é aceitável é divergência grande e "
              "sistemática — isso indicaria erro de casamento de nome.")
    return 0


def cmd_importar_scopus(args: argparse.Namespace) -> int:
    scopus_export.importar(args.arquivos, mesclar=not args.substituir)
    return 0


def cmd_tabela(args: argparse.Namespace) -> int:
    print("\nÁrea 02 — Computação | ciclo 2025-2028 | Procedimento 2")
    print("Documento de Área, seção 2.2 (págs. 20-23)\n")
    print("PERIÓDICOS — percentil do WoS ou Scopus (o MAIOR entre os dois):")
    for e in rules.ESTRATOS[:-1]:
        print(f"  {e}   percentil >= {rules.PERCENTIL_MINIMO[e]:>5.1f}")
    print(f"  A8   percentil <  {rules.PERCENTIL_MINIMO['A7']:>5.1f}")
    print("  + periódico da SBC: até +2 níveis por análise qualitativa")
    print("  + 5% de maior FWCI abaixo de A3: +1 nível")
    print("  - editora com más práticas (COPE) ou sem aderência: descartado\n")
    print("EVENTOS — h5-index do Google Scholar:")
    for e in rules.ESTRATOS:
        print(f"  {e}   h5 >= {rules.H5_MINIMO[e]}")
    print("  + CE-SBC Top10: +2 níveis | Top20: +1 nível | relevante: mantém")
    print("  + sem h5: 'Top' da CE -> A7 | 'relevante' -> A8")
    print("  + indução SBC: >=20 anos de tradição -> A4 | >=10 anos -> A5")
    print(f"  ! critério qualitativo satura em {rules.SATURACAO_QUALITATIVA}")
    print("  - fora do padrão do GT, sem h5 e sem CE-SBC: não considerado\n")
    return 0


def _add_fonte_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--percentil", type=float, help="informe o percentil manualmente")
    p.add_argument(
        "--percentil-wos", type=float, help="JIF Percentile do WoS, se você tiver"
    )
    p.add_argument(
        "--scopus-xlsx",
        help="caminho do Scopus Source List (.xlsx) para usar o percentil oficial",
    )
    p.add_argument("--sbc", action="store_true", help="tratar como periódico da SBC")
    p.add_argument(
        "--bonus-sbc", type=int, default=0, choices=(0, 1, 2),
        help="níveis concedidos pela análise qualitativa a periódico da SBC (0-2)",
    )
    p.add_argument(
        "--tratar-como-periodico", action="store_true",
        help="força tratar como periódico um título que parece de evento",
    )
    p.add_argument(
        "--sem-scopus-local",
        action="store_true",
        help="ignora a base local do Scopus e usa o proxy OpenAlex",
    )
    p.add_argument(
        "--email",
        help="e-mail para buscar ao vivo no OpenAlex periódicos fora da base local",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="qualis",
        description="Onde publicar, segundo as regras da Área 02 (Computação) "
        "da CAPES para o ciclo 2025-2028.",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("atualizar", help="baixa/atualiza a base de referência")
    p.add_argument("--email", required=True, help="e-mail para o pool polido do OpenAlex")
    p.add_argument("--min-works", type=int, default=50)
    p.set_defaults(func=cmd_atualizar)

    p = sub.add_parser("periodico", help="classifica um periódico")
    p.add_argument("nome")
    _add_fonte_args(p)
    p.set_defaults(func=cmd_periodico)

    p = sub.add_parser("comparar", help="ranqueia vários periódicos")
    p.add_argument("nomes", nargs="+")
    _add_fonte_args(p)
    p.set_defaults(func=cmd_comparar)

    p = sub.add_parser("evento", help="classifica um evento")
    p.add_argument("nome")
    p.add_argument("--h5", type=int)
    p.add_argument("--ce-sbc", choices=rules.CE_SBC_TIERS)
    p.add_argument("--anos-tradicao", type=int)
    p.add_argument(
        "--sociedade", action="store_true",
        help="evento nacional da SBC (ou de outra sociedade científica com "
             "aderência) — pré-requisito do critério de indução por tradição",
    )
    p.add_argument(
        "--sem-teto-qualitativo", action="store_true",
        help="não aplica a saturação em A3 sobre o ganho por CE-SBC "
             "(leitura alternativa do documento)",
    )
    p.add_argument("--fora-do-gt", action="store_true")
    p.set_defaults(func=cmd_evento)

    p = sub.add_parser(
        "validar",
        help="confere o h5 da base contra um snapshot independente do Scholar",
    )
    p.set_defaults(func=cmd_validar)

    p = sub.add_parser(
        "coletar-eventos",
        help="baixa a planilha das CEs da SBC e busca o h5 de cada evento no Scholar",
    )
    p.add_argument("--intervalo", type=float, default=2.0)
    p.set_defaults(func=cmd_coletar_eventos)

    p = sub.add_parser(
        "h5",
        help="calcula um PISO do h5 de um evento via OpenAlex (nunca o valor real)",
    )
    p.add_argument("nome")
    p.add_argument("--email", required=True)
    p.set_defaults(func=cmd_h5)

    p = sub.add_parser(
        "importar-scopus",
        help="importa exports .xlsx da tela Scopus Sources (scopus.com/sources.uri)",
    )
    p.add_argument("arquivos", nargs="+")
    p.add_argument(
        "--substituir",
        action="store_true",
        help="recomeça a base em vez de mesclar com o que já existe",
    )
    p.set_defaults(func=cmd_importar_scopus)

    p = sub.add_parser("tabela", help="mostra os cortes oficiais")
    p.set_defaults(func=cmd_tabela)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
