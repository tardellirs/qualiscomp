/* Tema: automático (segue o sistema), claro ou escuro.
 *
 * Não é módulo e roda antes do resto de propósito: aplicado depois da primeira
 * pintura, o tema causaria um flash da cor errada. Por isso este arquivo é
 * pequeno e síncrono, no <head>.
 *
 * O padrão continua sendo seguir o sistema. A escolha manual existe porque o
 * uso em projetor pede claro mesmo com o sistema no escuro. */
(function () {
  var CHAVE = 'qualiscomp:tema';
  var CICLO = ['auto', 'claro', 'escuro'];

  function aplicar(t) {
    var raiz = document.documentElement;
    if (t === 'auto') raiz.removeAttribute('data-theme');
    else raiz.setAttribute('data-theme', t === 'claro' ? 'light' : 'dark');
    raiz.dataset.tema = t;
  }

  var atual = 'auto';
  try { atual = localStorage.getItem(CHAVE) || 'auto'; } catch (e) {}
  if (CICLO.indexOf(atual) < 0) atual = 'auto';
  aplicar(atual);

  addEventListener('DOMContentLoaded', function () {
    var b = document.getElementById('tema');
    if (!b) return;
    var rotulo = { auto: 'tema do sistema', claro: 'tema claro', escuro: 'tema escuro' };
    function rotular() { b.setAttribute('aria-label', 'Tema: ' + rotulo[atual] + '. Clique para alternar.'); }
    rotular();
    b.addEventListener('click', function () {
      atual = CICLO[(CICLO.indexOf(atual) + 1) % CICLO.length];
      aplicar(atual);
      rotular();
      try { localStorage.setItem(CHAVE, atual); } catch (e) {}
    });
  });
})();
