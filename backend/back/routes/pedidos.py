from flask import Blueprint, jsonify, request
import json
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from database import get_conn
from extensions import limiter
from routes.auth import login_required
import horario as horario_mod
import push

pedidos_bp = Blueprint('pedidos', __name__)

FUSO_LOJA = ZoneInfo("America/Sao_Paulo")


class PedidoInvalido(Exception):
    def __init__(self, mensagem, status_code, **extra):
        self.mensagem = mensagem
        self.status_code = status_code
        self.extra = extra
        super().__init__(mensagem)


ORDEM_STATUS = ['aguardando', 'confirmado', 'a_caminho', 'entregue']
FORMAS_PAGAMENTO = ('pix', 'cartao', 'dinheiro')
TAXA_MAQUININHA_ATE_50 = 2.0
TAXA_MAQUININHA_ACIMA_50 = 3.0
LIMITE_ITENS_TAXA_MAQUININHA = 50.0
STATUS_RECUSADO = 'recusado'

_COLUNAS_PEDIDO = (
    "id, cliente, itens, total, status, hora, forma_pagamento, taxa_entrega, "
    "taxa_maquininha, troco_para, observacao"
)


def _serializar_pedido(row):
    return {
        "id":               row["id"],
        "cliente":          json.loads(row["cliente"]),
        "itens":            json.loads(row["itens"]),
        "total":            row["total"],
        "status":           row["status"],
        "hora":             row["hora"],
        "forma_pagamento":  row["forma_pagamento"],
        "taxa_entrega":     row["taxa_entrega"],
        "taxa_maquininha":  row["taxa_maquininha"],
        "troco_para":       row["troco_para"],
        "observacao":       row["observacao"],
    }


def _notificar_gestor(pedido_id, cliente, total):
    nome = cliente.get("nome", "Cliente")
    push.enviar_para_todos(
        "Novo pedido recebido!",
        f"Pedido #{str(pedido_id)[-5:]} — {nome} — R$ {total:.2f}",
        f"pedido-{pedido_id}",
    )


@pedidos_bp.route("/pedidos", methods=["GET"])
@login_required
def listar_pedidos():
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {_COLUNAS_PEDIDO} FROM pedidos "
            "WHERE arquivado = FALSE ORDER BY id DESC"
        ).fetchall()
    return jsonify([_serializar_pedido(r) for r in rows])


def _limiar_id_dias(dias):
    """Converte 'N dias atrás' num id mínimo (id = timestamp em ms). Usar
    'id >= limiar' em vez de 'to_timestamp(id/1000.0) >= ...' permite ao
    Postgres usar o índice da chave primária em vez de varrer a tabela
    inteira aplicando a função em cada linha — essencial pois a tabela
    'pedidos' só cresce (pedidos antigos são arquivados, nunca apagados)."""
    limite = datetime.now(timezone.utc) - timedelta(days=dias)
    return int(limite.timestamp() * 1000)


@pedidos_bp.route("/pedidos/historico", methods=["GET"])
@login_required
def historico_pedidos():
    """Pedidos entregues/recusados dos últimos 7 dias, incluindo os já
    arquivados por 'Limpar Entregues/Recusados' — pra o gestor achar um
    pedido antigo e, se precisar, usar 'Voltar Status' nele de novo."""
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {_COLUNAS_PEDIDO} FROM pedidos "
            "WHERE status IN ('entregue', %s) AND id >= %s "
            "ORDER BY id DESC",
            (STATUS_RECUSADO, _limiar_id_dias(7))
        ).fetchall()
    return jsonify([_serializar_pedido(r) for r in rows])


@pedidos_bp.route("/pedidos/vendas-por-dia", methods=["GET"])
@login_required
def vendas_por_dia():
    """Total vendido por dia nos últimos 7 dias corridos, só pedidos já
    entregues. O id do pedido é usado como data (timestamp em milissegundos),
    já que não existe coluna de data — só 'hora' (HH:MM)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                (to_timestamp(id / 1000.0) AT TIME ZONE 'America/Sao_Paulo')::date AS dia,
                SUM(total) AS total_dia,
                COUNT(*) AS pedidos_dia
            FROM pedidos
            WHERE status = 'entregue' AND id >= %s
            GROUP BY dia
            """,
            (_limiar_id_dias(7),)
        ).fetchall()

    por_dia = {row["dia"].isoformat(): row for row in rows}

    hoje = datetime.now(FUSO_LOJA).date()
    resultado = []
    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)
        chave = dia.isoformat()
        encontrado = por_dia.get(chave)
        resultado.append({
            "dia":     chave,
            "total":   encontrado["total_dia"] if encontrado else 0,
            "pedidos": encontrado["pedidos_dia"] if encontrado else 0,
        })

    return jsonify(resultado)


@pedidos_bp.route("/pedidos/<int:pedido_id>", methods=["GET"])
def buscar_pedido(pedido_id):
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT {_COLUNAS_PEDIDO} FROM pedidos WHERE id = %s",
            (pedido_id,)
        ).fetchone()

    if not row:
        return jsonify({"erro": "Pedido não encontrado"}), 404

    return jsonify(_serializar_pedido(row))


def _validar_pedido_basico(data):
    if not data or not all(k in data for k in ("cliente", "itens", "total", "forma_pagamento")):
        raise PedidoInvalido("Dados incompletos", 400)
    if not isinstance(data["total"], (int, float)):
        raise PedidoInvalido("Campo 'total' deve ser numérico", 400)


def _checar_aberto():
    aberto, motivo = horario_mod.esta_aberto()
    if not aberto:
        raise PedidoInvalido("Estabelecimento fechado no momento", 403, motivo=motivo)


def _normalizar_observacao(data):
    observacao = data.get("observacao")
    if not observacao:
        return None
    observacao = str(observacao).strip()
    return observacao[:500] if observacao else None


def _calcular_taxa_maquininha(forma_pagamento, itens):
    """Cartão paga na entrega com maquininha física, que cobra uma taxa
    PRÓPRIA e separada da taxa de entrega: R$2 quando os itens (sem taxas)
    somam até R$50; R$3 quando somam mais que isso."""
    if forma_pagamento != "cartao":
        return 0.0
    subtotal_itens = sum(item["preco"] * item.get("qtd", 1) for item in itens)
    return TAXA_MAQUININHA_ATE_50 if subtotal_itens <= LIMITE_ITENS_TAXA_MAQUININHA else TAXA_MAQUININHA_ACIMA_50


def _buscar_taxa_bairro(data):
    """A taxa de entrega varia por bairro (cadastrado/editável no painel
    Admin). O cliente escolhe o bairro numa caixinha de seleção — não digita
    livremente — então aqui é sempre um match exato contra o que está
    cadastrado."""
    bairro = str(data.get("bairro", "")).strip()
    if not bairro:
        raise PedidoInvalido("Campo 'bairro' é obrigatório", 400)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT taxa FROM bairros WHERE nome = %s", (bairro,)
        ).fetchone()
    if not row:
        raise PedidoInvalido("Bairro inválido para entrega", 400)
    return row["taxa"]


def _inserir_pedido(data, forma_pagamento, status_pedido, *, taxa_entrega,
                     taxa_maquininha=0.0, troco_para=None, observacao=None):
    pedido_id = int(time.time() * 1000)
    hora      = datetime.now().strftime("%H:%M")

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO pedidos "
            "(id, cliente, itens, total, status, hora, forma_pagamento, taxa_entrega, "
            "taxa_maquininha, troco_para, observacao) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                pedido_id,
                json.dumps(data["cliente"], ensure_ascii=False),
                json.dumps(data["itens"],   ensure_ascii=False),
                data["total"],
                status_pedido,
                hora,
                forma_pagamento,
                taxa_entrega,
                taxa_maquininha,
                troco_para,
                observacao,
            )
        )

    _notificar_gestor(pedido_id, data["cliente"], data["total"])

    return {"id": pedido_id, "hora": hora, "status": status_pedido}


def _criar_pedido_interno(data):
    """Valida e grava um pedido. Levanta PedidoInvalido em caso de erro.
    Retorna {"id", "hora", "status"} em caso de sucesso. Reaproveitado tanto
    pela rota HTTP quanto pelo chatbot (tool criar_pedido). Nenhuma forma de
    pagamento depende de confirmação de gateway nem de aprovação manual do
    gestor antes de entrar na fila: Pix e cartão são pagos por fora do app
    (Pix por chave estática, cartão na entrega com maquininha física) e
    entram direto como 'aguardando', igual dinheiro — a conferência do
    pagamento acontece pelo WhatsApp, fora do fluxo da fila."""
    _checar_aberto()
    _validar_pedido_basico(data)

    forma_pagamento = data["forma_pagamento"]
    if forma_pagamento not in FORMAS_PAGAMENTO:
        raise PedidoInvalido("Forma de pagamento inválida", 400)

    taxa_entrega = _buscar_taxa_bairro(data)
    observacao = _normalizar_observacao(data)

    if forma_pagamento == "dinheiro":
        troco_para = None
        if data.get("troco_para") is not None:
            if not isinstance(data["troco_para"], (int, float)) or data["troco_para"] < data["total"]:
                raise PedidoInvalido("Valor para troco inválido", 400)
            troco_para = data["troco_para"]
        return _inserir_pedido(data, forma_pagamento, "aguardando", taxa_entrega=taxa_entrega,
                                troco_para=troco_para, observacao=observacao)

    if forma_pagamento == "cartao":
        taxa_maquininha = _calcular_taxa_maquininha(forma_pagamento, data["itens"])
        return _inserir_pedido(data, forma_pagamento, "aguardando", taxa_entrega=taxa_entrega,
                                taxa_maquininha=taxa_maquininha, observacao=observacao)

    # pix
    return _inserir_pedido(data, forma_pagamento, "aguardando", taxa_entrega=taxa_entrega,
                            observacao=observacao)


@pedidos_bp.route("/pedidos", methods=["POST"])
@limiter.limit("15 per minute")
def criar_pedido():
    data = request.get_json()
    try:
        resultado = _criar_pedido_interno(data)
    except PedidoInvalido as e:
        return jsonify({"erro": e.mensagem, **e.extra}), e.status_code
    return jsonify(resultado), 201


@pedidos_bp.route("/pedidos/<int:pedido_id>/status", methods=["PATCH"])
@login_required
def avancar_status(pedido_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM pedidos WHERE id = %s", (pedido_id,)
        ).fetchone()

        if not row:
            return jsonify({"erro": "Pedido não encontrado"}), 404

        if row["status"] not in ORDEM_STATUS:
            return jsonify({"erro": "Status inválido no banco"}), 500

        idx = ORDEM_STATUS.index(row["status"])

        if idx >= len(ORDEM_STATUS) - 1:
            return jsonify({"erro": "Pedido já está no status final"}), 400

        novo_status = ORDEM_STATUS[idx + 1]
        conn.execute(
            "UPDATE pedidos SET status = %s WHERE id = %s", (novo_status, pedido_id)
        )

    return jsonify({"id": pedido_id, "status": novo_status})


@pedidos_bp.route("/pedidos/<int:pedido_id>/status/voltar", methods=["PATCH"])
@login_required
def voltar_status(pedido_id):
    """Desfaz um avanço de status por engano (ex: o gestor clicou 'Marcar
    como Entregue' sem querer) — volta uma etapa em ORDEM_STATUS. Também
    desarquiva o pedido, pra cobrir o caso dele já ter sido tirado da fila
    por 'Limpar Entregues' antes do gestor perceber o engano."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM pedidos WHERE id = %s", (pedido_id,)
        ).fetchone()

        if not row:
            return jsonify({"erro": "Pedido não encontrado"}), 404

        if row["status"] not in ORDEM_STATUS:
            return jsonify({"erro": "Não é possível voltar o status desse pedido"}), 400

        idx = ORDEM_STATUS.index(row["status"])

        if idx <= 0:
            return jsonify({"erro": "Pedido já está no status inicial"}), 400

        novo_status = ORDEM_STATUS[idx - 1]
        conn.execute(
            "UPDATE pedidos SET status = %s, arquivado = FALSE WHERE id = %s",
            (novo_status, pedido_id)
        )

    return jsonify({"id": pedido_id, "status": novo_status})


@pedidos_bp.route("/pedidos/<int:pedido_id>/recusar", methods=["PATCH"])
@login_required
def recusar_pedido(pedido_id):
    """O gestor nega um pedido (ex: fora da área de entrega, item em falta).
    Só pode recusar enquanto o pedido ainda não foi entregue nem já recusado."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM pedidos WHERE id = %s", (pedido_id,)
        ).fetchone()

        if not row:
            return jsonify({"erro": "Pedido não encontrado"}), 404

        if row["status"] in (ORDEM_STATUS[-1], STATUS_RECUSADO):
            return jsonify({"erro": "Pedido não pode mais ser recusado"}), 400

        conn.execute(
            "UPDATE pedidos SET status = %s WHERE id = %s", (STATUS_RECUSADO, pedido_id)
        )

    return jsonify({"id": pedido_id, "status": STATUS_RECUSADO})


@pedidos_bp.route("/pedidos/entregues", methods=["DELETE"])
@login_required
def limpar_entregues():
    """Tira os pedidos entregues e recusados da fila do gestor sem apagar a
    linha do banco — o histórico de vendas (/pedidos/vendas-por-dia) soma
    pedidos 'entregue' independente de arquivado, então limpar a fila não
    pode fazer o valor do dia sumir do painel."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE pedidos SET arquivado = TRUE "
            "WHERE status IN ('entregue', %s) AND arquivado = FALSE",
            (STATUS_RECUSADO,)
        )
        arquivados = cur.rowcount

    return jsonify({"arquivados": arquivados})
