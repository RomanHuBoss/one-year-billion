#!/usr/bin/env python
from __future__ import annotations
import compileall
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.runtime import build_runtime_config
from app.config.phase_validator import startup_phase_validation


def run_pytest() -> None:
    cmd = [sys.executable, '-m', 'pytest', '-q']
    print('$', ' '.join(cmd), flush=True)
    subprocess.run(cmd, check=True, timeout=180)
    print('OK command:', ' '.join(cmd), flush=True)


def run_check(name: str, func) -> None:
    print('$', name, flush=True)
    code = func()
    if code:
        raise SystemExit(code)
    print('OK command:', name, flush=True)


def run_compileall() -> None:
    targets = ['main.py', 'app', 'scripts', 'tests', 'universe']
    print('$ compileall -q ' + ' '.join(targets), flush=True)
    ok = True
    for target in targets:
        path = Path(target)
        if path.is_dir():
            ok = compileall.compile_dir(str(path), quiet=1, force=True) and ok
        else:
            ok = compileall.compile_file(str(path), quiet=1, force=True) and ok
    if not ok:
        raise SystemExit(2)
    print('OK command: compileall', flush=True)


def main() -> int:
    runtime = build_runtime_config()
    phase_reasons = startup_phase_validation(runtime.raw)
    if phase_reasons:
        print('unsafe_phase_config:', ';'.join(phase_reasons), file=sys.stderr)
        return 2
    print('config_hash=', runtime.config_hash, flush=True)
    run_compileall()
    run_pytest()
    from scripts.check_strategy_imports import main as strategy_imports_main
    from scripts.check_architecture import main as architecture_main
    from scripts.check_migrations_static import main as migrations_main
    from scripts.secret_scan import main as secret_scan_main
    run_check('scripts/check_strategy_imports.py', strategy_imports_main)
    run_check('scripts/check_architecture.py', architecture_main)
    run_check('scripts/check_migrations_static.py', migrations_main)
    run_check('scripts/secret_scan.py', secret_scan_main)
    return 0


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
