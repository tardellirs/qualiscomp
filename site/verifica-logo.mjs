/* A marca precisa mesmo devolver o estado inicial. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(400);
const estado = async () => ({
  q: await p.inputValue('#q'),
  n: (await p.textContent('#contagem')).trim(),
  ficha: await p.getAttribute('#det', 'data-aberto'),
  url: new URL(p.url()).search || '(limpa)',
});
console.log('inicial  ', await estado());
await p.fill('#q', 'sbes');
await p.click('.segm span:text-is("Eventos")');
await p.click('.estratos span:text-is("A3")');
await p.waitForTimeout(400);
await p.click('.item');
await p.waitForTimeout(600);
console.log('sujo     ', await estado());
await p.click('#ir-inicio');
await p.waitForTimeout(600);
console.log('após clique', await estado());
await b.close();
