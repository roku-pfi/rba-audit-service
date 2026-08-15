# rba-audit-service

Async consumer of `rba.decision.made.v1`. Persists the **full**
`DecisionMadeEvent` payload in Postgres `rba_audit` for later admin /
thesis write-up / replay. **Idempotent on `event_id`.**

Does not touch Redis or the decision DB. Package version: **0.1.0**.
CLI: `rba-audit-service`.

> Status: [`../docs/plans/status.md`](../docs/plans/status.md).
> ADR-0011. AI: [`AGENTS.md`](AGENTS.md).

## What it does

```
RabbitMQ  rba.events / rba.decision.made.v1
    queue rba.audit.decision-made.v1
        → skip if event_id already in audit_decisions
        → INSERT row (denormalised fields + full JSON payload)
        → ACK
```

Handler failures **nack without requeue** (no DLQ yet). Prefetch = 1.

`tests/` exists but has no cases yet (thin slice).

## Layout

```
src/rba_audit_service/
├── main.py      # pika consumer loop
├── config.py
└── db.py        # audit_decisions
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
rba-audit-service
```

`ONCE=true` processes one message then exits.

## Env

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://rba:rba@localhost:5432/rba_audit` |
| `RABBITMQ_URL` | `amqp://rba:rba@localhost:5672/` |
| `EXCHANGE_NAME` | `rba.events` |
| `QUEUE_NAME` | `rba.audit.decision-made.v1` |
| `ROUTING_KEY` | `rba.decision.made.v1` |
| `ONCE` | `false` |

## Guardrails

- Idempotent on `event_id`. Owns `rba_audit` only.
- Do not call Redis or the decision DB from here.

## Status

Phase 4 thin slice. Remaining: DLQ, metrics, k8s Deployment. Admin will read
this store at IdP-6. Roadmap: `../docs/plans/status.md`.
