# QualisComp

<p align="center"><strong><a href="https://qualiscomp.com">qualiscomp.com</a></strong></p>

<p align="center">
  <a href="https://qualiscomp.com"><img alt="Site" src="https://img.shields.io/badge/site-qualiscomp.com-2f6feb?style=flat-square"></a>
  <a href="https://github.com/tardellirs/qualiscomp/actions/workflows/testes.yml"><img alt="Testes" src="https://github.com/tardellirs/qualiscomp/actions/workflows/testes.yml/badge.svg"></a>
  <img alt="Veículos" src="https://img.shields.io/badge/ve%C3%ADculos-3.816-0b7285?style=flat-square">
  <img alt="Ciclo" src="https://img.shields.io/badge/ciclo-2025--2028-495057?style=flat-square">
  <a href="LICENSE"><img alt="Licença" src="https://img.shields.io/badge/c%C3%B3digo-MIT-1c7ed6?style=flat-square"></a>
  <a href="CONTRIBUTING.md"><img alt="Contribuições" src="https://img.shields.io/badge/PRs-bem--vindos-2b8a3e?style=flat-square"></a>
</p>

Estrato **A1–A8** de periódicos e eventos de Computação segundo as regras do
**Documento de Área 02 (Computação)** da CAPES para o ciclo **2025-2028** — o
que substituiu o Qualis Periódicos.

O site mostra a **conta**: qual indicador foi usado, qual corte, qual ajuste, e
de onde veio cada número.

**Fonte de tudo:** [Documento de Área — Computação (PDF)](https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/colegio-de-ciencias-exatas-tecnologicas-e-multidisciplinar/ciencias-exatas-e-da-terra/ciencia-da-computacao/computacao-docarea.pdf/@@download/file),
seção 2.2, págs. 20-23.

> **Estimativa não oficial.** A CAPES não publica lista de estratos por veículo
> no novo ciclo, e a decisão final é da comissão da área. Este é um projeto
> independente, sem vínculo com a CAPES, a SBC ou instituições de ensino.

## As regras

**Periódicos** — percentil do WoS ou do Scopus, o **maior entre os dois**:

| A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 |
|---|---|---|---|---|---|---|---|
| ≥87,5 | ≥75 | ≥62,5 | ≥50 | ≥37,5 | ≥25 | ≥12,5 | <12,5 |

Periódico de sociedade científica pode subir até 2 níveis. Os 5% de maior FWCI
do conjunto, se abaixo de A3, sobem 1 nível.

**Eventos** — h5-index do **Google Scholar**:

| A1 | A2 | A3 | A4 | A5 | A6 | A7 | A8 |
|---|---|---|---|---|---|---|---|
| ≥35 | ≥25 | ≥20 | ≥15 | ≥12 | ≥9 | ≥6 | >0 |

CE-SBC Top10 sobe 2 níveis, Top20 sobe 1, relevante mantém. Sem h5: "Top" → A7,
"relevante" → A8. O ganho qualitativo satura em A3 — o h5 sozinho não.

## Como rodar

```bash
pip install -r requirements-dev.txt
python site/build.py --servir      # gera site/dist e sobe em localhost:8000
python -m pytest -q                # 156 testes
node site/checar.mjs               # abre em 5 tamanhos de tela e reporta problemas
```

CLI, para consultar sem o site:

```bash
python -m qualis tabela
python -m qualis periodico "IEEE Transactions on Software Engineering"
python -m qualis evento SBES
```

## Dados

| Fonte | O que fornece | No repositório |
|---|---|---|
| API Serial Title da Elsevier | percentil e ISSN dos periódicos | **não** — uso acadêmico, sem redistribuição |
| JCR / Web of Science (Clarivate) | percentil do WoS — a outra metade da regra | **não** — licenciado, via Portal de Periódicos |
| Scopus Sources (export) | percentil dos periódicos | **não** — assinatura institucional |
| Google Scholar Metrics | h5 dos eventos | sim (`data/scholar_cache.json.gz`) |
| Planilha das CEs da SBC | Top10 / Top20 / relevante | **não** — sem licença declarada |
| Qualis Eventos oficial 2021-2024 | classificação do ciclo anterior | **não** — sem licença declarada |
| Qualis Periódicos oficial 2010-2024 | histórico por ciclo na ficha | **não** — baixe da Sucupira |
| OpenAlex | base de referência de Computação | sim |
| [acordos-capes](https://periodicos.ifsp.dev/) | acordos de isenção de APC | **não** — base de outro projeto |

Os arquivos de origem sob assinatura ou sem licença declarada ficam fora do
versionamento (ver `.gitignore`). Para reconstruir do zero é preciso baixá-los:

```bash
export ELSEVIER_API_KEY=...                # dev.elsevier.com/apikey/manage
python -m qualis importar-api --areas COMP MULT
python -m qualis importar-scopus ~/Downloads/*-source-results.xlsx   # alternativa manual
python -m qualis coletar-eventos          # baixa a planilha da SBC e consulta o Scholar
python -m qualis atualizar --email voce@exemplo
```

## Uma decisão que a evidência resolveu

O documento diz que "haverá uma saturação no nível A3", sem dizer se o teto
limita o resultado ou só o ganho qualitativo. Comparando com o **Qualis Eventos
oficial 2021-2024** (mesma comissão, mesmo método): entre eventos Top10/Top20
cujo h5 sozinho daria pior que A3, apenas **3 de 93** ficaram acima de A3 — mas
no grupo de controle, cujo h5 já justificava A1/A2, **109 de 140** ficaram.
O teto limita o ganho, não o indicador. Travado em `test_saturacao_oficial.py`.

## Estrutura

```
qualis/rules.py       as regras da Área 02 — puro, sem I/O
qualis/scopus_export.py, scholar.py, sbc.py, coleta.py, oficial.py
site/build.py         gera o site estático
site/app/             index.html · sobre.html · estilo.css · pagina.css · app.js
site/dist/            saída publicada (versionada para o Vercel servir sem build)
test_*.py             156 testes
```

## Contribuindo

O site está em **[qualiscomp.com](https://qualiscomp.com)**. Achou um estrato errado, um h5 desatualizado ou um veículo faltando?
[Abra uma issue](https://github.com/tardellirs/qualiscomp/issues/new/choose) —
há modelos prontos e não precisa clonar nada. Para mandar correção direto, veja
[CONTRIBUTING.md](CONTRIBUTING.md).

O que mais precisa de gente da área: o **ano de fundação dos eventos da SBC**
(sem ele o critério de indução não dispara e o CSBC aparece como A8) e os
**nomes alternativos** de eventos que o Google Scholar indexa duas vezes.

## Funcionalidades em teste

`FLAGS` em `site/app/app.js` guarda o que ainda está em avaliação. O padrão vem
do código, e a URL sobrepõe sem precisar publicar de novo:

```
?flag=subareas      liga só nesta visita
?flag=-subareas     desliga
```

Nenhuma em avaliação no momento. **subareas** — o painel das Comissões
Especiais da SBC quando o filtro é Eventos — passou a ser o padrão; se algo
quebrar, `?flag=-subareas` desliga sem publicar de novo.

## Limites conhecidos

- Alguns eventos casaram com a entrada errada no Google Scholar e aparecem com
  estrato indevido.
- O histórico oficial por ciclo cobre 1.051 dos 2.692 periódicos — só os que a
  área de Computação chegou a classificar em algum ciclo.
- A marca **APC** cobre só os acordos das sete editoras negociadas pela CAPES;
  isenção por acordo da própria instituição não aparece.
- Livros, capítulos, produção técnica e as cotas de seleção do documento não são
  modelados.
