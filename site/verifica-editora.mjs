import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(500);
for (const q of ['MDPI', 'Springer', 'ACM', 'SBC']) {
  await p.fill('#q', q); await p.waitForTimeout(350);
  console.log(`busca "${q}": ${(await p.textContent('#contagem')).trim()} -> ` +
    (await p.textContent('.item .item__nome b')).slice(0, 40));
}
await p.fill('#q', 'IEEE Access'); await p.waitForTimeout(400);
await p.click('.item'); await p.waitForTimeout(700);
const d = await p.evaluate(() => ({
  meta: document.querySelector('#det-tit p').textContent.trim(),
  scopus: document.querySelector('.ver-fonte a')?.href || '(sem link)',
}));
console.log('\nficha:', d.meta);
console.log('link :', d.scopus);
await b.close();
