from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request
from slowapi.middleware import SlowAPIMiddleware

# Instance du limiteur global
# Limite par défaut : 100 requêtes par minute par IP
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

def configure_rate_limiter(app: FastAPI):
    """Applique le rate limiting à l'application FastAPI"""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, lambda req, exc: (
        FastAPI.exception_handler(req, exc)  # gestion automatique
    ))
    app.add_middleware(SlowAPIMiddleware)