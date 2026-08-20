const API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend-738933484701.us-east1.run.app';

function escapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto;
  return div.innerHTML;
}

function formatarPagamento(pedido) {
  if (pedido.forma_pagamento === 'cartao') {
    return 'Cartão (maquininha na entrega)';
  }
  if (pedido.forma_pagamento === 'dinheiro') {
    return pedido.troco_para
      ? `Dinheiro (troco para R$ ${Number(pedido.troco_para).toFixed(2)})`
      : 'Dinheiro (sem troco)';
  }
  return 'Pix';
}
