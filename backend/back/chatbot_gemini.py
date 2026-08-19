import json
import os
import re
import time

from google import genai

from database import get_conn
import horario as horario_mod
from routes.pedidos import PedidoInvalido, _criar_pedido_interno

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
Você é o atendente virtual da Lovers Açaí, uma loja de açaí.

- Cumprimente o cliente de forma calorosa e breve. Seja objetivo e direto, como uma \
conversa real de WhatsApp — sem parágrafos longos.
- NUNCA responda sobre cardápio, complementos, bairros/taxa de entrega ou horário de \
funcionamento usando conhecimento próprio ou suposição — a resposta pode estar errada e \
o cliente confia nela pra fazer o pedido. Sempre chame a ferramenta correspondente antes \
de responder essa parte, mesmo quando a mensagem do cliente misturar vários assuntos ao \
mesmo tempo (ex: pergunta preço de um item E taxa de um bairro na mesma mensagem — chame \
consultar_cardapio E consultar_bairros antes de responder qualquer uma das duas partes).
- Quando perguntarem sobre o cardápio, chame consultar_cardapio e apresente os produtos \
com preços em R$. Os tamanhos já fazem parte do nome de cada produto.
- Quando perguntarem sobre complementos, chame consultar_complementos. Alguns são grátis \
(preço 0) e outros têm custo adicional — deixe isso claro ao apresentar a lista, e some o \
preço de cada complemento pago escolhido ao preço do item antes de montar o total.
- Antes de confirmar qualquer pedido, chame consultar_horario. Se "aberto_agora" for falso, \
explique educadamente o motivo (se "fechado_hoje", diga que não abrimos nesse dia; se \
"fora_do_horario", informe o horário de funcionamento do dia) e agradeça o contato — não \
continue o fluxo de pedido.
- Colete: itens desejados (com tamanho/sabor), nome do cliente, telefone e endereço de entrega \
(rua, número e bairro). O bairro precisa ser um dos cadastrados — chame consultar_bairros para \
saber quais bairros existem e a taxa de entrega de cada um (ela varia por bairro, não é mais \
fixa). Se o cliente disser um bairro que não está na lista, avise e peça pra confirmar ou \
escolher outro. Ao chamar criar_pedido, passe o nome do bairro exatamente como veio de \
consultar_bairros no campo "bairro", e use a taxa dele (não um valor fixo) ao montar o total. \
Se o cliente mencionar alguma observação especial do pedido (ex: sem cebola, trocar embalagem, \
ponto de referência), inclua no campo observacao ao chamar criar_pedido.
- Pergunte a forma de pagamento: Pix, cartão ou dinheiro.
  - Pix: informe a chave Pix "50633540000180" para o cliente pagar, e explique que depois de \
pagar ele deve enviar o comprovante pelo WhatsApp da loja, (51) 99483-4263. Pode chamar \
criar_pedido com forma_pagamento "pix" assim que o pedido estiver fechado, sem esperar \
confirmação de pagamento nenhuma — o pedido já entra direto na fila normal, igual aos outros.
  - Cartão: o pagamento é feito na entrega, com maquininha física que o entregador leva. A taxa \
de entrega do bairro continua normal — a maquininha cobra, além dela, uma taxa própria e \
separada: R$2,00 em compras de até R$50,00 em itens, ou R$3,00 em compras acima de R$50,00. \
Pode chamar criar_pedido com forma_pagamento "cartao" direto, sem nenhuma verificação prévia.
  - Dinheiro: pergunte se precisa de troco e para qual valor.
- Revalide o horário de funcionamento (consultar_horario) logo antes de chamar criar_pedido, \
pois a loja pode ter fechado durante a conversa.
- Depois de criar o pedido com sucesso, informe o número do pedido e agradeça. Para pedidos \
via Pix, lembre o cliente de enviar o comprovante pelo WhatsApp da loja.
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
        "name": "consultar_bairros",
        "description": "Retorna a lista de bairros para os quais a loja entrega, cada um com "
                        "sua taxa de entrega (a taxa varia por bairro). Use para saber se o "
                        "bairro do cliente é atendido e qual o valor certo da taxa antes de "
                        "montar o total e chamar criar_pedido.",
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
                "bairro": {
                    "type": "string",
                    "description": "Nome do bairro de entrega, exatamente como retornado por "
                                    "consultar_bairros — precisa ser um bairro cadastrado.",
                },
                "total": {
                    "type": "number",
                    "description": "Soma dos itens + taxa de entrega do bairro (ver "
                                    "consultar_bairros) + taxa da maquininha (só para cartão: "
                                    "R$2,00 se os itens somarem até R$50,00, ou R$3,00 se "
                                    "somarem mais que isso).",
                },
                "forma_pagamento": {"type": "string", "enum": ["pix", "cartao", "dinheiro"]},
                "troco_para": {"type": "number", "description": "Opcional, só para dinheiro"},
                "observacao": {"type": "string", "description": "Opcional, observação especial do pedido"},
            },
            "required": ["cliente", "itens", "bairro", "total", "forma_pagamento"],
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


def _consultar_bairros():
    with get_conn() as conn:
        rows = conn.execute("SELECT nome, taxa FROM bairros ORDER BY nome").fetchall()
    return [{"nome": r["nome"], "taxa": r["taxa"]} for r in rows]


def _consultar_horario():
    aberto, motivo = horario_mod.esta_aberto()
    return {"aberto_agora": aberto, "motivo": motivo, "horarios": horario_mod.buscar_horarios()}


def executar_tool(nome, entrada, sessao_id):
    """Executa uma tool chamada pelo Gemini. Retorna sempre uma string JSON."""
    if nome == "consultar_cardapio":
        return json.dumps(_consultar_cardapio(), ensure_ascii=False)

    if nome == "consultar_complementos":
        return json.dumps(_consultar_complementos(), ensure_ascii=False)

    if nome == "consultar_bairros":
        return json.dumps(_consultar_bairros(), ensure_ascii=False)

    if nome == "consultar_horario":
        return json.dumps(_consultar_horario(), ensure_ascii=False)

    if nome == "criar_pedido":
        try:
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
