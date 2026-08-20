import json
import pytest


def _criar_pedido_dinheiro(client, valor=20.0):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "bairro": "Centro",
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


def test_recusar_pedido(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/recusar", headers=auth_headers)

    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["status"] == "recusado"


def test_recusar_pedido_ja_entregue_falha(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    for _ in range(3):
        client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)

    response = client.patch(f"/pedidos/{pedido_id}/recusar", headers=auth_headers)

    assert response.status_code == 400


def test_recusar_pedido_inexistente(client, auth_headers):
    response = client.patch("/pedidos/999999/recusar", headers=auth_headers)

    assert response.status_code == 404


def test_recusar_pedido_sem_auth(client):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/recusar")

    assert response.status_code == 401


def test_limpar_entregues(client, auth_headers):

    response = client.delete("/pedidos/entregues", headers=auth_headers)

    assert response.status_code == 200


def test_limpar_entregues_tambem_arquiva_recusados(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    client.patch(f"/pedidos/{pedido_id}/recusar", headers=auth_headers)

    limpar = client.delete("/pedidos/entregues", headers=auth_headers)
    assert limpar.status_code == 200
    assert json.loads(limpar.data)["arquivados"] == 1

    ativos = json.loads(client.get("/pedidos", headers=auth_headers).data)
    assert pedido_id not in [p["id"] for p in ativos]


def test_voltar_status(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)  # aguardando -> confirmado

    response = client.patch(f"/pedidos/{pedido_id}/status/voltar", headers=auth_headers)

    assert response.status_code == 200
    assert json.loads(response.data)["status"] == "aguardando"


def test_voltar_status_no_inicial_falha(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/status/voltar", headers=auth_headers)

    assert response.status_code == 400


def test_voltar_status_pedido_inexistente(client, auth_headers):
    response = client.patch("/pedidos/999999/status/voltar", headers=auth_headers)

    assert response.status_code == 404


def test_voltar_status_exige_login(client):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.patch(f"/pedidos/{pedido_id}/status/voltar")

    assert response.status_code == 401


def test_voltar_status_desarquiva_pedido(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=25.0)
    pedido_id = json.loads(criar.data)["id"]

    for _ in range(3):
        client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)  # -> entregue

    client.delete("/pedidos/entregues", headers=auth_headers)  # arquiva

    ativos_antes = json.loads(client.get("/pedidos", headers=auth_headers).data)
    assert pedido_id not in [p["id"] for p in ativos_antes]

    voltar = client.patch(f"/pedidos/{pedido_id}/status/voltar", headers=auth_headers)
    assert voltar.status_code == 200
    assert json.loads(voltar.data)["status"] == "a_caminho"

    ativos_depois = json.loads(client.get("/pedidos", headers=auth_headers).data)
    assert pedido_id in [p["id"] for p in ativos_depois]


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


def test_buscar_pedido_por_token(client):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    token = json.loads(criar.data)["token"]

    response = client.get(f"/pedidos/rastrear/{token}")

    assert response.status_code == 200

    data = json.loads(response.data)

    assert data["forma_pagamento"] == "dinheiro"
    assert data["taxa_entrega"] == 3.0


def test_buscar_pedido_token_inexistente_falha(client):
    response = client.get("/pedidos/rastrear/token-que-nao-existe")

    assert response.status_code == 404


def test_buscar_pedido_por_id_numerico_nao_funciona_mais(client):
    """A rota pública de acompanhamento não aceita mais o id numérico como
    chave de busca — só o token aleatório (id sequencial permitia adivinhar
    pedidos de outros clientes)."""
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.get(f"/pedidos/rastrear/{pedido_id}")

    assert response.status_code == 404


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
        "bairro": "Centro",
        "total": 20,
        "forma_pagamento": "dinheiro",
        "troco_para": 50
    }

    criar = client.post("/pedidos", json=pedido)
    assert criar.status_code == 201
    token = json.loads(criar.data)["token"]

    busca = client.get(f"/pedidos/rastrear/{token}")
    dados = json.loads(busca.data)

    assert dados["forma_pagamento"] == "dinheiro"
    assert dados["troco_para"] == 50


def test_criar_pedido_dinheiro_troco_menor_que_total_invalido(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "bairro": "Centro",
        "total": 20,
        "forma_pagamento": "dinheiro",
        "troco_para": 10
    }

    response = client.post("/pedidos", json=pedido)

    assert response.status_code == 400


# ── Pix: entra direto na fila normal, sem espera de confirmação ───

def _criar_pedido_pix(client, valor=20.0):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "bairro": "Centro",
        "total": valor,
        "forma_pagamento": "pix",
    }
    return client.post("/pedidos", json=pedido)


def test_criar_pedido_pix_vai_direto_aguardando(client):
    response = _criar_pedido_pix(client, valor=20.0)

    assert response.status_code == 201

    data = json.loads(response.data)
    assert data["status"] == "aguardando"


def test_criar_pedido_pix_aparece_em_listar(client, auth_headers):
    criar = _criar_pedido_pix(client, valor=20.0)
    assert criar.status_code == 201

    pedido_id = json.loads(criar.data)["id"]

    listagem = client.get("/pedidos", headers=auth_headers)
    ids_listados = [p["id"] for p in json.loads(listagem.data)]
    assert pedido_id in ids_listados


# ── Cartão: pago na entrega (maquininha), sem verificação online ──

def _criar_pedido_cartao(client, itens, total):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": itens,
        "bairro": "Centro",
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
    token = json.loads(criar.data)["token"]

    dados = json.loads(client.get(f"/pedidos/rastrear/{token}").data)
    assert dados["taxa_entrega"] == 3.0
    assert dados["taxa_maquininha"] == 2.0


def test_criar_pedido_cartao_taxa_maquininha_acima_de_50_reais_em_itens(client):
    itens = [{"nome": "Açaí", "preco": 50.01, "qtd": 1}]
    criar = _criar_pedido_cartao(client, itens, 53.01)
    token = json.loads(criar.data)["token"]

    dados = json.loads(client.get(f"/pedidos/rastrear/{token}").data)
    assert dados["taxa_entrega"] == 3.0
    assert dados["taxa_maquininha"] == 3.0


def test_criar_pedido_pix_taxa_maquininha_sempre_zero(client):
    response = _criar_pedido_pix(client, valor=20.0)
    token = json.loads(response.data)["token"]

    dados = json.loads(client.get(f"/pedidos/rastrear/{token}").data)
    assert dados["taxa_maquininha"] == 0.0


def test_criar_pedido_dinheiro_taxa_maquininha_sempre_zero(client):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    token = json.loads(criar.data)["token"]

    dados = json.loads(client.get(f"/pedidos/rastrear/{token}").data)
    assert dados["taxa_maquininha"] == 0.0


def test_criar_pedido_com_cartao_fluxo_completo(client):
    itens = [{"nome": "Açaí", "preco": 20.0, "qtd": 1}]
    criar = _criar_pedido_cartao(client, itens, 23.0)
    assert criar.status_code == 201

    token = json.loads(criar.data)["token"]

    response = client.get(f"/pedidos/rastrear/{token}")
    data = json.loads(response.data)

    assert data["forma_pagamento"] == "cartao"
    assert data["status"] == "aguardando"


# ── Observação ──────────────────────────────────────────────────

def test_criar_pedido_com_observacao(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "bairro": "Centro",
        "total": 20,
        "forma_pagamento": "dinheiro",
        "observacao": "  sem leite condensado  ",
    }
    criar = client.post("/pedidos", json=pedido)
    token = json.loads(criar.data)["token"]

    busca = client.get(f"/pedidos/rastrear/{token}")
    assert json.loads(busca.data)["observacao"] == "sem leite condensado"


def test_criar_pedido_sem_observacao_vira_none(client):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    token = json.loads(criar.data)["token"]

    busca = client.get(f"/pedidos/rastrear/{token}")
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


# ── Taxa de entrega por bairro ─────────────────────────────────────

def test_criar_pedido_sem_bairro_falha(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "total": 20,
        "forma_pagamento": "dinheiro",
    }
    response = client.post("/pedidos", json=pedido)
    assert response.status_code == 400


def test_criar_pedido_bairro_inexistente_falha(client):
    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "bairro": "Bairro Que Não Existe",
        "total": 20,
        "forma_pagamento": "dinheiro",
    }
    response = client.post("/pedidos", json=pedido)
    assert response.status_code == 400


def test_criar_pedido_usa_taxa_do_bairro_cadastrado(client, auth_headers):
    novo = client.post("/bairros", json={"nome": "Vila Rica", "taxa": 7.5}, headers=auth_headers)
    assert novo.status_code == 201

    pedido = {
        "cliente": {"nome": "Kauê"},
        "itens": [{"nome": "Açaí", "quantidade": 1}],
        "bairro": "Vila Rica",
        "total": 27.5,
        "forma_pagamento": "dinheiro",
    }
    criar = client.post("/pedidos", json=pedido)
    assert criar.status_code == 201
    token = json.loads(criar.data)["token"]

    dados = json.loads(client.get(f"/pedidos/rastrear/{token}").data)
    assert dados["taxa_entrega"] == 7.5


# ── CRUD de bairros ──────────────────────────────────────────────

def test_listar_bairros_publico_traz_seed_centro(client):
    response = client.get("/bairros")

    assert response.status_code == 200
    nomes = [b["nome"] for b in json.loads(response.data)]
    assert "Centro" in nomes


def test_criar_bairro_exige_login(client):
    response = client.post("/bairros", json={"nome": "Vila Nova", "taxa": 5.0})

    assert response.status_code == 401


def test_criar_bairro_taxa_invalida(client, auth_headers):
    response = client.post("/bairros", json={"nome": "Vila Nova", "taxa": -1}, headers=auth_headers)

    assert response.status_code == 400


def test_criar_bairro_duplicado_falha(client, auth_headers):
    client.post("/bairros", json={"nome": "Vila Nova", "taxa": 5.0}, headers=auth_headers)
    resposta = client.post("/bairros", json={"nome": "Vila Nova", "taxa": 6.0}, headers=auth_headers)

    assert resposta.status_code == 409


def test_editar_bairro(client, auth_headers):
    criar = client.post("/bairros", json={"nome": "Vila Nova", "taxa": 5.0}, headers=auth_headers)
    bairro_id = json.loads(criar.data)["id"]

    resposta = client.put(
        f"/bairros/{bairro_id}",
        json={"nome": "Vila Nova", "taxa": 8.0},
        headers=auth_headers,
    )

    assert resposta.status_code == 200
    assert json.loads(resposta.data)["taxa"] == 8.0


def test_editar_bairro_inexistente(client, auth_headers):
    resposta = client.put(
        "/bairros/999999",
        json={"nome": "X", "taxa": 1.0},
        headers=auth_headers,
    )

    assert resposta.status_code == 404


def test_remover_bairro(client, auth_headers):
    criar = client.post("/bairros", json={"nome": "Vila Nova", "taxa": 5.0}, headers=auth_headers)
    bairro_id = json.loads(criar.data)["id"]

    resposta = client.delete(f"/bairros/{bairro_id}", headers=auth_headers)

    assert resposta.status_code == 200
    nomes = [b["nome"] for b in json.loads(client.get("/bairros").data)]
    assert "Vila Nova" not in nomes


def test_remover_bairro_inexistente(client, auth_headers):
    resposta = client.delete("/bairros/999999", headers=auth_headers)

    assert resposta.status_code == 404


# ── Histórico (entregues/recusados dos últimos 7 dias) ─────────────

def test_historico_exige_login(client):
    response = client.get("/pedidos/historico")

    assert response.status_code == 401


def test_historico_nao_traz_pedidos_ativos(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    response = client.get("/pedidos/historico", headers=auth_headers)

    assert response.status_code == 200
    ids = [p["id"] for p in json.loads(response.data)]
    assert pedido_id not in ids


def test_historico_traz_entregues(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    for _ in range(3):
        client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)  # -> entregue

    response = client.get("/pedidos/historico", headers=auth_headers)

    assert response.status_code == 200
    ids = [p["id"] for p in json.loads(response.data)]
    assert pedido_id in ids


def test_historico_traz_recusados(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    client.patch(f"/pedidos/{pedido_id}/recusar", headers=auth_headers)

    response = client.get("/pedidos/historico", headers=auth_headers)

    assert response.status_code == 200
    ids = [p["id"] for p in json.loads(response.data)]
    assert pedido_id in ids


def test_historico_inclui_pedidos_ja_arquivados(client, auth_headers):
    criar = _criar_pedido_dinheiro(client, valor=20.0)
    pedido_id = json.loads(criar.data)["id"]

    for _ in range(3):
        client.patch(f"/pedidos/{pedido_id}/status", headers=auth_headers)  # -> entregue

    client.delete("/pedidos/entregues", headers=auth_headers)  # arquiva

    ativos = json.loads(client.get("/pedidos", headers=auth_headers).data)
    assert pedido_id not in [p["id"] for p in ativos]

    historico = json.loads(client.get("/pedidos/historico", headers=auth_headers).data)
    assert pedido_id in [p["id"] for p in historico]
