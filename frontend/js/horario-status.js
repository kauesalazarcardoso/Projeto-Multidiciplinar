function _diaAtual() {
  const dias = ['domingo', 'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado'];
  return dias[new Date().getDay()];
}

function _resumoSemanal(horarios) {
  const nomes = { domingo: 'Dom', segunda: 'Seg', terca: 'Ter', quarta: 'Qua', quinta: 'Qui', sexta: 'Sex', sabado: 'Sáb' };
  const abertos = horarios.filter(h => !h.fechado);
  if (abertos.length === 0) return 'Fechado todos os dias';

  const mesmoHorario = abertos.every(h => h.abre === abertos[0].abre && h.fecha === abertos[0].fecha);
  if (mesmoHorario) {
    const primeiro = nomes[abertos[0].dia];
    const ultimo = nomes[abertos[abertos.length - 1].dia];
    const intervalo = abertos.length > 1 ? `${primeiro} a ${ultimo}` : primeiro;
    return `${intervalo}: ${abertos[0].abre} às ${abertos[0].fecha}`;
  }
  return abertos.map(h => `${nomes[h.dia]} ${h.abre}-${h.fecha}`).join(', ');
}

async function carregarStatusHorario() {
  const alvo = document.getElementById('horario-status');
  const resumo = document.getElementById('footer-horario');
  if (!alvo && !resumo) return;

  try {
    const res = await fetch(`${API}/horario`);
    const data = await res.json();
    const hoje = data.horarios.find(h => h.dia === _diaAtual());

    if (alvo) {
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
    }

    if (resumo) {
      resumo.textContent = `⏰ ${_resumoSemanal(data.horarios)}`;
    }
  } catch (e) {
    if (alvo) alvo.textContent = '';
  }
}

carregarStatusHorario();
