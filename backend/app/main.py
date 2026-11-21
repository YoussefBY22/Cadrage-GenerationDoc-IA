import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from . import __version__
from .config import get_settings
from .llm import LLMProvider, build_provider
from .logging_setup import configure_logging

log = logging.getLogger("app")


def check_database(url: str) -> str:
    """'unconfigured' | 'ok' | 'error' — sans jamais exposer l'URL (mot de passe) dans la réponse."""
    if not url:
        return "unconfigured"
    try:
        import psycopg

        with psycopg.connect(url, connect_timeout=3) as conn:
            conn.execute("SELECT 1")
            row = conn.execute(
                "SELECT 1 FROM pg_extension WHERE extname = 'vector'").fetchone()
        return "ok" if row else "error"
    except Exception:  # noqa: BLE001 — l'état suffit, pas le détail (peut contenir l'URL)
        log.warning("database check failed")
        return "error"


def create_app(provider: LLMProvider | None = None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.provider = provider or build_provider(settings)
        log.info("startup", extra={"provider": app.state.provider.name, "version": __version__})
        yield

    app = FastAPI(title="Assistant IA local de cadrage", version=__version__, lifespan=lifespan,
                  docs_url="/docs", redoc_url=None)

    @app.get("/health")
    def health() -> dict:
        """Vivacité : le processus répond."""
        return {"status": "ok", "version": __version__}

    @app.get("/ready")
    def ready() -> dict:
        """Disponibilité : base de données joignable (si configurée) et modèle déclaré."""
        db = check_database(settings.database_url)
        body = {"status": "ok" if db in ("ok", "unconfigured") else "degraded",
                "database": db, "llm_provider": app.state.provider.name}
        if db == "error":
            raise HTTPException(status_code=503, detail=body)
        return body

    return app


app = create_app()
