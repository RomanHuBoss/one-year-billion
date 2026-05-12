#!/usr/bin/env python
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config.runtime import build_runtime_config
from app.config.phase_validator import startup_phase_validation


def run(cmd: list[str]) -> None:
    print('$', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def main() -> int:
    runtime = build_runtime_config()
    phase_reasons = startup_phase_validation(runtime.raw)
    if phase_reasons:
        print('unsafe_phase_config:', ';'.join(phase_reasons), file=sys.stderr)
        return 2
    print('config_hash=', runtime.config_hash)
    run([sys.executable, '-m', 'compileall', '-q', 'app', 'scripts', 'tests', 'universe'])
    run([sys.executable, '-m', 'pytest', '-q'])
    run([sys.executable, 'scripts/check_strategy_imports.py'])
    run([sys.executable, 'scripts/check_migrations_static.py'])
    run([sys.executable, 'scripts/secret_scan.py'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
