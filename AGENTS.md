# AGENTS.md — rba-audit-service

Async audit store for decision events. Status: `../docs/plans/status.md`.

## Guardrails

- Idempotent on `event_id`. Owns `rba_audit` only.
- Do not call Redis or decision DB from here.
