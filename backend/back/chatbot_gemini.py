import json
import os
import re
import time

from google import genai

from database import get_conn
import horario as horario_mod
import mercado_pago
from routes.pedidos import PedidoInvalido, _criar_pedido_interno, criar_pedido_cartao_verificado

_MAX_TENTATIVAS_RATE_LIMIT = 3
_ESPERA_INICIAL_SEGUNDOS = 3
_ESPERA_MAXIMA_SEGUNDOS = 35
_RETRY_EM_SEGUNDOS_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE)

# Modelos testados nesta conta: gemini-3.6-flash tem só 20 req/dia grátis
# (pouco pro chat, que faz várias chamadas por mensagem via tool use); a
# geração 2.5 não aceita mais contas novas; gemini-3.5-flash também esgotou
# a cota rápido nos nossos testes. gemini-3.1-flash-lite tem cota própria
# separada e ainda respondia quando os outros já tinham estourado.
_MODEL = "gemini-3.1-flash-lite"
_MAX_ITERACOES = 6

SYSTEM_PROMPT = """\
Você é o atendente virtual da Açaí Express, uma loja de açaí.

- Cumprimente o cliente de forma calorosa e breve. Seja objetivo e direto, como uma \
conversa real de WhatsApp — sem parágrafos longos.
- Quando perguntarem sobre o cardápio, chame consultar_cardapio e apresente os produtos \
com preços em R$. Os tamanhos já fazem parte do nome de cada produto.
- Quando perguntarem sobre complementos, chame consultar_complementos. Alguns são grátis \
(preço 0) e outros têm custo adicional — deixe isso claro ao apresentar a lista, e some o \
preço de cada complemento pago escolhido ao preço do item antes de montar o total.
- Antes de confirmar qualquer pedido, chame consultar_horario. Se "aberto_agora" for falso, \
explique educadamente o motivo (se "fechado_hoje", diga que não abrimos nesse dia; se \
"fora_do_horario", informe o horário de funcionamento do dia) e agradeça o contato — não \
continue o fluxo de pedido.
- Colete: itens desejados (com tamanho/sabor), nome do cliente, telefone e endereço de entrega.
- Sempre some a taxa de entrega de R$3,00 ao total antes de prosseguir com o pagamento.
- Pergunte a forma de pagamento: Pix, cartão ou dinheiro.
  - Pix: chame gerar_cobranca_pix e envie o código copia-e-cola para o cliente colar no \
aplicativo do banco.
  - Cartão: chame gerar_link_pagamento_cartao e envie o link. Só depois que o cliente \
confirmar que pagou, chame verificar_pagamento_cartao; se aprovado, prossiga para criar_pedido \
com forma_pagamento "cartao". Se ainda não estiver aprovado, avise que ainda não identificou \
o pagamento e peça para aguardar um pouco.
  - Dinheiro: pergunte se precisa de troco e para qual valor.
- Revalide o horário de funcionamento (consultar_horario) logo antes de chamar criar_pedido, \
pois a loja pode ter fechado durante a conversa.
- Depois de criar o pedido com sucesso, informe o número do pedido e agradeça.
"""

TOOLS = [
    {
        "type": "function",
        "name": "consultar_cardapio",
        "description": "Retorna a lista completa de produtos do cardápio (nome e preço). "
                        "Use para responder perguntas sobre o que está disponível, tamanhos e preços.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "consultar_complementos",
        "description": "Retorna a lista de complementos/adicionais disponíveis, cada um com "
                        "seu preço (preço 0 significa que é grátis; os demais têm custo "
                        "adicional que deve ser somado ao preço do item).",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "consultar_horario",
        "description": "Verifica se o estabelecimento está aberto agora e retorna o horário "
                        "de funcionamento de todos os dias da semana. Chame antes de confirmar "
                        "qualquer pedido.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "gerar_cobranca_pix",
        "description": "Gera uma cobrança Pix (QR code e código copia-e-cola) para o valor do "
                        "pedido. Chame depois de confirmar o pedido completo com o cliente, "
                        "quando ele escolher pagar via Pix.",
        "parameters": {
            "type": "object",
            "properties": {
                "valor": {"type": "number", "description": "Valor total do pedido, incluindo a taxa de entrega"},
                "email": {"type": "string", "description": "E-mail do cliente para o pagamento"},
                "nome": {"type": "string", "description": "Nome do cliente"},
            },
            "required": ["valor", "email", "nome"],
        },
    },
    {
        "type": "function",
        "name": "gerar_link_pagamento_cartao",
        "description": "Gera um link de pagamento hospedado pelo Mercado Pago (Checkout Pro) "
                        "para o cliente inserir os dados do cartão. Chame quando o cliente "
                        "escolher pagar com cartão, depois de confirmar o pedido completo.",
        "parameters": {
            "type": "object",
            "properties": {
                "valor": {"type": "number", "description": "Valor total do pedido, incluindo a taxa de entrega"},
                "email": {"type": "string", "description": "E-mail do cliente para o pagamento"},
                "nome": {"type": "string", "description": "Nome do cliente"},
            },
            "required": ["valor", "email", "nome"],
        },
    },
    {
        "type": "function",
        "name": "verificar_pagamento_cartao",
        "description": "Verifica se o pagamento via link de cartão (Checkout Pro) já foi "
                        "aprovado. Chame quando o cliente disser que já pagou, antes de "
                        "chamar criar_pedido com forma_pagamento cartao.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "criar_pedido",
        "description": "Cria o pedido definitivo depois que o cliente confirmou os itens, "
                        "endereço e forma de pagamento, e o pagamento (quando aplicável) já "
                        "foi confirmado. Para dinheiro não é necessário confirmação prévia.",
        "parameters": {
            "type": "object",
            "properties": {
                "cliente": {
                    "type": "object",
                    "properties": {
                        "nome": {"type": "string"},
                        "tel": {"type": "string"},
                        "end": {"type": "string", "description": "Endereço completo de entrega"},
                    },
                    "required": ["nome", "tel", "end"],
                },
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nome": {"type": "string"},
                            "preco": {
                                "type": "number",
                                "description": "Preço do item já somado com o preço de "
                                                "qualquer complemento pago escolhido",
                            },
                            "qtd": {"type": "integer"},
                            "extras": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["nome", "preco", "qtd"],
                    },
                },
                "total": {"type": "number", "description": "Soma dos itens + taxa de entrega (R$3,00)"},
                "forma_pagamento": {"type": "string", "enum": ["pix", "cartao", "dinheiro"]},
                "troco_para": {"type": "number", "description": "Opcional, só para dinheiro"},
            },
            "required": ["cliente", "itens", "total", "forma_pagamento"],
        },
    },
]


def _cliente():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _consultar_cardapio():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, nome, preco FROM cardapio ORDER BY id").fetchall()
    return [{"id": r["id"], "nome": r["nome"], "preco": r["preco"]} for r in rows]


def _consultar_complementos():
    with get_conn() as conn:
        rows = conn.execute("SELECT id, nome, preco FROM complementos ORDER BY id").fetchall()
    return [{"id": r["id"], "nome": r["nome"], "preco": r["preco"]} for r in rows]


def _consultar_horario():
    aberto, motivo = horario_mod.esta_aberto()
    return {"aberto_agora": aberto, "motivo": motivo, "horarios": horario_mod.buscar_horarios()}


def executar_tool(nome, entrada, sessao_id):
    """Executa uma tool chamada pelo Gemini. Retorna sempre uma string JSON."""
    if nome == "consultar_cardapio":
        return json.dumps(_consultar_cardapio(), ensure_ascii=False)

    if nome == "consultar_complementos":
        return json.dumps(_consultar_complementos(), ensure_ascii=False)

    if nome == "consultar_horario":
        return json.dumps(_consultar_horario(), ensure_ascii=False)

    if nome == "gerar_cobranca_pix":
        order = mercado_pago.criar_order_pix(
            entrada["valor"], entrada["email"], sessao_id, entrada.get("nome")
        )
        payment_method = order.get("transactions", {}).get("payments", [{}])[0].get("payment_method", {})
        return json.dumps({
            "copia_cola": payment_method.get("qr_code"),
            "mp_order_id": order.get("id"),
        }, ensure_ascii=False)

    if nome == "gerar_link_pagamento_cartao":
        pref = mercado_pago.criar_preferencia_checkout_pro(
            entrada["valor"], entrada["email"], sessao_id, entrada.get("nome")
        )
        return json.dumps(pref, ensure_ascii=False)

    if nome == "verificar_pagamento_cartao":
        pagamento = mercado_pago.buscar_pagamento_por_referencia(sessao_id)
        if pagamento:
            return json.dumps({"aprovado": True, "payment_id": pagamento.get("id")}, ensure_ascii=False)
        return json.dumps({"aprovado": False}, ensure_ascii=False)

    if nome == "criar_pedido":
        try:
            if entrada.get("forma_pagamento") == "cartao":
                pagamento = mercado_pago.buscar_pagamento_por_referencia(sessao_id)
                if not pagamento:
                    return json.dumps({"erro": "Pagamento com cartão ainda não foi confirmado"}, ensure_ascii=False)
                resultado = criar_pedido_cartao_verificado(entrada, str(pagamento.get("id")))
            else:
                resultado = _criar_pedido_interno(entrada)
            return json.dumps(resultado, ensure_ascii=False)
        except PedidoInvalido as e:
            return json.dumps({"erro": e.mensagem, **e.extra}, ensure_ascii=False)

    return json.dumps({"erro": f"Tool desconhecida: {nome}"}, ensure_ascii=False)


def _argumentos(passo):
    """passo.arguments pode vir como dict já parseado ou como string JSON,
    dependendo da versão do SDK — trata os dois casos."""
    args = getattr(passo, "arguments", None)
    if args is None:
        return {}
    if isinstance(args, str):
        return json.loads(args) if args.strip() else {}
    return args


def _eh_rate_limit(erro):
    return getattr(erro, "status_code", None) == 429 or getattr(erro, "code", None) == 429


def _tempo_de_espera_sugerido(erro):
    """A API do Gemini embute o tempo de espera recomendado na própria
    mensagem de erro (ex: "Please retry in 29.8s"), sem header estruturado.
    Extrai esse valor quando presente; senão usa backoff exponencial."""
    match = _RETRY_EM_SEGUNDOS_RE.search(str(erro))
    if match:
        return min(float(match.group(1)) + 1, _ESPERA_MAXIMA_SEGUNDOS)
    return None


def _criar_interaction_com_retry(client, **kwargs):
    """A camada gratuita do Gemini tem um limite de requisições por minuto
    bem apertado — é comum estourar em conversas com várias chamadas de
    tool seguidas. Em vez de falhar na hora, espera o tempo recomendado
    pela própria API (ou um backoff exponencial, se não vier informado) e
    tenta de novo."""
    for tentativa in range(_MAX_TENTATIVAS_RATE_LIMIT):
        try:
            return client.interactions.create(**kwargs)
        except Exception as erro:
            ultima_tentativa = tentativa == _MAX_TENTATIVAS_RATE_LIMIT - 1
            if not _eh_rate_limit(erro) or ultima_tentativa:
                raise
            espera = _tempo_de_espera_sugerido(erro)
            if espera is None:
                espera = min(_ESPERA_INICIAL_SEGUNDOS * (2 ** tentativa), _ESPERA_MAXIMA_SEGUNDOS)
            time.sleep(espera)


def rodar_loop_gemini(mensagem_usuario, sessao_id, interaction_id_anterior=None):
    """Roda o loop de tool use do Gemini. O histórico da conversa é mantido
    pelo próprio Gemini via previous_interaction_id — não precisamos
    reenviar as mensagens anteriores a cada chamada.
    Retorna (texto_resposta, id_da_ultima_interacao)."""
    client = _cliente()

    interaction = _criar_interaction_com_retry(
        client,
        model=_MODEL,
        system_instruction=SYSTEM_PROMPT,
        input=mensagem_usuario,
        tools=TOOLS,
        previous_interaction_id=interaction_id_anterior,
    )

    for _ in range(_MAX_ITERACOES):
        chamadas = [s for s in interaction.steps if s.type == "function_call"]
        if not chamadas:
            return interaction.output_text, interaction.id

        resultados = []
        for passo in chamadas:
            resultado = executar_tool(passo.name, _argumentos(passo), sessao_id)
            resultados.append({
                "type": "function_result",
                "name": passo.name,
                "call_id": passo.id,
                "result": [{"type": "text", "text": resultado}],
            })

        interaction = _criar_interaction_com_retry(
            client,
            model=_MODEL,
            system_instruction=SYSTEM_PROMPT,
            input=resultados,
            tools=TOOLS,
            previous_interaction_id=interaction.id,
        )

    return "Desculpe, não consegui processar sua mensagem agora. Pode tentar novamente?", interaction.id
