import json


def test_criar_complemento_sem_preco_fica_gratuito(client, auth_headers):
    response = client.post("/complementos", json={"nome": "Confete"}, headers=auth_headers)

    assert response.status_code == 201

    data = json.loads(response.data)
    assert data["preco"] == 0


def test_criar_complemento_com_preco(client, auth_headers):
    response = client.post(
        "/complementos", json={"nome": "Oreo", "preco": 2.0}, headers=auth_headers
    )

    assert response.status_code == 201

    data = json.loads(response.data)
    assert data["preco"] == 2.0


def test_criar_complemento_preco_negativo_invalido(client, auth_headers):
    response = client.post(
        "/complementos", json={"nome": "Oreo", "preco": -1}, headers=auth_headers
    )

    assert response.status_code == 400


def test_listar_complementos_retorna_preco(client, auth_headers):
    client.post("/complementos", json={"nome": "Kitkat", "preco": 2.0}, headers=auth_headers)

    response = client.get("/complementos")

    data = json.loads(response.data)
    kitkat = next(c for c in data if c["nome"] == "Kitkat")
    assert kitkat["preco"] == 2.0


def test_editar_complemento_exige_login(client):
    response = client.put("/complementos/1", json={"nome": "Kitkat", "preco": 2.0})

    assert response.status_code == 401


def test_editar_complemento_atualiza_preco(client, auth_headers):
    criado = client.post(
        "/complementos", json={"nome": "Granulado", "preco": 0}, headers=auth_headers
    )
    comp_id = json.loads(criado.data)["id"]

    response = client.put(
        f"/complementos/{comp_id}",
        json={"nome": "Granulado", "preco": 3.0},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert json.loads(response.data)["preco"] == 3.0

    listagem = json.loads(client.get("/complementos").data)
    granulado = next(c for c in listagem if c["id"] == comp_id)
    assert granulado["preco"] == 3.0


def test_editar_complemento_inexistente(client, auth_headers):
    response = client.put(
        "/complementos/999999", json={"nome": "X", "preco": 1}, headers=auth_headers
    )

    assert response.status_code == 404
