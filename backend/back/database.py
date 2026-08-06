import sqlite3
import os
from contextlib import contextmanager
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'pedidos.db')

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
    colunas_atuais = {row["name"] for row in conn.execute("PRAGMA table_info(pedidos)")}
    for coluna, definicao in _PEDIDOS_COLUNAS_NOVAS.items():
        if coluna not in colunas_atuais:
            conn.execute(f"ALTER TABLE pedidos ADD COLUMN {coluna} {definicao}")


_CHAT_SESSOES_COLUNAS_NOVAS = {
    "ultima_interaction_id": "TEXT",
}


def _migrar_chat_sessoes(conn):
    colunas_atuais = {row["name"] for row in conn.execute("PRAGMA table_info(chat_sessoes)")}
    for coluna, definicao in _CHAT_SESSOES_COLUNAS_NOVAS.items():
        if coluna not in colunas_atuais:
            conn.execute(f"ALTER TABLE chat_sessoes ADD COLUMN {coluna} {definicao}")


_COMPLEMENTOS_COLUNAS_NOVAS = {
    "preco": "REAL NOT NULL DEFAULT 0",
}


def _migrar_complementos(conn):
    colunas_atuais = {row["name"] for row in conn.execute("PRAGMA table_info(complementos)")}
    for coluna, definicao in _COMPLEMENTOS_COLUNAS_NOVAS.items():
        if coluna not in colunas_atuais:
            conn.execute(f"ALTER TABLE complementos ADD COLUMN {coluna} {definicao}")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id              INTEGER PRIMARY KEY,
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
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                nome  TEXT    NOT NULL,
                preco REAL    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complementos (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                nome  TEXT    NOT NULL UNIQUE,
                preco REAL    NOT NULL DEFAULT 0
            )
        """)
        _migrar_complementos(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cartoes (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
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
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                txid       TEXT    NOT NULL UNIQUE,
                valor      REAL    NOT NULL,
                copia_cola TEXT    NOT NULL,
                criado_em  TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
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
        if conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
            usuario = os.environ.get("OWNER_USUARIO", OWNER_USUARIO_PADRAO)
            senha = os.environ.get("OWNER_SENHA", OWNER_SENHA_PADRAO)
            conn.execute(
                "INSERT INTO usuarios (usuario, senha_hash) VALUES (?, ?)",
                (usuario, generate_password_hash(senha))
            )
        if conn.execute("SELECT COUNT(*) FROM cardapio").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO cardapio (nome, preco) VALUES (?, ?)",
                _ITENS_INICIAIS
            )
        if conn.execute("SELECT COUNT(*) FROM complementos").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO complementos (nome) VALUES (?)",
                [(n,) for n in _COMPLEMENTOS_INICIAIS]
            )
        if conn.execute("SELECT COUNT(*) FROM horarios").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO horarios (dia, abre, fecha, fechado) VALUES (?, ?, ?, ?)",
                _HORARIOS_INICIAIS
            )
    print("Banco SQLite inicializado!")
