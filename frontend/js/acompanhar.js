const STEPS = [
  { status: 'aguardando', icone: '🕐', titulo: 'Pedido Recebido',   desc: 'Aguardando confirmação do estabelecimento' },
  { status: 'confirmado', icone: '✅', titulo: 'Pedido Confirmado', desc: 'O estabelecimento confirmou seu pedido' },
  { status: 'a_caminho',  icone: '🛵', titulo: 'Pedido a Caminho',  desc: 'Seu açaí está saindo para entrega' },
  { status: 'entregue',   icone: '🎉', titulo: 'Pedido Entregue',   desc: 'Aproveite seu açaí!' },
];

const ORDEM = ['aguardando', 'confirmado', 'a_caminho', 'entregue'];

function getIds() {
  try { return JSON.parse(localStorage.getItem('pedidoIds') || '[]'); }
  catch { return []; }
}

function addId(id) {
  const ids = getIds();
  if (!ids.includes(String(id))) {
    ids.push(String(id));
    localStorage.setItem('pedidoIds', JSON.stringify(ids));
  }
}

function removeId(id) {
  localStorage.setItem('pedidoIds', JSON.stringify(getIds().filter(i => i !== String(id))));
}

const idFromUrl = new URLSearchParams(window.location.search).get('id');
if (idFromUrl) addId(idFromUrl);

async function fetchPedido(id) {
  try {
    const res = await fetch(`${API}/pedidos/rastrear/${id}`);
    return res.ok ? await res.json() : null;
  } catch { return null; }
}

function cardHTML(pedido) {
  if (pedido.status === 'recusado') {
    return cardRecusadoHTML(pedido);
  }

  const statusIdx = ORDEM.indexOf(pedido.status);

  const stepsHTML = STEPS.map((s, i) => {
    const cls = i < statusIdx ? 'ativo' : i === statusIdx ? 'atual' : '';
    return `
      <div class="step ${cls}">
        <div class="step-icon">${s.icone}</div>
        <div class="step-texto">
          <h4>${s.titulo}</h4>
          <p>${s.desc}</p>
        </div>
      </div>`;
  }).join('');

  const itensHTML = pedido.itens.map(item => `
    <div class="item-linha">
      <div>
        <div>${item.qtd}× ${escapeHtml(item.nome)}</div>
        ${item.extras && item.extras.length
          ? `<div class="item-extras">${escapeHtml(item.extras.join(', '))}</div>`
          : ''}
      </div>
      <div>R$ ${(item.preco * item.qtd).toFixed(2)}</div>
    </div>`).join('');

  return `
    <div class="pedido-card">
      <h2>Pedido das ${pedido.hora}</h2>
      <div class="dados-cliente">
        <strong>📍 ${escapeHtml(pedido.cliente.nome)}</strong><br>
        📞 ${escapeHtml(pedido.cliente.tel)}<br>
        🏠 ${escapeHtml(pedido.cliente.end)}
      </div>
      <div class="timeline">${stepsHTML}</div>
      <h3 class="itens-titulo">Itens do Pedido</h3>
      ${itensHTML}
      <div class="item-linha">
        <div>Taxa de entrega</div>
        <div>R$ ${Number(pedido.taxa_entrega || 0).toFixed(2)}</div>
      </div>
      ${pedido.taxa_maquininha > 0 ? `
      <div class="item-linha">
        <div>Taxa da maquininha</div>
        <div>R$ ${Number(pedido.taxa_maquininha).toFixed(2)}</div>
      </div>` : ''}
      <div class="item-linha">
        <div>Pagamento</div>
        <div>${formatarPagamento(pedido)}</div>
      </div>
      <div class="total-linha">
        <span>Total</span>
        <span>R$ ${Number(pedido.total).toFixed(2)}</span>
      </div>
    </div>`;
}

function cardRecusadoHTML(pedido) {
  return `
    <div class="pedido-card">
      <h2>Pedido das ${pedido.hora}</h2>
      <div class="dados-cliente">
        <strong>📍 ${escapeHtml(pedido.cliente.nome)}</strong><br>
        📞 ${escapeHtml(pedido.cliente.tel)}<br>
        🏠 ${escapeHtml(pedido.cliente.end)}
      </div>
      <div class="item-linha">
        <div>🚫 Este pedido não pôde ser aceito pelo estabelecimento.</div>
      </div>
      <p class="pix-info">Entre em contato pelo WhatsApp da loja se tiver dúvidas.</p>
    </div>`;
}

async function render() {
  const el  = document.getElementById('conteudo');
  const ids = getIds();

  if (ids.length === 0) {
    el.innerHTML = `
      <div class="sem-pedido">
        <h2>Nenhum pedido encontrado</h2>
        <p>Faça seu pedido primeiro!</p>
        <a class="btn-voltar" href="pedido.html">Fazer Pedido</a>
      </div>`;
    return;
  }

  const resultados = await Promise.all(ids.map(id => fetchPedido(id).then(p => ({ id, p }))));

  resultados.forEach(({ id, p }) => { if (!p) removeId(id); });

  const pedidos = resultados.map(r => r.p).filter(Boolean);

  if (pedidos.length === 0) {
    el.innerHTML = `
      <div class="sem-pedido">
        <h2>Nenhum pedido encontrado</h2>
        <p>Faça seu pedido primeiro!</p>
        <a class="btn-voltar" href="pedido.html">Fazer Pedido</a>
      </div>`;
    return;
  }

  pedidos.forEach(p => { if (p.status === 'entregue' || p.status === 'recusado') removeId(p.id); });

  el.innerHTML = pedidos.map(cardHTML).join('') +
    `<a class="btn-voltar" href="pedido.html">Fazer Novo Pedido</a>`;

  if (pedidos.every(p => p.status === 'entregue' || p.status === 'recusado')) clearInterval(intervalo);
}

render();
const intervalo = setInterval(render, 5000);
