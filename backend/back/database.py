import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")

OWNER_USUARIO_PADRAO = "admin"
OWNER_SENHA_PADRAO = "acai2026"

_ITENS_INICIAIS = [
    ("Copo 200ml Econômico",   10.00),
    ("Copo 300ml Tradicional", 15.00),
    ("Copo 400ml Médio",       18.00),
    ("Copo 500ml Grande",      22.00),
    ("Copo 700ml Gigante",     28.00),
    ("Tigela 500ml Casa",      24.00),
    ("Tigela 800ml Família",   35.00),
    ("Barca de Açaí P",        45.00),
    ("Barca de Açaí G",        65.00),
    ("Copo Trufado Nutella",   26.00),
    ("Copo Trufado Ninho",     26.00),
    ("Açaí Zero Açúcar 400ml", 21.00),
]

_COMPLEMENTOS_INICIAIS = [
    "Leite em Pó", "Granola", "Banana", "Morango", "Nutella",
    "Paçoca", "Leite Condensado", "M&Ms", "Coco Ralado",
    "Ovomaltine", "Bis", "Kiwi",
]

_HORARIOS_INICIAIS = [
    # dia,      abre,    fecha,   fechado
    ("segunda", "13:30", "22:00", 1),
    ("terca",   "13:30", "22:00", 0),
    ("quarta",  "13:30", "22:00", 0),
    ("quinta",  "13:30", "22:00", 0),
    ("sexta",   "13:30", "22:00", 0),
    ("sabado",  "13:30", "22:00", 0),
    ("domingo", "13:30", "22:00", 0),
]


@contextmanager
def get_conn():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_PEDIDOS_COLUNAS_NOVAS = {
    "forma_pagamento": "TEXT NOT NULL DEFAULT 'pix'",
    "taxa_entrega":    "REAL NOT NULL DEFAULT 3.0",
    "cartao_ultimos4": "TEXT",
    "cartao_bandeira": "TEXT",
    "pix_txid":        "TEXT",
    "mp_order_id":     "TEXT",
    "pix_qr_base64":   "TEXT",
    "pix_copia_cola":  "TEXT",
    "troco_para":      "REAL",
}


def _migrar_pedidos(conn):
    for coluna, definicao in _PEDIDOS_COLUNAS_NOVAS.items():
        conn.execute(f"ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS {coluna} {definicao}")


_CHAT_SESSOES_COLUNAS_NOVAS = {
    "ultima_interaction_id": "TEXT",
}


def _migrar_chat_sessoes(conn):
    for coluna, definicao in _CHAT_SESSOES_COLUNAS_NOVAS.items():
        conn.execute(f"ALTER TABLE chat_sessoes ADD COLUMN IF NOT EXISTS {coluna} {definicao}")


_COMPLEMENTOS_COLUNAS_NOVAS = {
    "preco": "REAL NOT NULL DEFAULT 0",
}


def _migrar_complementos(conn):
    for coluna, definicao in _COMPLEMENTOS_COLUNAS_NOVAS.items():
        conn.execute(f"ALTER TABLE complementos ADD COLUMN IF NOT EXISTS {coluna} {definicao}")


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id              BIGINT  PRIMARY KEY,
                cliente         TEXT    NOT NULL,
                itens           TEXT    NOT NULL,
                total           REAL    NOT NULL,
                status          TEXT    NOT NULL DEFAULT 'aguardando',
                hora            TEXT    NOT NULL,
                forma_pagamento TEXT    NOT NULL DEFAULT 'pix',
                taxa_entrega    REAL    NOT NULL DEFAULT 3.0,
                cartao_ultimos4 TEXT,
                cartao_bandeira TEXT,
                pix_txid        TEXT,
                mp_order_id     TEXT,
                pix_qr_base64   TEXT,
                pix_copia_cola  TEXT,
                troco_para      REAL
            )
        """)
        _migrar_pedidos(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cardapio (
                id    SERIAL  PRIMARY KEY,
                nome  TEXT    NOT NULL,
                preco REAL    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complementos (
                id    SERIAL  PRIMARY KEY,
                nome  TEXT    NOT NULL UNIQUE,
                preco REAL    NOT NULL DEFAULT 0
            )
        """)
        _migrar_complementos(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cartoes (
                id           SERIAL  PRIMARY KEY,
                token        TEXT    NOT NULL UNIQUE,
                nome_titular TEXT    NOT NULL,
                ultimos4     TEXT    NOT NULL,
                bandeira     TEXT    NOT NULL,
                validade     TEXT    NOT NULL,
                criado_em    TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pix_cobrancas (
                id         SERIAL  PRIMARY KEY,
                txid       TEXT    NOT NULL UNIQUE,
                valor      REAL    NOT NULL,
                copia_cola TEXT    NOT NULL,
                criado_em  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id         SERIAL  PRIMARY KEY,
                usuario    TEXT    NOT NULL UNIQUE,
                senha_hash TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                token     TEXT    PRIMARY KEY,
                usuario   TEXT    NOT NULL,
                criado_em TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS horarios (
                dia     TEXT    PRIMARY KEY,
                abre    TEXT    NOT NULL,
                fecha   TEXT    NOT NULL,
                fechado INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessoes (
                id                    TEXT PRIMARY KEY,
                ultima_interaction_id TEXT,
                criado_em             TEXT NOT NULL,
                atualizado_em         TEXT NOT NULL
            )
        """)
        _migrar_chat_sessoes(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id         SERIAL  PRIMARY KEY,
                endpoint   TEXT    NOT NULL UNIQUE,
                p256dh     TEXT    NOT NULL,
                auth       TEXT    NOT NULL,
                criado_em  TEXT    NOT NULL
            )
        """)
        if conn.execute("SELECT COUNT(*) AS c FROM usuarios").fetchone()["c"] == 0:
            usuario = os.environ.get("OWNER_USUARIO", OWNER_USUARIO_PADRAO)
            senha = os.environ.get("OWNER_SENHA", OWNER_SENHA_PADRAO)
            conn.execute(
                "INSERT INTO usuarios (usuario, senha_hash) VALUES (%s, %s)",
                (usuario, generate_password_hash(senha))
            )
        if conn.execute("SELECT COUNT(*) AS c FROM cardapio").fetchone()["c"] == 0:
            conn.cursor().executemany(
                "INSERT INTO cardapio (nome, preco) VALUES (%s, %s)",
                _ITENS_INICIAIS
            )
        if conn.execute("SELECT COUNT(*) AS c FROM complementos").fetchone()["c"] == 0:
            conn.cursor().executemany(
                "INSERT INTO complementos (nome) VALUES (%s)",
                [(n,) for n in _COMPLEMENTOS_INICIAIS]
            )
        if conn.execute("SELECT COUNT(*) AS c FROM horarios").fetchone()["c"] == 0:
            conn.cursor().executemany(
                "INSERT INTO horarios (dia, abre, fecha, fechado) VALUES (%s, %s, %s, %s)",
                _HORARIOS_INICIAIS
            )
    print("Banco PostgreSQL inicializado!")
