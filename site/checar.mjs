/* Abre o site em vários tamanhos de tela, tira print e reporta problemas.
 *
 * Existe porque erro de layout não aparece em teste de dados: já publiquei duas
 * vezes uma página quebrada por não conseguir vê-la. Aqui o navegador de
 * verdade mede o que os testes de CSS não alcançam — rolagem horizontal,
 * elementos fora da tela, alvos de toque pequenos demais, erro de console.
 *
 *   node site/checar.mjs [url]        (padrão: http://localhost:8080)
 */

import { chromium, devices } from 'playwright';
import fs from 'fs';

const BASE = process.argv[2] || 'http://localhost:8080';
const SAIDA = 'site/prints';
const ALVO_TOQUE = 40; // px; o ideal é 44, mas 40 já é utilizável

const TELAS = [
  { nome: 'celular',        viewport: { width: 390, height: 844 },  movel: true },
  { nome: 'celular-pequeno',viewport: { width: 320, height: 640 },  movel: true },
  { nome: 'tablet-retrato', viewport: { width: 768, height: 1024 }, movel: true },
  { nome: 'tablet-paisagem',viewport: { width: 1024, height: 768 }, movel: true },
  { nome: 'desktop',        viewport: { width: 1440, height: 900 }, movel: false },
];

const PAGINAS = [
  { nome: 'busca', url: '/' },
  { nome: 'sobre', url: '/sobre/' },
  { nome: 'ficha', url: '/?v=e-sbes' },
];

async function medir(page) {
  return page.evaluate((ALVO) => {
    const doc = document.documentElement;
    const vw = doc.clientWidth;

    // Elementos que estouram a largura da tela.
    const estouros = [];
    for (const el of document.querySelectorAll('body *')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      const est = getComputedStyle(el);
      if (est.position === 'fixed' && est.visibility === 'hidden') continue;
      if (r.right > vw + 1 || r.left < -1) {
        // Ignora o que está intencionalmente fora da tela: a gaveta de filtros
        // e o painel de detalhe ficam deslocados quando fechados, e os filhos
        // deles herdam a posição sem ter translate próprio.
        if (el.closest('.lado, .det, .fundo-modal')) continue;
        // Conteúdo dentro de um rolador horizontal intencional (uma tabela
        // larga, por exemplo) pode passar da tela: quem rola é o contêiner.
        let anc = el.parentElement, dentroDeRolador = false;
        while (anc && anc !== document.body) {
          const ox = getComputedStyle(anc).overflowX;
          if (ox === 'auto' || ox === 'scroll') { dentroDeRolador = true; break; }
          anc = anc.parentElement;
        }
        if (dentroDeRolador) continue;
        estouros.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className || '').toString().slice(0, 40),
          left: Math.round(r.left), right: Math.round(r.right),
        });
      }
    }

    // Alvos de toque pequenos entre os elementos interativos visíveis.
    const pequenos = [];
    for (const el of document.querySelectorAll('a,button,input,select,label,[role=option]')) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const ce = getComputedStyle(el);
      if (ce.visibility === 'hidden') continue;
      // Controles escondidos atrás de um <label> estilizado: quem recebe o
      // toque é o label, não o input.
      if (ce.opacity === '0' || ce.pointerEvents === 'none') continue;
      // Link dentro de parágrafo não precisa de 44px: o alvo é a linha de texto.
      if (el.tagName === 'A' && el.closest('p, li')) continue;
      if (r.height < ALVO || r.width < ALVO) {
        pequenos.push({
          tag: el.tagName.toLowerCase(),
          cls: (el.className || '').toString().slice(0, 34),
          w: Math.round(r.width), h: Math.round(r.height),
        });
      }
    }

    return {
      rolagemHorizontal: doc.scrollWidth > vw + 1,
      scrollWidth: doc.scrollWidth,
      clientWidth: vw,
      estouros: estouros.slice(0, 8),
      pequenos: pequenos.slice(0, 10),
      texto: (document.body.innerText || '').length,
    };
  }, ALVO_TOQUE);
}

const navegador = await chromium.launch();
fs.mkdirSync(SAIDA, { recursive: true });
let problemas = 0;

for (const tela of TELAS) {
  const ctx = await navegador.newContext({
    viewport: tela.viewport,
    deviceScaleFactor: 2,
    isMobile: tela.movel,
    hasTouch: tela.movel,
    userAgent: tela.movel ? devices['iPhone 13'].userAgent : undefined,
  });

  for (const pag of PAGINAS) {
    const page = await ctx.newPage();
    const erros = [];
    page.on('console', (m) => m.type() === 'error' && erros.push(m.text()));
    page.on('pageerror', (e) => erros.push(String(e)));

    await page.goto(BASE + pag.url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);

    const m = await medir(page);
    const arq = `${SAIDA}/${tela.nome}-${pag.nome}.png`;
    await page.screenshot({ path: arq, fullPage: pag.nome === 'sobre' });

    const ruim = m.rolagemHorizontal || m.estouros.length || erros.length;
    if (ruim) problemas++;
    console.log(`\n${ruim ? '✗' : '✓'} ${tela.nome} · ${pag.nome}  (${tela.viewport.width}px)`);
    if (m.rolagemHorizontal)
      console.log(`    rolagem horizontal: ${m.scrollWidth} > ${m.clientWidth}`);
    for (const e of m.estouros)
      console.log(`    estoura: <${e.tag} class="${e.cls}"> ${e.left}..${e.right}`);
    for (const e of erros.slice(0, 3)) console.log(`    console: ${e.slice(0, 110)}`);
    if (tela.movel && m.pequenos.length)
      console.log(`    alvos < ${ALVO_TOQUE}px: ` +
        m.pequenos.map((p) => `${p.tag}.${p.cls.split(' ')[0]}(${p.w}x${p.h})`).join(', '));

    await page.close();
  }
  await ctx.close();
}

await navegador.close();
console.log(`\nprints em ${SAIDA}/  |  telas com problema: ${problemas}`);
process.exit(problemas ? 1 : 0);
