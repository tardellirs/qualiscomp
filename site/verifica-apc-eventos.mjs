/* APC é coisa de periódico. Ao trocar para Eventos o filtro tem que se
   desmarcar sozinho — senão a lista vem vazia sem dizer por quê. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const estado = () => p.evaluate(() => ({
  n: document.querySelector('#contagem')?.textContent.trim(),
  marcado: document.querySelector('input[name="soapc"]')?.checked,
  visivel: !document.querySelector('#caixa-apc')?.hidden,
}));
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(400);
console.log('inicial          ', JSON.stringify(await estado()));
await p.check('input[name="soapc"]'); await p.waitForTimeout(350);
console.log('APC marcado      ', JSON.stringify(await estado()));
await p.click('label:has(input[value="e"])'); await p.waitForTimeout(400);
console.log('-> Eventos       ', JSON.stringify(await estado()));
await p.click('label:has(input[value="p"])'); await p.waitForTimeout(400);
console.log('-> Periódicos    ', JSON.stringify(await estado()));
await b.close();
