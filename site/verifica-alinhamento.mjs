/* Todo bloco da /sobre/ tem que começar e terminar na mesma coluna. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/sobre/', { waitUntil: 'networkidle' });
const r = await p.evaluate(() => {
  // Só blocos de primeiro nível: o que está dentro de cartão tem recuo próprio
  // e não deve alinhar com a coluna.
  const alvos = ['h1', '.doc__abre', '.doc__indice', '#mudou > h2', '#mudou > p',
                 '#tabela > p', '.doc__cita', '.doc__h3', '.doc__coment',
                 '#perguntas > h2', '.doc__links', '.doc__rodape > p'];
  return alvos.map((s) => {
    const el = document.querySelector(s);
    if (!el) return { s, falta: true };
    const b = el.getBoundingClientRect();
    return { s, esq: Math.round(b.left), dir: Math.round(b.right) };
  });
});
const esq = new Set(r.filter(x => !x.falta).map(x => x.esq));
const dir = new Set(r.filter(x => !x.falta).map(x => x.dir));
for (const x of r) console.log(`  ${String(x.s).padEnd(16)} ${x.falta ? 'AUSENTE' : `${x.esq} .. ${x.dir}`}`);
console.log(`\nbordas esquerdas distintas: ${[...esq].join(', ')}`);
console.log(`bordas direitas distintas:  ${[...dir].join(', ')}`);
console.log(esq.size === 1 && dir.size === 1 ? '\nalinhado' : '\nDESALINHADO');
process.exit(esq.size === 1 && dir.size === 1 ? 0 : 1);
