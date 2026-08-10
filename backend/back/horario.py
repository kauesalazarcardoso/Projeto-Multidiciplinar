from datetime import datetime

from database import get_conn

_DIAS_SEMANA_PY = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def _dia_da_semana(momento):
    return _DIAS_SEMANA_PY[momento.weekday()]


def buscar_horarios():
    """Retorna um dict {dia: {"abre":.., "fecha":.., "fechado":..}} para os 7 dias."""
    with get_conn() as conn:
        rows = conn.execute("SELECT dia, abre, fecha, fechado FROM horarios").fetchall()
    return {r["dia"]: {"abre": r["abre"], "fecha": r["fecha"], "fechado": bool(r["fechado"])} for r in rows}


def esta_aberto(momento=None):
    """Retorna (aberto: bool, motivo: str|None).

    motivo ∈ {"fechado_hoje", "fora_do_horario", None}
    """
    momento = momento or datetime.now()
    dia = _dia_da_semana(momento)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT abre, fecha, fechado FROM horarios WHERE dia = %s", (dia,)
        ).fetchone()

    if not row or row["fechado"]:
        return False, "fechado_hoje"

    hora_atual = momento.strftime("%H:%M")
    if not (row["abre"] <= hora_atual <= row["fecha"]):
        return False, "fora_do_horario"

    return True, None
