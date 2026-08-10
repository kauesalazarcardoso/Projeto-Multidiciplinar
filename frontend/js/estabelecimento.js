
const API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend.onrender.com';

const ORDEM  = ['aguardando', 'confirmado', 'a_caminho', 'entregue'];
const LABELS = {
  aguardando: '🕐 Aguardando',
  confirmado: '✅ Confirmado',
  a_caminho:  '🛵 A Caminho',
  entregue:   '🎉 Entregue',
};

function formatarPagamento(pedido) {
  if (pedido.forma_pagamento === 'cartao') {
    return `Cartão •••• ${pedido.cartao_ultimos4 || '----'} (${pedido.cartao_bandeira || 'Outro'})`;
  }
  if (pedido.forma_pagamento === 'dinheiro') {
    return pedido.troco_para
      ? `Dinheiro (troco para R$ ${Number(pedido.troco_para).toFixed(2)})`
      : 'Dinheiro (sem troco)';
  }
  return 'Pix';
}

// ── NOTIFICAÇÃO WHATSAPP (link wa.me, envio é manual) ─────────
// OBS: o link wa.me corrompe emoji no texto pré-preenchido (confirmado em teste
// manual — mesmo emoji simples como ✅ vira "�" na conversa). Por isso as
// mensagens abaixo usam só texto puro, sem emoji.
const MENSAGENS_WHATSAPP = {
  aguardando: (p, id, nome) => `Oi ${nome}! Recebemos seu pedido #${id} na Açaí Express. Já vamos confirmar!`,
  confirmado: (p, id, nome) => `Oi ${nome}! Seu pedido #${id} foi *confirmado* e já está sendo preparado!`,
  a_caminho:  (p, id, nome) => `Oi ${nome}! Seu pedido #${id} saiu para entrega. Chega já já!`,
  entregue:   (p, id, nome) => `Oi ${nome}! Seu pedido #${id} foi *entregue*. Bom apetite! Obrigado por pedir na Açaí Express.`,
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

// ── RENDERIZAÇÃO ──────────────────────────────────────────────
async function render() {
  const pedidos = await fetchPedidos();
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

  const idsAtuais = new Set(pedidos.map(p => p.id));
  const novosIds  = idsConhecidos === null
    ? new Set()
    : new Set(pedidos.filter(p => !idsConhecidos.has(p.id)).map(p => p.id));
  idsConhecidos = idsAtuais;

  if (novosIds.size > 0) {
    notificarNovosPedidos(pedidos.filter(p => novosIds.has(p.id)));
  }

  // Mais recentes primeiro, entregues por último
  const ordenados = [...pedidos].sort((a, b) => {
    if (a.status === 'entregue' && b.status !== 'entregue') return  1;
    if (b.status === 'entregue' && a.status !== 'entregue') return -1;
    return b.id - a.id;
  });

  el.innerHTML = ordenados.map(p => {
    const idx         = ORDEM.indexOf(p.status);
    const podeAvancar = idx < ORDEM.length - 1;

    const itensHTML = p.itens.map(item => `
      <div class="item-row">
        <div>
          <div>${item.qtd}× ${item.nome}</div>
          ${item.extras && item.extras.length
            ? `<div class="item-extras">${item.extras.join(', ')}</div>`
            : ''}
        </div>
        <div>R$ ${(item.preco * item.qtd).toFixed(2)}</div>
      </div>`).join('');

    const proximoLabel = {
      aguardando: '✅ Confirmar Pedido',
      confirmado: '🛵 Marcar a Caminho',
      a_caminho:  '🎉 Marcar como Entregue',
      entregue:   'Entregue',
    }[p.status];

    const proximoClass = {
      aguardando: 'btn-confirmar',
      confirmado: 'btn-caminho',
      a_caminho:  'btn-entregue',
      entregue:   'btn-entregue',
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
          <strong>👤 ${p.cliente.nome}</strong><br>
          📞 ${p.cliente.tel}<br>
          🏠 ${p.cliente.end}
        </div>

        <div class="itens-lista">
          ${itensHTML}
          <div class="item-row">
            <span>Taxa de entrega</span>
            <span>R$ ${Number(p.taxa_entrega || 0).toFixed(2)}</span>
          </div>
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
          ${linkWA ? `
            <a class="btn-acao btn-whatsapp" href="${linkWA}" target="_blank" rel="noopener">
              📲 Avisar no WhatsApp
            </a>` : ''}
        </div>
      </div>`;
  }).join('');
}

// Atualiza a cada 5 segundos para pegar novos pedidos
atualizarBotaoNotificacao();
render();
setInterval(render, 5000);
