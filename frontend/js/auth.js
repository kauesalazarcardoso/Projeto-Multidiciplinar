const AUTH_API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend-738933484701.us-east1.run.app';

function getToken() {
  return localStorage.getItem('authToken');
}

function setToken(token) {
  localStorage.setItem('authToken', token);
}

function clearToken() {
  localStorage.removeItem('authToken');
}

function authHeaders() {
  const token = getToken();
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

// Chame no topo de páginas protegidas para barrar acesso sem login.
function exigirLogin() {
  if (!getToken()) {
    const pagina = location.pathname.split('/').pop();
    location.href = `login.html?next=${encodeURIComponent(pagina)}`;
  }
}

// Se a resposta indicar sessão inválida/expirada, limpa o token e manda pro login.
// Retorna true quando isso aconteceu (o chamador deve parar o que estava fazendo).
function tratarRespostaAuth(res) {
  if (res.status === 401) {
    clearToken();
    location.href = 'login.html';
    return true;
  }
  return false;
}

async function logout() {
  const token = getToken();
  clearToken();
  if (token) {
    try {
      await fetch(`${AUTH_API}/logout`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
    } catch (e) { /* sessão local já foi limpa, ignora falha de rede */ }
  }
  location.href = 'login.html';
}
