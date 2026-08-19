const CHAT_API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend-738933484701.us-east1.run.app';

const CHAT_SESSAO_KEY = 'acaiChatSessaoId';

function getChatSessaoId() {
  return localStorage.getItem(CHAT_SESSAO_KEY);
}

function setChatSessaoId(id) {
  localStorage.setItem(CHAT_SESSAO_KEY, id);
}

function montarChatWidget() {
  const wrap = document.createElement('div');
  wrap.id = 'chat-widget';
  wrap.innerHTML = `
    <button id="chat-bolha" aria-label="Abrir chat">💬</button>
    <div id="chat-painel" style="display:none">
      <div id="chat-cabecalho">
        <span>Fale com a gente</span>
        <button id="chat-fechar" aria-label="Fechar chat">✕</button>
      </div>
      <div id="chat-mensagens"></div>
      <form id="chat-form">
        <input id="chat-input" type="text" placeholder="Digite sua mensagem..." autocomplete="off" />
        <button type="submit">Enviar</button>
      </form>
    </div>
  `;
  document.body.appendChild(wrap);

  document.getElementById('chat-bolha').addEventListener('click', () => togglePainelChat(true));
  document.getElementById('chat-fechar').addEventListener('click', () => togglePainelChat(false));
  document.getElementById('chat-form').addEventListener('submit', enviarMensagemChat);
}

function togglePainelChat(abrir) {
  const painel = document.getElementById('chat-painel');
  painel.style.display = abrir ? 'flex' : 'none';
  if (abrir && !document.getElementById('chat-mensagens').childElementCount) {
    adicionarBalaoChat('Oi! 👋 Posso te ajudar a montar seu pedido por aqui. O que você gostaria de pedir?', 'bot');
  }
}

function adicionarBalaoChat(texto, autor) {
  const div = document.createElement('div');
  div.className = `chat-balao chat-balao-${autor}`;
  div.textContent = texto;
  const lista = document.getElementById('chat-mensagens');
  lista.appendChild(div);
  lista.scrollTop = lista.scrollHeight;
  return div;
}

async function enviarMensagemChat(e) {
  e.preventDefault();
  const input = document.getElementById('chat-input');
  const texto = input.value.trim();
  if (!texto) return;
  input.value = '';
  adicionarBalaoChat(texto, 'user');

  const indicador = adicionarBalaoChat('...', 'bot');
  indicador.classList.add('chat-digitando');

  try {
    const res = await fetch(`${CHAT_API}/chatbot/mensagem`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessao_id: getChatSessaoId(), mensagem: texto }),
    });
    const data = await res.json();
    indicador.remove();
    if (!res.ok) {
      adicionarBalaoChat(data.erro || 'Não consegui processar sua mensagem agora.', 'bot');
      return;
    }
    if (data.sessao_id) setChatSessaoId(data.sessao_id);
    adicionarBalaoChat(data.resposta, 'bot');
  } catch (err) {
    indicador.remove();
    adicionarBalaoChat('Não foi possível conectar ao servidor. Tente novamente em instantes.', 'bot');
  }
}

montarChatWidget();
