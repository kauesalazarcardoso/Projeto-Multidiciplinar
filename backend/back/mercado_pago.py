import os
import time
import uuid

import requests

API_BASE = "https://api.mercadopago.com/v1"

# A Mercado Pago às vezes leva alguns segundos para gerar o QR Code do Pix
# depois de criar a order (fica em status "processing"/"in_process" até lá).
_PIX_QR_TENTATIVAS = 10
_PIX_QR_INTERVALO_SEGUNDOS = 2


def _access_token():
    return os.environ["MP_ACCESS_TOKEN"]


def _headers():
    return {
        "Authorization": f"Bearer {_access_token()}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4()),
    }


def _normalizar(resp_json):
    return resp_json.get("data", resp_json)


def _payer(email, nome=None):
    """Monta o payer da order. Em sandbox, o primeiro nome do pagador determina
    o resultado simulado (ex: 'APRO' aprova automaticamente, 'FUND' recusa por
    saldo insuficiente) — por isso vale sempre repassar o nome informado."""
    payer = {"email": email}
    if nome:
        primeiro, *resto = nome.strip().split(None, 1)
        payer["first_name"] = primeiro
        if resto:
            payer["last_name"] = resto[0]
    return payer


def criar_order_pix(valor, email, external_reference, nome=None):
    body = {
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": f"{valor:.2f}",
        "external_reference": external_reference,
        "payer": _payer(email, nome),
        "transactions": {
            "payments": [
                {
                    "amount": f"{valor:.2f}",
                    "payment_method": {"id": "pix", "type": "bank_transfer"},
                }
            ]
        },
    }
    resp = requests.post(f"{API_BASE}/orders", json=body, headers=_headers(), timeout=15)
    order = _normalizar(resp.json())

    for _ in range(_PIX_QR_TENTATIVAS):
        if "errors" in order or "transactions" not in order:
            break
        payment_method = order["transactions"]["payments"][0].get("payment_method", {})
        if payment_method.get("qr_code"):
            break
        time.sleep(_PIX_QR_INTERVALO_SEGUNDOS)
        order = buscar_order(order["id"])

    return order


def criar_order_cartao(valor, email, token, payment_method_id, installments, external_reference, nome=None):
    body = {
        "type": "online",
        "processing_mode": "automatic",
        "total_amount": f"{valor:.2f}",
        "external_reference": external_reference,
        "payer": _payer(email, nome),
        "transactions": {
            "payments": [
                {
                    "amount": f"{valor:.2f}",
                    "payment_method": {
                        "id": payment_method_id,
                        "type": "credit_card",
                        "token": token,
                        "installments": installments,
                    },
                }
            ]
        },
    }
    resp = requests.post(f"{API_BASE}/orders", json=body, headers=_headers(), timeout=15)
    return _normalizar(resp.json())


def buscar_order(mp_order_id):
    resp = requests.get(
        f"{API_BASE}/orders/{mp_order_id}",
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=15,
    )
    return _normalizar(resp.json())


def order_aprovada(order):
    return order.get("status") == "processed" and order.get("status_detail") == "accredited"


def order_pix_pendente(order):
    return order.get("status") == "action_required"


def criar_preferencia_checkout_pro(valor, email, external_reference, nome=None):
    """Gera um link de pagamento hospedado (Checkout Pro) para o cliente
    inserir os dados do cartão fora do chat. Usa a API de Preferences, que é
    diferente da API de Orders usada em criar_order_pix/criar_order_cartao."""
    body = {
        "items": [{
            "title": "Pedido Açaí Express",
            "quantity": 1,
            "unit_price": valor,
            "currency_id": "BRL",
        }],
        "payer": _payer(email, nome),
        "external_reference": external_reference,
    }
    resp = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        json=body, headers=_headers(), timeout=15,
    )
    pref = resp.json()
    return {"id": pref.get("id"), "checkout_url": pref.get("init_point")}


def buscar_pagamento_por_referencia(external_reference):
    """Procura, via API de Payments (Checkout Pro não expõe uma 'order' como
    a API de Orders), um pagamento aprovado com o external_reference dado.
    Retorna o payment dict se encontrar um aprovado, senão None."""
    resp = requests.get(
        "https://api.mercadopago.com/v1/payments/search",
        params={"external_reference": external_reference, "sort": "date_created", "criteria": "desc"},
        headers={"Authorization": f"Bearer {_access_token()}"},
        timeout=15,
    )
    resultados = resp.json().get("results", [])
    for pagamento in resultados:
        if pagamento.get("status") == "approved":
            return pagamento
    return None
