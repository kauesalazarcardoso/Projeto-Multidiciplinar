import json

from database import OWNER_USUARIO_PADRAO, OWNER_SENHA_PADRAO


def test_login_sucesso(client):
    response = client.post("/login", json={
        "usuario": OWNER_USUARIO_PADRAO, "senha": OWNER_SENHA_PADRAO
    })

    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["token"]


def test_login_senha_incorreta(client):
    response = client.post("/login", json={
        "usuario": OWNER_USUARIO_PADRAO, "senha": "senha-errada"
    })

    assert response.status_code == 401


def test_login_usuario_inexistente(client):
    response = client.post("/login", json={
        "usuario": "ladrao", "senha": "qualquer"
    })

    assert response.status_code == 401


def test_login_dados_incompletos(client):
    response = client.post("/login", json={"usuario": OWNER_USUARIO_PADRAO})

    assert response.status_code == 400


def test_rota_protegida_sem_token(client):
    response = client.get("/pedidos")

    assert response.status_code == 401


def test_rota_protegida_com_token_invalido(client):
    response = client.get("/pedidos", headers={"Authorization": "Bearer token-invalido"})

    assert response.status_code == 401


def test_rota_protegida_com_token_valido(client, auth_headers):
    response = client.get("/pedidos", headers=auth_headers)

    assert response.status_code == 200


def test_logout_invalida_token(client, auth_headers):
    resp_logout = client.post("/logout", headers=auth_headers)
    assert resp_logout.status_code == 200

    response = client.get("/pedidos", headers=auth_headers)
    assert response.status_code == 401


def test_cardapio_post_exige_login(client):
    response = client.post("/cardapio", json={"nome": "Item Teste", "preco": 10, "categoria": "Cupuaçu"})

    assert response.status_code == 401


def test_cardapio_post_com_login_funciona(client, auth_headers):
    response = client.post(
        "/cardapio", json={"nome": "Item Teste", "preco": 10, "categoria": "Cupuaçu"}, headers=auth_headers
    )

    assert response.status_code == 201
