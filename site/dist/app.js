/* Qualis Computação — lista + painel de detalhe.
 *
 * Nada de navegar para outra página ao clicar num resultado: a lista é o
 * lugar de trabalho, e o detalhe abre num painel sobre ela. O que muda é a
 * query string (?v=slug), então o link continua colável.
 */

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const norm = (s) =>
  s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
   .replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();

const ESTRATOS = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'];
const CORTE_PCT = { A1: 87.5, A2: 75, A3: 62.5, A4: 50, A5: 37.5, A6: 25, A7: 12.5 };
const CORTE_H5 = { A1: 35, A2: 25, A3: 20, A4: 15, A5: 12, A6: 9, A7: 6, A8: 1 };

let BASE = null;
let filtrados = [];
let atual = null;
let limite = 80;

/* ---------------------------------------------------------------- dados -- */

async function carregar() {
  const r = await fetch('dados/indice.json');
  if (!r.ok) throw new Error(`índice não carregou (HTTP ${r.status})`);
  BASE = await r.json();
  BASE.veiculos.forEach((v) => {
    v._n = norm(v.n);
    v._g = norm(v.g || '');
    v._ap = (v.a || '').split(' · ').map(norm).filter(Boolean);
    v._a = v._ap.join(' ');
  });
}

const fichas = new Map();
async function ficha(slug) {
  if (fichas.has(slug)) return fichas.get(slug);
  const r = await fetch(`dados/v/${encodeURIComponent(slug)}.json`);
  if (!r.ok) throw new Error(`ficha não encontrada (HTTP ${r.status})`);
  const d = await r.json();
  fichas.set(slug, d);
  return d;
}

/* --------------------------------------------------------------- filtro -- */

function estado() {
  const f = $('#form-filtros');
  const d = new FormData(f);
  return {
    q: $('#q').value.trim(),
    tipo: d.get('tipo') || 'todos',
    estratos: new Set(d.getAll('estrato')),
    min: parseFloat(d.get('min')),
    max: parseFloat(d.get('max')),
    ordem: $('#ordem').value,
  };
}

function pontuar(v, q) {
  const { _n: a, _g: s, _a: ap } = v;
  if (s && s === q) return 1000;
  if (a === q) return 900;
  if (v._ap.some((x) => x === q)) return 850;
  if (s && s.startsWith(q)) return 800;
  if (a.startsWith(q)) return 700;

  // Casar no INÍCIO DE UMA PALAVRA vale quase tanto quanto casar no começo do
  // título. Antes o peso caía com a posição do caractere, então "computational
  // linguistics" achava a "Transactions of the Association for Computational
  // Linguistics" com 300 pontos, atrás de revistas muito menores cujo nome
  // apenas começa com o termo. Punir o título por ser comprido não faz sentido.
  const i = a.indexOf(q);
  if (i > 0) return a[i - 1] === ' ' ? 620 : 450;
  if (ap && ap.includes(q)) return 420;

  const ps = q.split(' ').filter(Boolean);
  if (ps.length > 1 && ps.every((x) => a.includes(x) || ap.includes(x))) return 300;
  return 0;
}

// Desempate por qualidade do veículo: entre casamentos de força parecida, quem
// busca "computational linguistics" quer o A1 antes do A6. O bônus é pequeno de
// propósito — reordena dentro de uma faixa, nunca entre faixas.
function bonusEstrato(v) {
  const i = ESTRATOS.indexOf(v.e || '');
  return i < 0 ? 0 : (8 - i) * 7;
}

function aplicar() {
  const e = estado();
  const q = norm(e.q);
  let rs = [];

  for (const v of BASE.veiculos) {
    if (e.tipo !== 'todos' && v.t !== e.tipo) continue;
    if (e.estratos.size && !e.estratos.has(v.e)) continue;
    // O indicador: percentil para periódico, h5 para evento.
    const ind = v.i;
    if (!Number.isNaN(e.min) && (ind == null || ind < e.min)) continue;
    if (!Number.isNaN(e.max) && (ind == null || ind > e.max)) continue;
    if (q) {
      const p = pontuar(v, q);
      if (!p) continue;
      rs.push([p + bonusEstrato(v), v]);
    } else {
      rs.push([0, v]);
    }
  }

  const cmpNome = (a, b) => a[1].n.localeCompare(b[1].n, 'pt');
  const ord = {
    relevancia: (a, b) => b[0] - a[0] || cmpNome(a, b),
    estrato: (a, b) => (a[1].e || 'Z').localeCompare(b[1].e || 'Z') || cmpNome(a, b),
    indicador: (a, b) => (b[1].i ?? -1) - (a[1].i ?? -1) || cmpNome(a, b),
    nome: cmpNome,
    // Estado de abertura: periódicos primeiro, depois eventos, cada grupo em
    // ordem alfabética. Em ordem puramente alfabética a primeira tela ficava
    // tomada por conferências da ACM e da AAAI, e o site parecia ser só de
    // eventos. Vale só quando não há busca nem ordenação escolhida.
    inicial: (a, b) =>
      (a[1].t === 'p' ? 0 : 1) - (b[1].t === 'p' ? 0 : 1) || cmpNome(a, b),
  };
  const criterio = e.ordem !== 'relevancia' ? e.ordem : (q ? 'relevancia' : 'inicial');
  rs.sort(ord[criterio]);

  filtrados = rs.map(([, v]) => v);
  limite = 80;
  desenhar();
}

/* --------------------------------------------------------------- lista --- */

function chip(e, extra = '') {
  if (!e) return `<span class="e e--v ${extra}">—</span>`;
  return `<span class="e ${extra}" data-e="${e}">${e}</span>`;
}

function desenhar() {
  const lista = $('#lista');
  const n = filtrados.length;
  $('#contagem').textContent = n.toLocaleString('pt-BR');

  // O rótulo acompanha o filtro de tipo: dizer "periódicos e eventos" com o
  // filtro em "Periódicos" seria falso.
  const tipo = new FormData($('#form-filtros')).get('tipo');
  const um = n === 1;
  $('#rotulo-tipo').textContent =
    tipo === 'p' ? (um ? 'periódico' : 'periódicos')
    : tipo === 'e' ? (um ? 'evento' : 'eventos')
    : (um ? 'periódico ou evento' : 'periódicos e eventos');

  if (!n) {
    lista.innerHTML = `<div class="vazio">
      <h2>Nada encontrado</h2>
      <p>Tente outra grafia, a sigla, ou limpe os filtros.<br>
      Se o veículo existe e não está aqui, ele pode estar fora da nossa base —
      o que não é o mesmo que não ser classificável.</p></div>`;
    return;
  }

  const parte = filtrados.slice(0, limite);
  lista.innerHTML = parte.map((v) => {
    const ind = v.i == null ? '—'
      : v.t === 'p' ? `${v.i.toFixed(0)}<small style="opacity:.6">%</small>`
      : `h5 ${v.i}`;
    return `<button class="item" data-slug="${v.s}" aria-current="${v.s === atual}">
      ${chip(v.e)}
      <span class="item__nome">
        <b>${v.g ? `${esc(v.g)} · ` : ''}${esc(v.n)}</b>
        ${v.g && v.a ? `<small>${esc(v.a.split(' · ')[0])}</small>` : ''}
      </span>
      <span class="item__ind">${ind}</span>
      <span class="item__tipo">${v.t === 'p' ? 'periódico' : 'evento'}</span>
    </button>`;
  }).join('');

  if (n > limite) {
    lista.insertAdjacentHTML('beforeend',
      `<div style="padding:.8rem 1rem"><button class="btn" id="mais">
        Mostrar mais ${Math.min(200, n - limite)} de ${(n - limite).toLocaleString('pt-BR')}
      </button></div>`);
    $('#mais').onclick = () => { limite += 200; desenhar(); };
  }
}

/* -------------------------------------------------------------- detalhe -- */

function passos(d) {
  // O chip só aparece quando o estrato MUDA. Repetir "A1" em cada linha do
  // recibo não informa nada e polui — o que interessa é onde a conta virou.
  let anterior = null;
  return d.passos.map((p, i) => {
    const mudou = p.estrato !== anterior;
    const saldo = p.estrato
      ? (mudou ? chip(p.estrato) : '<span style="color:var(--txt-3);font-size:.8rem">sem mudança</span>')
      : '<span style="color:var(--txt-3);font-size:.8rem">—</span>';
    anterior = p.estrato;
    return `<div class="passo">
      <span class="passo__n">${i + 1}</span>
      <span>
        <span class="passo__r">${esc(p.rotulo)}</span>
        <span class="passo__d">${esc(p.detalhe)}</span>
        ${p.fonte ? `<span class="passo__f">${esc(p.fonte)}</span>` : ''}
      </span>
      <span>${saldo}</span>
    </div>`;
  }).join('');
}

function regua(d) {
  if (d.percentil == null && d.h5 == null) return '';
  const serie = d.tipo === 'periodico' ? BASE.dist.percentis : BASE.dist.h5;
  const valor = d.tipo === 'periodico' ? d.percentil : d.h5;
  let menores = 0;
  for (const x of serie) { if (x < valor) menores++; else break; }
  const pos = serie.length ? (100 * menores) / serie.length : 0;
  // A faixa colorida É a escala de percentil (8 faixas de 12,5%). Para evento
  // isso não vale: h5 não é percentil, e pintar o h5 sobre faixas de percentil
  // colocaria o marcador numa cor que não é a do estrato dele. Então a régua de
  // evento usa os cortes de h5 reais como escala.
  const cortesH5 = [0, 6, 9, 12, 15, 20, 25, 35];
  let p, escala;
  if (d.tipo === 'periodico') {
    p = valor;
    escala = [0, 25, 50, 75, 100].map((x) => `<span>${x}</span>`).join('');
  } else {
    // Posição do h5 dentro das 8 faixas, cada uma ocupando 12,5% da largura.
    let f = 0;
    while (f < 7 && valor >= cortesH5[f + 1]) f++;
    const ini = cortesH5[f], fim = f === 7 ? Math.max(50, valor) : cortesH5[f + 1];
    p = (f + (fim > ini ? (valor - ini) / (fim - ini) : 0)) * 12.5;
    escala = cortesH5.map((x, i) => `<span>${i === 7 ? '35+' : x}</span>`).join('');
  }
  const nota = d.tipo === 'periodico'
    ? `Percentil ${valor.toFixed(0)} — acima de ${menores} dos ${serie.length} periódicos da base.`
    : `h5 ${valor} — acima de ${menores} dos ${serie.length} eventos com h5 no Scholar.`;
  return `<div class="cartao">
    <h3>${d.tipo === 'periodico' ? 'Percentil no Scopus' : 'h5 no Google Scholar'}</h3>
    <div class="regua"><i style="--p:${Math.max(0, Math.min(100, p))}"></i></div>
    <div class="regua-esc">${escala}</div>
    <p style="font-size:.74rem;color:var(--txt-3);margin-block-start:.4rem">${nota}</p>
    ${d.fronteira ? `<p class="fronteira"><b>Na fronteira:</b> ${esc(d.fronteira)}.
       Confira na fonte antes de decidir.</p>` : ''}
  </div>`;
}

function simulador(d) {
  const base = d.estrato_base || d.estrato;
  if (!base) return '';
  const i = ESTRATOS.indexOf(base) + 1;
  if (i < 1) return '';

  const linhas = [];

  // A classificação da CE-SBC NÃO é pergunta: vem da planilha das Comissões
  // Especiais e já está aplicada. Mostramos qual é, e deixamos trocar só para
  // quem quiser ver o efeito de outra — não para o usuário informar o dado.
  if (d.tipo === 'evento') {
    const atual = d.ce_sbc || 'relevante';
    const op = (v, r) => `<label class="${v === atual ? 'sim--atual' : ''}">
        <input type="radio" name="ce" value="${v}" ${v === atual ? 'checked' : ''}>
        ${r}${v === atual ? ' <b>· classificação real</b>' : ''}</label>`;
    linhas.push(op('top10', 'Top 10 da CE-SBC (+2 níveis)'));
    linhas.push(op('top20', 'Top 20 da CE-SBC (+1 nível)'));
    linhas.push(op('relevante', 'Relevante para a CE (mantém o h5)'));
  } else if (d.e_sbc) {
    linhas.push(`<label><input type="checkbox" name="sbc">
      Análise qualitativa como periódico de sociedade científica (até +2)</label>`);
  }

  // O FWCI é o único ajuste que depende do ARTIGO, não do veículo — por isso
  // é o único que faz sentido perguntar.
  linhas.push(`<label><input type="checkbox" name="fwci">
    Meu artigo entre os 5% de maior FWCI (+1 nível)</label>`);

  return `<form class="cartao sim" id="sim" data-base="${i}" data-tipo="${d.tipo}">
    <h3>E se?</h3>
    <p class="sim__ajuda">Partindo de <b>${base}</b>, que é o que o
      ${d.tipo === 'evento' ? 'h5' : 'percentil'} dá sozinho.</p>
    ${linhas.join('')}
    <p class="sim__ajuda" style="margin-block:.5rem 0">O FWCI é do artigo, não do
      veículo: só existe depois de publicado, e quem fornece o valor é a CAPES.
      É o único ajuste que não dá para saber de antemão.</p>
    <div class="sim__saida"><output id="sim-txt"></output>
      <span id="sim-chip">${chip(base)}</span></div>
  </form>`;
}

function ligarSim() {
  const f = $('#sim');
  if (!f) return;
  const base = +f.dataset.base;
  const evento = f.dataset.tipo === 'evento';

  const calc = () => {
    const d = new FormData(f);
    const notas = [];
    let n = base;

    let ganho = 0;
    if (evento) {
      const ce = d.get('ce');
      if (ce === 'top10') { ganho = 2; notas.push('Top 10 (+2)'); }
      else if (ce === 'top20') { ganho = 1; notas.push('Top 20 (+1)'); }
    } else if (d.get('sbc')) {
      ganho = 2; notas.push('sociedade científica (+2)');
    }
    if (ganho) {
      const promovido = Math.max(1, base - ganho);
      // O teto de A3 vale para o ganho qualitativo de EVENTO. O bônus de
      // periódico de sociedade científica é regra separada e não tem teto.
      n = evento ? Math.min(base, Math.max(promovido, 3)) : promovido;
      if (evento && n !== promovido) notas.push('saturação em A3');
    }

    if (d.get('fwci')) {
      if (n > 3) { n = Math.max(1, n - 1); notas.push('FWCI (+1)'); }
      else notas.push('FWCI não se aplica a partir de A3');
    }

    n = Math.min(8, Math.max(1, n));
    const e = ESTRATOS[n - 1];
    $('#sim-chip').innerHTML = chip(e);
    $('#sim-txt').textContent = notas.length
      ? `${ESTRATOS[base - 1]} → ${e} · ${notas.join(', ')}`
      : `${e} — sem ajustes`;
  };

  f.addEventListener('change', calc);
  calc();
}

function falhaNoPainel(slug, erro) {
  // Antes, qualquer exceção aqui deixava o painel mudo e o clique parecia
  // não funcionar. Um erro de dado tem que aparecer, não sumir.
  console.error('[qualis] falha ao abrir', slug, erro);
  const det = $('#det');
  $('#det-tit').innerHTML = '<h2>Não foi possível abrir</h2>';
  $('#det-chip').innerHTML = '';
  $('#det-corpo').innerHTML = `<div class="cartao">
    <p>Algo deu errado ao montar esta ficha.</p>
    <p class="sim__ajuda">${esc(String(erro && erro.message || erro))}</p>
    <p class="sim__ajuda">Veículo: <code>${esc(slug)}</code></p></div>`;
  det.dataset.aberto = '1';
  det.setAttribute('aria-hidden', 'false');
}

async function abrir(slug) {
  atual = slug;
  let d;
  try {
    d = await ficha(slug);
  } catch (e) {
    return falhaNoPainel(slug, e);
  }
  const det = $('#det');

  $('#det-tit').innerHTML = `<h2>${d.sigla ? `${esc(d.sigla)} · ` : ''}${esc(d.nome)}</h2>
    <p>${d.tipo === 'periodico' ? 'Periódico' : 'Evento'}${d.ce_sbc ? ` · CE-SBC: ${esc(d.ce_sbc)}` : ''}${d.ces?.length ? ` · ${esc(d.ces.join(', '))}` : ''}</p>`;
  $('#det-chip').innerHTML = chip(d.estrato, 'e--g');

  $('#det-corpo').innerHTML = `
    <div class="cartao">
      <h3>Como chegamos nesse estrato</h3>
      ${passos(d)}
      <div class="total"><span>Resultado</span>${chip(d.estrato)}</div>
      ${d.ambiguo && d.entradas?.length ? `<div class="bifurca">
        <b>Este evento aparece ${d.entradas.length} vezes no Google Scholar</b>
        <p>Em português e em inglês, com as citações divididas entre as duas
           entradas. Usamos a de maior h5.</p>
        <ul>${d.entradas.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>` : ''}
    </div>
    ${d.oficial_estrato ? `<div class="cartao">
      <h3>Classificação oficial da CAPES</h3>
      <div class="oficial"><span>Qualis Eventos ${esc(d.sigla)} — ciclo 2021-2024</span>
        ${chip(d.oficial_estrato)}</div>
      <p class="sim__ajuda">Publicado como <b>${esc(d.oficial_original)}</b> na escala
        antiga (A1–A4, B1–B4), que tem os mesmos oito degraus e os mesmos cortes de h5.
        É do ciclo anterior — não vale para 2025-2028, mas é a única classificação
        oficial de eventos que existe.</p></div>` : ''}
    ${regua(d)}
    ${simulador(d)}
    <p class="aviso-legal">Somente uma <b>estimativa do estrato</b>, com base nos
      critérios do documento da Área 02 — Computação, divulgado pela CAPES em 2025.
      Não nos responsabilizamos por incompatibilidade com a decisão da comissão.</p>`;

  try {
    ligarSim();
  } catch (e) {
    return falhaNoPainel(slug, e);
  }
  det.dataset.aberto = '1';
  det.setAttribute('aria-hidden', 'false');
  $('#det-x').focus();
  history.replaceState(null, '', `?v=${slug}`);
  desenhar();
}

function fechar() {
  atual = null;
  const det = $('#det');
  det.dataset.aberto = '0';
  det.setAttribute('aria-hidden', 'true');
  history.replaceState(null, '', location.pathname);
  desenhar();
}

/* ----------------------------------------------------------------- init -- */

addEventListener('DOMContentLoaded', async () => {
  try {
    await carregar();
  } catch (e) {
    console.error('[qualis]', e);
    $('#lista').innerHTML = `<div class="vazio"><h2>Não foi possível carregar a base</h2>
      <p>${esc(e.message)}</p><p>Se estiver rodando local, confira se o servidor
      está de pé na pasta <code>site/dist</code>.</p></div>`;
    return;
  }

  // O documento define DOIS indicadores, não um genérico: percentil para
  // periódico, h5 para evento. O rótulo do campo segue o tipo escolhido, em vez
  // de inventar um nome guarda-chuva que não existe na regra.
  const rotularFaixa = () => {
    const t = new FormData($('#form-filtros')).get('tipo');
    const r = $('#rot-faixa'), a = $('#ajuda-faixa');
    if (t === 'p') { r.textContent = 'Percentil'; a.textContent = 'Posição do periódico no Scopus, de 0 a 100.'; }
    else if (t === 'e') { r.textContent = 'h5-index'; a.textContent = 'h5 do evento no Google Scholar.'; }
    else { r.textContent = 'Percentil e h5'; a.textContent = 'Periódico vai por percentil (0–100), evento por h5.'; }
  };

  const rodar = () => { rotularFaixa(); aplicar(); };
  let t;
  $('#q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(rodar, 80); });
  $('#form-filtros').addEventListener('change', rodar);
  $('#ordem').addEventListener('change', rodar);
  $('#limpar').addEventListener('click', () => {
    $('#form-filtros').reset(); $('#q').value = ''; rodar();
  });
  $('#q-x').addEventListener('click', () => { $('#q').value = ''; $('#q').focus(); rodar(); });

  if (BASE.snapshot) {
    const el = $('#snapshot');
    if (el) el.textContent = BASE.snapshot;
  }

  // A marca no canto esquerdo devolve o estado inicial sem recarregar: fecha a
  // ficha, limpa busca e filtros, volta a ordenação e sobe a lista.
  $('#ir-inicio').addEventListener('click', () => {
    if (atual) fechar();
    $('#form-filtros').reset();
    $('#q').value = '';
    $('#ordem').value = 'relevancia';
    history.replaceState(null, '', location.pathname);
    rodar();
    $('.rolo').scrollTop = 0;
    if (matchMedia('(pointer: fine)').matches) $('#q').focus();
  });

  $('#lista').addEventListener('click', (e) => {
    const b = e.target.closest('[data-slug]');
    if (b) abrir(b.dataset.slug);
  });
  $('#det-x').addEventListener('click', fechar);
  $('#fundo-modal').addEventListener('click', fechar);
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && atual) fechar();
    if (e.key === '/' && document.activeElement !== $('#q')) { e.preventDefault(); $('#q').focus(); }
  });

  const par = new URLSearchParams(location.search);
  const q = par.get('q');
  if (q) $('#q').value = q;
  aplicar();

  // Foco no campo de busca ao abrir: quem chega aqui quer digitar um nome.
  // Só em ponteiro fino (mouse/trackpad) — no celular, focar sozinho abre o
  // teclado, come metade da tela e esconde a lista antes de a pessoa ver o que
  // o site é.
  const podeFocar = matchMedia('(pointer: fine)').matches;
  if (q || podeFocar) $('#q').focus();
  const v = par.get('v');
  if (v) abrir(v);
});
