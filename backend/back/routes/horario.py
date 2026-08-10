import re

from flask import Blueprint, jsonify, request

import horario as horario_mod
from database import get_conn
from routes.auth import login_required

horario_bp = Blueprint('horario', __name__)

_ORDEM_SEMANA = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
_HORA_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@horario_bp.route("/horario", methods=["GET"])
def listar_horarios():
    mapa = horario_mod.buscar_horarios()
    horarios = [
        {"dia": d, "abre": mapa[d]["abre"], "fecha": mapa[d]["fecha"], "fechado": mapa[d]["fechado"]}
        for d in _ORDEM_SEMANA if d in mapa
    ]
    aberto, motivo = horario_mod.esta_aberto()
    return jsonify({"horarios": horarios, "aberto_agora": aberto, "motivo": motivo})


@horario_bp.route("/horario/<dia>", methods=["PUT"])
@login_required
def atualizar_horario(dia):
    if dia not in _ORDEM_SEMANA:
        return jsonify({"erro": "Dia inválido"}), 400

    data = request.get_json()
    if not data or not all(k in data for k in ("abre", "fecha", "fechado")):
        return jsonify({"erro": "Campos 'abre', 'fecha' e 'fechado' são obrigatórios"}), 400

    if not _HORA_RE.match(str(data["abre"])) or not _HORA_RE.match(str(data["fecha"])):
        return jsonify({"erro": "Horário inválido, use HH:MM"}), 400

    fechado = bool(data["fechado"])
    if not fechado and data["abre"] >= data["fecha"]:
        return jsonify({"erro": "Horário de abertura deve ser antes do fechamento"}), 400

    with get_conn() as conn:
        conn.execute(
            "UPDATE horarios SET abre = %s, fecha = %s, fechado = %s WHERE dia = %s",
            (data["abre"], data["fecha"], int(fechado), dia)
        )

    return jsonify({"dia": dia, "abre": data["abre"], "fecha": data["fecha"], "fechado": fechado})
