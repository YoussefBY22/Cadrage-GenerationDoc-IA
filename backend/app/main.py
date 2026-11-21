import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api import discover_routers
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


def create_app(provider: LLMProvider | None = None, repo=None) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.provider = provider or build_provider(settings)
        log.info("startup", extra={"provider": app.state.provider.name, "version": __version__})
        yield

    app = FastAPI(title="Assistant IA local de cadrage", version=__version__, lifespan=lifespan,
                  docs_url="/docs", redoc_url=None)

    if settings.cors_origin_list:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                           allow_methods=["*"], allow_headers=["authorization", "content-type"],
                           expose_headers=["Content-Disposition", "X-Content-SHA256"])

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        """Toute erreur HTTP suit le format de 06 §6 : {"error": {"code", "message"}}."""
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            body = detail
        else:
            code = {401: "UNAUTHENTICATED", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
                exc.status_code, f"HTTP_{exc.status_code}")
            body = {"error": {"code": code, "message": str(detail)}}
        return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = "; ".join(f"{'.'.join(str(x) for x in e['loc'][1:])}: {e['msg']}" for e in exc.errors())
        return JSONResponse({"error": {"code": "VALIDATION_ERROR", "message": fields}}, status_code=422)

    # Dépôt : fourni, sinon construit paresseusement par app.api.deps.get_repo
    app.state.repo = repo
    for router in discover_routers():
        app.include_router(router, prefix="/api/v1")

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
