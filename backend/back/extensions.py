from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Storage em memória: correto porque o Gunicorn roda com 1 worker só (ver
# comentário em routes/auth.py) — todas as threads compartilham o mesmo
# processo, então os contadores por IP ficam consistentes.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],
    storage_uri="memory://",
)
