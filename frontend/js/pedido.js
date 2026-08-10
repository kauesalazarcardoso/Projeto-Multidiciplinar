const API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend.onrender.com';
const TAXA_ENTREGA = 3.0;

let produtos     = [];
let complementos = [];
let mp           = null;

let carrinho = [];
const MAX_ACOMPANHAMENTOS = 4;

let mpOrderId          = null;
let cardBrickController = null;

function limitarAcompanhamentos(produtoId) {
  const checkboxes = document.querySelectorAll(`.check-${produtoId}`);
  const marcados   = Array.from(checkboxes).filter(c => c.checked).length;
  checkboxes.forEach(c => {
    if (!c.checked) c.disabled = marcados >= MAX_ACOMPANHAMENTOS;
  });
  const contador = document.getElementById(`contador-${produtoId}`);
  if (contador) {
    contador.textContent = marcados > 0
      ? `${marcados}/${MAX_ACOMPANHAMENTOS} escolhidos`
      : 'toque para escolher';
    contador.style.color = marcados >= MAX_ACOMPANHAMENTOS ? '#e74c3c' : '#888';
  }
}

function toggleOpcoes(produtoId) {
  const painel = document.getElementById(`opcoes-${produtoId}`);
  const seta   = document.getElementById(`seta-${produtoId}`);
  const abrir  = painel.style.display === 'none';
  painel.style.display = abrir ? 'flex' : 'none';
  seta.textContent = abrir ? '▴' : '▾';
}

function _opcaoComplemento(p, comp) {
  return `
    <label class="opcao-item">
      <span class="opcao-nome">
        <input type="checkbox" class="check-${p.id}" value="${comp.nome}" data-preco="${comp.preco}"
          onchange="limitarAcompanhamentos(${p.id})">
        ${comp.nome}
      </span>
      ${comp.preco > 0 ? `<span class="preco-extra">+R$ ${comp.preco.toFixed(2)}</span>` : ''}
    </label>`;
}

function renderVitrine() {
  const gratuitos = complementos.filter(c => c.preco === 0);
  const pagos     = complementos.filter(c => c.preco > 0).sort((a, b) => a.preco - b.preco);

  document.getElementById('produtos-grid').innerHTML = produtos.map(p => `
    <div class="card">
      <h3>${p.nome}</h3>
      <span class="preco">R$ ${p.preco.toFixed(2)}</span>
      <button type="button" class="btn-toggle-opcoes" onclick="toggleOpcoes(${p.id})">
        <span>🍫 Complementos <span id="contador-${p.id}" class="contador-opcoes">toque para escolher</span></span>
        <span class="seta-toggle" id="seta-${p.id}">▾</span>
      </button>
      <div class="opcoes-container" id="opcoes-${p.id}" style="display:none">
        <p class="opcoes-limite">Escolha até ${MAX_ACOMPANHAMENTOS} acompanhamentos</p>
        ${gratuitos.length > 0 ? `<p class="opcoes-titulo">Grátis</p>` : ''}
        ${gratuitos.map(comp => _opcaoComplemento(p, comp)).join('')}
        ${pagos.length > 0 ? `<p class="opcoes-titulo">Com custo adicional</p>` : ''}
        ${pagos.map(comp => _opcaoComplemento(p, comp)).join('')}
      </div>
      <button class="btn-add-vitrine" onclick="addToCart(${p.id})">Adicionar</button>
    </div>
  `).join('');
}

function addToCart(id) {
  const prod       = produtos.find(p => p.id === id);
  const marcados   = Array.from(document.querySelectorAll(`.check-${id}:checked`));
  const selected   = marcados.map(c => c.value);
  const precoExtras = marcados.reduce((s, c) => s + (parseFloat(c.dataset.preco) || 0), 0);
  const itemKey    = prod.nome + ':' + selected.sort().join(',');
  const existente  = carrinho.find(i => i.key === itemKey);
  if (existente) {
    existente.qtd++;
  } else {
    carrinho.push({ key: itemKey, nome: prod.nome, preco: prod.preco + precoExtras, extras: selected, qtd: 1 });
  }
  document.querySelectorAll(`.check-${id}`).forEach(c => { c.checked = false; c.disabled = false; });
  limitarAcompanhamentos(id);
  updateUI();
  toggleCart(true);
}

function changeQty(key, delta) {
  const index = carrinho.findIndex(i => i.key === key);
  if (index !== -1) {
    carrinho[index].qtd += delta;
    if (carrinho[index].qtd <= 0) carrinho.splice(index, 1);
  }
  updateUI();
}

function calcularTotal() {
  const subtotal = carrinho.reduce((s, i) => s + i.preco * i.qtd, 0);
  return subtotal + (carrinho.length > 0 ? TAXA_ENTREGA : 0);
}

function updateUI() {
  let total = 0, qtdTotal = 0;
  document.getElementById('cart-list').innerHTML = carrinho.map(item => {
    total    += item.preco * item.qtd;
    qtdTotal += item.qtd;
    return `
      <div class="cart-item">
        <h4>${item.nome}</h4>
        <p style="font-size:0.8rem;color:#666;margin:0">${item.extras.join(', ') || 'Puro'}</p>
        <div class="cart-controls">
          <span style="font-weight:bold">R$ ${(item.preco * item.qtd).toFixed(2)}</span>
          <div class="qty-box">
            <button class="qty-btn" onclick="changeQty('${item.key}', -1)">−</button>
            <span>${item.qtd}</span>
            <button class="qty-btn" onclick="changeQty('${item.key}', 1)">+</button>
          </div>
        </div>
      </div>`;
  }).join('');
  const taxa = qtdTotal > 0 ? TAXA_ENTREGA : 0;
  document.getElementById('cart-count').innerText = qtdTotal;
  document.getElementById('cart-taxa').innerText  = `R$ ${taxa.toFixed(2)}`;
  document.getElementById('cart-total').innerText  = `R$ ${(total + taxa).toFixed(2)}`;
}

function alternarFormaPagamento() {
  const forma = document.querySelector('input[name="forma-pagamento"]:checked').value;
  document.getElementById('cartao-campos').classList.toggle('active', forma === 'cartao');
  document.getElementById('pix-campos').classList.toggle('active', forma === 'pix');
  document.getElementById('dinheiro-campos').classList.toggle('active', forma === 'dinheiro');
  document.getElementById('btn-enviar-pedido').style.display = forma === 'cartao' ? 'none' : 'block';

  if (forma === 'pix') {
    tentarGerarPixSeEmailValido();
  } else if (forma === 'cartao') {
    montarCardBrick();
  }
}

function alternarTroco() {
  const precisa = document.getElementById('input-precisa-troco').checked;
  document.getElementById('troco-wrapper').style.display = precisa ? 'block' : 'none';
  if (!precisa) document.getElementById('input-troco-para').value = '';
}

function tentarGerarPixSeEmailValido() {
  const formaAtual = document.querySelector('input[name="forma-pagamento"]:checked').value;
  if (formaAtual !== 'pix') return;

  const email = document.getElementById('input-email').value.trim();
  if (!email.includes('@')) {
    mpOrderId = null;
    document.getElementById('pix-qrcode').textContent = 'Preencha seu e-mail acima para gerar o QR Code.';
    document.getElementById('pix-copia-cola').value = '';
    return;
  }
  const nome = document.getElementById('input-nome').value.trim();
  gerarPix(email, nome);
}

async function gerarPix(email, nome) {
  const qrEl        = document.getElementById('pix-qrcode');
  const copiaColaEl = document.getElementById('pix-copia-cola');

  mpOrderId = null;
  copiaColaEl.value = '';
  qrEl.textContent = 'Gerando QR Code…';

  try {
    const res  = await fetch(`${API}/pagamentos/pix`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ valor: calcularTotal(), email, nome })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.erro || `Erro ${res.status}`);

    mpOrderId = data.mp_order_id;
    qrEl.innerHTML = `<img src="data:image/png;base64,${data.qr_code_base64}" alt="QR Code Pix">`;
    copiaColaEl.value = data.qr_code;

  } catch (e) {
    console.error(e);
    qrEl.textContent = e.message && e.message !== 'Failed to fetch'
      ? e.message
      : 'Não foi possível gerar o QR Code Pix. Tente novamente.';
  }
}

function copiarPix() {
  const copiaColaEl = document.getElementById('pix-copia-cola');
  if (!copiaColaEl.value) return;
  navigator.clipboard.writeText(copiaColaEl.value).then(() => {
    const btn = document.querySelector('.btn-copiar');
    const textoOriginal = btn.textContent;
    btn.textContent = 'Copiado!';
    setTimeout(() => { btn.textContent = textoOriginal; }, 2000);
  });
}

async function montarCardBrick() {
  const container = document.getElementById('cardPaymentBrick_container');

  if (!mp) {
    container.textContent = 'Erro: SDK da Mercado Pago não carregou. Recarregue a página.';
    return;
  }

  if (cardBrickController) {
    try { await cardBrickController.unmount(); } catch (e) { /* já desmontado */ }
    cardBrickController = null;
  }
  container.innerHTML = '<p class="brick-loading">Carregando formulário de cartão…</p>';

  try {
    const bricksBuilder = mp.bricks();
    cardBrickController = await bricksBuilder.create('cardPayment', 'cardPaymentBrick_container', {
      initialization: { amount: calcularTotal() },
      callbacks: {
        onReady: () => {
          const aviso = container.querySelector('.brick-loading');
          if (aviso) aviso.remove();
        },
        onSubmit: (formData) => processarCartao(formData),
        onError: (error) => {
          console.error('Card Brick onError:', error);
          document.getElementById('modal-erro').textContent = 'Erro no formulário de cartão.';
        }
      }
    });
  } catch (e) {
    console.error('Falha ao montar Card Brick:', e);
    container.textContent = 'Não foi possível carregar o formulário de cartão: ' + (e.message || e);
  }
}

function dadosClienteValidos() {
  const nome   = document.getElementById('input-nome').value.trim();
  const tel    = document.getElementById('input-tel').value.trim();
  const email  = document.getElementById('input-email').value.trim();
  const rua    = document.getElementById('input-rua').value.trim();
  const numero = document.getElementById('input-numero').value.trim();
  const bairro = document.getElementById('input-bairro').value.trim();
  return { nome, tel, email, rua, numero, bairro };
}

async function processarCartao(formData) {
  const erro = document.getElementById('modal-erro');
  const { nome, tel, email, rua, numero, bairro } = dadosClienteValidos();

  if (!nome || !tel || !email || !rua || !numero || !bairro) {
    erro.textContent = 'Preencha todos os campos para continuar.';
    throw new Error('Dados do cliente incompletos');
  }
  erro.textContent = '';

  const resCartao = await fetch(`${API}/pagamentos/cartao`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      valor: calcularTotal(),
      email,
      nome,
      token: formData.token,
      payment_method_id: formData.payment_method_id,
      installments: formData.installments
    })
  });
  const dataCartao = await resCartao.json();
  if (!resCartao.ok) {
    erro.textContent = dataCartao.erro || 'Pagamento recusado.';
    throw new Error(dataCartao.erro || 'Pagamento recusado');
  }

  const end = `${rua}, ${numero} — ${bairro}, Rolante`;
  const payload = {
    cliente: { nome, tel, end },
    itens: carrinho.map(i => ({ nome: i.nome, preco: i.preco, extras: i.extras, qtd: i.qtd })),
    total: calcularTotal(),
    forma_pagamento: 'cartao',
    mp_order_id: dataCartao.mp_order_id
  };

  const res  = await fetch(`${API}/pedidos`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload)
  });
  if (!res.ok) {
    erro.textContent = 'Pagamento aprovado, mas houve um erro ao registrar o pedido. '
      + 'Entre em contato com o estabelecimento informando o horário da compra.';
    throw new Error(`Erro ${res.status}`);
  }

  const data = await res.json();
  salvarPedidoLocal(data.id);
  window.location.href = `acompanhar.html?id=${data.id}`;
}

function salvarPedidoLocal(id) {
  const ids = JSON.parse(localStorage.getItem('pedidoIds') || '[]');
  if (!ids.includes(String(id))) ids.push(String(id));
  localStorage.setItem('pedidoIds', JSON.stringify(ids));
}

function toggleCart(estado) {
  document.getElementById('cart-sidebar').classList.toggle('active', estado);
}

function abrirModal() {
  if (carrinho.length === 0) return;
  document.getElementById('modal-erro').textContent = '';
  document.getElementById('modal-overlay').classList.add('active');

  const formaAtual = document.querySelector('input[name="forma-pagamento"]:checked').value;
  document.getElementById('btn-enviar-pedido').style.display = formaAtual === 'cartao' ? 'none' : 'block';

  if (formaAtual === 'cartao') {
    montarCardBrick();
  } else if (formaAtual === 'pix') {
    tentarGerarPixSeEmailValido();
  }
}

function fecharModal() {
  document.getElementById('modal-overlay').classList.remove('active');
  mpOrderId = null;
  document.getElementById('pix-qrcode').textContent = 'Preencha seu e-mail acima para gerar o QR Code.';
  document.getElementById('pix-copia-cola').value = '';
  document.getElementById('input-precisa-troco').checked = false;
  alternarTroco();
  if (cardBrickController) {
    cardBrickController.unmount().catch(() => {});
    cardBrickController = null;
  }
  document.getElementById('cardPaymentBrick_container').innerHTML = '';
}

async function confirmarPedido() {
  const erro = document.getElementById('modal-erro');
  const { nome, tel, email, rua, numero, bairro } = dadosClienteValidos();

  if (!nome || !tel || !email || !rua || !numero || !bairro) {
    erro.textContent = 'Preencha todos os campos para continuar.';
    return;
  }

  const forma = document.querySelector('input[name="forma-pagamento"]:checked').value;

  let trocoPara = null;
  if (forma === 'dinheiro' && document.getElementById('input-precisa-troco').checked) {
    trocoPara = parseFloat(document.getElementById('input-troco-para').value);
    if (isNaN(trocoPara) || trocoPara < calcularTotal()) {
      erro.textContent = 'Informe um valor de troco maior ou igual ao total do pedido.';
      return;
    }
  }

  if (forma === 'pix' && !mpOrderId) {
    erro.textContent = 'Aguarde o QR Code Pix ser gerado.';
    return;
  }

  const end = `${rua}, ${numero} — ${bairro}, Rolante`;
  const btnEnviar = document.getElementById('btn-enviar-pedido');

  try {
    erro.textContent = '';
    btnEnviar.disabled    = true;
    btnEnviar.textContent = 'Enviando…';

    const payload = {
      cliente: { nome, tel, end },
      itens: carrinho.map(i => ({ nome: i.nome, preco: i.preco, extras: i.extras, qtd: i.qtd })),
      total: calcularTotal(),
      forma_pagamento: forma,
    };
    if (forma === 'pix') payload.mp_order_id = mpOrderId;
    if (trocoPara !== null) payload.troco_para = trocoPara;

    const res  = await fetch(`${API}/pedidos`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload)
    });
    const data = await res.json();

    if (!res.ok) {
      if (data.motivo === 'fechado_hoje') {
        throw new Error('O estabelecimento está fechado hoje. Tente novamente em outro dia.');
      }
      if (data.motivo === 'fora_do_horario') {
        throw new Error('Fora do horário de atendimento no momento.');
      }
      throw new Error(data.erro || `Erro ${res.status}`);
    }

    salvarPedidoLocal(data.id);
    window.location.href = `acompanhar.html?id=${data.id}`;

  } catch (e) {
    console.error(e);
    erro.textContent = e.message && e.message !== 'Failed to fetch'
      ? e.message
      : 'Erro ao enviar pedido. Verifique a conexão e tente novamente.';
    btnEnviar.disabled    = false;
    btnEnviar.textContent = 'Enviar Pedido →';
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    const [resProd, resComp] = await Promise.all([
      fetch(`${API}/cardapio`),
      fetch(`${API}/complementos`),
    ]);
    produtos     = await resProd.json();
    complementos = await resComp.json();
  } catch (e) {
    console.error('Erro ao carregar cardápio/complementos:', e);
    document.getElementById('produtos-grid').innerHTML =
      '<p style="text-align:center;color:#e74c3c">Erro ao carregar cardápio. Verifique a conexão.</p>';
    return;
  }

  try {
    const resConfig = await fetch(`${API}/config`);
    const config    = await resConfig.json();
    if (typeof MercadoPago === 'undefined') throw new Error('SDK da Mercado Pago não carregou (verifique sua conexão)');
    mp = new MercadoPago(config.mp_public_key, { locale: 'pt-BR' });
  } catch (e) {
    console.error('Erro ao inicializar Mercado Pago:', e);
  }

  renderVitrine();
  const ids = JSON.parse(localStorage.getItem('pedidoIds') || '[]');
  if (ids.length > 0) {
    const link = document.getElementById('link-acompanhar');
    if (link) link.href = 'acompanhar.html';
  }
});
