import logging
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request

import chatbot_gemini
from database import get_conn
from extensions import limiter

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint('chatbot', __name__)


def _carregar_interaction_id(sessao_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ultima_interaction_id FROM chat_sessoes WHERE id = %s", (sessao_id,)
        ).fetchone()
    return row["ultima_interaction_id"] if row else None


def _salvar_interaction_id(sessao_id, interaction_id):
    agora = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_sessoes (id, ultima_interaction_id, criado_em, atualizado_em) "
            "VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET "
            "ultima_interaction_id = EXCLUDED.ultima_interaction_id, "
            "atualizado_em = EXCLUDED.atualizado_em",
            (sessao_id, interaction_id, agora, agora)
        )


@chatbot_bp.route("/chatbot/mensagem", methods=["POST"])
@limiter.limit("10 per minute")
def enviar_mensagem():
    data = request.get_json()
    if not data or not str(data.get("mensagem", "")).strip():
        return jsonify({"erro": "Campo 'mensagem' é obrigatório"}), 400

    sessao_id = data.get("sessao_id") or uuid.uuid4().hex
    interaction_anterior = _carregar_interaction_id(sessao_id)

    try:
        resposta_texto, nova_interaction_id = chatbot_gemini.rodar_loop_gemini(
            data["mensagem"], sessao_id, interaction_anterior
        )
    except Exception:
        logger.exception("Erro ao processar mensagem do chat (sessao_id=%s)", sessao_id)
        return jsonify({"erro": "Erro ao processar a mensagem, tente novamente."}), 500

    _salvar_interaction_id(sessao_id, nova_interaction_id)
    return jsonify({"sessao_id": sessao_id, "resposta": resposta_texto})
