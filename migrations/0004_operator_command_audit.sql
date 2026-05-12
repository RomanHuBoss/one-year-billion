BEGIN;

-- Операторский экран может запускать только allowlisted backend-команды.
-- Они не являются торговыми действиями и не увеличивают риск, но должны
-- попадать в audit trail так же строго, как manual safe-actions.
ALTER TABLE manual_request_log
    DROP CONSTRAINT IF EXISTS manual_reduce_only;
ALTER TABLE manual_request_log
    ADD CONSTRAINT manual_reduce_only CHECK (
        action IN (
            'DISABLE_TRADING',
            'CANCEL_OPEN_ENTRIES',
            'FLATTEN_REDUCE',
            'RESOLVE_INCIDENT',
            'PROPOSE_CONFIG',
            'ACTIVATE_CONFIG',
            'RUN_OPERATOR_COMMAND',
            'REJECTED_UNSAFE_ACTION'
        )
    );

COMMIT;
