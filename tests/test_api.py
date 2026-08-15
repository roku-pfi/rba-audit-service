"""HTTP decision read API (IdP-6). No RabbitMQ required."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from rba_contracts import Action, DecisionMadeEvent, RiskLevel

from rba_audit_service.api import create_app
from rba_audit_service.config import Settings
from rba_audit_service.db import AuditDecision


EVENT_ID = UUID("4f9a8c2e-1b3d-4a6f-9c8e-2d1b3a6f9c8e")


def _client() -> TestClient:
    return TestClient(create_app(Settings(use_memory_db=True)))


def _insert(client: TestClient, **overrides) -> UUID:
    event_id = overrides.pop("event_id", uuid4())
    occurred = overrides.pop("occurred_at", datetime.now(timezone.utc))
    action = overrides.pop("action", Action.REQUIRE_MFA)
    event = DecisionMadeEvent(
        event_id=event_id,
        occurred_at=occurred,
        application_id=overrides.pop("application_id", "demo-banking-app"),
        user_id=overrides.pop("user_id", "usr_demo"),
        risk_score=overrides.pop("risk_score", 0.61),
        risk_level=overrides.pop("risk_level", RiskLevel.MEDIUM),
        action=action,
        model_version="freeman-0.1.0",
        policy_version="1.0.0",
        feature_schema_version="1.0.0",
        fallback=False,
        reasons=overrides.pop("reasons", []),
    )
    with client.app.state.session_factory() as session:
        session.add(
            AuditDecision(
                event_id=event.event_id,
                occurred_at=event.occurred_at,
                application_id=event.application_id,
                user_id=event.user_id,
                risk_score=event.risk_score,
                risk_level=event.risk_level.value,
                action=event.action.value,
                model_version=event.model_version,
                policy_version=event.policy_version,
                feature_schema_version=event.feature_schema_version,
                fallback=event.fallback,
                payload=event.model_dump(mode="json"),
            )
        )
        session.commit()
    return event_id


def test_healthz() -> None:
    with _client() as client:
        assert client.get("/healthz").json() == {"status": "ok"}


def test_list_and_get_decision_includes_reasons() -> None:
    from rba_contracts import Reason

    with _client() as client:
        _insert(
            client,
            event_id=EVENT_ID,
            reasons=[
                Reason(
                    code="signal_novel",
                    signal="device_type",
                    contribution=1.8,
                    detail="device_type not previously seen for this user",
                )
            ],
        )
        listed = client.get("/decisions")
        assert listed.status_code == 200
        body = listed.json()
        assert body["count"] == 1
        item = body["items"][0]
        assert item["event_id"] == str(EVENT_ID)
        assert item["action"] == "REQUIRE_MFA"
        assert item["reasons"][0]["signal"] == "device_type"

        got = client.get(f"/decisions/{EVENT_ID}")
        assert got.status_code == 200
        assert got.json()["user_id"] == "usr_demo"


def test_list_filters_and_unknown_event() -> None:
    with _client() as client:
        _insert(client, user_id="usr_a", action=Action.ALLOW)
        _insert(client, user_id="usr_b", action=Action.BLOCK)
        only_a = client.get("/decisions", params={"user_id": "usr_a"})
        assert only_a.json()["count"] == 1
        assert only_a.json()["items"][0]["user_id"] == "usr_a"
        blocked = client.get("/decisions", params={"action": "BLOCK"})
        assert blocked.json()["count"] == 1
        missing = client.get("/decisions/00000000-0000-0000-0000-000000000001")
        assert missing.status_code == 404
