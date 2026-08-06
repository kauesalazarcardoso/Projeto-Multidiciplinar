const HORARIO_API = location.hostname === 'localhost'
  ? 'http://localhost:5000'
  : 'https://acai-express-backend.onrender.com';

function _diaAtual() {
  const dias = ['domingo', 'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado'];
  return dias[new Date().getDay()];
}

async function carregarStatusHorario() {
  const alvo = document.getElementById('horario-status');
  if (!alvo) return;

  try {
    const res = await fetch(`${HORARIO_API}/horario`);
    const data = await res.json();
    const hoje = data.horarios.find(h => h.dia === _diaAtual());

    if (data.aberto_agora) {
      alvo.textContent = `Aberto agora — hoje até às ${hoje ? hoje.fecha : '22:00'}`;
      alvo.className = 'horario-status horario-aberto';
    } else if (hoje && hoje.fechado) {
      alvo.textContent = 'Fechado hoje';
      alvo.className = 'horario-status horario-fechado';
    } else {
      alvo.textContent = `Fechado agora — hoje: ${hoje ? `${hoje.abre} às ${hoje.fecha}` : 'consulte o chat'}`;
      alvo.className = 'horario-status horario-fechado';
    }
  } catch (e) {
    alvo.textContent = '';
  }
}

carregarStatusHorario();
