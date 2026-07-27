/* Subáreas: aparecem só em Eventos, aceitam múltipla escolha, mostram o nome
   por extenso no hover, e cedem o lugar da tabela de cortes. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/?flag=subareas', { waitUntil: 'networkidle' });
await p.waitForTimeout(600);

const est = async () => ({
  subareas: await p.isVisible('#subareas'),
  cortes: await p.isVisible('#regras'),
  n: (await p.textContent('#contagem')).trim(),
});
console.log('Tudo       ', await est());
await p.click('.segm span:text-is("Periódicos")'); await p.waitForTimeout(300);
console.log('Periódicos ', await est());
await p.click('.segm span:text-is("Eventos")'); await p.waitForTimeout(400);
console.log('Eventos    ', await est());

const chips = await p.$$eval('#subareas-grade .atalho',
  els => els.slice(0, 4).map(e => ({ txt: e.textContent.trim(), title: e.title })));
console.log('primeiras pastilhas:', chips.map(c => `${c.txt} → "${c.title}"`).join(' | '));

await p.click('#subareas-grade .atalho[data-ce]'); await p.waitForTimeout(350);
const um = (await p.textContent('#contagem')).trim();
const alvos = await p.$$('#subareas-grade .atalho');
await alvos[1].click(); await p.waitForTimeout(350);
const dois = (await p.textContent('#contagem')).trim();
console.log(`uma subárea: ${um} -> duas (união): ${dois}`);

await p.click('.segm span:text-is("Tudo")'); await p.waitForTimeout(400);
console.log('voltando a Tudo', await est());
await b.close();
