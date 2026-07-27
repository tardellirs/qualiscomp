/* Ao abrir, a lista deve começar por periódicos. Buscar e ordenar seguem
   inalterados. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(500);

const tipos = async (n = 15) => p.evaluate((n) =>
  [...document.querySelectorAll('.item')].slice(0, n)
    .map(el => el.querySelector('.item__tipo').textContent.trim()), n);

const t = await tipos();
const per = t.filter(x => x === 'periódico').length;
console.log(`abertura: ${per}/${t.length} periódicos nas primeiras linhas`);
console.log('  primeiros:', (await p.evaluate(() =>
  [...document.querySelectorAll('.item .item__nome b')].slice(0, 4).map(e => e.textContent.trim()))).join(' | '));

await p.fill('#q', 'sbes'); await p.waitForTimeout(400);
console.log('busca "sbes":', (await p.textContent('#contagem')).trim(), '->',
  await p.textContent('.item .item__nome b'));

await p.fill('#q', ''); await p.waitForTimeout(400);
await p.selectOption('#ordem', 'estrato'); await p.waitForTimeout(400);
console.log('ordem por estrato:', (await p.evaluate(() =>
  [...document.querySelectorAll('.item .e')].slice(0, 3).map(e => e.textContent))).join(', '));

await p.selectOption('#ordem', 'relevancia'); await p.waitForTimeout(400);
const t2 = await tipos();
console.log(`voltando a relevância: ${t2.filter(x=>x==='periódico').length}/${t2.length} periódicos`);
process.exit(per >= 13 ? 0 : 1);
