import uuid
from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from database import get_conn

auth_bp = Blueprint('auth', __name__)


def _token_da_requisicao():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    return header[len("Bearer "):].strip()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = _token_da_requisicao()
        if not token:
            return jsonify({"erro": "Autenticação necessária"}), 401
        with get_conn() as conn:
            sessao = conn.execute(
                "SELECT usuario FROM sessoes WHERE token = %s", (token,)
            ).fetchone()
        if not sessao:
            return jsonify({"erro": "Sessão inválida ou expirada"}), 401
        return fn(*args, **kwargs)
    return wrapper


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("usuario") or not data.get("senha"):
        return jsonify({"erro": "Usuário e senha são obrigatórios"}), 400

    with get_conn() as conn:
        row = conn.execute(
            "SELECT usuario, senha_hash FROM usuarios WHERE usuario = %s",
            (str(data["usuario"]).strip(),)
        ).fetchone()

        if not row or not check_password_hash(row["senha_hash"], str(data["senha"])):
            return jsonify({"erro": "Usuário ou senha incorretos"}), 401

        token = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO sessoes (token, usuario, criado_em) VALUES (%s, %s, %s)",
            (token, row["usuario"], datetime.now().isoformat())
        )

    return jsonify({"token": token, "usuario": row["usuario"]})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = _token_da_requisicao()
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM sessoes WHERE token = %s", (token,))
    return jsonify({"ok": True})
