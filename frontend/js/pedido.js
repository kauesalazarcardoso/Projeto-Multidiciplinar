const API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend-738933484701.us-east1.run.app';
// Deve espelhar TAXA_MAQUININHA_ATE_50/TAXA_MAQUININHA_ACIMA_50/LIMITE_ITENS_TAXA_MAQUININHA
// em backend/back/routes/pedidos.py
const TAXA_MAQUININHA_ATE_50 = 2.0;
const TAXA_MAQUININHA_ACIMA_50 = 3.0;
const LIMITE_ITENS_TAXA_MAQUININHA = 50.0;

// Deve espelhar CATEGORIAS_CARDAPIO em backend/back/database.py
const ORDEM_CATEGORIAS = ["Açaí Tradicional", "Cupuaçu", "Iogurte Grego", "Iogurte Grego com Morango"];
let categoriaAtiva = 'Todos';

// Deve espelhar CATEGORIAS_COMPLEMENTOS em backend/back/database.py
const ORDEM_CATEGORIAS_COMPLEMENTOS = ["Calda", "Frutas", "Complementos Gratuitos", "Complementos Adicionais"];

let produtos     = [];
let complementos = [];
let bairros      = [];

let carrinho = [];

function renderBairros() {
  const select = document.getElementById('input-bairro');
  const atual  = select.value;
  select.innerHTML = '';
  const optPlaceholder = document.createElement('option');
  optPlaceholder.value = '';
  optPlaceholder.disabled = true;
  optPlaceholder.textContent = 'Selecione o bairro';
  select.appendChild(optPlaceholder);
  bairros.forEach(b => {
    const opt = document.createElement('option');
    opt.value = b.nome;
    opt.textContent = `${b.nome} — R$ ${b.taxa.toFixed(2)}`;
    select.appendChild(opt);
  });
  if (atual && bairros.some(b => b.nome === atual)) {
    select.value = atual;
  } else {
    optPlaceholder.selected = true;
  }
}

function taxaEntregaSelecionada() {
  const nome   = document.getElementById('input-bairro').value;
  const bairro = bairros.find(b => b.nome === nome);
  return bairro ? bairro.taxa : 0;
}

function atualizarTaxaEntrega() {
  updateUI();
  atualizarResumoModal();
}

function limitarAcompanhamentos(produtoId) {
  const checkboxes = document.querySelectorAll(`.check-${produtoId}`);
  const marcados   = Array.from(checkboxes).filter(c => c.checked).length;
  const contador = document.getElementById(`contador-${produtoId}`);
  if (contador) {
    contador.textContent = marcados > 0 ? `${marcados} escolhido${marcados > 1 ? 's' : ''}` : 'toque para escolher';
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

function renderCategoriaTabs() {
  const presentes = ORDEM_CATEGORIAS.filter(cat => produtos.some(p => p.categoria === cat));
  const tabs = ['Todos', ...presentes];
  document.getElementById('categoria-tabs').innerHTML = tabs.map(cat => `
    <button type="button" class="categoria-tab ${cat === categoriaAtiva ? 'active' : ''}"
      onclick="selecionarCategoria('${cat}')">${cat}</button>
  `).join('');
}

function selecionarCategoria(cat) {
  categoriaAtiva = cat;
  renderCategoriaTabs();
  renderVitrine();
}

function _gruposComplementos() {
  return ORDEM_CATEGORIAS_COMPLEMENTOS
    .map(categoria => ({ categoria, itens: complementos.filter(c => c.categoria === categoria) }))
    .filter(g => g.itens.length > 0);
}

function renderVitrine() {
  const visiveis = categoriaAtiva === 'Todos'
    ? produtos
    : produtos.filter(p => p.categoria === categoriaAtiva);

  const gruposComplementos = _gruposComplementos();

  document.getElementById('produtos-grid').innerHTML = visiveis.map(p => `
    <div class="card">
      <h3>${p.nome}</h3>
      <span class="preco">R$ ${p.preco.toFixed(2)}</span>
      <button type="button" class="btn-toggle-opcoes" onclick="toggleOpcoes(${p.id})">
        <span>🍫 Complementos <span id="contador-${p.id}" class="contador-opcoes">toque para escolher</span></span>
        <span class="seta-toggle" id="seta-${p.id}">▾</span>
      </button>
      <div class="opcoes-container" id="opcoes-${p.id}" style="display:none">
        ${gruposComplementos.map(g => `
          <p class="opcoes-titulo">${g.categoria}</p>
          ${g.itens.map(comp => _opcaoComplemento(p, comp)).join('')}
        `).join('')}
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
  document.querySelectorAll(`.check-${id}`).forEach(c => { c.checked = false; });
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

function calcularTaxaMaquininha() {
  const formaEl = document.querySelector('input[name="forma-pagamento"]:checked');
  const forma   = formaEl ? formaEl.value : 'pix';
  if (forma !== 'cartao') return 0;
  const subtotalItens = carrinho.reduce((s, i) => s + i.preco * i.qtd, 0);
  return subtotalItens <= LIMITE_ITENS_TAXA_MAQUININHA ? TAXA_MAQUININHA_ATE_50 : TAXA_MAQUININHA_ACIMA_50;
}

function calcularTotal() {
  const subtotal = carrinho.reduce((s, i) => s + i.preco * i.qtd, 0);
  if (carrinho.length === 0) return 0;
  return subtotal + taxaEntregaSelecionada() + calcularTaxaMaquininha();
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
  const taxaEntrega    = qtdTotal > 0 ? taxaEntregaSelecionada() : 0;
  const taxaMaquininha = qtdTotal > 0 ? calcularTaxaMaquininha() : 0;
  document.getElementById('cart-count').innerText = qtdTotal;
  document.getElementById('cart-taxa').innerText  = `R$ ${taxaEntrega.toFixed(2)}`;
  document.getElementById('cart-total').innerText  = `R$ ${(total + taxaEntrega + taxaMaquininha).toFixed(2)}`;

  const linhaMaquininha = document.getElementById('cart-taxa-maquininha-row');
  if (taxaMaquininha > 0) {
    linhaMaquininha.style.display = 'flex';
    document.getElementById('cart-taxa-maquininha').innerText = `R$ ${taxaMaquininha.toFixed(2)}`;
  } else {
    linhaMaquininha.style.display = 'none';
  }
}

function atualizarResumoModal() {
  const taxaMaquininha = calcularTaxaMaquininha();
  document.getElementById('modal-resumo-taxa').textContent = `R$ ${taxaEntregaSelecionada().toFixed(2)}`;
  document.getElementById('modal-resumo-total').textContent = `R$ ${calcularTotal().toFixed(2)}`;

  const linhaMaquininha = document.getElementById('modal-resumo-maquininha-linha');
  if (taxaMaquininha > 0) {
    linhaMaquininha.style.display = 'flex';
    document.getElementById('modal-resumo-maquininha').textContent = `R$ ${taxaMaquininha.toFixed(2)}`;
  } else {
    linhaMaquininha.style.display = 'none';
  }
}

function alternarFormaPagamento() {
  const forma = document.querySelector('input[name="forma-pagamento"]:checked').value;
  document.getElementById('cartao-campos').classList.toggle('active', forma === 'cartao');
  document.getElementById('pix-campos').classList.toggle('active', forma === 'pix');
  document.getElementById('dinheiro-campos').classList.toggle('active', forma === 'dinheiro');
  atualizarResumoModal();
  updateUI();
}

function alternarTroco() {
  const precisa = document.getElementById('input-precisa-troco').checked;
  document.getElementById('troco-wrapper').style.display = precisa ? 'block' : 'none';
  if (!precisa) document.getElementById('input-troco-para').value = '';
}

function copiarPix() {
  const chaveEl = document.getElementById('pix-chave');
  navigator.clipboard.writeText(chaveEl.value).then(() => {
    const btn = document.querySelector('.btn-copiar');
    const textoOriginal = btn.textContent;
    btn.textContent = 'Copiado!';
    setTimeout(() => { btn.textContent = textoOriginal; }, 2000);
  });
}

function dadosClienteValidos() {
  const nome   = document.getElementById('input-nome').value.trim();
  const tel    = document.getElementById('input-tel').value.trim();
  const rua    = document.getElementById('input-rua').value.trim();
  const numero = document.getElementById('input-numero').value.trim();
  const bairro = document.getElementById('input-bairro').value.trim();
  return { nome, tel, rua, numero, bairro };
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
  atualizarResumoModal();
}

function fecharModal() {
  document.getElementById('modal-overlay').classList.remove('active');
  document.getElementById('input-precisa-troco').checked = false;
  alternarTroco();
}

async function confirmarPedido() {
  const erro = document.getElementById('modal-erro');
  const { nome, tel, rua, numero, bairro } = dadosClienteValidos();

  if (!nome || !tel || !rua || !numero || !bairro) {
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

  const end = `${rua}, ${numero} — ${bairro}, Rolante`;
  const observacao = document.getElementById('input-observacao').value.trim();
  const btnEnviar = document.getElementById('btn-enviar-pedido');

  try {
    erro.textContent = '';
    btnEnviar.disabled    = true;
    btnEnviar.textContent = 'Enviando…';

    const payload = {
      cliente: { nome, tel, end },
      itens: carrinho.map(i => ({ nome: i.nome, preco: i.preco, extras: i.extras, qtd: i.qtd })),
      bairro,
      total: calcularTotal(),
      forma_pagamento: forma,
    };
    if (trocoPara !== null) payload.troco_para = trocoPara;
    if (observacao) payload.observacao = observacao;

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

async function carregarCardapioInicial(tentativa = 1) {
  const [resProd, resComp, resBairros] = await Promise.all([
    fetch(`${API}/cardapio`),
    fetch(`${API}/complementos`),
    fetch(`${API}/bairros`),
  ]);
  produtos     = await resProd.json();
  complementos = await resComp.json();
  bairros      = await resBairros.json();
}

document.addEventListener('DOMContentLoaded', async () => {
  // Uma nova tentativa cobre o backend acordando de um cold start (Cloud Run):
  // a primeira chamada pode falhar/expirar antes da instância terminar de subir.
  try {
    await carregarCardapioInicial();
  } catch (e) {
    console.warn('Falha ao carregar cardápio, tentando novamente em 3s...', e);
    await new Promise(r => setTimeout(r, 3000));
    try {
      await carregarCardapioInicial();
    } catch (e2) {
      console.error('Erro ao carregar cardápio/complementos/bairros:', e2);
      document.getElementById('produtos-grid').innerHTML =
        '<p style="text-align:center;color:#e74c3c">Erro ao carregar cardápio. Verifique a conexão.</p>';
      return;
    }
  }

  renderCategoriaTabs();
  renderVitrine();
  renderBairros();
  const ids = JSON.parse(localStorage.getItem('pedidoIds') || '[]');
  if (ids.length > 0) {
    const link = document.getElementById('link-acompanhar');
    if (link) link.href = 'acompanhar.html';
  }
});
