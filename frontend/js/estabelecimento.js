
const API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend.onrender.com';

const ORDEM  = ['aguardando', 'confirmado', 'a_caminho', 'entregue'];
const LABELS = {
  aguardando: '🕐 Aguardando',
  confirmado: '✅ Confirmado',
  a_caminho:  '🛵 A Caminho',
  entregue:   '🎉 Entregue',
  recusado:   '🚫 Recusado',
};

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

function escapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto;
  return div.innerHTML;
}

// ── NOTIFICAÇÃO WHATSAPP (link wa.me, envio é manual) ─────────
// OBS: o link wa.me corrompe emoji no texto pré-preenchido (confirmado em teste
// manual — mesmo emoji simples como ✅ vira "�" na conversa). Por isso as
// mensagens abaixo usam só texto puro, sem emoji.
const MENSAGENS_WHATSAPP = {
  aguardando: (p, id, nome) => `Oi ${nome}! Recebemos seu pedido #${id} na Lovers Açaí. Já vamos confirmar!`,
  confirmado: (p, id, nome) => `Oi ${nome}! Seu pedido #${id} foi *confirmado* e já está sendo preparado!`,
  a_caminho:  (p, id, nome) => `Oi ${nome}! Seu pedido #${id} saiu para entrega. Chega já já!`,
  entregue:   (p, id, nome) => `Oi ${nome}! Seu pedido #${id} foi *entregue*. Bom apetite! Obrigado por pedir na Lovers Açaí.`,
  recusado:   (p, id, nome) => `Oi ${nome}, infelizmente não conseguimos aceitar seu pedido #${id} desta vez. Pedimos desculpas pelo transtorno.`,
};

function normalizarTelefoneBR(tel) {
  const digitos = (tel || '').replace(/\D/g, '');
  if (!digitos) return null;
  return digitos.startsWith('55') ? digitos : `55${digitos}`;
}

function linkWhatsapp(pedido) {
  const gerarMsg = MENSAGENS_WHATSAPP[pedido.status];
  const numero   = normalizarTelefoneBR(pedido.cliente.tel);
  if (!gerarMsg || !numero) return null;

  const idCurto     = String(pedido.id).slice(-5);
  const primeiroNome = (pedido.cliente.nome || '').trim().split(/\s+/)[0] || 'cliente';
  const mensagem    = gerarMsg(pedido, idCurto, primeiroNome);

  return `https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`;
}

// ── ALERTA DE PEDIDO NOVO (som + destaque visual + Notification) ──
let audioCtx = null;
let idsConhecidos = null;

function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

function tocarSomNovoPedido() {
  try {
    const ctx = getAudioCtx();
    if (ctx.state === 'suspended') ctx.resume();
    const tocarNota = (freq, inicio, duracao) => {
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + inicio);
      gain.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + inicio + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + inicio + duracao);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + inicio);
      osc.stop(ctx.currentTime + inicio + duracao + 0.05);
    };
    tocarNota(880, 0, 0.15);
    tocarNota(1174.66, 0.18, 0.2);
  } catch (e) {
    console.error('Erro ao tocar som de notificação:', e);
  }
}

function notificarNovosPedidos(novos) {
  // O aviso quando a aba está em segundo plano ou fechada é responsabilidade
  // do push (Service Worker); aqui só cuidamos do feedback com a aba aberta.
  tocarSomNovoPedido();
}

// ── PUSH NOTIFICATION (funciona com a aba/navegador fechado) ──────
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
}

function suportaPush() {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

async function inscricaoAtiva() {
  if (!suportaPush()) return null;
  const reg = await navigator.serviceWorker.getRegistration();
  if (!reg) return null;
  return reg.pushManager.getSubscription();
}

async function atualizarBotaoNotificacao() {
  const btn = document.getElementById('btn-notif');
  if (!btn) return;
  if (!suportaPush()) {
    btn.style.display = 'none';
    return;
  }
  const sub = await inscricaoAtiva();
  if (sub && Notification.permission === 'granted') {
    btn.textContent = '🔔 Notificações ativadas';
    btn.disabled = true;
  } else {
    btn.textContent = '🔔 Ativar notificações';
    btn.disabled = false;
  }
}

async function ativarNotificacoes() {
  getAudioCtx().resume().catch(() => {});

  if (!suportaPush()) {
    alert('Seu navegador não suporta notificações push.');
    return;
  }
  try {
    const permissao = await Notification.requestPermission();
    if (permissao !== 'granted') return;

    const reg = await navigator.serviceWorker.register('/sw.js');
    await navigator.serviceWorker.ready;

    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      const { vapid_public_key } = await fetch(`${API}/config`).then(r => r.json());
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapid_public_key),
      });
    }

    await fetch(`${API}/push/subscribe`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body:    JSON.stringify(sub.toJSON()),
    });
  } catch (e) {
    console.error('Erro ao ativar notificações:', e);
    alert('Não foi possível ativar as notificações. Tente novamente.');
  } finally {
    atualizarBotaoNotificacao();
  }
}

// ── BUSCA TODOS OS PEDIDOS ────────────────────────────────────
async function fetchPedidos() {
  try {
    const res = await fetch(`${API}/pedidos`, { headers: authHeaders() });
    if (tratarRespostaAuth(res)) return null;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    return await res.json();   // espera array de pedidos
  } catch (e) {
    console.error('Erro ao buscar pedidos:', e);
    return null;
  }
}

// ── AVANÇA STATUS ─────────────────────────────────────────────
async function avancarStatus(id) {
  try {
    const res = await fetch(`${API}/pedidos/${id}/status`, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() }
    });
    if (tratarRespostaAuth(res)) return;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    render();
  } catch (e) {
    console.error('Erro ao avançar status:', e);
    alert('Não foi possível atualizar o status. Tente novamente.');
  }
}

// ── VOLTA STATUS (desfaz avanço por engano) ─────────────────────
async function voltarStatus(id) {
  try {
    const res = await fetch(`${API}/pedidos/${id}/status/voltar`, {
      method:  'PATCH',
      headers: { 'Content-Type': 'application/json', ...authHeaders() }
    });
    if (tratarRespostaAuth(res)) return;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    render();
    if (historicoAberto) renderHistorico();
  } catch (e) {
    console.error('Erro ao voltar status:', e);
    alert('Não foi possível voltar o status. Tente novamente.');
  }
}

// ── NEGAR PEDIDO ───────────────────────────────────────────────
async function negarPedido(id) {
  if (!confirm('Tem certeza que deseja negar este pedido?')) return;
  try {
    const res = await fetch(`${API}/pedidos/${id}/recusar`, {
      method:  'PATCH',
      headers: authHeaders()
    });
    if (tratarRespostaAuth(res)) return;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    render();
  } catch (e) {
    console.error('Erro ao negar pedido:', e);
    alert('Não foi possível negar o pedido. Tente novamente.');
  }
}

// ── IMPRESSÃO DO PEDIDO (recibo p/ impressora de cupom, via impressão do navegador) ──
let pedidosAtuais = [];

function reciboPedidoHTML(p) {
  const idCurto = String(p.id).slice(-5);

  const itensHTML = p.itens.map(item => `
    <div class="linha">
      <span>${item.qtd}x ${escapeHtml(item.nome)}</span>
      <span>R$ ${(item.preco * item.qtd).toFixed(2)}</span>
    </div>
    ${item.extras && item.extras.length
      ? `<div class="extras">${escapeHtml(item.extras.join(', '))}</div>`
      : ''}
  `).join('');

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Pedido #${idCurto}</title>
<style>
  @page { margin: 2mm; size: 58mm auto; }
  * { box-sizing: border-box; }
  body { font-family: 'Courier New', monospace; font-size: 10px; width: 48mm; margin: 0; padding: 0; color: #000; }
  h1 { font-size: 13px; text-align: center; margin: 0 0 4px; }
  .sep { border-top: 1px dashed #000; margin: 4px 0; }
  .linha { display: flex; justify-content: space-between; gap: 4px; }
  .extras { font-size: 9px; padding-left: 6px; color: #333; }
  .total { font-weight: bold; font-size: 11px; }
  .info p { margin: 2px 0; word-break: break-word; }
</style>
</head>
<body>
  <h1>Lovers Açaí</h1>
  <div class="info">
    <p>Pedido #${idCurto} — ${p.hora}</p>
    <p>Cliente: ${escapeHtml(p.cliente.nome || '')}</p>
    <p>Tel: ${escapeHtml(p.cliente.tel || '')}</p>
    <p>End: ${escapeHtml(p.cliente.end || '')}</p>
    ${p.observacao ? `<p>Obs: ${escapeHtml(p.observacao)}</p>` : ''}
  </div>
  <div class="sep"></div>
  ${itensHTML}
  <div class="sep"></div>
  <div class="linha"><span>Taxa de entrega</span><span>R$ ${Number(p.taxa_entrega || 0).toFixed(2)}</span></div>
  ${p.taxa_maquininha > 0 ? `<div class="linha"><span>Taxa maquininha</span><span>R$ ${Number(p.taxa_maquininha).toFixed(2)}</span></div>` : ''}
  <div class="linha"><span>Pagamento</span><span>${escapeHtml(formatarPagamento(p))}</span></div>
  <div class="sep"></div>
  <div class="linha total"><span>TOTAL</span><span>R$ ${Number(p.total).toFixed(2)}</span></div>
</body>
</html>`;
}

function imprimirPedido(id) {
  const pedido = pedidosAtuais.find(p => p.id === id);
  if (!pedido) return;

  const janela = window.open('', '_blank', 'width=300,height=600');
  if (!janela) {
    alert('Não foi possível abrir a janela de impressão. Verifique o bloqueador de pop-ups.');
    return;
  }
  janela.document.write(reciboPedidoHTML(pedido));
  janela.document.close();
  janela.onload = () => {
    janela.focus();
    janela.print();
  };
}

// ── LIMPAR ENTREGUES ──────────────────────────────────────────
async function limparEntregues() {
  try {
    const res = await fetch(`${API}/pedidos/entregues`, {
      method:  'DELETE',
      headers: authHeaders()
    });
    if (tratarRespostaAuth(res)) return;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    render();
  } catch (e) {
    console.error('Erro ao limpar entregues:', e);
    alert('Não foi possível limpar os pedidos entregues.');
  }
}

// ── HISTÓRICO (entregues/recusados dos últimos 7 dias) ────────
let historicoAberto = false;

async function fetchHistorico() {
  try {
    const res = await fetch(`${API}/pedidos/historico`, { headers: authHeaders() });
    if (tratarRespostaAuth(res)) return null;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error('Erro ao buscar histórico:', e);
    return null;
  }
}

async function toggleHistorico() {
  historicoAberto = !historicoAberto;
  const btn         = document.getElementById('btn-historico');
  const el          = document.getElementById('secao-historico');
  const listaPedidos = document.getElementById('lista-pedidos');
  if (historicoAberto) {
    btn.textContent = '📜 Fechar Histórico';
    listaPedidos.style.display = 'none';
    await renderHistorico();
  } else {
    btn.textContent = '📜 Histórico (7 dias)';
    listaPedidos.style.display = '';
    el.innerHTML = '';
  }
}

async function renderHistorico() {
  const el = document.getElementById('secao-historico');
  el.innerHTML = '<p style="text-align:center;color:#999">Carregando...</p>';

  const pedidos = await fetchHistorico();
  if (!historicoAberto) return; // fechou enquanto carregava

  if (pedidos === null) {
    el.innerHTML = '<p style="text-align:center;color:#e74c3c">Erro ao carregar histórico.</p>';
    return;
  }

  const botaoVoltar = `
    <button class="btn-acao btn-voltar" onclick="toggleHistorico()" style="margin-bottom:12px">
      ⬅️ Voltar para a Fila
    </button>`;

  if (pedidos.length === 0) {
    el.innerHTML = `
      ${botaoVoltar}
      <h2 class="secao-titulo">📜 Histórico (últimos 7 dias)</h2>
      <p style="text-align:center;color:#999">Nenhum pedido entregue ou recusado nos últimos 7 dias.</p>`;
    return;
  }

  el.innerHTML = `
    ${botaoVoltar}
    <h2 class="secao-titulo">📜 Histórico (últimos 7 dias)</h2>
    ${pedidos.map(p => {
      const podeVoltar = ORDEM.indexOf(p.status) > 0;
      return `
      <div class="pedido-card ${p.status}">
        <div class="pedido-topo">
          <h2>Pedido #${String(p.id).slice(-5)} — ${p.hora}</h2>
          <span class="badge ${p.status}">${LABELS[p.status]}</span>
        </div>
        <div class="pedido-info">
          <strong>👤 ${escapeHtml(p.cliente.nome)}</strong><br>
          📞 ${escapeHtml(p.cliente.tel)}<br>
          🏠 ${escapeHtml(p.cliente.end)}
        </div>
        <div class="total-row">
          <span>Total</span>
          <span>R$ ${Number(p.total).toFixed(2)}</span>
        </div>
        ${podeVoltar ? `
          <div class="acoes">
            <button class="btn-acao btn-voltar" onclick="voltarStatus(${p.id})" title="Desfazer último avanço de status">
              ↩️ Voltar Status
            </button>
          </div>` : ''}
      </div>`;
    }).join('')}`;
}

// ── HISTÓRICO DE VENDAS (últimos 7 dias) ───────────────────────
async function fetchVendasPorDia() {
  try {
    const res = await fetch(`${API}/pedidos/vendas-por-dia`, { headers: authHeaders() });
    if (tratarRespostaAuth(res)) return null;
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error('Erro ao buscar histórico de vendas:', e);
    return null;
  }
}

function _formatarDiaCurto(diaISO) {
  const [ano, mes, dia] = diaISO.split('-');
  return `${dia}/${mes}`;
}

let renderVendasTokenAtual = 0;

async function renderVendasSemana() {
  const meuToken = ++renderVendasTokenAtual;
  const dados = await fetchVendasPorDia();
  if (meuToken !== renderVendasTokenAtual) return;

  const el = document.getElementById('vendas-semana');
  if (!dados) { el.innerHTML = ''; return; }

  el.innerHTML = `
    <h2 class="secao-titulo">📊 Vendas dos últimos 7 dias</h2>
    <div class="vendas-grid">
      ${dados.map(d => `
        <div class="venda-dia">
          <span class="venda-dia-data">${_formatarDiaCurto(d.dia)}</span>
          <span class="venda-dia-total">R$ ${Number(d.total).toFixed(2)}</span>
          <span class="venda-dia-qtd">${d.pedidos} pedido${d.pedidos === 1 ? '' : 's'}</span>
        </div>
      `).join('')}
    </div>`;
}

// ── RENDERIZAÇÃO ──────────────────────────────────────────────
// Guarda "última chamada vence": evita que um GET de polling mais lento
// (ex: backend acordando de um cold start) sobrescreva a tela com dados
// desatualizados depois de uma ação mais recente do gestor já ter mudado
// o status na tela.
let renderTokenAtual = 0;

async function render() {
  const meuToken = ++renderTokenAtual;
  const pedidos = await fetchPedidos();
  if (meuToken !== renderTokenAtual) return;

  const el      = document.getElementById('lista-pedidos');

  // Erro de conexão com a API
  if (pedidos === null) {
    el.innerHTML = `
      <div class="sem-pedidos">
        <h2>⚠️ Erro de conexão</h2>
        <p>Não foi possível conectar ao servidor. Verifique se o Flask está rodando.</p>
      </div>`;
    return;
  }

  if (pedidos.length === 0) {
    el.innerHTML = `
      <div class="sem-pedidos">
        <h2>Nenhum pedido ainda</h2>
        <p>Os pedidos dos clientes aparecerão aqui automaticamente.</p>
      </div>`;
    idsConhecidos = new Set();
    return;
  }

  pedidosAtuais = pedidos;

  const idsAtuais = new Set(pedidos.map(p => p.id));
  const novosIds  = idsConhecidos === null
    ? new Set()
    : new Set(pedidos.filter(p => !idsConhecidos.has(p.id)).map(p => p.id));
  idsConhecidos = idsAtuais;

  if (novosIds.size > 0) {
    notificarNovosPedidos(pedidos.filter(p => novosIds.has(p.id)));
  }

  // Mais recentes primeiro, entregues/recusados por último
  const finalizado = status => status === 'entregue' || status === 'recusado';
  const ordenados = [...pedidos].sort((a, b) => {
    if (finalizado(a.status) && !finalizado(b.status)) return  1;
    if (finalizado(b.status) && !finalizado(a.status)) return -1;
    return b.id - a.id;
  });

  el.innerHTML = ordenados.map(p => {
    const idx         = ORDEM.indexOf(p.status);
    const podeAvancar = idx !== -1 && idx < ORDEM.length - 1;
    const podeVoltar  = idx > 0;
    const podeNegar   = !finalizado(p.status);

    const itensHTML = p.itens.map(item => `
      <div class="item-row">
        <div>
          <div>${item.qtd}× ${escapeHtml(item.nome)}</div>
          ${item.extras && item.extras.length
            ? `<div class="item-extras">${escapeHtml(item.extras.join(', '))}</div>`
            : ''}
        </div>
        <div>R$ ${(item.preco * item.qtd).toFixed(2)}</div>
      </div>`).join('');

    const proximoLabel = {
      aguardando: '✅ Confirmar Pedido',
      confirmado: '🛵 Marcar a Caminho',
      a_caminho:  '🎉 Marcar como Entregue',
      entregue:   'Entregue',
      recusado:   'Recusado',
    }[p.status];

    const proximoClass = {
      aguardando: 'btn-confirmar',
      confirmado: 'btn-caminho',
      a_caminho:  'btn-entregue',
      entregue:   'btn-entregue',
      recusado:   'btn-recusado',
    }[p.status];

    // Exibe apenas os últimos 5 dígitos do ID para leitura rápida
    const idCurto   = String(p.id).slice(-5);
    const linkWA    = linkWhatsapp(p);
    const classeNovo = novosIds.has(p.id) ? ' novo' : '';

    return `
      <div class="pedido-card ${p.status}${classeNovo}">
        <div class="pedido-topo">
          <h2>Pedido #${idCurto} — ${p.hora}</h2>
          <span class="badge ${p.status}">${LABELS[p.status]}</span>
        </div>

        <div class="pedido-info">
          <strong>👤 ${escapeHtml(p.cliente.nome)}</strong><br>
          📞 ${escapeHtml(p.cliente.tel)}<br>
          🏠 ${escapeHtml(p.cliente.end)}
        </div>

        ${p.observacao ? `<div class="pedido-obs">📝 ${escapeHtml(p.observacao)}</div>` : ''}

        <div class="itens-lista">
          ${itensHTML}
          <div class="item-row">
            <span>Taxa de entrega</span>
            <span>R$ ${Number(p.taxa_entrega || 0).toFixed(2)}</span>
          </div>
          ${p.taxa_maquininha > 0 ? `
          <div class="item-row">
            <span>Taxa da maquininha</span>
            <span>R$ ${Number(p.taxa_maquininha).toFixed(2)}</span>
          </div>` : ''}
          <div class="item-row">
            <span>Pagamento</span>
            <span>${formatarPagamento(p)}</span>
          </div>
          <div class="total-row">
            <span>Total</span>
            <span>R$ ${Number(p.total).toFixed(2)}</span>
          </div>
        </div>

        <div class="acoes">
          <button
            class="btn-acao ${proximoClass}"
            onclick="avancarStatus(${p.id})"
            ${!podeAvancar ? 'disabled' : ''}>
            ${proximoLabel}
          </button>
          ${podeVoltar ? `
            <button class="btn-acao btn-voltar" onclick="voltarStatus(${p.id})" title="Desfazer último avanço de status">
              ↩️ Voltar Status
            </button>` : ''}
          <button class="btn-acao btn-imprimir" onclick="imprimirPedido(${p.id})">
            🖨️ Imprimir
          </button>
          ${linkWA ? `
            <a class="btn-acao btn-whatsapp" href="${linkWA}" target="_blank" rel="noopener">
              📲 Avisar no WhatsApp
            </a>` : ''}
          ${podeNegar ? `
            <button class="btn-acao btn-negar" onclick="negarPedido(${p.id})">
              🚫 Negar Pedido
            </button>` : ''}
        </div>
      </div>`;
  }).join('');
}

// Atualiza a cada 5 segundos para pegar novos pedidos
atualizarBotaoNotificacao();
render();
setInterval(render, 5000);

// Histórico de vendas muda devagar — não precisa do polling rápido
renderVendasSemana();
setInterval(renderVendasSemana, 60000);
