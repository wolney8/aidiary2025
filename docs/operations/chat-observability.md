# Chat Observability And SLOs

## Purpose

Chat reliability should be reviewable from persisted lifecycle events, not only from
ad hoc server logs. The local implementation stores chat observability events in
`chat_observability_events`; a cloud deployment can move the same event contract to
managed logs or metrics without changing chat route behavior.

## Event Taxonomy

- `request_started`: authenticated request accepted for processing.
- `completed`: assistant stream completed, including replayed idempotent responses.
- `failed`: provider or stream failure after processing began.
- `validation_failed`: malformed request, invalid message, or idempotency conflict.
- `token_budget_exceeded`: user daily token budget rejected the request.
- `rate_limited`: request rejected by the chat rate limiter.
- `storage_unavailable`: chat storage table missing or unavailable.

Each event may include `user_id`, `conversation_id`, `request_id`, `error_code`,
`latency_ms`, input/output token estimates, model, and bounded JSON metadata.

## Initial SLO Targets

- Success completion rate: `>= 98%` of terminal chat events.
- Error rate: `<= 2%` of terminal chat events.
- p95 completed-request latency: `<= 15 seconds`.
- Rate-limit events: target `0` during ordinary local usage; spikes should trigger review
  of limits, UI copy, or misuse.

## Weekly Review

Use `GET /api/chat/observability/report?days=7` with an authenticated token to review:

- event counts by lifecycle state
- error counts by `error_code`
- success completion rate
- error rate
- average and p95 latency
- input, output, and total token estimates
- `slo_status`, with each target marked `met`, `breached`, or `no_data`
- `slo_summary`, with the overall status and any breached target names
- `slo_alerts`, with machine-readable alert objects for any breached SLO

This endpoint is intentionally read-only and user-scoped. If an admin-wide dashboard is
needed later, add an admin-only reporting route rather than widening the current endpoint.
