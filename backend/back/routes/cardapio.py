from flask import Blueprint, jsonify, request
from psycopg.errors import UniqueViolation
from database import get_conn, CATEGORIAS_CARDAPIO, CATEGORIAS_COMPLEMENTOS
from routes.auth import login_required

cardapio_bp = Blueprint('cardapio', __name__)


def _validar_categoria(data):
    categoria = data.get("categoria")
    if categoria not in CATEGORIAS_CARDAPIO:
        return None, jsonify({"erro": "Categoria inválida"}), 400
    return categoria, None, None


@cardapio_bp.route("/cardapio", methods=["GET"])
def listar_cardapio():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, nome, preco, categoria FROM cardapio ORDER BY id").fetchall()
    return jsonify([{"id": r["id"], "nome": r["nome"], "preco": r["preco"], "categoria": r["categoria"]} for r in rows])


@cardapio_bp.route("/cardapio", methods=["POST"])
@login_required
def criar_item():
    data = request.get_json()
    if not data or not all(k in data for k in ("nome", "preco", "categoria")):
        return jsonify({"erro": "Campos 'nome', 'preco' e 'categoria' são obrigatórios"}), 400
    if not isinstance(data["preco"], (int, float)) or data["preco"] <= 0:
        return jsonify({"erro": "Preço inválido"}), 400
    nome = str(data["nome"]).strip()
    if not nome:
        return jsonify({"erro": "Nome não pode ser vazio"}), 400
    categoria, erro_resp, status = _validar_categoria(data)
    if erro_resp:
        return erro_resp, status
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cardapio (nome, preco, categoria) VALUES (%s, %s, %s) RETURNING id",
            (nome, data["preco"], categoria)
        )
        item_id = cur.fetchone()["id"]
    return jsonify({"id": item_id, "nome": nome, "preco": data["preco"], "categoria": categoria}), 201


@cardapio_bp.route("/cardapio/<int:item_id>", methods=["PUT"])
@login_required
def editar_item(item_id):
    data = request.get_json()
    if not data or not all(k in data for k in ("nome", "preco", "categoria")):
        return jsonify({"erro": "Campos 'nome', 'preco' e 'categoria' são obrigatórios"}), 400
    if not isinstance(data["preco"], (int, float)) or data["preco"] <= 0:
        return jsonify({"erro": "Preço inválido"}), 400
    nome = str(data["nome"]).strip()
    if not nome:
        return jsonify({"erro": "Nome não pode ser vazio"}), 400
    categoria, erro_resp, status = _validar_categoria(data)
    if erro_resp:
        return erro_resp, status
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE cardapio SET nome = %s, preco = %s, categoria = %s WHERE id = %s",
            (nome, data["preco"], categoria, item_id)
        )
        if cur.rowcount == 0:
            return jsonify({"erro": "Item não encontrado"}), 404
    return jsonify({"id": item_id, "nome": nome, "preco": data["preco"], "categoria": categoria})


@cardapio_bp.route("/cardapio/<int:item_id>", methods=["DELETE"])
@login_required
def remover_item(item_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM cardapio WHERE id = %s", (item_id,))
        if cur.rowcount == 0:
            return jsonify({"erro": "Item não encontrado"}), 404
    return jsonify({"deletado": item_id})


def _validar_preco_complemento(data):
    preco = data.get("preco", 0)
    if preco in (None, ""):
        preco = 0
    if not isinstance(preco, (int, float)) or preco < 0:
        return None, jsonify({"erro": "Preço deve ser um número maior ou igual a zero"}), 400
    return preco, None, None


def _validar_categoria_complemento(data):
    categoria = data.get("categoria")
    if categoria not in CATEGORIAS_COMPLEMENTOS:
        return None, jsonify({"erro": "Categoria inválida"}), 400
    return categoria, None, None


@cardapio_bp.route("/complementos", methods=["GET"])
def listar_complementos():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, nome, preco, categoria FROM complementos ORDER BY id").fetchall()
    return jsonify([{"id": r["id"], "nome": r["nome"], "preco": r["preco"], "categoria": r["categoria"]} for r in rows])


@cardapio_bp.route("/complementos", methods=["POST"])
@login_required
def criar_complemento():
    data = request.get_json()
    if not data or not data.get("nome", "").strip():
        return jsonify({"erro": "Campo 'nome' é obrigatório"}), 400
    nome = data["nome"].strip()
    preco, erro_resp, status = _validar_preco_complemento(data)
    if erro_resp:
        return erro_resp, status
    categoria, erro_resp, status = _validar_categoria_complemento(data)
    if erro_resp:
        return erro_resp, status
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO complementos (nome, preco, categoria) VALUES (%s, %s, %s) RETURNING id",
                (nome, preco, categoria)
            )
            return jsonify({"id": cur.fetchone()["id"], "nome": nome, "preco": preco, "categoria": categoria}), 201
    except UniqueViolation:
        return jsonify({"erro": "Complemento já existe"}), 409


@cardapio_bp.route("/complementos/<int:comp_id>", methods=["PUT"])
@login_required
def editar_complemento(comp_id):
    data = request.get_json()
    if not data or not data.get("nome", "").strip():
        return jsonify({"erro": "Campo 'nome' é obrigatório"}), 400
    nome = data["nome"].strip()
    preco, erro_resp, status = _validar_preco_complemento(data)
    if erro_resp:
        return erro_resp, status
    categoria, erro_resp, status = _validar_categoria_complemento(data)
    if erro_resp:
        return erro_resp, status
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE complementos SET nome = %s, preco = %s, categoria = %s WHERE id = %s",
                (nome, preco, categoria, comp_id)
            )
            if cur.rowcount == 0:
                return jsonify({"erro": "Complemento não encontrado"}), 404
    except UniqueViolation:
        return jsonify({"erro": "Já existe um complemento com esse nome"}), 409
    return jsonify({"id": comp_id, "nome": nome, "preco": preco, "categoria": categoria})


@cardapio_bp.route("/complementos/<int:comp_id>", methods=["DELETE"])
@login_required
def remover_complemento(comp_id):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM complementos WHERE id = %s", (comp_id,))
        if cur.rowcount == 0:
            return jsonify({"erro": "Complemento não encontrado"}), 404
    return jsonify({"deletado": comp_id})
