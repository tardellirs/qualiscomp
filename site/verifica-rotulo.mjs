/* Confere que o rótulo da contagem acompanha o filtro de tipo.
   Clica no texto visível, não no radio — ele fica atrás do rótulo estilizado,
   que é justamente como o usuário interage. */
import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
await p.waitForTimeout(400);
const ler = async () => (await p.textContent('.barra span')).replace(/\s+/g, ' ').trim();

console.log('tudo       ->', await ler());
for (const [rotulo, nome] of [['Periódicos','periódicos'], ['Eventos','eventos'], ['Tudo','tudo']]) {
  await p.click(`.segm span:text-is("${rotulo}")`);
  await p.waitForTimeout(300);
  console.log(`${nome.padEnd(11)}->`, await ler());
}
await p.fill('#q', 'ACM Computing Surveys');
await p.waitForTimeout(400);
console.log('1 resultado->', await ler());
await b.close();
