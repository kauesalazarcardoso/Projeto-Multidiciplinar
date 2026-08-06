import json

import horario


def test_get_horario_retorna_7_dias(client):
    response = client.get("/horario")

    assert response.status_code == 200

    data = json.loads(response.data)

    assert len(data["horarios"]) == 7
    dias = {h["dia"] for h in data["horarios"]}
    assert dias == {"segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"}

    segunda = next(h for h in data["horarios"] if h["dia"] == "segunda")
    assert segunda["fechado"] is True


def test_get_horario_aberto_agora_campo_presente(client):
    response = client.get("/horario")

    data = json.loads(response.data)

    assert "aberto_agora" in data
    assert "motivo" in data


def test_put_horario_requer_login(client):
    response = client.put("/horario/segunda", json={"abre": "10:00", "fecha": "20:00", "fechado": False})

    assert response.status_code == 401


def test_put_horario_atualiza_dia(client, auth_headers):
    response = client.put(
        "/horario/terca",
        json={"abre": "10:00", "fecha": "20:00", "fechado": False},
        headers=auth_headers,
    )

    assert response.status_code == 200

    data = json.loads(response.data)
    assert data["abre"] == "10:00"
    assert data["fecha"] == "20:00"

    # persistiu de fato
    response = client.get("/horario")
    terca = next(h for h in json.loads(response.data)["horarios"] if h["dia"] == "terca")
    assert terca["abre"] == "10:00"
    assert terca["fecha"] == "20:00"


def test_put_horario_dia_invalido(client, auth_headers):
    response = client.put(
        "/horario/foo",
        json={"abre": "10:00", "fecha": "20:00", "fechado": False},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_put_horario_valida_formato_hora(client, auth_headers):
    response = client.put(
        "/horario/quarta",
        json={"abre": "25:99", "fecha": "20:00", "fechado": False},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_put_horario_abre_apos_fecha_invalido(client, auth_headers):
    response = client.put(
        "/horario/quinta",
        json={"abre": "20:00", "fecha": "10:00", "fechado": False},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_put_horario_fechado_ignora_ordem_dos_horarios(client, auth_headers):
    response = client.put(
        "/horario/sexta",
        json={"abre": "20:00", "fecha": "10:00", "fechado": True},
        headers=auth_headers,
    )

    assert response.status_code == 200


def test_pedidos_bloqueado_quando_fechado(client, monkeypatch):
    monkeypatch.setattr(horario, "esta_aberto", lambda momento=None: (False, "fechado_hoje"))

    pedido = {
        "cliente": {"nome": "Kauê", "tel": "51999999999", "end": "Rua X, 123"},
        "itens": [{"nome": "Açaí", "preco": 20.0, "qtd": 1}],
        "total": 20.0,
        "forma_pagamento": "dinheiro",
    }
    response = client.post("/pedidos", json=pedido)

    assert response.status_code == 403

    data = json.loads(response.data)
    assert data["motivo"] == "fechado_hoje"
