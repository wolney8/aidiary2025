"""Small persistence boundary for chat reliability events and SLO reporting."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from services.database import connect_sqlite_path

logger = logging.getLogger(__name__)

CHAT_SLO_TARGETS = {
    'success_completion_rate': 0.98,
    'error_rate': 0.02,
    'p95_latency_ms': 15000,
    'rate_limit_events': 0,
}

TERMINAL_EVENTS = {
    'completed',
    'failed',
    'rate_limited',
    'token_budget_exceeded',
    'validation_failed',
    'storage_unavailable',
}


def _evaluate_slo(
    actual: int | float | None,
    target: int | float,
    *,
    direction: str,
) -> dict[str, Any]:
    if actual is None:
        return {
            'actual': None,
            'target': target,
            'status': 'no_data',
            'met': None,
        }
    if direction == 'gte':
        met = actual >= target
    elif direction == 'lte':
        met = actual <= target
    else:
        raise ValueError(f'Unsupported SLO direction: {direction}')
    return {
        'actual': actual,
        'target': target,
        'status': 'met' if met else 'breached',
        'met': met,
    }


def _build_slo_alerts(slo_status: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {
        'success_completion_rate': 'Chat success completion rate',
        'error_rate': 'Chat error rate',
        'p95_latency_ms': 'Chat p95 latency',
        'rate_limit_events': 'Chat rate-limit events',
    }
    severities = {
        'success_completion_rate': 'critical',
        'error_rate': 'critical',
        'p95_latency_ms': 'warning',
        'rate_limit_events': 'warning',
    }
    alerts: list[dict[str, Any]] = []
    for metric, status in slo_status.items():
        if status['status'] != 'breached':
            continue
        label = labels.get(metric, metric)
        alerts.append({
            'code': 'chat_slo_breached',
            'metric': metric,
            'severity': severities.get(metric, 'warning'),
            'message': f'{label} breached its configured target.',
            'actual': status['actual'],
            'target': status['target'],
        })
    return alerts


def _safe_json(value: dict[str, Any] | None) -> str:
    if not value:
        return '{}'
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * percentile), len(ordered) - 1)
    return ordered[index]


class ChatObservabilityService:
    """Record and report chat lifecycle signals without affecting user flows."""

    def __init__(self, database_path: str, *, log: logging.Logger | None = None) -> None:
        self.database_path = database_path
        self.log = log or logger

    def record_event(
        self,
        *,
        event_type: str,
        user_id: int | None = None,
        conversation_id: str | None = None,
        request_id: str | None = None,
        error_code: str | None = None,
        latency_ms: int | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = {
            'event_type': event_type,
            'user_id': user_id,
            'conversation_id': conversation_id,
            'request_id': request_id,
            'error_code': error_code,
            'latency_ms': latency_ms,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'model': model,
            'metadata': metadata or {},
        }
        self.log.info('chat_observability_event %s', _safe_json(event))
        try:
            with connect_sqlite_path(self.database_path, timeout=10) as conn:
                conn.execute(
                    """
                    INSERT INTO chat_observability_events (
                        user_id, conversation_id, request_id, event_type, error_code,
                        latency_ms, input_tokens, output_tokens, model, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        conversation_id,
                        request_id,
                        event_type,
                        error_code,
                        latency_ms,
                        input_tokens,
                        output_tokens,
                        model,
                        _safe_json(metadata),
                    ),
                )
        except sqlite3.Error:
            self.log.exception('Chat observability event could not be persisted')

    def build_report(self, *, user_id: int, days: int = 7) -> dict[str, Any]:
        bounded_days = min(max(int(days or 7), 1), 90)
        since = datetime.now(timezone.utc) - timedelta(days=bounded_days)
        with connect_sqlite_path(self.database_path, timeout=10) as conn:
            rows = conn.execute(
                """
                SELECT event_type, error_code, latency_ms, input_tokens, output_tokens,
                       model, created_at
                FROM chat_observability_events
                WHERE user_id = ?
                  AND created_at >= ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id, since.strftime('%Y-%m-%d %H:%M:%S')),
            ).fetchall()

        event_counts = Counter(str(row['event_type']) for row in rows)
        error_counts = Counter(
            str(row['error_code'] or 'unknown')
            for row in rows
            if row['event_type'] in TERMINAL_EVENTS and row['error_code']
        )
        terminal_count = sum(event_counts[event_type] for event_type in TERMINAL_EVENTS)
        completed_count = event_counts['completed']
        failed_count = terminal_count - completed_count
        latencies = [
            int(row['latency_ms'])
            for row in rows
            if row['event_type'] == 'completed' and row['latency_ms'] is not None
        ]
        input_tokens = sum(int(row['input_tokens'] or 0) for row in rows)
        output_tokens = sum(int(row['output_tokens'] or 0) for row in rows)
        success_rate = completed_count / terminal_count if terminal_count else None
        error_rate = failed_count / terminal_count if terminal_count else None
        average_latency_ms = (
            round(sum(latencies) / len(latencies)) if latencies else None
        )
        p95_latency_ms = _percentile(latencies, 0.95)
        rate_limit_events = event_counts['rate_limited']
        slo_status = {
            'success_completion_rate': _evaluate_slo(
                success_rate,
                CHAT_SLO_TARGETS['success_completion_rate'],
                direction='gte',
            ),
            'error_rate': _evaluate_slo(
                error_rate,
                CHAT_SLO_TARGETS['error_rate'],
                direction='lte',
            ),
            'p95_latency_ms': _evaluate_slo(
                p95_latency_ms,
                CHAT_SLO_TARGETS['p95_latency_ms'],
                direction='lte',
            ),
            'rate_limit_events': _evaluate_slo(
                rate_limit_events,
                CHAT_SLO_TARGETS['rate_limit_events'],
                direction='lte',
            ),
        }
        breached_slos = [
            name
            for name, status in slo_status.items()
            if status['status'] == 'breached'
        ]
        missing_slos = [
            name
            for name, status in slo_status.items()
            if status['status'] == 'no_data'
        ]

        return {
            'period_days': bounded_days,
            'slo_targets': CHAT_SLO_TARGETS,
            'slo_status': slo_status,
            'slo_summary': {
                'status': 'breached'
                if breached_slos
                else 'no_data'
                if missing_slos and len(missing_slos) == len(slo_status)
                else 'met',
                'breached': breached_slos,
                'no_data': missing_slos,
            },
            'slo_alerts': _build_slo_alerts(slo_status),
            'event_counts': dict(event_counts),
            'error_counts': dict(error_counts),
            'terminal_events': terminal_count,
            'completed_events': completed_count,
            'failed_events': failed_count,
            'success_completion_rate': success_rate,
            'error_rate': error_rate,
            'average_latency_ms': average_latency_ms,
            'p95_latency_ms': p95_latency_ms,
            'token_usage': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
            },
        }
