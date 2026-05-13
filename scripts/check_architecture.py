#!/usr/bin/env python3
from __future__ import annotations
import ast
from pathlib import Path

REQUIRED_DIRS = [
    'app/market_data', 'app/regime', 'app/strategies', 'app/ml', 'app/risk_engine',
    'app/execution', 'app/reconciliation', 'app/api', 'frontend', 'migrations', 'docs',
]
STRATEGY_FORBIDDEN = ('app.execution', 'app.reconciliation', 'bybit_adapter', 'order_router', 'exchange_client')
FRONTEND_FORBIDDEN = ('BYBIT_API_KEY', 'BYBIT_API_SECRET', 'api.bybit.com', 'api-testnet.bybit.com', '/v5/order', '/v5/market')
FRONTEND_LOCAL_STATUS_DERIVATION = (
    'row.risk?.approved',
    'row.risk.approved',
    "? 'risk_approved'",
    '? "risk_approved"',
)
TARGET_FORBIDDEN_PATHS = [Path('app/risk_engine'), Path('app/execution')]
TARGET_FORBIDDEN_TOKENS = ('target_equity_usdt', 'target_equity', '2000x')


def _py_modules() -> dict[str, Path]:
    return {'.'.join(p.with_suffix('').parts): p for p in Path('app').rglob('*.py')}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def _detect_app_cycles() -> list[list[str]]:
    modules = _py_modules()
    adj = {name: set() for name in modules}
    for name, path in modules.items():
        for dep in _imports(path):
            if not dep.startswith('app.'):
                continue
            if dep in modules:
                adj[name].add(dep)
                continue
            parts = dep.split('.')
            for i in range(len(parts), 1, -1):
                prefix = '.'.join(parts[:i])
                if prefix in modules:
                    adj[name].add(prefix)
                    break
    visiting: dict[str, int] = {}
    stack: list[str] = []
    cycles: list[list[str]] = []

    def dfs(node: str) -> None:
        visiting[node] = 1
        stack.append(node)
        for dep in adj[node]:
            if visiting.get(dep) == 1:
                cycles.append(stack[stack.index(dep):] + [dep])
            elif visiting.get(dep) != 2:
                dfs(dep)
        stack.pop()
        visiting[node] = 2

    for module in modules:
        if visiting.get(module) != 2:
            dfs(module)
    return cycles


def main() -> int:
    failures: list[str] = []
    for dirname in REQUIRED_DIRS:
        if not Path(dirname).is_dir():
            failures.append(f'missing_required_layer:{dirname}')

    for path in Path('app/strategies').glob('*.py'):
        imports = _imports(path)
        for item in imports:
            if any(token in item for token in STRATEGY_FORBIDDEN):
                failures.append(f'strategy_direct_execution_import:{path}:{item}')

    for root in TARGET_FORBIDDEN_PATHS:
        for path in root.rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            for token in TARGET_FORBIDDEN_TOKENS:
                if token in text:
                    failures.append(f'target_equity_in_safety_layer:{path}:{token}')

    for path in list(Path('frontend').rglob('*.js')) + list(Path('frontend').rglob('*.html')):
        text = path.read_text(encoding='utf-8', errors='ignore')
        for token in FRONTEND_FORBIDDEN:
            if token in text:
                failures.append(f'frontend_forbidden_secret_or_bybit_call:{path}:{token}')
        for token in FRONTEND_LOCAL_STATUS_DERIVATION:
            if token in text:
                failures.append(f'frontend_local_status_derivation:{path}:{token}')

    cycles = _detect_app_cycles()
    if cycles:
        failures.extend('cyclic_app_dependency:' + ' -> '.join(cycle) for cycle in cycles[:10])

    if failures:
        print('FAIL:', ';'.join(failures))
        return 2
    print('OK: architecture invariants present')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
