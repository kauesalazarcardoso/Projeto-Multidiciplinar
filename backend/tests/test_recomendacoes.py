import json


def _criar_pedido(client, extras):
    """Cria um pedido com um único item cujos complementos são `extras`."""
    return client.post(
        "/pedidos",
        json={
            "cliente": {"nome": "Cliente", "tel": "51999999999", "end": "Rua X, 1 — Centro, Rolante"},
            "itens": [{"nome": "Copo 330ml Açaí Tradicional", "preco": 19.0, "extras": extras, "qtd": 1}],
            "bairro": "Centro",
            "total": 22.0,
            "forma_pagamento": "pix",
        },
    )


def test_sem_selecao_retorna_lista_vazia(client):
    response = client.get("/recomendacoes/complementos")

    assert response.status_code == 200
    assert json.loads(response.data) == []


def test_sem_historico_cai_para_lista_vazia(client):
    response = client.get("/recomendacoes/complementos?selecionados=Nutella")

    assert response.status_code == 200
    assert json.loads(response.data) == []


def test_fallback_popularidade_sem_regra_para_o_item(client):
    for _ in range(4):
        assert _criar_pedido(client, ["Granola", "Banana"]).status_code == 201

    # "Morango" nunca apareceu junto de nada no histórico: não há regra de
    # associação aplicável, então cai pro mais pedido no geral (excluindo
    # o próprio selecionado).
    response = client.get("/recomendacoes/complementos?selecionados=Morango")

    assert response.status_code == 200
    sugestoes = json.loads(response.data)
    assert sugestoes[0] in ("Granola", "Banana")
    assert "Morango" not in sugestoes


def test_regra_de_associacao_e_priorizada(client):
    for _ in range(6):
        assert _criar_pedido(client, ["Nutella", "Morango"]).status_code == 201
    for _ in range(2):
        assert _criar_pedido(client, ["Nutella", "Granola"]).status_code == 201
    for _ in range(5):
        assert _criar_pedido(client, ["Banana", "Leite em Pó"]).status_code == 201

    response = client.get("/recomendacoes/complementos?selecionados=Nutella")

    assert response.status_code == 200
    sugestoes = json.loads(response.data)
    # "Morango" tem confiança alta o suficiente pra vir de regra de
    # associação (6/8 dos pedidos com Nutella também têm Morango) e por
    # isso fica na frente; "Granola" (2/8, abaixo do limiar de confiança)
    # não gera regra, então só aparece — se aparecer — como preenchimento
    # de popularidade, atrás dos itens de regra.
    assert sugestoes[0] == "Morango"
    assert "Nutella" not in sugestoes


def test_recomendacao_nao_repete_complemento_ja_selecionado(client):
    for _ in range(4):
        assert _criar_pedido(client, ["Nutella", "Morango", "Granola"]).status_code == 201

    response = client.get("/recomendacoes/complementos?selecionados=Nutella,Morango")

    sugestoes = json.loads(response.data)
    assert "Nutella" not in sugestoes
    assert "Morango" not in sugestoes

