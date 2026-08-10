import uuid

from flask import Blueprint, jsonify, request

import horario as horario_mod
import mercado_pago

pagamentos_bp = Blueprint('pagamentos', __name__)


def _checar_aberto():
    aberto, motivo = horario_mod.esta_aberto()
    if not aberto:
        return jsonify({"erro": "Estabelecimento fechado no momento", "motivo": motivo}), 403
    return None


def _validar_valor_email(data):
    if not data or "valor" not in data or "email" not in data:
        return "Campos 'valor' e 'email' são obrigatórios"

    if not isinstance(data["valor"], (int, float)) or data["valor"] <= 0:
        return "Valor inválido"

    email = str(data["email"]).strip()
    if "@" not in email or len(email) < 5:
        return "E-mail inválido"

    return None


def _erro_mp(order):
    """Extrai uma mensagem de erro legível quando a resposta da Mercado Pago
    não tem o formato esperado (ex: erro de validação sem 'transactions')."""
    if not order:
        return "Sem resposta da Mercado Pago"
    if order.get("errors"):
        return order["errors"][0].get("message", "Erro na Mercado Pago")
    if order.get("status") == "failed" or "transactions" not in order:
        return "Não foi possível processar o pagamento"
    return None


@pagamentos_bp.route("/pagamentos/pix", methods=["POST"])
def gerar_cobranca_pix():
    erro_aberto = _checar_aberto()
    if erro_aberto:
        return erro_aberto

    data = request.get_json()

    erro = _validar_valor_email(data)
    if erro:
        return jsonify({"erro": erro}), 400

    external_reference = "acai-" + uuid.uuid4().hex[:12]
    order = mercado_pago.criar_order_pix(
        data["valor"], data["email"], external_reference, nome=data.get("nome")
    )

    erro_mp = _erro_mp(order)
    if erro_mp:
        return jsonify({"erro": erro_mp}), 400

    payment_method = order["transactions"]["payments"][0]["payment_method"]

    return jsonify({
        "mp_order_id": order["id"],
        "qr_code_base64": payment_method.get("qr_code_base64"),
        "qr_code": payment_method.get("qr_code"),
    }), 201


@pagamentos_bp.route("/pagamentos/cartao", methods=["POST"])
def processar_cartao():
    erro_aberto = _checar_aberto()
    if erro_aberto:
        return erro_aberto

    data = request.get_json()

    erro = _validar_valor_email(data)
    if erro:
        return jsonify({"erro": erro}), 400

    if not data or not all(k in data for k in ("token", "payment_method_id", "installments")):
        return jsonify({"erro": "Dados do cartão incompletos"}), 400

    external_reference = "acai-" + uuid.uuid4().hex[:12]
    order = mercado_pago.criar_order_cartao(
        data["valor"], data["email"], data["token"], data["payment_method_id"],
        data["installments"], external_reference, nome=data.get("nome")
    )

    erro_mp = _erro_mp(order)
    if erro_mp:
        return jsonify({"aprovado": False, "erro": erro_mp}), 400

    if not mercado_pago.order_aprovada(order):
        motivo = order["transactions"]["payments"][0].get("status_detail", "recusado")
        return jsonify({"aprovado": False, "erro": f"Pagamento recusado ({motivo})"}), 400

    return jsonify({"aprovado": True, "mp_order_id": order["id"]}), 201
