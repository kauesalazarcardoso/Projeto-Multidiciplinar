import os
from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from werkzeug.security import generate_password_hash

DATABASE_URL = os.environ.get("DATABASE_URL")

OWNER_USUARIO_PADRAO = "admin"
OWNER_SENHA_PADRAO = "acai2026"

CATEGORIAS_CARDAPIO = ["Açaí Tradicional", "Cupuaçu", "Iogurte Grego", "Iogurte Grego com Morango"]

_ITENS_INICIAIS = [
    ("Copo 330ml Açaí Tradicional", 19.00, "Açaí Tradicional"),
    ("Copo 440ml Açaí Tradicional", 21.00, "Açaí Tradicional"),
    ("Copo 550ml Açaí Tradicional", 24.00, "Açaí Tradicional"),
    ("Copo 770ml Açaí Tradicional", 29.00, "Açaí Tradicional"),
    ("Copo 330ml Cupuaçu", 19.00, "Cupuaçu"),
    ("Copo 440ml Cupuaçu", 21.00, "Cupuaçu"),
    ("Copo 550ml Cupuaçu", 24.00, "Cupuaçu"),
    ("Copo 770ml Cupuaçu", 29.00, "Cupuaçu"),
    ("Copo 330ml Iogurte Grego", 19.00, "Iogurte Grego"),
    ("Copo 440ml Iogurte Grego", 21.00, "Iogurte Grego"),
    ("Copo 550ml Iogurte Grego", 24.00, "Iogurte Grego"),
    ("Copo 770ml Iogurte Grego", 29.00, "Iogurte Grego"),
    ("Copo 330ml Iogurte Grego com Morango", 19.00, "Iogurte Grego com Morango"),
    ("Copo 440ml Iogurte Grego com Morango", 21.00, "Iogurte Grego com Morango"),
    ("Copo 550ml Iogurte Grego com Morango", 24.00, "Iogurte Grego com Morango"),
    ("Copo 770ml Iogurte Grego com Morango", 29.00, "Iogurte Grego com Morango"),
]

CATEGORIAS_COMPLEMENTOS = ["Calda", "Frutas", "Complementos Gratuitos", "Complementos Adicionais"]

_COMPLEMENTOS_INICIAIS = [
    ("Leite em Pó",      "Complementos Gratuitos"),
    ("Granola",          "Complementos Gratuitos"),
    ("Banana",           "Frutas"),
    ("Morango",          "Frutas"),
    ("Nutella",          "Calda"),
    ("Paçoca",           "Complementos Gratuitos"),
    ("Leite Condensado", "Calda"),
    ("M&Ms",             "Complementos Gratuitos"),
    ("Coco Ralado",      "Complementos Gratuitos"),
    ("Ovomaltine",       "Complementos Gratuitos"),
    ("Bis",              "Complementos Gratuitos"),
    ("Kiwi",             "Frutas"),
]

_BAIRROS_INICIAIS = [
    ("Centro", 3.0),
    ("Rio Branco", 3.0),
    ("Rolantinho", 8.0),
    ("Alto Rolantinho", 8.0),
    ("Areia", 7.0),
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


_pool = None
_pool_dsn = None


def _get_pool():
    """Cria o pool sob demanda (nunca na importação do módulo — os testes
    trocam DATABASE_URL via monkeypatch depois de importar, e o Gunicorn em
    produção roda com um único worker, então não há problema de pool
    sobrevivendo a um fork). Recria o pool se o DSN mudar, o que é exatamente
    o que acontece a cada teste ao alternar entre o banco real e o de teste."""
    global _pool, _pool_dsn
    if _pool is None or _pool_dsn != DATABASE_URL:
        if _pool is not None:
            _pool.close()
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
        _pool_dsn = DATABASE_URL
    return _pool


@contextmanager
def get_conn():
    with _get_pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


_PEDIDOS_COLUNAS_NOVAS = {
    "forma_pagamento": "TEXT NOT NULL DEFAULT 'pix'",
    "taxa_entrega":    "REAL NOT NULL DEFAULT 3.0",
    "taxa_maquininha": "REAL NOT NULL DEFAULT 0",
    "troco_para":      "REAL",
    "observacao":      "TEXT",
    "arquivado":       "BOOLEAN NOT NULL DEFAULT FALSE",
}

_PEDIDOS_COLUNAS_REMOVIDAS = (
    "cartao_ultimos4", "cartao_bandeira", "pix_txid",
    "mp_order_id", "pix_qr_base64", "pix_copia_cola",
)


def _migrar_pedidos(conn):
    for coluna, definicao in _PEDIDOS_COLUNAS_NOVAS.items():
        conn.execute(f"ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS {coluna} {definicao}")
    for coluna in _PEDIDOS_COLUNAS_REMOVIDAS:
        conn.execute(f"ALTER TABLE pedidos DROP COLUMN IF EXISTS {coluna}")
    # Pix deixou de esperar confirmação manual do comprovante — qualquer
    # pedido antigo ainda preso em 'pendente_pagamento' (produção pode ter
    # algum) passa a entrar direto na fila normal, como os demais.
    conn.execute("UPDATE pedidos SET status = 'aguardando' WHERE status = 'pendente_pagamento'")


_CHAT_SESSOES_COLUNAS_NOVAS = {
    "ultima_interaction_id": "TEXT",
}


def _migrar_chat_sessoes(conn):
    for coluna, definicao in _CHAT_SESSOES_COLUNAS_NOVAS.items():
        conn.execute(f"ALTER TABLE chat_sessoes ADD COLUMN IF NOT EXISTS {coluna} {definicao}")


def _migrar_bairros(conn):
    # ON CONFLICT DO NOTHING preserva bairros já cadastrados/editados no Admin
    # e só acrescenta os padrões que ainda não existem (por nome).
    conn.cursor().executemany(
        "INSERT INTO bairros (nome, taxa) VALUES (%s, %s) ON CONFLICT (nome) DO NOTHING",
        _BAIRROS_INICIAIS
    )


_COMPLEMENTOS_COLUNAS_NOVAS = {
    "preco": "REAL NOT NULL DEFAULT 0",
}


def _migrar_complementos(conn):
    for coluna, definicao in _COMPLEMENTOS_COLUNAS_NOVAS.items():
        conn.execute(f"ALTER TABLE complementos ADD COLUMN IF NOT EXISTS {coluna} {definicao}")

    conn.execute("ALTER TABLE complementos ADD COLUMN IF NOT EXISTS categoria TEXT")
    for nome, categoria in _COMPLEMENTOS_INICIAIS:
        conn.execute(
            "UPDATE complementos SET categoria = %s WHERE nome = %s AND categoria IS NULL",
            (categoria, nome)
        )
    # itens desconhecidos (fora do seed original) caem num dos dois grupos de
    # preço, já que não há como adivinhar se são calda/fruta
    conn.execute(
        "UPDATE complementos SET categoria = 'Complementos Gratuitos' "
        "WHERE categoria IS NULL AND preco = 0"
    )
    conn.execute(
        "UPDATE complementos SET categoria = 'Complementos Adicionais' WHERE categoria IS NULL"
    )
    conn.execute("ALTER TABLE complementos ALTER COLUMN categoria SET DEFAULT 'Complementos Adicionais'")
    conn.execute("ALTER TABLE complementos ALTER COLUMN categoria SET NOT NULL")


def _migrar_cardapio(conn):
    conn.execute("ALTER TABLE cardapio ADD COLUMN IF NOT EXISTS categoria TEXT")
    # As categorias antigas (Copos, Tigelas, Barcas, Trufados, Zero Açúcar,
    # Outros) e os itens que estavam nelas foram descontinuados — o cardápio
    # passa a ter só as 4 categorias novas. Remove qualquer linha (inclusive
    # sem categoria nenhuma) que não seja uma delas.
    placeholders = ", ".join(["%s"] * len(CATEGORIAS_CARDAPIO))
    conn.execute(
        f"DELETE FROM cardapio WHERE categoria IS NULL OR categoria NOT IN ({placeholders})",
        CATEGORIAS_CARDAPIO
    )
    conn.execute("ALTER TABLE cardapio ALTER COLUMN categoria DROP DEFAULT")
    conn.execute("ALTER TABLE cardapio ALTER COLUMN categoria SET NOT NULL")


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
                taxa_maquininha REAL    NOT NULL DEFAULT 0,
                troco_para      REAL
            )
        """)
        _migrar_pedidos(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cardapio (
                id        SERIAL  PRIMARY KEY,
                nome      TEXT    NOT NULL,
                preco     REAL    NOT NULL,
                categoria TEXT    NOT NULL
            )
        """)
        _migrar_cardapio(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS complementos (
                id        SERIAL  PRIMARY KEY,
                nome      TEXT    NOT NULL UNIQUE,
                preco     REAL    NOT NULL DEFAULT 0,
                categoria TEXT    NOT NULL DEFAULT 'Complementos Adicionais'
            )
        """)
        _migrar_complementos(conn)
        conn.execute("DROP TABLE IF EXISTS cartoes")
        conn.execute("DROP TABLE IF EXISTS pix_cobrancas")
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
            CREATE TABLE IF NOT EXISTS bairros (
                id    SERIAL  PRIMARY KEY,
                nome  TEXT    NOT NULL UNIQUE,
                taxa  REAL    NOT NULL DEFAULT 3.0
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
                "INSERT INTO cardapio (nome, preco, categoria) VALUES (%s, %s, %s)",
                _ITENS_INICIAIS
            )
        if conn.execute("SELECT COUNT(*) AS c FROM complementos").fetchone()["c"] == 0:
            conn.cursor().executemany(
                "INSERT INTO complementos (nome, categoria) VALUES (%s, %s)",
                _COMPLEMENTOS_INICIAIS
            )
        _migrar_bairros(conn)
        if conn.execute("SELECT COUNT(*) AS c FROM horarios").fetchone()["c"] == 0:
            conn.cursor().executemany(
                "INSERT INTO horarios (dia, abre, fecha, fechado) VALUES (%s, %s, %s, %s)",
                _HORARIOS_INICIAIS
            )
    print("Banco PostgreSQL inicializado!")
