from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy.types import JSON, Uuid


class Base(DeclarativeBase):
    pass


class AuditDecision(Base):
    __tablename__ = "audit_decisions"

    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    application_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def already_stored(session: Session, event_id: UUID) -> bool:
    return session.get(AuditDecision, event_id) is not None
