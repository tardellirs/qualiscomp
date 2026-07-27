// Confere que a última linha da lista NÃO fica escondida atrás da pastilha.
import { chromium } from 'playwright';
const b = await chromium.launch();
for (const [nome, w, h] of [['celular',390,844],['desktop',1440,900]]) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(500);
  // rola a lista até o fim
  await p.evaluate(() => { const r = document.querySelector('.rolo'); r.scrollTop = r.scrollHeight; });
  await p.waitForTimeout(400);
  const r = await p.evaluate(() => {
    const itens = [...document.querySelectorAll('.item')];
    const ultimo = itens[itens.length - 1].getBoundingClientRect();
    const pil = document.querySelector('.desca a').getBoundingClientRect();
    return { ultimo: Math.round(ultimo.bottom), pilTopo: Math.round(pil.top), sobrepoe: ultimo.bottom > pil.top };
  });
  console.log(`${nome}: fim da última linha ${r.ultimo}px, topo da pastilha ${r.pilTopo}px -> ${r.sobrepoe ? 'SOBREPÕE' : 'ok, livre'}`);
  await p.screenshot({ path: `site/prints/${nome}-fim-da-lista.png` });
  await p.close();
}
await b.close();
