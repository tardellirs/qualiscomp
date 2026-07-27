import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(400);
const ler = () => p.evaluate(() => ({
  tema: document.documentElement.dataset.tema,
  attr: document.documentElement.getAttribute('data-theme') || '(nenhum)',
  texto: getComputedStyle(document.body).color,
  painel: getComputedStyle(document.querySelector('.cab')).borderBottomColor,
}));
console.log('inicial ', await ler());
for (let i = 0; i < 3; i++) {
  await p.click('#tema'); await p.waitForTimeout(250);
  console.log('clique  ', await ler());
}
await p.reload({ waitUntil: 'networkidle' }); await p.waitForTimeout(400);
console.log('persiste', await ler());
// Em "Tudo" as subáreas não aparecem — elas só valem para eventos. Quem cobre
// o comportamento completo é verifica-subareas.mjs.
console.log('subáreas escondidas fora de Eventos:', await p.isHidden('#subareas'));
await b.close();
