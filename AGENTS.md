# AGENTS.md — rba-audit-service

Async audit store for decision events, plus a thin HTTP read API for the
IdP-6 decision browser. Status: `../docs/plans/status.md`. ADR-0011, ADR-0017.

## Guardrails

- Idempotent on `event_id`. Owns `rba_audit` only.
- Do not call Redis or decision DB from here.
- HTTP is read-only (`GET /decisions`). Do not write audit rows from the API.
