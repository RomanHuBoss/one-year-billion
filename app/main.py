from __future__ import annotations
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.settings import Settings
from app.services.demo_state import DemoState
from app.config.runtime import build_runtime_config
from app.config.phase_validator import startup_phase_validation
from app.execution.idempotency import InMemoryIdempotencyStore
from app.execution.order_router import OrderRouter
from app.security.startup_guard import validate_startup_security
from app.db.connection import Database
from app.db.repository import Repository
from app.api.routes import health, state, risk, signals, execution, actions, ml, llm, paper, incidents, runtime


def _install_database(app: FastAPI, settings: Settings) -> None:
    """Подключает PostgreSQL, когда он нужен.

    Локальный demo/smoke режим может работать без БД. Любой live-запуск обязан
    стартовать только с открытой PostgreSQL-сессией, потому что именно БД
    дублирует критические constraints: approved risk_decision_id, idempotency,
    positions protection and audit trail.
    """

    app.state.db = None
    app.state.repository = None
    app.state.db_available = False
    app.state.db_startup_error = None

    should_open = settings.require_db_for_live and settings.live_requested
    if not should_open and settings.app_env == 'local':
        return

    db = Database(settings.database_url)
    try:
        db.open()
        # Дешевый sanity-check вместо молчаливого pool-open.
        db.fetch_one('SELECT 1 AS ok')
    except Exception as exc:  # pragma: no cover - зависит от внешнего PostgreSQL.
        app.state.db_startup_error = f'{type(exc).__name__}:{exc}'
        if should_open:
            raise RuntimeError('database_required_for_live_but_unavailable') from exc
        return
    app.state.db = db
    app.state.repository = Repository(db)
    app.state.db_available = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        yield
    finally:
        db = getattr(app.state, 'db', None)
        if db is not None:
            db.close()


def create_app() -> FastAPI:
    settings = Settings()
    runtime_config = build_runtime_config()
    validate_startup_security(settings, runtime_config)
    phase_reasons = startup_phase_validation(runtime_config.raw)
    if phase_reasons:
        raise RuntimeError('unsafe_phase_config:' + ';'.join(phase_reasons))
    app = FastAPI(title=settings.app_name, version='1.7.0-total-project-check-live-gated', lifespan=lifespan)
    app.state.settings = settings
    app.state.runtime_config = runtime_config
    app.state.demo_state = DemoState(symbols=runtime_config.live_universe, phase=runtime_config.phase)
    app.state.idempotency = InMemoryIdempotencyStore()
    app.state.order_router = OrderRouter(app.state.idempotency)
    _install_database(app, settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['http://127.0.0.1:8000', 'http://localhost:8000'],
        allow_credentials=True,
        allow_methods=['*'],
        allow_headers=['*'],
    )
    for router in [health.router, state.router, risk.router, signals.router, execution.router, actions.router, ml.router, llm.router, paper.router, incidents.router, runtime.router]:
        app.include_router(router)

    frontend = Path(__file__).resolve().parent.parent / 'frontend'
    app.mount('/', StaticFiles(directory=str(frontend), html=True), name='frontend')
    return app


app = create_app()
