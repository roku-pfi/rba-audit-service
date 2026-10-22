"""HTTP read API for the IdP-6 decision browser. Consumer loop stays in main.py."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from rba_contracts import Action, DecisionListResponse, DecisionRecord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from rba_audit_service.config import Settings, get_settings
from rba_audit_service.db import AuditDecision, Base, row_to_record

logger = logging.getLogger(__name__)


def _make_engine(settings: Settings):
    if settings.use_memory_db:
        return create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
    return create_engine(settings.database_url, future=True)


def create_app(
    settings: Settings | None = None,
    *,
    session_factory=None,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logging.basicConfig(level=logging.INFO)
        if session_factory is None:
            engine = _make_engine(settings)
            Base.metadata.create_all(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        else:
            factory = session_factory
        app.state.settings = settings
        app.state.session_factory = factory
        logger.info("rba-audit-service HTTP ready (decision read API)")
        yield

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/decisions", response_model=DecisionListResponse)
    def list_decisions(
        request: Request,
        tenant_id: str,
        user_id: str | None = None,
        application_id: str | None = None,
        action: Action | None = None,
        limit: int = Query(default=50, ge=1, le=200),
    ) -> DecisionListResponse:
        factory = request.app.state.session_factory
        stmt = (
            select(AuditDecision)
            .where(AuditDecision.tenant_id == tenant_id)
            .order_by(AuditDecision.occurred_at.desc())
        )
        if user_id:
            stmt = stmt.where(AuditDecision.user_id == user_id)
        if application_id:
            stmt = stmt.where(AuditDecision.application_id == application_id)
        if action is not None:
            stmt = stmt.where(AuditDecision.action == action.value)
        stmt = stmt.limit(limit)
        with factory() as session:
            rows = list(session.scalars(stmt))
        items = [row_to_record(row) for row in rows]
        return DecisionListResponse(items=items, count=len(items))

    @app.get("/decisions/{event_id}", response_model=DecisionRecord)
    def get_decision(event_id: UUID, tenant_id: str, request: Request) -> DecisionRecord:
        factory = request.app.state.session_factory
        with factory() as session:
            row = session.get(AuditDecision, event_id)
        # Another tenant's event is indistinguishable from a missing one.
        if row is None or row.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="unknown event")
        return row_to_record(row)

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "rba_audit_service.api:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
