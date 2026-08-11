# rba-audit-service

Consumes `rba.decision.made.v1` and persists the full payload in `rba_audit`
(idempotent on `event_id`).

```bash
cd ../rba-infra && docker compose up -d && cd -
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../rba-contracts -e ".[dev]"
rba-audit-service
```
