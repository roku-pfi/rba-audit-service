"""Create the audit schema, once (C-4).

    python -m rba_audit_service.init

Runs as a Kubernetes Job before the consumer and the read API start, so they
never race on `create_all`. Idempotent.
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine

from rba_audit_service.config import get_settings
from rba_audit_service.db import Base


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(create_engine(get_settings().database_url, future=True))
    logging.getLogger(__name__).info("rba_audit schema in place")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
