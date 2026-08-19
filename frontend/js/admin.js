const API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend-738933484701.us-east1.run.app';

let _itensMap = {};

function escapeHtml(texto) {
  const div = document.createElement('div');
  div.textContent = texto;
  return div.innerHTML;
}

// ── CARDÁPIO ─────────────────────────────────────────────────────

async function carregarCardapio() {
  try {
    const res   = await fetch(`${API}/cardapio`);
    const itens = await res.json();
    _itensMap   = {};
    itens.forEach(i => { _itensMap[i.id] = i; });

    const tbody = document.getElementById('tabela-body');
    if (itens.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999">Nenhum item no cardápio.</td></tr>';
      return;
    }
    tbody.innerHTML = itens.map(item => `
      <tr>
        <td>${item.id}</td>
        <td>${escapeHtml(item.nome)}</td>
        <td>R$ ${item.preco.toFixed(2)}</td>
        <td>${escapeHtml(item.categoria)}</td>
        <td class="acoes-td">
          <button class="btn-editar" data-id="${item.id}">Editar</button>
          <button class="btn-remover" data-id="${item.id}">✕</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    document.getElementById('tabela-body').innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:#e74c3c">Erro ao conectar ao servidor.</td></tr>';
  }
}

document.getElementById('tabela-body').addEventListener('click', e => {
  const btn = e.target;
  const id  = parseInt(btn.dataset.id);
  if (btn.classList.contains('btn-editar')) abrirModal(id);
  if (btn.classList.contains('btn-remover')) removerItem(id);
});

async function adicionarItem() {
  const nome      = document.getElementById('novo-nome').value.trim();
  const preco     = parseFloat(document.getElementById('novo-preco').value);
  const categoria = document.getElementById('novo-categoria').value;
  const erro      = document.getElementById('erro-form');
  if (!nome || isNaN(preco) || preco <= 0 || !categoria) { erro.textContent = 'Preencha nome, preço e categoria válidos.'; return; }
  const res = await fetch(`${API}/cardapio`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nome, preco, categoria }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) {
    erro.textContent = '';
    document.getElementById('novo-nome').value  = '';
    document.getElementById('novo-preco').value = '';
    carregarCardapio();
  } else {
    erro.textContent = (await res.json()).erro || 'Erro ao adicionar.';
  }
}

async function removerItem(id) {
  if (!confirm('Remover este item do cardápio?')) return;
  const res = await fetch(`${API}/cardapio/${id}`, { method: 'DELETE', headers: authHeaders() });
  if (tratarRespostaAuth(res)) return;
  carregarCardapio();
}

function abrirModal(id) {
  const item = _itensMap[id];
  if (!item) return;
  document.getElementById('editar-id').value       = item.id;
  document.getElementById('editar-nome').value     = item.nome;
  document.getElementById('editar-preco').value    = item.preco;
  document.getElementById('editar-categoria').value = item.categoria;
  document.getElementById('erro-modal').textContent = '';
  document.getElementById('modal').style.display = 'flex';
}

function fecharModal() {
  document.getElementById('modal').style.display = 'none';
}

async function salvarEdicao() {
  const id        = parseInt(document.getElementById('editar-id').value);
  const nome      = document.getElementById('editar-nome').value.trim();
  const preco     = parseFloat(document.getElementById('editar-preco').value);
  const categoria = document.getElementById('editar-categoria').value;
  const erro      = document.getElementById('erro-modal');
  if (!nome || isNaN(preco) || preco <= 0 || !categoria) { erro.textContent = 'Preencha nome, preço e categoria válidos.'; return; }
  const res = await fetch(`${API}/cardapio/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nome, preco, categoria }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) { fecharModal(); carregarCardapio(); }
  else { erro.textContent = (await res.json()).erro || 'Erro ao salvar.'; }
}

document.getElementById('modal').addEventListener('click', e => {
  if (e.target === document.getElementById('modal')) fecharModal();
});

// ── COMPLEMENTOS ─────────────────────────────────────────────────

let _complementosMap = {};

// Deve espelhar CATEGORIAS_COMPLEMENTOS em backend/back/database.py
const ORDEM_CATEGORIAS_COMPLEMENTOS = ["Calda", "Frutas", "Complementos Gratuitos", "Complementos Adicionais"];

function _linhaComplemento(c) {
  const badge = c.preco > 0
    ? `<span class="badge-preco badge-pago">+R$ ${c.preco.toFixed(2)}</span>`
    : `<span class="badge-preco badge-gratis">Grátis</span>`;
  return `
    <tr>
      <td>${c.id}</td>
      <td>${escapeHtml(c.nome)}</td>
      <td>${badge}</td>
      <td>${escapeHtml(c.categoria)}</td>
      <td class="acoes-td">
        <button class="btn-editar" data-id="${c.id}">Editar</button>
        <button class="btn-remover" data-id="${c.id}">✕</button>
      </td>
    </tr>`;
}

function _linhaSeparadora(texto) {
  return `<tr class="linha-separadora"><td colspan="5">${texto}</td></tr>`;
}

async function carregarComplementos() {
  try {
    const res   = await fetch(`${API}/complementos`);
    const itens = await res.json();
    _complementosMap = {};
    itens.forEach(c => { _complementosMap[c.id] = c; });

    const tbody = document.getElementById('tabela-complementos');
    if (itens.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#999">Nenhum complemento cadastrado.</td></tr>';
      return;
    }

    let html = '';
    ORDEM_CATEGORIAS_COMPLEMENTOS.forEach(categoria => {
      const doGrupo = itens.filter(c => c.categoria === categoria);
      if (doGrupo.length === 0) return;
      html += _linhaSeparadora(`${categoria} (${doGrupo.length})`);
      html += doGrupo.map(_linhaComplemento).join('');
    });
    tbody.innerHTML = html;
  } catch (e) {
    document.getElementById('tabela-complementos').innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:#e74c3c">Erro ao conectar ao servidor.</td></tr>';
  }
}

document.getElementById('tabela-complementos').addEventListener('click', e => {
  const btn = e.target;
  const id  = parseInt(btn.dataset.id);
  if (btn.classList.contains('btn-editar')) abrirModalComplemento(id);
  if (btn.classList.contains('btn-remover')) removerComplemento(id);
});

async function adicionarComplemento() {
  const nome      = document.getElementById('novo-complemento').value.trim();
  const preco     = parseFloat(document.getElementById('novo-complemento-preco').value) || 0;
  const categoria = document.getElementById('novo-complemento-categoria').value;
  const erro      = document.getElementById('erro-complemento');
  if (!nome) { erro.textContent = 'Digite o nome do complemento.'; return; }
  if (preco < 0) { erro.textContent = 'Preço não pode ser negativo.'; return; }
  const res = await fetch(`${API}/complementos`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nome, preco, categoria }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) {
    erro.textContent = '';
    document.getElementById('novo-complemento').value = '';
    document.getElementById('novo-complemento-preco').value = '0';
    carregarComplementos();
  } else {
    erro.textContent = (await res.json()).erro || 'Erro ao adicionar.';
  }
}

async function removerComplemento(id) {
  if (!confirm('Remover este complemento?')) return;
  const res = await fetch(`${API}/complementos/${id}`, { method: 'DELETE', headers: authHeaders() });
  if (tratarRespostaAuth(res)) return;
  carregarComplementos();
}

function abrirModalComplemento(id) {
  const comp = _complementosMap[id];
  if (!comp) return;
  document.getElementById('editar-complemento-id').value        = comp.id;
  document.getElementById('editar-complemento-nome').value      = comp.nome;
  document.getElementById('editar-complemento-preco').value     = comp.preco;
  document.getElementById('editar-complemento-categoria').value = comp.categoria;
  document.getElementById('erro-modal-complemento').textContent = '';
  document.getElementById('modal-complemento').style.display = 'flex';
}

function fecharModalComplemento() {
  document.getElementById('modal-complemento').style.display = 'none';
}

async function salvarEdicaoComplemento() {
  const id        = parseInt(document.getElementById('editar-complemento-id').value);
  const nome      = document.getElementById('editar-complemento-nome').value.trim();
  const preco     = parseFloat(document.getElementById('editar-complemento-preco').value) || 0;
  const categoria = document.getElementById('editar-complemento-categoria').value;
  const erro      = document.getElementById('erro-modal-complemento');
  if (!nome) { erro.textContent = 'Digite o nome do complemento.'; return; }
  if (preco < 0) { erro.textContent = 'Preço não pode ser negativo.'; return; }
  const res = await fetch(`${API}/complementos/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nome, preco, categoria }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) { fecharModalComplemento(); carregarComplementos(); }
  else { erro.textContent = (await res.json()).erro || 'Erro ao salvar.'; }
}

document.getElementById('modal-complemento').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-complemento')) fecharModalComplemento();
});

// ── BAIRROS E TAXA DE ENTREGA ────────────────────────────────────

let _bairrosMap = {};

async function carregarBairros() {
  try {
    const res     = await fetch(`${API}/bairros`);
    const bairros = await res.json();
    _bairrosMap    = {};
    bairros.forEach(b => { _bairrosMap[b.id] = b; });

    const tbody = document.getElementById('tabela-bairros');
    if (bairros.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#999">Nenhum bairro cadastrado.</td></tr>';
      return;
    }
    tbody.innerHTML = bairros.map(b => `
      <tr>
        <td>${b.id}</td>
        <td>${escapeHtml(b.nome)}</td>
        <td>R$ ${b.taxa.toFixed(2)}</td>
        <td class="acoes-td">
          <button class="btn-editar" data-id="${b.id}">Editar</button>
          <button class="btn-remover" data-id="${b.id}">✕</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    document.getElementById('tabela-bairros').innerHTML =
      '<tr><td colspan="4" style="text-align:center;color:#e74c3c">Erro ao conectar ao servidor.</td></tr>';
  }
}

document.getElementById('tabela-bairros').addEventListener('click', e => {
  const btn = e.target;
  const id  = parseInt(btn.dataset.id);
  if (btn.classList.contains('btn-editar')) abrirModalBairro(id);
  if (btn.classList.contains('btn-remover')) removerBairro(id);
});

async function adicionarBairro() {
  const nome = document.getElementById('novo-bairro').value.trim();
  const taxa = parseFloat(document.getElementById('novo-bairro-taxa').value);
  const erro = document.getElementById('erro-bairro');
  if (!nome) { erro.textContent = 'Digite o nome do bairro.'; return; }
  if (isNaN(taxa) || taxa < 0) { erro.textContent = 'Informe uma taxa válida.'; return; }
  const res = await fetch(`${API}/bairros`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nome, taxa }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) {
    erro.textContent = '';
    document.getElementById('novo-bairro').value = '';
    document.getElementById('novo-bairro-taxa').value = '3.00';
    carregarBairros();
  } else {
    erro.textContent = (await res.json()).erro || 'Erro ao adicionar.';
  }
}

async function removerBairro(id) {
  if (!confirm('Remover este bairro?')) return;
  const res = await fetch(`${API}/bairros/${id}`, { method: 'DELETE', headers: authHeaders() });
  if (tratarRespostaAuth(res)) return;
  carregarBairros();
}

function abrirModalBairro(id) {
  const bairro = _bairrosMap[id];
  if (!bairro) return;
  document.getElementById('editar-bairro-id').value   = bairro.id;
  document.getElementById('editar-bairro-nome').value = bairro.nome;
  document.getElementById('editar-bairro-taxa').value = bairro.taxa;
  document.getElementById('erro-modal-bairro').textContent = '';
  document.getElementById('modal-bairro').style.display = 'flex';
}

function fecharModalBairro() {
  document.getElementById('modal-bairro').style.display = 'none';
}

async function salvarEdicaoBairro() {
  const id   = parseInt(document.getElementById('editar-bairro-id').value);
  const nome = document.getElementById('editar-bairro-nome').value.trim();
  const taxa = parseFloat(document.getElementById('editar-bairro-taxa').value);
  const erro = document.getElementById('erro-modal-bairro');
  if (!nome) { erro.textContent = 'Digite o nome do bairro.'; return; }
  if (isNaN(taxa) || taxa < 0) { erro.textContent = 'Informe uma taxa válida.'; return; }
  const res = await fetch(`${API}/bairros/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nome, taxa }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) { fecharModalBairro(); carregarBairros(); }
  else { erro.textContent = (await res.json()).erro || 'Erro ao salvar.'; }
}

document.getElementById('modal-bairro').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-bairro')) fecharModalBairro();
});

// ── HORÁRIO DE ATENDIMENTO ─────────────────────────────────────────

const DIAS_LABEL = {
  segunda: 'Segunda', terca: 'Terça', quarta: 'Quarta', quinta: 'Quinta',
  sexta: 'Sexta', sabado: 'Sábado', domingo: 'Domingo',
};

async function carregarHorarios() {
  try {
    const res  = await fetch(`${API}/horario`);
    const data = await res.json();
    const tbody = document.getElementById('tabela-horarios');
    tbody.innerHTML = data.horarios.map(h => `
      <tr data-dia="${h.dia}">
        <td>${DIAS_LABEL[h.dia] || h.dia}</td>
        <td><input type="time" class="input-abre" value="${h.abre}" ${h.fechado ? 'disabled' : ''}></td>
        <td><input type="time" class="input-fecha" value="${h.fecha}" ${h.fechado ? 'disabled' : ''}></td>
        <td><input type="checkbox" class="input-fechado" ${h.fechado ? 'checked' : ''}></td>
        <td class="acoes-td"><button class="btn-editar btn-salvar-horario" data-dia="${h.dia}">Salvar</button></td>
      </tr>
    `).join('');
  } catch (e) {
    document.getElementById('tabela-horarios').innerHTML =
      '<tr><td colspan="5" style="text-align:center;color:#e74c3c">Erro ao conectar ao servidor.</td></tr>';
  }
}

document.getElementById('tabela-horarios').addEventListener('change', e => {
  if (!e.target.classList.contains('input-fechado')) return;
  const tr = e.target.closest('tr');
  tr.querySelector('.input-abre').disabled  = e.target.checked;
  tr.querySelector('.input-fecha').disabled = e.target.checked;
});

document.getElementById('tabela-horarios').addEventListener('click', async e => {
  if (!e.target.classList.contains('btn-salvar-horario')) return;
  const tr  = e.target.closest('tr');
  const dia = e.target.dataset.dia;
  const abre    = tr.querySelector('.input-abre').value;
  const fecha   = tr.querySelector('.input-fecha').value;
  const fechado = tr.querySelector('.input-fechado').checked;
  const res = await fetch(`${API}/horario/${dia}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ abre, fecha, fechado }),
  });
  if (tratarRespostaAuth(res)) return;
  if (res.ok) {
    const textoOriginal = e.target.textContent;
    e.target.textContent = 'Salvo ✓';
    setTimeout(() => { e.target.textContent = textoOriginal; }, 1500);
  } else {
    alert((await res.json()).erro || 'Erro ao salvar horário.');
  }
});

// ── INIT ─────────────────────────────────────────────────────────
carregarCardapio();
carregarComplementos();
carregarBairros();
carregarHorarios();
