from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.types import JSON, Uuid

from rba_contracts import Action, DecisionMadeEvent, DecisionRecord, EngineMode, Reason, RiskLevel
from rba_contracts.events import LoginEventSnapshot
from rba_contracts.features import FeatureVectorV1


class Base(DeclarativeBase):
    pass


class AuditDecision(Base):
    __tablename__ = "audit_decisions"

    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # ADR-0033: every read is scoped to one tenant.
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    application_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    # The engine's verdict and what was applied (ADR-0034).
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    enforced_action: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def row_from_event(event: DecisionMadeEvent) -> AuditDecision:
    """The audit row for one bus event; the full payload is kept alongside."""
    return AuditDecision(
        event_id=event.event_id,
        occurred_at=event.occurred_at,
        tenant_id=event.tenant_id,
        application_id=event.application_id,
        user_id=event.user_id,
        risk_score=event.risk_score,
        risk_level=event.risk_level.value,
        action=event.action.value,
        enforced_action=event.enforced_action.value,
        engine_mode=event.engine_mode.value,
        simulated=event.simulated,
        model_version=event.model_version,
        policy_version=event.policy_version,
        feature_schema_version=event.feature_schema_version,
        fallback=event.fallback,
        payload=event.model_dump(mode="json"),
    )


def already_stored(session: Session, event_id: UUID) -> bool:
    return session.get(AuditDecision, event_id) is not None


def row_to_record(row: AuditDecision) -> DecisionRecord:
    payload = row.payload or {}
    raw_reasons = payload.get("reasons") or []
    return DecisionRecord(
        event_id=row.event_id,
        occurred_at=row.occurred_at,
        tenant_id=row.tenant_id,
        application_id=row.application_id,
        user_id=row.user_id,
        risk_score=row.risk_score,
        risk_level=RiskLevel(row.risk_level),
        action=Action(row.action),
        enforced_action=Action(row.enforced_action),
        engine_mode=EngineMode(row.engine_mode),
        simulated=row.simulated,
        reasons=[Reason.model_validate(item) for item in raw_reasons],
        model_version=row.model_version,
        policy_version=row.policy_version,
        feature_schema_version=row.feature_schema_version,
        fallback=row.fallback,
        # Already in the stored event; events from before Phase 4 lack them.
        login=LoginEventSnapshot.model_validate(payload["login"]) if payload.get("login") else None,
        features=FeatureVectorV1.model_validate(payload["features"]) if payload.get("features") else None,
    )
