"""Script de uso único: copia os dados do db/pedidos.db (SQLite) para o
PostgreSQL configurado em DATABASE_URL. Não faz parte do fluxo normal da
aplicação — rode manualmente uma vez ao migrar um ambiente existente.

Uso:
    docker compose run --rm -v "$(pwd)/db:/db" backend \
        python migrar_sqlite_para_postgres.py
"""
import os
import sqlite3

from database import get_conn, init_db

SQLITE_PATH = os.environ.get(
    "SQLITE_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "db", "pedidos.db")
)

_TABELAS = (
    "pedidos", "cardapio", "complementos",
    "usuarios", "horarios", "chat_sessoes",
)

_TABELAS_COM_SERIAL = ("cardapio", "complementos", "usuarios")


def _colunas_postgres(conn, tabela):
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (tabela,)
    ).fetchall()
    return {r["column_name"] for r in rows}


def _linhas_sqlite(tabela, colunas_validas):
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(f"SELECT * FROM {tabela}")
        colunas = [d[0] for d in cur.description if d[0] in colunas_validas]
        indices = [i for i, d in enumerate(cur.description) if d[0] in colunas_validas]
        linhas = [tuple(row[i] for i in indices) for row in cur.fetchall()]
        return colunas, linhas
    finally:
        conn.close()


def migrar():
    if not os.path.exists(SQLITE_PATH):
        raise SystemExit(f"Arquivo SQLite não encontrado: {SQLITE_PATH}")

    print(f"Lendo dados de {SQLITE_PATH}")

    init_db()

    with get_conn() as conn:
        conn.execute(f"TRUNCATE {', '.join(_TABELAS)}, sessoes RESTART IDENTITY CASCADE")

    resumo = {}
    for tabela in _TABELAS:
        with get_conn() as conn:
            colunas_validas = _colunas_postgres(conn, tabela)
        colunas, linhas = _linhas_sqlite(tabela, colunas_validas)
        if linhas:
            placeholders = ", ".join(["%s"] * len(colunas))
            colunas_sql = ", ".join(colunas)
            with get_conn() as conn:
                conn.cursor().executemany(
                    f"INSERT INTO {tabela} ({colunas_sql}) VALUES ({placeholders})",
                    linhas
                )
        resumo[tabela] = len(linhas)

    with get_conn() as conn:
        for tabela in _TABELAS_COM_SERIAL:
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{tabela}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {tabela}), 1))"
            )

    print("\nLinhas copiadas:")
    for tabela, qtd in resumo.items():
        print(f"  {tabela}: {qtd}")
    print("\nMigração concluída.")


if __name__ == "__main__":
    migrar()
