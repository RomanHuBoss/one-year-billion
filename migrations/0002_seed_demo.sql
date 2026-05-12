BEGIN;

INSERT INTO instruments(symbol, category, status, tick_size, qty_step, min_qty, min_notional, max_leverage, specs_version, raw_payload_hash, fetched_at, expires_at)
VALUES
('BTCUSDT','linear','Trading',0.10,0.001,0.001,5,100,'demo-v1','demo-btc',now(),now()+interval '10 minutes'),
('ETHUSDT','linear','Trading',0.01,0.01,0.01,5,100,'demo-v1','demo-eth',now(),now()+interval '10 minutes'),
('SOLUSDT','linear','Trading',0.001,0.1,0.1,5,75,'demo-v1','demo-sol',now(),now()+interval '10 minutes')
ON CONFLICT DO NOTHING;

INSERT INTO account_snapshots(equity_usdt, available_balance_usdt, account_mode, permissions_json, raw_payload_hash, fetched_at, expires_at)
VALUES (500, 500, 'isolated_or_unified_checked_runtime', '{"trade": false, "read": true}', 'demo-account', now(), now()+interval '5 minutes');

INSERT INTO orderbook_snapshots(symbol, ts, bid1, ask1, spread_bps, depth_0_5pct, depth_1pct, imbalance, raw_topn_hash, expires_at)
VALUES
('BTCUSDT', now(), 100000, 100001, 0.10, 5000000, 9000000, 0, 'demo-ob-btc', now()+interval '20 seconds'),
('ETHUSDT', now(), 3000, 3000.5, 1.67, 2000000, 5000000, 0, 'demo-ob-eth', now()+interval '20 seconds'),
('SOLUSDT', now(), 150, 150.02, 1.33, 1000000, 2500000, 0, 'demo-ob-sol', now()+interval '20 seconds')
ON CONFLICT DO NOTHING;

COMMIT;
