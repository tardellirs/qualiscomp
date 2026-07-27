/* A série anual precisa aparecer, marcar o ano usado e o ano em curso. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/?v=p-journal-of-the-brazilian-computer-society',
             { waitUntil: 'networkidle' });
await p.waitForTimeout(900);
const r = await p.evaluate(() => {
  const anos = [...document.querySelectorAll('.serie__ano')].map(el => ({
    txt: el.textContent.replace(/\s+/g, ' ').trim(),
    usado: el.className.includes('usado'),
    curso: el.className.includes('curso'),
  }));
  return { anos, nota: document.querySelector('.serie')?.parentElement
    ?.querySelector('.sim__ajuda')?.textContent.replace(/\s+/g,' ').trim().slice(0,150) };
});
r.anos.forEach(a => console.log(`  ${a.txt.padEnd(16)} ${a.usado ? '← usado' : ''}${a.curso ? ' (em curso)' : ''}`));
console.log('\nnota:', r.nota);
await p.screenshot({ path: 'site/prints/serie-jbcs.png' });
await b.close();
