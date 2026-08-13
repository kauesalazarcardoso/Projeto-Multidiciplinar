import json
import pytest


def _criar_pedido_dinheiro(client, valor=20.0):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": valor,
        "forma_pagamento": "dinheiro",
    }
    return client.post("/pedidos", json=pedido)


def test_criar_pedido(client):
    response = _criar_pedido_dinheiro(client, valor=30.0)

    assert response.status_code == 201

    data = json.loads(response.data)

    assert data["status"] == "aguardando"


def test_listar_pedidos(client, auth_headers):
    _criar_pedido_dinheiro(client, valor=15.0)

    response = client.get("/pedidos", headers=auth_headers)

    assert response.status_code == 200

    data = json.loads(response.data)

    assert isinstance(data, list)


def test_avancar_status(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)

    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["status"] == "confirmado"


def test_limpar_entregues(client, auth_headers):

    response = client.delete("/pedidos/entregues", headers=auth_headers)

    assert response.status_code == 200


def test_limpar_entregues_some_da_fila_mas_mantem_venda_no_historico(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=42.0)
    pedido_id = json.loads(criar.data)["id"]

    for _ in range(3):
        client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)

    limpar = client.delete("/pedidos/entregues", headers=auth_headers)
    assert limpar.status_code == 200
    assert json.loads(limpar.data)["arquivados"] == 1

    ativos = json.loads(client.get("/pedidos", headers=auth_headers).data)
    assert pedido_id not in [p["id"] for p in ativos]

    vendas = json.loads(client.get("/pedidos/vendas-por-dia", headers=auth_headers).data)
    assert sum(d["total"] for d in vendas) == 42.0


def test_buscar_pedido_por_id(client):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.get(f"/pedidos/{pedido_id}")

    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["forma_pagamento"] == "dinheiro"
    assert data["taxa_entrega"] == 3.0


def test_criar_pedido_sem_forma_pagamento(client):

    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": 20
    }

    response = client.post("/pedidos", json=pedido)

    assert response.status_code == 400


def test_criar_pedido_forma_pagamento_invalida(client):

    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": 20,
        "forma_pagamento": "boleto"
    }

    response = client.post("/pedidos", json=pedido)

    assert response.status_code == 400


def test_criar_pedido_dinheiro_com_troco(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": 20,
        "forma_pagamento": "dinheiro",
        "troco_para": 50
    }

    criar = client.post("/pedidos", json=pedido)
    assert criar.status_code == 201
    pedido_id = json.loads(criar.data)["id"]

    busca = client.get(f"/pedidos/{pedido_id}")
    dados = json.loads(busca.data)

    assert dados["forma_pagamento"] == "dinheiro"
    assert dados["troco_para"] == 50


def test_criar_pedido_dinheiro_troco_menor_que_total_invalido(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": 20,
        "forma_pagamento": "dinheiro",
        "troco_para": 10
    }

    response = client.post("/pedidos", json=pedido)

    assert response.status_code == 400


# ── Pix: nasce sempre pendente_pagamento, confirmação é manual ────

def _criar_pedido_pix(client, valor=20.0):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": valor,
        "forma_pagamento": "pix",
    }
    return client.post("/pedidos", json=pedido)


def test_criar_pedido_pix_sempre_pendente_pagamento(client):
    response = _criar_pedido_pix(client, valor=20.0)

    assert response.status_code == 201

    data = json.loads(response.data)
    assert data["status"] == "pendente_pagamento"


def test_criar_pedido_pix_pendente_nao_aparece_em_listar(client, auth_headers):
    criar = _criar_pedido_pix(client, valor=20.0)
    assert criar.status_code == 201

    pedido_id = json.loads(criar.data)["id"]

    listagem = client.get("/pedidos", headers=auth_headers)
    ids_listados = [p["id"] for p in json.loads(listagem.data)]
    assert pedido_id not in ids_listados

    busca = client.get(f"/pedidos/{pedido_id}")
    dados_busca = json.loads(busca.data)
    assert dados_busca["status"] == "pendente_pagamento"


def test_listar_pendentes_retorna_pix_aguardando(client, auth_headers):
    criar = _criar_pedido_pix(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.get("/pedidos/pendentes", headers=auth_headers)

    assert response.status_code == 200
    ids = [p["id"] for p in json.loads(response.data)]
    assert pedido_id in ids


def test_listar_pendentes_exige_login(client):
    response = client.get("/pedidos/pendentes")

    assert response.status_code == 401


def test_confirmar_pagamento_move_para_aguardando(client, auth_headers):
    criar = _criar_pedido_pix(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/confirmar-pagamento", headers=auth_headers)

    assert response.status_code == 200
    assert json.loads(response.data)["status"] == "aguardando"

    listagem = client.get("/pedidos", headers=auth_headers)
    ids_listados = [p["id"] for p in json.loads(listagem.data)]
    assert pedido_id in ids_listados


def test_confirmar_pagamento_exige_login(client):
    criar = _criar_pedido_pix(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/confirmar-pagamento")

    assert response.status_code == 401


def test_confirmar_pagamento_pedido_inexistente(client, auth_headers):
    response = client.patch("/pedidos/999999/confirmar-pagamento", headers=auth_headers)

    assert response.status_code == 404


def test_confirmar_pagamento_pedido_ja_confirmado_falha(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/confirmar-pagamento", headers=auth_headers)

    assert response.status_code == 400


# ── Cartão: pago na entrega (maquininha), sem verificação online ──

def _criar_pedido_cartao(client, itens, total):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": itens,
        "total": total,
        "forma_pagamento": "cartao",
    }
    return client.post("/pedidos", json=pedido)


def test_criar_pedido_cartao_vai_direto_aguardando(client):
    itens = [{"nome": "Açaí", "preco": 20.0, "qtd": 1}]
    response = _criar_pedido_cartao(client, itens, 23.0)

    assert response.status_code == 201
    assert json.loads(response.data)["status"] == "aguardando"


def test_criar_pedido_cartao_taxa_maquininha_ate_50_reais_em_itens(client):
    itens = [{"nome": "Açaí", "preco": 50.0, "qtd": 1}]
    criar = _criar_pedido_cartao(client, itens, 55.0)
    pedido_id = json.loads(criar.data)["id"]

    dados = json.loads(client.get(f"/pedidos/{pedido_id}").data)
    assert dados["taxa_entrega"] == 3.0
    assert dados["taxa_maquininha"] == 2.0


def test_criar_pedido_cartao_taxa_maquininha_acima_de_50_reais_em_itens(client):
    itens = [{"nome": "Açaí", "preco": 50.01, "qtd": 1}]
    criar = _criar_pedido_cartao(client, itens, 53.01)
    pedido_id = json.loads(criar.data)["id"]

    dados = json.loads(client.get(f"/pedidos/{pedido_id}").data)
    assert dados["taxa_entrega"] == 3.0
    assert dados["taxa_maquininha"] == 3.0


def test_criar_pedido_pix_taxa_maquininha_sempre_zero(client):
    response = _criar_pedido_pix(client, valor=20.0)
    pedido_id = json.loads(response.data)["id"]

    dados = json.loads(client.get(f"/pedidos/{pedido_id}").data)
    assert dados["taxa_maquininha"] == 0.0


def test_criar_pedido_dinheiro_taxa_maquininha_sempre_zero(client):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    dados = json.loads(client.get(f"/pedidos/{pedido_id}").data)
    assert dados["taxa_maquininha"] == 0.0


def test_criar_pedido_com_cartao_fluxo_completo(client):
    itens = [{"nome": "Açaí", "preco": 20.0, "qtd": 1}]
    criar = _criar_pedido_cartao(client, itens, 23.0)
    assert criar.status_code == 201

    pedido_id = json.loads(criar.data)["id"]

    response = client.get(f"/pedidos/{pedido_id}")
    data = json.loads(response.data)

    assert data["forma_pagamento"] == "cartao"
    assert data["status"] == "aguardando"
    assert data["cartao_bandeira"] is None
    assert data["cartao_ultimos4"] is None


# ── Observação ──────────────────────────────────────────────────

def test_criar_pedido_com_observacao(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": 20,
        "forma_pagamento": "dinheiro",
        "observacao": "  sem leite condensado  ",
    }
    criar = client.post("/pedidos", json=pedido)
    pedido_id = json.loads(criar.data)["id"]

    busca = client.get(f"/pedidos/{pedido_id}")
    assert json.loads(busca.data)["observacao"] == "sem leite condensado"


def test_criar_pedido_sem_observacao_vira_none(client):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    busca = client.get(f"/pedidos/{pedido_id}")
    assert json.loads(busca.data)["observacao"] is None


# ── Histórico de vendas ─────────────────────────────────────────

def test_vendas_por_dia_exige_login(client):
    response = client.get("/pedidos/vendas-por-dia")

    assert response.status_code == 401


def test_vendas_por_dia_soma_so_entregues(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=42.0)
    pedido_id = json.loads(criar.data)["id"]

    # avança até "entregue"
    for _ in range(3):
        client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)

    response = client.get("/pedidos/vendas-por-dia", headers=auth_headers)
    assert response.status_code == 200

    dados = json.loads(response.data)
    assert len(dados) == 7
    total_geral = sum(d["total"] for d in dados)
    assert total_geral == 42.0


def test_vendas_por_dia_pedido_nao_entregue_nao_conta(client, auth_headers):
    _criar_pedido_dinheiro(client, valor=99.0)  # fica em "aguardando", não avança

    response = client.get("/pedidos/vendas-por-dia", headers=auth_headers)

    dados = json.loads(response.data)
    total_geral = sum(d["total"] for d in dados)
    assert total_geral == 0
