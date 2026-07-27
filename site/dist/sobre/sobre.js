/* Página "sobre" — melhoria progressiva apenas.
 *
 * Tudo aqui é HTML estático: a tabela de estratos, os critérios, as fontes. O
 * JS só acende a faixa da régua correspondente à linha sob o cursor. Sem ele,
 * a página continua completa — que é o que importa para quem chega pelo
 * buscador. */

const regua = document.querySelector('#regua');
const foco = document.querySelector('.doc__regua-foco');
const tab = document.querySelector('#tab');

if (regua && foco && tab) {
  const realcar = (tr) => {
    if (!tr) { regua.removeAttribute('data-ativo'); return; }
    foco.style.setProperty('--ini', tr.style.getPropertyValue('--ini'));
    foco.style.setProperty('--fim', tr.style.getPropertyValue('--fim'));
    regua.dataset.ativo = '1';
  };
  tab.addEventListener('pointerover', (e) => realcar(e.target.closest('tr')));
  tab.addEventListener('focusin', (e) => realcar(e.target.closest('tr')));
  tab.addEventListener('pointerleave', () => realcar(null));
}
