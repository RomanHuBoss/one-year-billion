from __future__ import annotations
from app.core.settings import Settings

UNSAFE_KEYS = {'', 'change-me-long-random-key', 'change-me-readonly-key', 'changeme', 'password'}


def validate_startup_security(settings: Settings, runtime_config) -> None:
    """Fail-closed проверки перед созданием FastAPI-приложения.

    Локальный read-only dashboard можно открыть без ключа, но любые live-флаги требуют
    явных секретов, подтверждения оператора и отсутствия небезопасных defaults.
    """

    reasons: list[str] = []
    if settings.operator_api_key == settings.readonly_api_key:
        reasons.append('operator_and_readonly_keys_must_differ')
    if settings.app_env != 'local' and settings.readonly_api_key in UNSAFE_KEYS:
        reasons.append('readonly_api_key_must_be_set_for_nonlocal_env')
    live_requested = settings.live_requested
    if live_requested:
        if settings.operator_api_key in UNSAFE_KEYS or len(settings.operator_api_key) < 24:
            reasons.append('operator_api_key_unsafe_for_live')
        if not settings.bybit_api_key or not settings.bybit_api_secret:
            reasons.append('bybit_credentials_required_for_live')
        if not settings.bybit_live_confirm:
            reasons.append('bybit_live_confirm_required')
        if settings.trading_enabled and not settings.enable_live_submit:
            reasons.append('trading_enabled_requires_cas_enable_live_submit')
        if settings.enable_live_submit and settings.require_go_nogo_for_live:
            if not settings.live_go_nogo_passed or not settings.live_approved_by:
                reasons.append('go_no_go_pass_and_approver_required_for_live_submit')
        if settings.allow_demo_ml:
            reasons.append('demo_ml_override_forbidden_for_live')
        if settings.demo_mode:
            reasons.append('demo_mode_forbidden_for_live')
        if settings.bybit_testnet is False and not settings.trading_enabled:
            reasons.append('prod_bybit_endpoint_requires_trading_enabled_explicit_policy')
        if runtime_config.phase < 0:
            reasons.append('invalid_runtime_phase')
    if settings.trading_enabled and not settings.can_live_trade:
        reasons.append('trading_enabled_without_live_submit_gate_or_confirmed_credentials')
    if reasons:
        raise RuntimeError('unsafe_startup_security:' + ';'.join(sorted(set(reasons))))
