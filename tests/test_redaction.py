from app.security.redaction import redact


def test_redaction_masks_common_bybit_secret_keys_case_insensitively():
    payload = {
        'apiSecret': 'secret-value',
        'BYBIT_API_KEY': 'key-value',
        'nested': {'X-BAPI-SIGN': 'signature', 'safe': 'visible'},
    }
    redacted = redact(payload)
    assert redacted['apiSecret'] == '***REDACTED***'
    assert redacted['BYBIT_API_KEY'] == '***REDACTED***'
    assert redacted['nested']['X-BAPI-SIGN'] == '***REDACTED***'
    assert redacted['nested']['safe'] == 'visible'
