from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Callable
import json
import os
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class OperatorCommandSpec:
    command_id: str
    title: str
    description: str
    safety: str
    timeout_sec: int
    args_factory: Callable[[dict[str, Any]], list[str]]


@dataclass
class OperatorJob:
    job_id: str
    command_id: str
    title: str
    actor: str
    reason: str
    options: dict[str, Any]
    status: str = 'queued'
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    stdout: str = ''
    stderr: str = ''
    command_display: str = ''
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            'job_id': self.job_id,
            'command_id': self.command_id,
            'title': self.title,
            'actor': self.actor,
            'reason': self.reason,
            'options': self.options,
            'status': self.status,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'exit_code': self.exit_code,
            'stdout': self.stdout,
            'stderr': self.stderr,
            'command_display': self.command_display,
            'error': self.error,
        }


class OperatorJobRunner:
    """Allowlist runner для операторского экрана.

    Браузер не получает произвольный терминал. Он может запустить только
    заранее разрешенные Python-команды backend. Это сохраняет auditability,
    idempotency and fail-closed safety: ни одна команда не включает live-submit
    и не обходит risk engine.
    """

    def __init__(self, secrets: list[str] | None = None):
        self._lock = Lock()
        self._jobs: dict[str, OperatorJob] = {}
        self._last_by_command: dict[str, str] = {}
        self._secrets = [s for s in (secrets or []) if s and len(s) >= 6]
        self._commands: dict[str, OperatorCommandSpec] = {
            'validate': OperatorCommandSpec(
                command_id='validate',
                title='Локальная проверка проекта',
                description='Запускает compileall, pytest, architecture checks, migration checks и secret scan.',
                safety='Проверка кода. Live-ордера не отправляются.',
                timeout_sec=180,
                args_factory=lambda _options: [sys.executable, 'main.py', 'validate'],
            ),
            'preflight_testnet': OperatorCommandSpec(
                command_id='preflight_testnet',
                title='Testnet preflight',
                description='Проверяет testnet/runtime gates без реальных денег и без отправки ордеров.',
                safety='Безопасная проверка. Ордеров нет.',
                timeout_sec=90,
                args_factory=lambda _options: [sys.executable, 'main.py', 'preflight', '--mode', 'testnet'],
            ),
            'bootstrap_db': OperatorCommandSpec(
                command_id='bootstrap_db',
                title='PostgreSQL: применить migrations',
                description='Python-замена ./scripts/bootstrap_db.sh: применяет SQL migrations через psycopg без shell/psql.',
                safety='Меняет только структуру/служебные таблицы PostgreSQL. Live не включает.',
                timeout_sec=120,
                args_factory=lambda options: [sys.executable, 'scripts/bootstrap_db.py'] + (['--seed-demo'] if options.get('seed_demo') is True else []),
            ),
            'preflight_live': OperatorCommandSpec(
                command_id='preflight_live',
                title='Live preflight',
                description='Проверяет live gates. До PASS обязан вернуть blocked.',
                safety='Проверка допуска. Live-submit не запускается.',
                timeout_sec=90,
                args_factory=lambda _options: [sys.executable, 'main.py', 'preflight', '--mode', 'live'],
            ),
        }

    def list_commands(self) -> list[dict[str, Any]]:
        return [
            {
                'command_id': spec.command_id,
                'title': spec.title,
                'description': spec.description,
                'safety': spec.safety,
                'timeout_sec': spec.timeout_sec,
                'last_job_id': self._last_by_command.get(spec.command_id),
            }
            for spec in self._commands.values()
        ]

    def list_jobs(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._jobs.values())[-limit:]
            return [job.as_dict() for job in reversed(items)]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.as_dict() if job else None

    def start(self, command_id: str, actor: str, reason: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        options = options or {}
        if command_id not in self._commands:
            raise KeyError('operator_command_not_allowed')
        if not reason.strip():
            raise ValueError('reason_required')
        spec = self._commands[command_id]
        job = OperatorJob(
            job_id=f'opjob_{uuid.uuid4().hex[:16]}',
            command_id=command_id,
            title=spec.title,
            actor=actor,
            reason=reason.strip(),
            options=self._safe_options(options),
            command_display=' '.join(self._display_args(spec.args_factory(options))),
        )
        with self._lock:
            self._jobs[job.job_id] = job
            self._last_by_command[command_id] = job.job_id
        thread = Thread(target=self._run_job, args=(job.job_id,), daemon=True)
        thread.start()
        return job.as_dict()

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            spec = self._commands[job.command_id]
            job.status = 'running'
            job.started_at = _utc_now()
        args = spec.args_factory(job.options)
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        try:
            completed = subprocess.run(
                args,
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=spec.timeout_sec,
                shell=False,
            )
            stdout = self._redact(completed.stdout)[-12000:]
            stderr = self._redact(completed.stderr)[-12000:]
            status = self._derive_status(completed.returncode, stdout, stderr)
            with self._lock:
                job = self._jobs[job_id]
                job.status = status
                job.exit_code = completed.returncode
                job.stdout = stdout
                job.stderr = stderr
                job.finished_at = _utc_now()
        except subprocess.TimeoutExpired as exc:
            with self._lock:
                job = self._jobs[job_id]
                job.status = 'timeout'
                job.exit_code = 124
                job.stdout = self._redact((exc.stdout or '') if isinstance(exc.stdout, str) else '')[-12000:]
                job.stderr = self._redact((exc.stderr or '') if isinstance(exc.stderr, str) else '')[-12000:]
                job.error = f'timeout_after_{spec.timeout_sec}_sec'
                job.finished_at = _utc_now()
        except Exception as exc:  # pragma: no cover - защитная ветка.
            with self._lock:
                job = self._jobs[job_id]
                job.status = 'error'
                job.exit_code = 1
                job.error = self._redact(f'{type(exc).__name__}:{exc}')
                job.finished_at = _utc_now()


    def _derive_status(self, returncode: int, stdout: str, stderr: str) -> str:
        """Переводит результат CLI в понятный операторский статус.

        Некоторые проверки специально печатают JSON со status=blocked. Даже если
        wrapper вернул 0, оператор не должен видеть зеленый OK. Traceback/pytest
        failures также не должны маскироваться как успешная команда.
        """

        combined = f'{stdout}\n{stderr}'
        if 'Traceback (most recent call last):' in combined or 'FAILURES' in combined or 'FAILED ' in combined:
            return 'error'
        parsed = self._extract_last_json(stdout)
        if isinstance(parsed, dict) and str(parsed.get('status', '')).lower() == 'blocked':
            return 'blocked'
        if returncode == 0:
            return 'ok'
        return 'blocked'

    def _extract_last_json(self, text: str) -> dict[str, Any] | None:
        text = (text or '').strip()
        if not text:
            return None
        # CLI может печатать служебные строки перед JSON. Берем последний объект.
        for idx in range(len(text) - 1, -1, -1):
            if text[idx] != '{':
                continue
            try:
                value = json.loads(text[idx:])
            except json.JSONDecodeError:
                continue
            return value if isinstance(value, dict) else None
        return None

    def _redact(self, text: str) -> str:
        out = text or ''
        for secret in self._secrets:
            out = out.replace(secret, '***REDACTED***')
        out = re.sub(r'(postgres(?:ql)?://[^:/\s]+:)([^@\s]+)(@)', r'\1***REDACTED***\3', out, flags=re.I)
        out = re.sub(r'(BYBIT_API_SECRET\s*=\s*)[^\n]+', r'\1***REDACTED***', out)
        out = re.sub(r'(BYBIT_API_KEY\s*=\s*)[^\n]+', r'\1***REDACTED***', out)
        out = re.sub(r'(OPERATOR_API_KEY\s*=\s*)[^\n]+', r'\1***REDACTED***', out)
        return out

    def _display_args(self, args: list[str]) -> list[str]:
        display: list[str] = []
        for item in args:
            if item == sys.executable:
                display.append('python')
            else:
                display.append(item)
        return display

    def _safe_options(self, options: dict[str, Any]) -> dict[str, Any]:
        allowed = {'seed_demo'}
        return {k: v for k, v in options.items() if k in allowed}
