# Como ajudar

O QualisComp depende de dados que **nenhuma automação resolve sozinha**. Se você
é da área e viu um número errado, sua correção vale mais que qualquer heurística
que eu escreva. Este documento diz exatamente onde mexer.

## O jeito mais rápido: abrir uma issue

Não precisa clonar nada. [Abra uma issue](https://github.com/tardellirs/qualiscomp/issues/new/choose)
e escolha o modelo:

| Situação | Modelo |
|---|---|
| O estrato de um veículo está errado | **Estrato incorreto** |
| Um evento ou periódico não está na base | **Veículo faltando** |
| O h5 que mostramos difere do Google Scholar | **h5 divergente** |
| O mesmo evento aparece duas vezes | **Veículo duplicado** |

Em todos, o essencial é o mesmo: **qual veículo, qual número deveria ser, e onde
conferir**. Sem a fonte, não dá para aceitar a correção — nem a sua nem a minha.

## Onde os dados moram

Três arquivos concentram quase todas as correções possíveis:

### `data/aliases_eventos.csv` — nomes alternativos

O Google Scholar indexa muitos eventos brasileiros **duas vezes**, em português e
em inglês, com as citações divididas. Quando as duas grafias não compartilham
palavras nem a sigla, nenhum algoritmo as une. O IHC é o caso extremo: a entrada
em português tem h5=5 e a em inglês, h5=16 — três estratos de diferença.

Cada linha aqui vira uma consulta extra ao Scholar e um alvo extra de casamento:

```csv
sigla,alias
IHC,Brazilian Symposium on Human Factors in Computing Systems
```

**Confira em** [Scholar Metrics](https://scholar.google.com/citations?view_op=search_venues)
antes de adicionar.

### `data/eventos.csv` — a base de eventos

Gerado por `qualis coletar-eventos`, mas pode ser editado à mão. As colunas que
mais precisam de gente:

- `h5` — o h5-index do Google Scholar. É o indicador que o Documento de Área
  manda usar para eventos.
- `anos_tradicao` — **vazio em todas as linhas hoje**, e por isso o critério de
  indução (evento nacional da SBC com 20+ anos → A4) nunca dispara. É a lacuna
  mais cara do projeto: o CSBC, que existe desde 1980, aparece como A8. Se você
  souber o ano da primeira edição de um evento da SBC **com fonte**, preencher
  aqui conserta um estrato inteiro.

### `qualis/rules.py` — as regras

Só mexa aqui se encontrou divergência com o
[Documento de Área](https://www.gov.br/capes/pt-br/acesso-a-informacao/acoes-e-programas/avaliacao/sobre-a-avaliacao/areas-avaliacao/sobre-as-areas-de-avaliacao/colegio-de-ciencias-exatas-tecnologicas-e-multidisciplinar/ciencias-exatas-e-da-terra/ciencia-da-computacao/computacao-docarea.pdf/@@download/file),
seção 2.2. **Cite a página** na descrição do PR.

## Mandando um PR

```bash
git clone https://github.com/tardellirs/qualiscomp && cd qualiscomp
pip install -r requirements-dev.txt
python -m pytest -q                 # tem que passar antes e depois
```

O site publicado fica em `site/dist/`, versionado para o Vercel servir sem
build. Se sua mudança afeta os dados ou o layout, **regenere e inclua**:

```bash
python site/build.py                # regenera site/dist
node site/checar.mjs                # 5 tamanhos de tela, reporta problemas
```

### O que faz um PR ser aceito rápido

1. **Fonte verificável para cada número.** Link do Scholar, do Scopus, da página
   do evento. Um h5 errado vira estrato errado, e estrato errado é o único jeito
   de este projeto perder utilidade.
2. **Teste, quando for regra.** Mudou `rules.py`? Adicione o caso em
   `test_rules.py`. Os testes existentes documentam decisões difíceis — veja
   `test_saturacao_oficial.py`, que trava a interpretação da saturação em A3 com
   base nos resultados oficiais da CAPES.
3. **Uma coisa por PR.** Corrigir o h5 do SBBD e reescrever o CSS na mesma
   mudança dificulta a revisão de ambos.

### O que eu vou recusar

- Número sem fonte, por mais certo que pareça.
- Mudança de regra sem citar a página do documento.
- Adicionar campos brutos do Scopus (CiteScore, SNIP, SJR) ao que é publicado:
  o export vem de assinatura institucional e o site publica o estrato derivado.

## Limites conhecidos, se você quiser atacar algum

- **Critério de indução não aplicado** — falta `anos_tradicao`. Impacto alto,
  trabalho manual, sem dificuldade técnica.
- **Casamentos ruins no Scholar** — alguns eventos casaram com o veículo errado
  e exibem estrato indevido, sem nenhum aviso. Precisa gravar a similaridade do
  casamento e rebaixar a confiança abaixo de um limiar.
- **Veículos duplicados** — a deduplicação é por slug, não por identidade.
- **Sem busca por ISSN** — a base do Scopus não traz ISSN; daria para cruzar com
  o OpenAlex, que tem `issn_l`.

## Código

Python com type hints, sem dependência que não seja necessária. Comentário
explica **por que**, não o que — de preferência registrando a armadilha que
motivou a linha. O projeto está cheio delas: a URL da planilha da SBC só resolve
em NFD, o JMLR aparece no OpenAlex com citedness zero, o asterisco na sigla criava
eventos duplicados.
