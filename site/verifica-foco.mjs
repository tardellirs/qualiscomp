// Confere onde o foco cai ao abrir, com e sem toque.
import { chromium, devices } from 'playwright';
const b = await chromium.launch();
for (const [nome, ctxOpts] of [
  ['desktop', { viewport: { width: 1440, height: 900 } }],
  ['celular', { ...devices['iPhone 13'] }],
]) {
  const ctx = await b.newContext(ctxOpts);
  const p = await ctx.newPage();
  await p.goto('http://localhost:8080/', { waitUntil: 'networkidle' });
  await p.waitForTimeout(500);
  const foco = await p.evaluate(() => {
    const a = document.activeElement;
    return { tag: a.tagName.toLowerCase(), id: a.id || '(sem id)' };
  });
  // digita sem clicar em nada
  await p.keyboard.type('sbes');
  await p.waitForTimeout(300);
  const valor = await p.inputValue('#q');
  const n = await p.textContent('#contagem');
  console.log(`${nome}: foco em <${foco.tag} id=${foco.id}> | digitou direto: ${valor ? `"${valor}" -> ${n} resultados` : 'não'}`);
  await ctx.close();
}
await b.close();
