import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'back')))

from app import app as flask_app
from database import init_db
from extensions import limiter
import database
import horario
from routes import auth as auth_module

# OWNER_USUARIO/OWNER_SENHA não têm mais valor padrão hardcoded no código —
# os testes precisam fornecer os próprios via env var antes de init_db()
# criar o usuário admin inicial (só acontece quando a tabela usuarios está vazia).
OWNER_USUARIO_PADRAO = "admin"
OWNER_SENHA_PADRAO = "senha-de-teste-123"
os.environ["OWNER_USUARIO"] = OWNER_USUARIO_PADRAO
os.environ["OWNER_SENHA"] = OWNER_SENHA_PADRAO


@pytest.fixture(autouse=True)
def loja_aberta_por_padrao(monkeypatch):
    """Os testes não devem depender do dia/hora real em que rodam. Por padrão
    a loja está "aberta"; testes de horário/fechamento sobrescrevem isso."""
    monkeypatch.setattr(horario, "esta_aberto", lambda momento=None: (True, None))


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://acai:acai@localhost:5432/acai_test"
)

_TABELAS = (
    "pedidos", "cardapio", "complementos", "bairros",
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
    # Estado do bloqueio de força bruta do /login é em memória (não é
    # limpo pelo TRUNCATE acima) — sem isso, um teste que erra a senha
    # várias vezes deixaria o usuário "admin" bloqueado pros testes seguintes.
    auth_module._tentativas_login.clear()
    # Contadores do rate limiting também são em memória e não são limpos pelo
    # TRUNCATE — sem isso, testes que criam vários pedidos em sequência
    # esbarrariam no limite por causa de execuções anteriores.
    limiter.reset()
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
