from __future__ import annotations


def build_go_no_go_report(checks: dict[str, bool], unresolved_incidents: list[dict]) -> dict:
    critical_open = [i for i in unresolved_incidents if i.get('severity') in {'CRITICAL','HIGH'} and i.get('status','OPEN') == 'OPEN']
    pass_all = all(checks.values()) and not critical_open
    return {
        'result': 'PASS' if pass_all else 'FAIL',
        'checks': checks,
        'unresolved_critical_high': critical_open,
        'live_allowed': pass_all,
    }
