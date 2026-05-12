from __future__ import annotations
from dataclasses import dataclass, field
import os


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class Settings:
    """Runtime-настройки.

    Важно: значения читаются при создании Settings(), а не при импорте модуля.
    Это исключает ситуацию, когда тесты/оператор меняют env, но приложение
    продолжает использовать старые defaults.
    """

    app_name: str = field(default_factory=lambda: os.getenv('APP_NAME', 'Crypto Acceleration System 2026'))
    app_env: str = field(default_factory=lambda: os.getenv('APP_ENV', 'local'))
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/cas2026'))
    operator_api_key: str = field(default_factory=lambda: os.getenv('OPERATOR_API_KEY', 'change-me-long-random-key'))
    readonly_api_key: str = field(default_factory=lambda: os.getenv('READONLY_API_KEY', 'change-me-readonly-key'))
    trading_enabled: bool = field(default_factory=lambda: _bool_env('TRADING_ENABLED', False))
    bybit_testnet: bool = field(default_factory=lambda: _bool_env('BYBIT_TESTNET', True))
    bybit_live_confirm: bool = field(default_factory=lambda: _bool_env('BYBIT_LIVE_CONFIRM', False))
    bybit_api_key: str = field(default_factory=lambda: os.getenv('BYBIT_API_KEY', ''))
    bybit_api_secret: str = field(default_factory=lambda: os.getenv('BYBIT_API_SECRET', ''))
    ollama_base_url: str = field(default_factory=lambda: os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434'))
    ollama_model: str = field(default_factory=lambda: os.getenv('OLLAMA_MODEL', 'llama3.1'))
    demo_mode: bool = field(default_factory=lambda: _bool_env('CAS_DEMO_MODE', False))
    allow_demo_ml: bool = field(default_factory=lambda: _bool_env('CAS_ALLOW_DEMO_ML', False))

    # Live-ready gates. Они намеренно требуют явного включения оператором.
    enable_live_submit: bool = field(default_factory=lambda: _bool_env('CAS_ENABLE_LIVE_SUBMIT', False))
    require_db_for_live: bool = field(default_factory=lambda: _bool_env('CAS_REQUIRE_DB_FOR_LIVE', True))
    require_live_preflight: bool = field(default_factory=lambda: _bool_env('CAS_REQUIRE_LIVE_PREFLIGHT', True))
    require_go_nogo_for_live: bool = field(default_factory=lambda: _bool_env('CAS_REQUIRE_GO_NOGO_FOR_LIVE', True))
    live_go_nogo_passed: bool = field(default_factory=lambda: _bool_env('CAS_GO_NOGO_PASS', False))
    live_approved_by: str = field(default_factory=lambda: os.getenv('CAS_LIVE_APPROVED_BY', ''))
    min_paper_days_required: int = field(default_factory=lambda: int(os.getenv('CAS_MIN_PAPER_DAYS', '14')))

    @property
    def live_requested(self) -> bool:
        return bool(self.trading_enabled or self.enable_live_submit or self.bybit_live_confirm or not self.bybit_testnet)

    @property
    def can_live_trade(self) -> bool:
        # Этот флаг означает только техническую возможность отправки submit.
        # Финальное разрешение live проверяет LiveGate: DB + preflight + Go/No-Go.
        return bool(self.trading_enabled and self.bybit_live_confirm and self.bybit_api_key and self.bybit_api_secret and self.enable_live_submit)
