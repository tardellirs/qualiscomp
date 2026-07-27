import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(400);
for (const q of ['0164-0925', '01640925', '1532-4435', '2169-3536']) {
  await p.fill('#q', q); await p.waitForTimeout(350);
  const n = (await p.textContent('#contagem')).trim();
  const primeiro = await p.textContent('.item .item__nome b').catch(() => '(nada)');
  console.log(`${q.padEnd(11)} -> ${n} | ${primeiro.slice(0, 52)}`);
}
await b.close();
