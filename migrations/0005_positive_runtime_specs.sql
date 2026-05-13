BEGIN;

-- Runtime specs участвуют в sizing/risk. Нулевые min_qty/min_notional/max_leverage
-- нельзя хранить даже как fallback: risk approval должен получить реальные
-- положительные значения Bybit V5 или fail-closed заблокировать торговлю.
ALTER TABLE instruments
    DROP CONSTRAINT IF EXISTS instruments_positive_specs;
ALTER TABLE instruments
    ADD CONSTRAINT instruments_positive_specs CHECK (
        tick_size > 0
        AND qty_step > 0
        AND min_qty > 0
        AND min_notional > 0
        AND max_leverage > 0
    );

COMMIT;
