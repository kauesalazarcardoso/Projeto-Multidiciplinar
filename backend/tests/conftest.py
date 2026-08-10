import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'back')))

from app import app as flask_app
from database import init_db, OWNER_USUARIO_PADRAO, OWNER_SENHA_PADRAO
import database
import horario


@pytest.fixture(autouse=True)
def loja_aberta_por_padrao(monkeypatch):
    """Os testes não devem depender do dia/hora real em que rodam. Por padrão
    a loja está "aberta"; testes de horário/fechamento sobrescrevem isso."""
    monkeypatch.setattr(horario, "esta_aberto", lambda momento=None: (True, None))


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://acai:acai@localhost:5432/acai_test"
)

_TABELAS = (
    "pedidos", "cardapio", "complementos", "cartoes", "pix_cobrancas",
    "usuarios", "sessoes", "horarios", "chat_sessoes",
)


def _limpar_tabelas():
    with database.get_conn() as conn:
        conn.execute(f"TRUNCATE {', '.join(_TABELAS)} RESTART IDENTITY CASCADE")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(database, "DATABASE_URL", TEST_DATABASE_URL)
    flask_app.config['TESTING'] = True
    init_db()
    _limpar_tabelas()
    init_db()
    with flask_app.test_client() as client:
        yield client


@pytest.fixture
def auth_headers(client):
    resp = client.post("/login", json={
        "usuario": OWNER_USUARIO_PADRAO,
        "senha": OWNER_SENHA_PADRAO,
    })
    token = resp.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}
