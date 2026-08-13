import json

import pytest

import chatbot_gemini
import horario


class FakePasso:
    """Dublê simples de um step de function_call da resposta do Gemini."""

    def __init__(self, type_, **kw):
        self.type = type_
        self.__dict__.update(kw)


class FakeInteraction:
    def __init__(self, steps, output_text, id_):
        self.steps = steps
        self.output_text = output_text
        self.id = id_


class FakeErroRateLimit(Exception):
    status_code = 429


class FakeInteractions:
    def __init__(self, respostas):
        self._respostas = list(respostas)

    def create(self, **kwargs):
        item = self._respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeCliente:
    def __init__(self, respostas):
        self.interactions = FakeInteractions(respostas)


def _mockar_gemini(monkeypatch, respostas):
    monkeypatch.setattr(chatbot_gemini, "_cliente", lambda: FakeCliente(respostas))


# ── Tool handlers isolados ──────────────────────────────────────────

def test_tool_consultar_cardapio(client):
    resultado = json.loads(chatbot_gemini.executar_tool("consultar_cardapio", {}, "sessao-x"))
    assert isinstance(resultado, list)
    assert len(resultado) > 0
    assert "nome" in resultado[0] and "preco" in resultado[0]


def test_tool_consultar_horario_fechado(client, monkeypatch):
    monkeypatch.setattr(horario, "esta_aberto", lambda momento=None: (False, "fechado_hoje"))
    resultado = json.loads(chatbot_gemini.executar_tool("consultar_horario", {}, "sessao-x"))
    assert resultado["aberto_agora"] is False
    assert resultado["motivo"] == "fechado_hoje"


def test_tool_criar_pedido_sucesso(client):
    entrada = {
        "cliente": {"nome": "Ana", "tel": "51988887777", "end": "Rua Y, 45"},
        "itens": [{"nome": "Açaí 300ml", "preco": 15.0, "qtd": 1}],
        "total": 18.0,
        "forma_pagamento": "dinheiro",
        "troco_para": 20.0,
    }
    resultado = json.loads(chatbot_gemini.executar_tool("criar_pedido", entrada, "sessao-y"))
    assert "id" in resultado
    assert resultado["status"] == "aguardando"

    from database import get_conn
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM pedidos WHERE id = %s", (resultado["id"],)).fetchone()
    assert row is not None


def test_tool_criar_pedido_invalido(client):
    entrada = {
        "cliente": {"nome": "Ana"},
        "itens": [],
        "total": "não é número",
        "forma_pagamento": "dinheiro",
    }
    resultado = json.loads(chatbot_gemini.executar_tool("criar_pedido", entrada, "sessao-z"))
    assert "erro" in resultado


def test_tools_nao_tem_mais_mercado_pago():
    nomes = {t["name"] for t in chatbot_gemini.TOOLS}
    assert "gerar_cobranca_pix" not in nomes
    assert "gerar_link_pagamento_cartao" not in nomes
    assert "verificar_pagamento_cartao" not in nomes
    assert "criar_pedido" in nomes


# ── Loop de tool use (mockando o cliente Gemini) ────────────────────

def test_loop_sem_tool_use_retorna_texto_direto(client, monkeypatch):
    _mockar_gemini(monkeypatch, [
        FakeInteraction([], "Oi! Como posso ajudar?", "int_1"),
    ])
    texto, interaction_id = chatbot_gemini.rodar_loop_gemini("oi", "sessao-a", None)
    assert texto == "Oi! Como posso ajudar?"
    assert interaction_id == "int_1"


def test_loop_com_tool_use_encadeia_e_nao_vaza_turno_intermediario(client, monkeypatch):
    _mockar_gemini(monkeypatch, [
        FakeInteraction(
            [FakePasso("function_call", id="fc_1", name="consultar_horario", arguments={})],
            None, "int_1",
        ),
        FakeInteraction([], "Estamos abertos agora!", "int_2"),
    ])
    texto, interaction_id = chatbot_gemini.rodar_loop_gemini("vocês estão abertos?", "sessao-b", None)
    assert texto == "Estamos abertos agora!"
    assert interaction_id == "int_2"


def test_loop_tenta_de_novo_apos_rate_limit(client, monkeypatch):
    monkeypatch.setattr(chatbot_gemini.time, "sleep", lambda segundos: None)
    _mockar_gemini(monkeypatch, [
        FakeErroRateLimit("limite excedido"),
        FakeInteraction([], "Consegui na segunda tentativa!", "int_1"),
    ])
    texto, interaction_id = chatbot_gemini.rodar_loop_gemini("oi", "sessao-d", None)
    assert texto == "Consegui na segunda tentativa!"
    assert interaction_id == "int_1"


def test_espera_sugerida_extraida_da_mensagem_de_erro():
    erro = FakeErroRateLimit("Quota exceeded... Please retry in 29.817626807s.")
    espera = chatbot_gemini._tempo_de_espera_sugerido(erro)
    assert espera == pytest.approx(30.817626807, abs=0.01)


def test_espera_sugerida_respeita_teto_maximo():
    erro = FakeErroRateLimit("Please retry in 9999s.")
    espera = chatbot_gemini._tempo_de_espera_sugerido(erro)
    assert espera == chatbot_gemini._ESPERA_MAXIMA_SEGUNDOS


def test_espera_sugerida_ausente_retorna_none():
    erro = FakeErroRateLimit("erro sem tempo sugerido")
    assert chatbot_gemini._tempo_de_espera_sugerido(erro) is None


def test_loop_usa_tempo_de_espera_sugerido_pela_api(client, monkeypatch):
    esperas_registradas = []
    monkeypatch.setattr(chatbot_gemini.time, "sleep", lambda segundos: esperas_registradas.append(segundos))
    _mockar_gemini(monkeypatch, [
        FakeErroRateLimit("Quota exceeded. Please retry in 5s."),
        FakeInteraction([], "ok", "int_1"),
    ])
    chatbot_gemini.rodar_loop_gemini("oi", "sessao-g", None)
    assert esperas_registradas == [pytest.approx(6.0, abs=0.01)]


def test_loop_desiste_apos_esgotar_tentativas_de_rate_limit(client, monkeypatch):
    monkeypatch.setattr(chatbot_gemini.time, "sleep", lambda segundos: None)
    _mockar_gemini(monkeypatch, [
        FakeErroRateLimit("limite excedido"),
        FakeErroRateLimit("limite excedido"),
        FakeErroRateLimit("limite excedido"),
    ])
    try:
        chatbot_gemini.rodar_loop_gemini("oi", "sessao-e", None)
        assert False, "deveria ter levantado a exceção depois de esgotar as tentativas"
    except FakeErroRateLimit:
        pass


def test_loop_nao_tenta_de_novo_em_erro_que_nao_e_rate_limit(client, monkeypatch):
    monkeypatch.setattr(chatbot_gemini.time, "sleep", lambda segundos: None)
    _mockar_gemini(monkeypatch, [ValueError("erro qualquer, sem status_code")])
    try:
        chatbot_gemini.rodar_loop_gemini("oi", "sessao-f", None)
        assert False, "deveria ter propagado o erro imediatamente"
    except ValueError:
        pass


def test_loop_argumentos_como_string_json(client, monkeypatch):
    """Alguns formatos do SDK podem devolver .arguments como string JSON
    em vez de dict já parseado — o código deve lidar com os dois casos."""
    _mockar_gemini(monkeypatch, [
        FakeInteraction(
            [FakePasso("function_call", id="fc_1", name="consultar_cardapio", arguments="{}")],
            None, "int_1",
        ),
        FakeInteraction([], "Temos vários tamanhos!", "int_2"),
    ])
    texto, _ = chatbot_gemini.rodar_loop_gemini("o que vocês têm?", "sessao-c", None)
    assert texto == "Temos vários tamanhos!"


# ── Endpoint /chatbot/mensagem ──────────────────────────────────────

def test_endpoint_sem_mensagem_400(client):
    response = client.post("/chatbot/mensagem", json={"sessao_id": None, "mensagem": ""})
    assert response.status_code == 400


def test_endpoint_sem_sessao_cria_nova(client, monkeypatch):
    _mockar_gemini(monkeypatch, [
        FakeInteraction([], "Oi! Como posso ajudar?", "int_1"),
    ])

    response = client.post("/chatbot/mensagem", json={"sessao_id": None, "mensagem": "oi"})

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["resposta"] == "Oi! Como posso ajudar?"
    assert data["sessao_id"]

    from database import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ultima_interaction_id FROM chat_sessoes WHERE id = %s", (data["sessao_id"],)
        ).fetchone()
    assert row is not None
    assert row["ultima_interaction_id"] == "int_1"


def test_endpoint_reusa_sessao_e_encadeia_interacoes(client, monkeypatch):
    _mockar_gemini(monkeypatch, [FakeInteraction([], "Resposta 1", "int_1")])
    r1 = client.post("/chatbot/mensagem", json={"sessao_id": None, "mensagem": "primeira mensagem"})
    sessao_id = json.loads(r1.data)["sessao_id"]

    _mockar_gemini(monkeypatch, [FakeInteraction([], "Resposta 2", "int_2")])
    r2 = client.post("/chatbot/mensagem", json={"sessao_id": sessao_id, "mensagem": "segunda mensagem"})

    assert r2.status_code == 200
    assert json.loads(r2.data)["sessao_id"] == sessao_id

    from database import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ultima_interaction_id FROM chat_sessoes WHERE id = %s", (sessao_id,)
        ).fetchone()
    assert row["ultima_interaction_id"] == "int_2"


def test_endpoint_erro_no_gemini_retorna_500(client, monkeypatch):
    class ClienteQuebrado:
        class interactions:
            @staticmethod
            def create(**kwargs):
                raise RuntimeError("falha de rede simulada")

    monkeypatch.setattr(chatbot_gemini, "_cliente", lambda: ClienteQuebrado())

    response = client.post("/chatbot/mensagem", json={"sessao_id": None, "mensagem": "oi"})

    assert response.status_code == 500
    assert "erro" in json.loads(response.data)
