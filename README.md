# QualisComp

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
python -m pytest -q                # 109 testes
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
| Scopus Sources (export) | percentil dos periódicos | **não** — assinatura institucional |
| Google Scholar Metrics | h5 dos eventos | sim (`data/scholar_cache.json.gz`) |
| Planilha das CEs da SBC | Top10 / Top20 / relevante | **não** — sem licença declarada |
| Qualis Eventos oficial 2021-2024 | classificação do ciclo anterior | **não** — sem licença declarada |
| OpenAlex | base de referência de Computação | sim |

Os arquivos de origem sob assinatura ou sem licença declarada ficam fora do
versionamento (ver `.gitignore`). Para reconstruir do zero é preciso baixá-los:

```bash
python -m qualis importar-scopus ~/Downloads/*-source-results.xlsx
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
test_*.py             109 testes
```

## Contribuindo

Achou um estrato errado, um h5 desatualizado ou um veículo faltando?
[Abra uma issue](https://github.com/tardellirs/qualiscomp/issues/new/choose) —
há modelos prontos e não precisa clonar nada. Para mandar correção direto, veja
[CONTRIBUTING.md](CONTRIBUTING.md).

O que mais precisa de gente da área: o **ano de fundação dos eventos da SBC**
(sem ele o critério de indução não dispara e o CSBC aparece como A8) e os
**nomes alternativos** de eventos que o Google Scholar indexa duas vezes.

## Limites conhecidos

- O **critério de indução** (evento nacional da SBC com 20+ anos → A4) não é
  aplicado: exige o ano de fundação, que não temos de fonte verificável. O CSBC,
  por exemplo, aparece como A8.
- Alguns eventos casaram com a entrada errada no Google Scholar e aparecem com
  estrato indevido.
- Livros, capítulos, produção técnica e as cotas de seleção do documento não são
  modelados.
