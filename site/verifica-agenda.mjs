/* A agenda junta data e estrato. O prazo é a informação com consequência
   irreversível: precisa estar visível, correto e clicável para a fonte. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 1000 } });
const erros = [];
p.on('console', m => m.type() === 'error' && erros.push(m.text()));
await p.goto('http://localhost:8080/agenda/', { waitUntil: 'networkidle' });
console.log('título :', await p.title());
console.log('itens  :', await p.locator('.ag__it').count());
console.log('resumo :', (await p.locator('.ag__resumo').textContent().catch(() => '—')).trim());
console.log('\nprazos abertos:');
for (const el of await p.locator('.ag__prazo:not(.ag__prazo--fim)').all()) {
  const t = (await el.textContent()).replace(/\s+/g, ' ').trim();
  const perto = (await el.getAttribute('class')).includes('perto');
  console.log(`   ${perto ? '!' : ' '} ${t}  ->  ${await el.getAttribute('href')}`);
}
const est = await p.locator('.ag__estrato .e').count();
console.log(`\ncom estrato: ${est} de ${await p.locator('.ag__it').count()}`);
// o link do estrato leva à ficha?
const href = await p.locator('.ag__estrato .e').first().getAttribute('href');
console.log('link do estrato:', href);
console.log('erros de console:', erros.length ? erros : 'nenhum');
await p.screenshot({ path: 'site/prints/agenda.png', fullPage: false });
await b.close();
