/* Na abertura, as primeiras linhas devem ser periódicos da área de Computação. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(500);
const r = await p.evaluate(async () => {
  const d = await (await fetch('dados/indice.json')).json();
  const porSlug = new Map(d.veiculos.map(v => [v.s, v]));
  return [...document.querySelectorAll('.item')].slice(0, 20)
    .map(el => porSlug.get(el.dataset.slug))
    .map(v => ({ n: v.n.slice(0, 34), tipo: v.t, comp: !!v.k }));
});
const comp = r.filter(x => x.comp).length;
console.log(`primeiras 20: ${comp} de Computação, ${r.filter(x=>x.tipo==='p').length} periódicos`);
r.slice(0, 6).forEach(x => console.log(`   ${x.comp ? 'COMP' : 'outra'}  ${x.n}`));
await b.close();
process.exit(comp >= 18 ? 0 : 1);
