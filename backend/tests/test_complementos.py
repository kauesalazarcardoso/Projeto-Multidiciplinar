import json


def test_criar_complemento_sem_preco_fica_gratuito(client, auth_headers):
    response = client.post(
        "/complementos", json={"nome": "Confete", "categoria": "Complementos Gratuitos"}, headers=auth_headers
    )

    assert response.status_code == 201

    data = json.loads(response.data)
    assert data["preco"] == 0


def test_criar_complemento_com_preco(client, auth_headers):
    response = client.post(
        "/complementos",
        json={"nome": "Oreo", "preco": 2.0, "categoria": "Complementos Adicionais"},
        headers=auth_headers,
    )

    assert response.status_code == 201

    data = json.loads(response.data)
    assert data["preco"] == 2.0


def test_criar_complemento_preco_negativo_invalido(client, auth_headers):
    response = client.post(
        "/complementos",
        json={"nome": "Oreo", "preco": -1, "categoria": "Complementos Adicionais"},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_criar_complemento_sem_categoria_invalido(client, auth_headers):
    response = client.post(
        "/complementos", json={"nome": "Oreo", "preco": 2.0}, headers=auth_headers
    )

    assert response.status_code == 400


def test_criar_complemento_categoria_invalida(client, auth_headers):
    response = client.post(
        "/complementos",
        json={"nome": "Oreo", "preco": 2.0, "categoria": "Sobremesas"},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_criar_complemento_categoria_valida(client, auth_headers):
    response = client.post(
        "/complementos", json={"nome": "Kiwi Fatiado", "categoria": "Frutas"}, headers=auth_headers
    )

    assert response.status_code == 201
    assert json.loads(response.data)["categoria"] == "Frutas"


def test_listar_complementos_retorna_preco_e_categoria(client, auth_headers):
    client.post(
        "/complementos",
        json={"nome": "Kitkat", "preco": 2.0, "categoria": "Complementos Adicionais"},
        headers=auth_headers,
    )

    response = client.get("/complementos")

    data = json.loads(response.data)
    kitkat = next(c for c in data if c["nome"] == "Kitkat")
    assert kitkat["preco"] == 2.0
    assert kitkat["categoria"] == "Complementos Adicionais"


def test_listar_complementos_retorna_categoria_do_seed(client):
    response = client.get("/complementos")

    data = json.loads(response.data)
    banana = next(c for c in data if c["nome"] == "Banana")
    assert banana["categoria"] == "Frutas"

    nutella = next(c for c in data if c["nome"] == "Nutella")
    assert nutella["categoria"] == "Calda"


def test_editar_complemento_exige_login(client):
    response = client.put(
        "/complementos/1", json={"nome": "Kitkat", "preco": 2.0, "categoria": "Complementos Adicionais"}
    )

    assert response.status_code == 401


def test_editar_complemento_atualiza_preco_e_categoria(client, auth_headers):
    criado = client.post(
        "/complementos",
        json={"nome": "Granulado", "preco": 0, "categoria": "Complementos Gratuitos"},
        headers=auth_headers,
    )
    comp_id = json.loads(criado.data)["id"]

    response = client.put(
        f"/complementos/{comp_id}",
        json={"nome": "Granulado", "preco": 3.0, "categoria": "Complementos Adicionais"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = json.loads(response.data)
    assert dados["preco"] == 3.0
    assert dados["categoria"] == "Complementos Adicionais"

    listagem = json.loads(client.get("/complementos").data)
    granulado = next(c for c in listagem if c["id"] == comp_id)
    assert granulado["preco"] == 3.0
    assert granulado["categoria"] == "Complementos Adicionais"


def test_editar_complemento_categoria_invalida(client, auth_headers):
    criado = client.post(
        "/complementos", json={"nome": "Granulado", "categoria": "Frutas"}, headers=auth_headers
    )
    comp_id = json.loads(criado.data)["id"]

    response = client.put(
        f"/complementos/{comp_id}",
        json={"nome": "Granulado", "preco": 0, "categoria": "Sobremesas"},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_editar_complemento_inexistente(client, auth_headers):
    response = client.put(
        "/complementos/999999",
        json={"nome": "X", "preco": 1, "categoria": "Complementos Adicionais"},
        headers=auth_headers,
    )

    assert response.status_code == 404
