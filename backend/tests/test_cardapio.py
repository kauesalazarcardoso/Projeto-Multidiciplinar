import json


def test_criar_item_sem_categoria_invalido(client, auth_headers):
    response = client.post("/cardapio", json={"nome": "Item X", "preco": 10}, headers=auth_headers)

    assert response.status_code == 400


def test_criar_item_categoria_invalida(client, auth_headers):
    response = client.post(
        "/cardapio", json={"nome": "Item X", "preco": 10, "categoria": "Sorvetes"}, headers=auth_headers
    )

    assert response.status_code == 400


def test_criar_item_categoria_valida(client, auth_headers):
    response = client.post(
        "/cardapio", json={"nome": "Item X", "preco": 10, "categoria": "Cupuaçu"}, headers=auth_headers
    )

    assert response.status_code == 201
    assert json.loads(response.data)["categoria"] == "Cupuaçu"


def test_listar_cardapio_retorna_categoria(client):
    response = client.get("/cardapio")

    data = json.loads(response.data)
    item = next(i for i in data if i["nome"] == "Copo 330ml Açaí Tradicional")
    assert item["categoria"] == "Açaí Tradicional"


def test_categorias_antigas_nao_existem_mais(client):
    response = client.get("/cardapio")

    data = json.loads(response.data)
    categorias = {i["categoria"] for i in data}
    assert categorias.issubset({"Açaí Tradicional", "Cupuaçu", "Iogurte Grego", "Iogurte Grego com Morango"})


def test_editar_item_atualiza_categoria(client, auth_headers):
    criado = client.post(
        "/cardapio", json={"nome": "Item Y", "preco": 10, "categoria": "Cupuaçu"}, headers=auth_headers
    )
    item_id = json.loads(criado.data)["id"]

    response = client.put(
        f"/cardapio/{item_id}",
        json={"nome": "Item Y", "preco": 10, "categoria": "Iogurte Grego"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert json.loads(response.data)["categoria"] == "Iogurte Grego"


def test_editar_item_categoria_invalida(client, auth_headers):
    criado = client.post(
        "/cardapio", json={"nome": "Item Z", "preco": 10, "categoria": "Cupuaçu"}, headers=auth_headers
    )
    item_id = json.loads(criado.data)["id"]

    response = client.put(
        f"/cardapio/{item_id}",
        json={"nome": "Item Z", "preco": 10, "categoria": "Invalida"},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_editar_item_categoria_antiga_agora_invalida(client, auth_headers):
    criado = client.post(
        "/cardapio", json={"nome": "Item W", "preco": 10, "categoria": "Cupuaçu"}, headers=auth_headers
    )
    item_id = json.loads(criado.data)["id"]

    response = client.put(
        f"/cardapio/{item_id}",
        json={"nome": "Item W", "preco": 10, "categoria": "Copos"},
        headers=auth_headers,
    )

    assert response.status_code == 400
