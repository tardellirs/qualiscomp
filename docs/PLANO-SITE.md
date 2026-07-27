# Plano — Qualis Computação (Área 02, ciclo 2025-2028)

> **Revisão 2.** Incorpora a crítica adversarial de produto/arquitetura e a de
> design. Mudanças principais: uma **Fase 0** de licenciamento e integridade de
> dados antes de qualquer HTML; canal de contribuição e API estática promovidos
> para a Fase 1; recibo redesenhado com coluna de saldo; command palette
> rebaixado de porta de entrada a atalho.

---

## 1. Posicionamento

**"Onde publicar em Computação — a regra da CAPES aplicada, com a conta à mostra."**

O diferencial não é a tabela de cortes, que cabe num PDF. É a **regra executada
com procedência rastreável**. As armadilhas que descobrimos construindo o
pipeline não são defeitos a esconder: são o conteúdo mais valioso do projeto.

| Descoberta | Vira no site |
|---|---|
| Fontes derivadas subestimam o Google (−3,9 a −8,9; pior −26) | Selo de procedência por número, com data e fonte |
| IHC tem 2 entradas no Scholar (h5 5 vs 16) | Bifurcação com os dois ramos e barra de erro |
| Planilha SBC diverge do Scholar (LADC 14 vs 7) | Coluna dupla "Scholar hoje" × "SBC 2024" |
| Saturação em A3 é ambígua no documento | Toggle de interpretação, com o trecho literal |
| CVPR listado como "Eventos da Área", CVPRW como Top10 | Anotação "a fonte oficial parece conter erro" |
| PACMPL é periódico com nome de evento | Desambiguação explícita |
| JBCS só apareceu no 5º export (10%, não 34%) | Distinguir "não encontrado" de "não classificável" |

---

## 2. Jornadas

Ordenadas por valor, não por frequência — a #1 é a mais acessada, a #2 é a que
produz endosso institucional.

1. **"Esta revista/evento dá quanto?"** — ~80% dos acessos. Busca → resposta.
2. **"Quanto valeu a produção do meu programa?"** — retrospectiva, em lote.
   Colar Lattes/BibTeX → matcher → três baldes (casado com confiança, casado
   confira, não encontrado) → CSV. É o que faz coordenação de PPG adotar.
3. **"Onde submeter?"** — prospectiva; periódico × evento lado a lado.
4. **"O que existe de A1/A2 na minha subárea?"** — exploração facetada.
5. **"Este veículo foi descartado?"** — COPE, aderência. Estado próprio.
6. **"Por que esse estrato?"** — o recibo.

---

## 3. Fase 0 — antes de qualquer HTML

A ordem das fases originalmente seguia complexidade de UI. Está errado: deve
seguir **risco**. O maior risco é dado errado, ou dado que não podemos publicar.

### 3.1 Licenciamento (bloqueante)

- **Scopus.** `data/scopus_percentis.json.gz` vem de export de assinatura
  institucional. Publicar CiteScore, SNIP, SJR e editora de 2.236 revistas é
  redistribuição. **Decisão: publicar apenas o estrato derivado (A1..A8), a data
  e o nome do veículo.** O estrato é fruto de regra pública da CAPES; o
  percentil é dado da Elsevier. Quem quiser o número volta ao Scopus, e nós
  linkamos. Custo de utilidade: quase zero.
- **SBC.** Sem licença declarada, o default é "todos os direitos reservados".
  Pedir autorização — e ver §8.1, porque isso é oportunidade, não obstáculo.
- **Google Scholar.** Tratar h5 como fato público citado com data de observação,
  nunca como dataset nosso. O canal de contribuição (§3.4) é o que dá
  resiliência se o acesso automatizado for cortado.

### 3.2 Integridade de dados

- ✅ **Feito.** O h5 da planilha da SBC não alimenta mais o estrato. Rotular a
  origem não bastava: o valor ocupava o campo que alimenta `estrato_por_h5`, e
  saía estrato publicado a partir de número que o próprio repositório documenta
  como divergente (delta médio +4,6 ≈ um estrato inteiro).
- ✅ **Feito.** Falha de rede não é mais cacheada como "não existe".
- ✅ **Feito.** Variantes de nome e arquivo de apelidos curado
  (`data/aliases_eventos.csv`), que resolveu o caso IHC.
- **Chave canônica estável, antes de qualquer URL ser indexada.** ISSN-L para
  periódicos (o OpenAlex já fornece), sigla+CE para eventos, com tabela de
  aliases. Sem isso, um título que mude entre snapshots quebra `/veiculo/:slug`
  e gera falso positivo no diff.
- **Casos-teste versionados** a partir das armadilhas (IHC, LADC, CVPRW,
  PACMPL, JBCS, NFD no nome do arquivo da SBC). Hoje são folclore no README;
  precisam virar teste que o CI roda a cada coleta.

### 3.3 Modelo de confiança (no `rules.py`, não na UI)

| Nível | Origem |
|---|---|
| alto | percentil do export Scopus; h5 do Scholar sem ambiguidade |
| médio | h5 do Scholar com múltiplas entradas |
| baixo | proxy OpenAlex |
| nenhum | sem dado — **não exibe estrato** |

E o mais importante: **aviso de fronteira**. Quando o valor está a ≤2 pontos de
h5 ou ≤3 de percentil de um corte, a ficha diz "está na fronteira A4/A3, confira
na fonte antes de decidir". O README já prega isso; precisa virar componente.

### 3.4 Canal de entrada de dados

Sem ele a base de eventos congela. Botão "reportar" abre **GitHub Issue
pré-preenchida** com slug, valor atual, fonte e data. Zero backend, moderação =
merge de PR, e quem corrige vira coautor. Depois, `qualis aplicar-correcoes` lê
issues com label aceita e regenera.

---

## 4. Fase 1 — buscar, ficha, recibo

Escopo: **periódicos E eventos**. A comparação entre os dois é justamente o que
a nova regra tornou decisiva, já que acabou a trava de 3 artigos em evento para
1 em periódico.

Eventos entram apenas com `h5_fonte=scholar`. Os demais aparecem como
*encontrado, não classificado — falta h5 do Google*, com link para o Scholar e
botão de contribuir.

### 4.1 Busca — a home É a busca

Command palette foi **rebaixado de porta de entrada a atalho**. `⌘K` é
vocabulário de desenvolvedor; a professora que chega pelo WhatsApp do PPG espera
campo grande com cursor dentro. Um `<dialog>` na home também custa deep-link, e
`/?q=sbes` precisa ser colável em e-mail e indexável.

| Contexto | Padrão |
|---|---|
| `/` | combobox inline grande, sempre aberto, autofocus |
| Demais telas | botão visível **e** `/` ou `⌘K` abrindo `<dialog closedby="any">` |

Requisitos que decidem adoção: insensível a acento e caixa; ISSN com e sem
hífen; sigla colada; tolerante a erro de digitação; e **colar uma referência
bibliográfica inteira** e achar o veículo — é o que a pessoa tem na mão.

### 4.2 O recibo — razão contábil de três colunas

O esboço anterior obrigava o leitor a fazer a conta de cabeça. A coluna de saldo
resolve:

```
                                            estrato corrente
 ① h5 = 23  (Google Scholar)                       A4
 ② CE-SBC "Top10"                       +2  →      A2
 ③ Saturação qualitativa (p.22)         ⤓   →      A3   ⚑ leitura ambígua
 ───────────────────────────────────────────────────────
    RESULTADO                                      A3
```

A coluna da direita é uma fita de chips coloridos: entende-se a conta pela cor,
sem ler o texto. Procedência fica **sob demanda** (tooltip), não competindo com
a regra. Por padrão só o veredito e uma linha-resumo; "ver a conta" expande.

O disclaimer vai **dentro** do recibo, na linha final — faixa fixa no topo vira
cegueira em três segundos.

### 4.3 Estados — três coisas que não podem ser confundidas

| Estado | Significado |
|---|---|
| **Não encontrado** | não está na nossa base |
| **Não classificável** | existe, mas a área não considera (sem h5 e sem CE-SBC) |
| **Descartado** | má prática editorial (COPE) ou sem aderência |

Nenhum dos três é **A8**. Borrar isso destrói a credibilidade. E A7/A8 nunca
usam a mesma tipografia de estrato calculado com dado forte.

Sobre descarte: mostrar que o critério existe e apontar a página do documento.
**Nunca** marcar um veículo como predatório na UI — isso é publicar uma
acusação, e a decisão é da comissão, não nossa.

### 4.4 Também na Fase 1

- **API JSON estática** (`/api/v1/veiculos.json`, `/api/v1/veiculo/<slug>.json`),
  CORS aberto, `v1` com schema imutável. O pipeline já produz JSON; publicar o
  artefato é ~1 dia e é o que faz outras ferramentas dependerem de nós.
- **Página por veículo renderizada no build** (não rota client-side), com
  `<title>` no formato "SBES — estrato A3 no ciclo 2025-2028". A busca real é
  `"qualis SBES 2025"`.
- **Copiar como texto / imprimir / URL citável** (`/v/2026-07/veiculo/sbes`).
  As pessoas colam isso em relatório do Sucupira e em slide de colegiado — é
  como o link chega no grupo da coordenação. Testar `@media print`.
- **Telemetria sem cookie e sem PII** (query, houve resultado, tipo clicado).
  A lista de buscas com zero resultado É o backlog de dados do projeto.
  `/meu-programa` continua 100% local, que é onde a sensibilidade está.

---

## 5. Design

### 5.1 Glassmorphism com contraste garantido

Vidro é **hierarquia, não textura**. Só em camadas flutuantes: header, dialog de
busca, popovers, bandeja de comparação, painel de filtros. **Nunca** atrás de
tabela, do recibo, ou de bloco com mais de três linhas.

Regras inegociáveis:

1. Texto nunca senta direto no vidro — o vidro é moldura, o texto senta em placa
   de tinta opaca.
2. `backdrop-filter` inclui `brightness()`, e é ele que garante o piso de
   contraste, não o `blur()`. Medido: claro α≥0,80 → ~10,7:1; escuro α≥0,80
   sozinho dá 6,3:1 (insuficiente), com `brightness(0.5)` → ~10,2:1.
3. Alfa mínimo por token, nunca ad hoc. Alvo ≥7:1 no texto principal.
4. `prefers-reduced-transparency` e `forced-colors` → superfície sólida.
5. Máximo 2 camadas; **nunca animar `backdrop-filter`**; nunca em lista rolante.

### 5.2 Rampa dos 8 estratos

Codificar por **lightness**, não por matiz — sobrevive a preto e branco e a
qualquer daltonismo. Matiz só como reforço redundante, e **sempre** com rótulo
textual junto.

```
L(n) = 0.400 + (n−1) × 0.0757      ΔL ≈ 0.076 por degrau
C(n) = 0.140 − (n−1) × 0.0070
H(n) = 258   − (n−1) × 25.4        azul → ciano → verde → oliva → âmbar
```

Eixo dominante azul→amarelo preserva a ordem em protanopia e deuteranopia; em
tritanopia a lightness carrega sozinha. Tinta branca em A1–A3, escura em A4–A8.

**Verificação no CI** sobre os 16 pares: contraste ≥7:1, ΔL ≥0,05 em escala de
cinza, ΔE ≥8 nas três simulações de daltonismo. Um script falha o build.

### 5.3 Momentos memoráveis

Selecionados por valor informacional, não por efeito:

1. **Régua de percentil** — a posição do veículo entre os 2.236, com as 8 faixas
   desenhadas atrás. Mostra que o TSE está colado na fronteira de A1, e por que
   a métrica é frágil. `@property` + scroll-driven (enhancement puro).
2. **Distância ao próximo degrau** — "faltam 2 pontos de h5 para A2", e o
   simétrico honesto: "1 ponto a menos e cai para A4".
3. **Simulador de ajustes em CSS puro** — ligar/desligar bônus SBC, CE-SBC,
   FWCI e saturação, e ver o estrato mudar ao vivo. Estrato como inteiro em
   custom property, `clamp()`, cor pela fórmula paramétrica. Funciona sem JS.
4. **Bifurcação de ambiguidade** — o caso IHC com os dois ramos e seletor. Na
   comparação, **barra de erro em vez de ponto**: `A8 ─── A4`.
5. **Morph do chip** — o chip de estrato voa da lista para o topo da ficha.
   View Transitions, Baseline.
6. **"Mudou desde o snapshot passado"** — `A3, era A4 em fev/2026`. Faz o site
   parecer vivo apesar de estático.

Suporte: `:has()`, container queries, `subgrid`, `color-mix()`,
`backdrop-filter`, `linear()` são Baseline widely available. View Transitions,
`@property`, `@starting-style`, `light-dark()`, Popover são Baseline newly
available. Scroll-driven e `interestfor` são enhancement puro, sem polyfill.
`prefers-reduced-motion` desliga 1, 5 e 6 sem perder conteúdo.

### 5.4 Densidade e mobile

Rolagem horizontal só quando o dado **é** um eixo horizontal (a régua). Na
comparação, inverter eixos em tela estreita: uma seção por atributo, veículos
como linhas. `@container` + `subgrid` alinham as colunas em tela larga sem
tabela. Toggle "modo compacto" na exploração — quem varre 200 periódicos quer
densidade de planilha.

---

## 6. Arquitetura

Site estático é a escolha certa para leitura: 3.400 registros, dados de
snapshot, sem login, sem dado de usuário a proteger. Três correções:

- **API não precisa de servidor** — arquivos estáticos versionados com CORS.
- **Separar índice de ficha.** Índice leve (sigla, nomes, tipo, estrato,
  confiança) carrega adiantado; a ficha completa vem por slug. "Tudo
  client-side" não escala para 3.400 fichas com trilha e entradas alternativas.
- **A Action mensal, como estava, não funciona.** IP de datacenter + Scholar =
  bloqueio; o export do Scopus não é automatizável. Dividir: (a) Action mensal
  só valida, regenera e produz o diff, falhando ruidosamente se um parser mudar;
  (b) coleta do Scholar é comando local rodado por humano, resultado commitado;
  (c) atualização do Scopus é ritual documentado — quem, quando, quais filtros.

---

## 7. Fases

| Fase | Entrega |
|---|---|
| **0** | Licenças, integridade, chave canônica, confiança, casos-teste, canal de contribuição |
| **1** | Busca + ficha + recibo (periódicos e eventos) + API + SEO + exportar + telemetria |
| **2** | `/meu-programa` com Lattes/BibTeX; upload do próprio export do Scopus no browser |
| **3** | `/explorar` facetado com deadline de eventos; `/mudancas` + RSS |

**Cortado:** navegador de snapshots (sobra o diff, que é o conteúdo
distribuível). **Mantido contra recomendação:** `/comparar` como tela — o
argumento de que "comparar é olhar 3 números" ignora que a decisão real é
periódico × evento, métricas diferentes que não se comparam numa lista.

Uma ideia que não estava no plano e é das melhores disponíveis: **arrastar o
próprio export do Scopus**, processado 100% no browser com IndexedDB. O
usuário-alvo tem acesso institucional. Resolve cobertura, dá precisão exata, e
resolve o problema de licença — o dado da Elsevier fica na máquina de quem tem
direito a ele.

---

## 8. Adoção

O plano anterior não tinha uma linha sobre isso, o que para um produto que quer
virar padrão nacional era o segundo maior furo depois dos dados.

1. **SBC primeiro, como parceria.** Temos moeda concreta: encontramos erros na
   planilha deles (CVPR classificado como "Evento da Área" enquanto CVPRW é
   Top10; h5 divergente do Scholar em 110 de 121 casos verificados). Levar isso
   como relatório de qualidade e oferecer a ferramenta como consumidora oficial
   resolve licença, endosso e sustentabilidade de uma vez. **Antes de lançar.**
2. **CEs individuais como beta-testers.** 30 CEs, cada uma dona da lista da sua
   subárea. Valida os dados e vira canal de divulgação.
3. **Fórum de Coordenadores de PPG e lista da SBC** — maior densidade de
   usuário-alvo por mensagem no Brasil.
4. **SEO** — página estática por veículo, renderizada no build.
5. **Diff mensal como motor de retorno** — "12 veículos mudaram de estrato em
   março" se compartilha sozinho. Página fixa + RSS.
6. **Artigo no SBC Horizontes ou no CSBC** sobre a metodologia, especialmente as
   divergências entre fontes. Citabilidade é a moeda de confiança deste público.

---

## 9. Riscos

- **Autoridade percebida.** Não somos a CAPES. Disclaimer no recibo, no momento
  da decisão.
- **Divergência de interpretação.** O modo de falha provável não é a CAPES
  mandar tirar do ar: é a coordenação da Área 02 discordar da nossa leitura. Há
  duas ambiguidades documentadas, e a da saturação em A3 afeta eventos Top10 com
  h5 entre 15 e 34 — a faixa mais consultada. **Mitigação: mostrar as duas
  respostas lado a lado**, não um número com asterisco. Não se pode estar errado
  sobre o que se apresentou como aberto.
- **Reputação de terceiros.** Página de correção com SLA público de 7 dias,
  linkada de toda ficha. Editora que tem para onde reclamar reclama por e-mail.
- **Erro de decisão.** Disclaimer não é mitigação, é retórica. A mitigação é
  precisão calibrada: nível de confiança e aviso de fronteira.
- **Sustentabilidade.** Ciclo até 2028, muito conhecimento tácito. Casos-teste
  versionados, hospedagem institucional na SBC, e **critério de morte definido
  hoje**: se em 2027 ninguém rodar a coleta, o site exibe banner de dado
  obsoleto e para de responder com estratos. Site abandonado que continua dando
  número é pior que site nenhum.
- **Glassmorphism envelhece.** Isolado em tokens de superfície, trocável sem
  tocar em layout.

---

## 10. Fora de escopo, declarado

A ferramenta responde "onde publicar" e "quanto valeu". O documento também trata
de livros e capítulos, produção técnica/tecnológica, artigos em bases abertas, e
das cotas de seleção (4N produtos bibliográficos, M técnicos, com M = maior
valor entre 10 e N/4). Nada disso está implementado, e o site deve dizer isso.
