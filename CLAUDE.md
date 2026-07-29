# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## O que é

**QualisComp** ([qualiscomp.com](https://qualiscomp.com)) estima o estrato **A1–A8**
de periódicos e eventos segundo o **Documento de Área 02 (Computação)** da CAPES
para o ciclo **2025-2028** — as regras que substituíram o Qualis Periódicos. O PDF
fonte está em `docs-computacao-docarea-2025-2028.pdf`; a seção 2.2 (págs. 20-23) é
o que o código implementa.

Código e comentários estão em **português**. Mantenha assim.

## Comandos

```bash
pip install -r requirements-dev.txt pytest
python site/build.py                  # gera site/dist a partir de data/
python site/build.py --servir         # gera e sobe em localhost:8000
python -m pytest -q                   # todos os testes
python -m pytest -q test_jcr.py       # um arquivo
python -m pytest -q -k percentil      # por nome
node site/testa_painel.mjs            # monta as ~3.800 fichas sem navegador
node site/checar.mjs                  # 5 tamanhos de tela x 3 páginas, reporta problemas
```

CLI, para consultar sem o site: `python -m qualis {tabela,periodico,evento,comparar,validar}`
e os importadores `{importar-api,importar-scopus,coletar-eventos,atualizar}`.

Os harnesses `site/verifica-*.mjs` são Playwright e assumem um servidor em
`localhost:8080` (`cd site/dist && python3 -m http.server 8080`). São de uso
pontual, escritos por causa de um defeito específico — leia o comentário no topo
antes de confiar num deles.

## Arquitetura

Pipeline de mão única, sem servidor:

```
fontes externas -> qualis/*.py (I/O + normalização)
                -> qualis/rules.py (regra pura)
                -> site/build.py -> site/dist/ (HTML + JSON estático)
                -> app.js filtra e busca no cliente
```

**`qualis/rules.py` não faz I/O.** É a única tradução do documento da CAPES em
código: `ESTRATOS`, `PERCENTIL_MINIMO`, `H5_MINIMO`, `classificar_periodico`,
`classificar_evento`, `aplicar_bonus_fwci`. Toda mudança de regra passa por aqui e
por `test_rules.py`. Quando não há dado para aplicar a regra, ela levanta
`RegraNaoAplicavel` em vez de devolver A8 — "sem percentil" não é "percentil zero".

**`site/build.py`** é o orquestrador: lê todas as fontes, chama as regras, monta
`Veiculo` e emite `site/dist`. Cada ficha carrega um **recibo** (`passos`) dizendo
qual indicador, qual corte e qual fonte produziram o estrato. Ao adicionar
informação a uma ficha, decida se ela é um *passo da derivação* ou um *cartão
separado* — dado que não altera o estrato (ex.: acordo de APC) não entra no recibo.

**Saída em `site/dist/` é versionada.** O Vercel serve sem build
(`vercel.json`: `buildCommand: ""`). Depois de mexer em `site/app/` ou em qualquer
fonte, rode `python site/build.py` e commite o `dist` — a CI avisa se divergir.

Números que aparecem no HTML vêm de **marcadores** substituídos no build —
`{{N_PERIODICOS}}` e `{{N_EVENTOS}}` estão em uso, e `{{N_TOTAL}}` está definido
em `build.py` disponível para quando precisar. Nunca crave contagem à mão
em `site/app/*.html`: já aconteceu de a meta description anunciar 1.983 periódicos
por meses quando eram 2.692 (`test_metadados.py` guarda isso).

## Hierarquia de fontes (decisões já tomadas)

Cada módulo em `qualis/` tem um docstring longo explicando *por que* aquela fonte é
usada para aquele campo e não para outro. Leia antes de trocar uma fonte.

| Campo | Fonte autoritativa | Não use |
|---|---|---|
| percentil de periódico | `elsevier.py` (Scopus) **e** `jcr.py` (WoS) — o **maior dos dois** | SJR/Scimago, quartis |
| h5 de evento | `scholar.py` / `coleta.py` (Google Scholar) | a coluna h5 da planilha da SBC; open-h5; CORE |
| Top10/Top20/relevante | `sbc.py` (planilha das CEs) | — |
| tradição de evento | `sbc.py` (nº de edições, medida conservadora) | — |
| histórico por ciclo | `historico_oficial.py` (Sucupira) | — |
| APC coberto | `apc.py` (projeto externo `acordos-capes`) | — |

Casamento entre bases é **sempre por ISSN**, nunca por título: existem duas
revistas chamadas *Internet of Things*, uma C e outra A1.

**JCR (`jcr.py`)** tem dois caminhos. Se o export traz a coluna `JIF Percentile`,
o valor é lido. Se não, é reconstituído por posição na categoria
(`(N-R+0,5)/N`, arredondando meia para **cima**, empatados na posição mínima), o
que exige a categoria **completa** — por isso o módulo recusa export cortado no
teto de 600 linhas e export sem categoria única (o filtrado por país mistura 122).
Sempre prefira pedir a coluna na tela do JCR: foi ela que expôs dois bugs.

Usamos **JIF Percentile**, não JCI Percentile — o JCI é normalizado por área, e a
regra pareia o percentil do WoS com o do CiteScore, que é bruto. A escolha muda
~32% dos estratos.

## Licença dos dados

Postura consistente e deliberada: **publicar apenas o estrato derivado** — que é
resultado de regra pública da CAPES — e nunca redistribuir dado bruto de fonte
licenciada (CiteScore, JIF, SNIP, SJR) nem os arquivos de origem.

Por isso `data/` é quase todo gitignorado: exports do Scopus e do JCR, planilhas
da SBC e da Sucupira. Versionados são só `aliases_eventos.csv`,
`ces_sbc_nomes.csv`, `eventos.csv`, `tradicao_eventos.csv`,
`scholar_cache.json.gz`, `openalex_cs_journals.json.gz` e
`validacao_open_h5.json`. Os testes que dependem de arquivo ausente **se
auto-pulam** (`pytest.mark.skipif`), então a CI passa sem eles.

Chave da Elsevier vem **só** de `ELSEVIER_API_KEY`. `test_segredos.py` varre o
repositório procurando hex de 32 caracteres, porque a resposta da API embute a
chave nas URLs de paginação que devolve.

## Ambiguidades do documento

Onde o documento é ambíguo, o código não escolhe por gosto — resolve contra
evidência e trava com teste. Se encontrar outra ambiguidade, siga o mesmo padrão.

**Saturação em A3.** O documento diz "haverá uma saturação no nível A3" sem dizer
se o teto limita o resultado ou só o ganho qualitativo. Comparado ao Qualis
Eventos oficial 2021-2024 (mesma comissão): entre eventos Top10/Top20 cujo h5
sozinho daria pior que A3, só **3 de 93** ficaram acima de A3; no controle, cujo
h5 já justificava A1/A2, **109 de 140** ficaram. O teto limita o **ganho**.
Travado em `test_saturacao_oficial.py`.

**Não indexado.** Periódico fora do WoS e do Scopus não é A8: a pág. 23 prevê
avaliação qualitativa pela área mediante justificativa do programa. O site
simplesmente não o lista, em vez de afirmar uma reprovação que a CAPES não emitiu.

## Interface

- **Nada de rótulo de incerteza na tela.** Se a fonte é fraca, resolva a fonte ou
  omita o dado — não escreva "dado forte" nem "estimativa provável" para o usuário.
- Lista primeiro; detalhe em **painel deslizante**, não em outra página.
- Estratos antigos (B1–B5, C) aparecem com estilo próprio, **fora da rampa de cor**
  dos estratos novos: as escalas mudaram duas vezes e a CAPES nunca publicou
  equivalência.
- `test_cores.py` lê o CSS e verifica contraste, monotonicidade e gamut da rampa
  `--e1`..`--e8`. A rampa é dividida em dois blocos de propósito, pulando a zona
  morta de luminosidade 0,44–0,68.
- Filtros que só valem para um tipo de veículo (subáreas das CEs, APC) precisam se
  desmarcar e ocultar quando o tipo muda — ver `ajustarAPC` e `desenharSubareas`
  em `app.js`.

**Feature flags:** `FLAGS` no topo de `site/app/app.js`, sobreponíveis por
`?flag=nome` / `?flag=-nome`. Guarde qualquer acesso a `location` com
`typeof location !== 'undefined'` — `testa_painel.mjs` roda o arquivo no Node.

## Limites conhecidos

- Alguns eventos casaram com a entrada errada no Google Scholar e aparecem com
  estrato indevido (~52 casos identificados, ainda não corrigidos).
- Veículos duplicados: a deduplicação é por slug, não por identidade.
- Livros, capítulos, produção técnica e as cotas de seleção do documento não são
  modelados.
- Cobertura de WoS chega a ~1.236 dos 2.692 periódicos; nos demais o estrato vem
  de uma base só e é, na prática, um piso.
