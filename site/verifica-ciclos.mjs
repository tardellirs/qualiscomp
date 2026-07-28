/* O histórico agora é o Qualis oficial de cada ciclo, não o percentil. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
for (const nome of ['IEEE Access', 'Computer', 'Journal of Machine Learning Research']) {
  await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
  await p.fill('#q', nome); await p.waitForTimeout(400);
  await p.click('.item'); await p.waitForTimeout(600);
  const c = await p.evaluate(() => {
    const el = [...document.querySelectorAll('.cartao')]
      .find(x => x.querySelector('h3')?.textContent.includes('classificou antes'));
    if (!el) return '(sem histórico)';
    return [...el.querySelectorAll('.ciclo')]
      .map(x => x.textContent.replace(/\s+/g, ' ').trim()).join('  ');
  });
  console.log(nome.padEnd(42), c);
}
await b.close();
