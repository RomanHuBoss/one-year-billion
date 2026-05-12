from pathlib import Path


def test_latest_symbol_status_view_matches_frontend_contract():
    sql = Path('migrations/0001_core_schema.sql').read_text(encoding='utf-8')
    view = sql.split('CREATE OR REPLACE VIEW latest_symbol_status AS', 1)[1]
    for token in [
        'status_effective',
        'AS severity',
        'AS allowed_actions',
        'AS updated_at',
        "'ERROR_RECONCILIATION_REQUIRED'",
        "'DISABLE_TRADING'",
        "'CANCEL_OPEN_ENTRIES'",
        "'FLATTEN_REDUCE'",
    ]:
        assert token in view
