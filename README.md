# rba-audit-service

Async consumer of `rba.decision.made.v1`. Persists the **full**
`DecisionMadeEvent` payload in Postgres `rba_audit` for later admin /
thesis write-up / replay. **Idempotent on `event_id`.**

**IdP-6:** also exposes a thin HTTP read API (`GET /decisions`) so the IdP
admin BFF can browse scores, actions, and reasons without sharing tables.
Consumer loop is unchanged.

Does not touch Redis or the decision DB. Package version: **0.1.0**.
CLIs: `rba-audit-service` (consumer), `rba-audit-api` (HTTP on :8002).

> Status: [`../docs/plans/status.md`](../docs/plans/status.md).
> ADR-0011, ADR-0017. AI: [`AGENTS.md`](AGENTS.md).

## What it does

```
RabbitMQ  rba.events / rba.decision.made.v1
    queue rba.audit.decision-made.v1
        → skip if event_id already in audit_decisions
        → INSERT row (denormalised fields + full JSON payload)
        → ACK

HTTP  GET /decisions?user_id=&application_id=&action=&limit=
      GET /decisions/{event_id}
        → DecisionListResponse / DecisionRecord (reasons from payload)
```

Handler failures **nack without requeue** (no DLQ yet). Prefetch = 1.

## Layout

```
src/rba_audit_service/
├── main.py      # pika consumer loop
├── api.py       # FastAPI decision read API
├── config.py
└── db.py        # audit_decisions
tests/test_api.py
```

### Postgres table (DB `rba_audit`)

Created on startup:

- `audit_decisions` — PK `event_id`; `occurred_at`, `application_id`,
  `user_id`, `risk_score`, `risk_level`, `action`, versions, `fallback`,
  `payload` (full event JSON)

## Setup

```bash
cd ../rba-infra && docker compose up -d && cd -

python3 -m venv .venv && source .venv/bin/activate
pip install -e ../rba-contracts -e ".[dev]"

# consumer (async plane)
rba-audit-service

# HTTP for the IdP-6 decision browser (separate process)
rba-audit-api
# or: uvicorn rba_audit_service.api:app --port 8002
```

`ONCE=true` on the consumer processes one message then exits.

## Env

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://rba:rba@localhost:5432/rba_audit` |
| `RABBITMQ_URL` | `amqp://rba:rba@localhost:5672/` |
| `EXCHANGE_NAME` | `rba.events` |
| `QUEUE_NAME` | `rba.audit.decision-made.v1` |
| `ROUTING_KEY` | `rba.decision.made.v1` |
| `ONCE` | `false` |
| `HOST` / `PORT` | `0.0.0.0` / `8002` (HTTP only) |

## Guardrails

- Idempotent on `event_id`. Owns `rba_audit` only.
- Do not call Redis or the decision DB from here.

## Status

Phase 4 consumer + IdP-6 HTTP read. Remaining: DLQ, metrics, k8s Deployment.
Roadmap: `../docs/plans/status.md`.
