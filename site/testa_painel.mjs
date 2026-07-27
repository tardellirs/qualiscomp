// Executa passos/regua/simulador de app.js contra TODAS as fichas geradas,
// sem navegador. O bug do `esc` sombreado só aparecia em fichas com fronteira.
import fs from 'fs';
import path from 'path';

let src = fs.readFileSync('site/app/app.js', 'utf8');
src = src.replace(/addEventListener\('DOMContentLoaded'[\s\S]*$/, '');
src = src.replace(/^const \$ =.*$/m, 'const $ = () => ({ innerHTML: "", textContent: "", dataset: {}, setAttribute(){}, focus(){}, addEventListener(){}, querySelector(){ return null; } });');
src += '\nexport { passos, regua, simulador, chip, pontuar };\n';
src += '\nexport function _setBase(b) { BASE = b; }\n';
const mod = await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));

const idx = JSON.parse(fs.readFileSync('site/dist/dados/indice.json', 'utf8'));
mod._setBase(idx);

const dir = 'site/dist/dados/v';
let ok = 0; const erros = [];
for (const f of fs.readdirSync(dir)) {
  const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  try {
    mod.passos(d); mod.regua(d); mod.simulador(d);
    ok++;
  } catch (e) {
    erros.push([f, e.message]);
  }
}
console.log(`fichas montadas sem erro: ${ok} | falharam: ${erros.length}`);
for (const [f, m] of erros.slice(0, 8)) console.log('   ', f, '->', m);
process.exit(erros.length ? 1 : 0);
