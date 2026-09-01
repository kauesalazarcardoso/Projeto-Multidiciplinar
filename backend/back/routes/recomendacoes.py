from flask import Blueprint, jsonify, request

import recomendacao

recomendacoes_bp = Blueprint('recomendacoes', __name__)


@recomendacoes_bp.route("/recomendacoes/complementos", methods=["GET"])
def recomendar_complementos():
    bruto = request.args.get("selecionados", "")
    selecionados = [nome.strip() for nome in bruto.split(",") if nome.strip()]
    if not selecionados:
        return jsonify([])
    return jsonify(recomendacao.recomendar_complementos(selecionados))
