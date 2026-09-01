import json
from collections import Counter

from database import get_conn

# Limiares baixos de propósito: o histórico de pedidos ainda é pequeno (TCC
# em fase piloto), então regras exigentes deixariam o Apriori sem achar
# nada quase sempre e a recomendação cairia sempre pro fallback de
# popularidade. Tende a subir conforme o volume real de pedidos crescer.
MIN_SUPPORT = 0.05
MIN_CONFIDENCE = 0.3
MIN_TRANSACOES = 3
LIMITE_PADRAO = 4


def _transacoes_complementos():
    """Cada item de um pedido (um copo com os complementos marcados nele) diz
    respeito a uma 'transação' pro Apriori — é o nível em que faz sentido
    perguntar 'quem escolhe X também costuma escolher Y', já que os
    complementos são marcados por item, não pelo pedido inteiro. Itens com
    menos de 2 complementos não geram associação nenhuma, então são
    descartados aqui."""
    with get_conn() as conn:
        rows = conn.execute("SELECT itens FROM pedidos").fetchall()

    transacoes = []
    for row in rows:
        for item in json.loads(row["itens"]):
            extras = item.get("extras") or []
            unicos = sorted(set(extras))
            if len(unicos) >= 2:
                transacoes.append(unicos)
    return transacoes


def _mais_populares(transacoes, excluir):
    contagem = Counter()
    for transacao in transacoes:
        contagem.update(transacao)
    return [nome for nome, _ in contagem.most_common() if nome not in excluir]


def _regras_associacao(transacoes):
    if len(transacoes) < MIN_TRANSACOES:
        return None
    try:
        import pandas as pd
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder
    except ImportError:
        return None

    encoder = TransactionEncoder()
    matriz = encoder.fit(transacoes).transform(transacoes)
    df = pd.DataFrame(matriz, columns=encoder.columns_)

    frequentes = apriori(df, min_support=MIN_SUPPORT, use_colnames=True)
    if frequentes.empty:
        return None

    regras = association_rules(frequentes, metric="confidence", min_threshold=MIN_CONFIDENCE)
    if regras.empty:
        return None

    return regras


def recomendar_complementos(selecionados, limite=LIMITE_PADRAO):
    """Retorna até `limite` nomes de complementos recomendados pra quem já
    escolheu `selecionados` num item do pedido, a partir de regras de
    associação (Apriori) sobre o histórico de pedidos. Quando não há regra
    aplicável — pouco histórico, combinação nunca vista, item novo — cai pro
    complemento mais pedido no geral (popularidade)."""
    ja_escolhidos = set(selecionados)
    transacoes = _transacoes_complementos()
    populares = _mais_populares(transacoes, ja_escolhidos)

    recomendados = []
    regras = _regras_associacao(transacoes)
    if regras is not None:
        aplicaveis = regras[
            regras["antecedents"].apply(lambda ant: bool(ant) and ant.issubset(ja_escolhidos))
        ].copy()
        aplicaveis["_tam_antecedente"] = aplicaveis["antecedents"].apply(len)
        aplicaveis = aplicaveis.sort_values(
            ["_tam_antecedente", "confidence", "lift"], ascending=False
        )
        for _, regra in aplicaveis.iterrows():
            for nome in regra["consequents"]:
                if nome not in ja_escolhidos and nome not in recomendados:
                    recomendados.append(nome)

    for nome in populares:
        if len(recomendados) >= limite:
            break
        if nome not in recomendados:
            recomendados.append(nome)

    return recomendados[:limite]
