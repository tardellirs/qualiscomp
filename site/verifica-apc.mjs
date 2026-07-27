/* A marca de APC precisa aparecer na lista, filtrar, e explicar na ficha. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(500);
console.log('total          ', (await p.textContent('#contagem')).trim());
await p.check('input[name="soapc"]'); await p.waitForTimeout(400);
console.log('só com APC     ', (await p.textContent('#contagem')).trim());
console.log('tags visíveis  ', await p.locator('.tag-apc').count());
await p.uncheck('input[name="soapc"]');
await p.fill('#q', 'IEEE Access'); await p.waitForTimeout(400);
await p.click('.item'); await p.waitForTimeout(700);
const c = await p.evaluate(() => {
  const el = document.querySelector('.cartao--apc');
  return el ? el.textContent.replace(/\s+/g, ' ').trim().slice(0, 150) : '(sem cartão)';
});
console.log('\nficha:', c);
await b.close();
