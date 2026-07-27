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
console.log('atalhos escondidos sem flag:', await p.isHidden('#atalhos'));
await p.goto('http://localhost:8080/?flag=subareas', { waitUntil: 'networkidle' });
await p.waitForTimeout(600);
console.log('com ?flag=subareas ->', (await p.textContent('#atalhos')).replace(/\s+/g,' ').slice(0, 90));
await b.close();
