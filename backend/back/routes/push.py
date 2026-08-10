from datetime import datetime

from flask import Blueprint, jsonify, request

import push
from database import get_conn
from routes.auth import login_required

push_bp = Blueprint('push', __name__)


@push_bp.route("/push/subscribe", methods=["POST"])
@login_required
def subscribe():
    data = request.get_json()
    if not data or "endpoint" not in data or "keys" not in data:
        return jsonify({"erro": "Inscrição inválida"}), 400

    if not push.endpoint_valido(data["endpoint"]):
        return jsonify({"erro": "Endpoint de push não reconhecido"}), 400

    keys = data["keys"]
    if not keys.get("p256dh") or not keys.get("auth"):
        return jsonify({"erro": "Inscrição inválida"}), 400

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO push_subscriptions (endpoint, p256dh, auth, criado_em) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (endpoint) DO NOTHING",
            (data["endpoint"], keys["p256dh"], keys["auth"], datetime.now().isoformat())
        )

    return jsonify({"ok": True}), 201
