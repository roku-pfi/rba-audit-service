from __future__ import annotations

import logging

import pika
from prometheus_client import start_http_server
from rba_contracts import DecisionMadeEvent
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rba_audit_service.config import Settings, get_settings
from rba_audit_service.db import Base, already_stored, row_from_event
from rba_audit_service.metrics import CONSUMED, observe_lag
from rba_audit_service.retry import apply_with_retries

logger = logging.getLogger(__name__)
CONSUMER = "audit"


def declare(ch, settings: Settings) -> None:
    """The queue and its dead-letter queue. A queue left from before the
    dead-letter queue existed must be deleted once (empty) to get them."""
    ch.exchange_declare(exchange=settings.exchange_name, exchange_type="topic", durable=True)
    ch.exchange_declare(exchange=settings.dead_letter_exchange, exchange_type="direct", durable=True)
    dlq = f"{settings.queue_name}.dlq"
    ch.queue_declare(queue=dlq, durable=True)
    ch.queue_bind(queue=dlq, exchange=settings.dead_letter_exchange, routing_key=settings.queue_name)
    ch.queue_declare(
        queue=settings.queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.dead_letter_exchange,
            "x-dead-letter-routing-key": settings.queue_name,
        },
    )
    ch.queue_bind(
        queue=settings.queue_name,
        exchange=settings.exchange_name,
        routing_key=settings.routing_key,
    )


def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = create_engine(settings.database_url, future=True)
    if settings.init_on_startup:
        Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    if settings.metrics_port:
        start_http_server(settings.metrics_port)
    params = pika.URLParameters(settings.rabbitmq_url)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    declare(ch, settings)
    ch.basic_qos(prefetch_count=1)

    def _apply(body: bytes) -> DecisionMadeEvent:
        event = DecisionMadeEvent.model_validate_json(body)
        with factory() as session:
            if already_stored(session, event.event_id):
                logger.info("skip duplicate event_id=%s", event.event_id)
            else:
                session.add(row_from_event(event))
                session.commit()
                logger.info("audited event_id=%s action=%s", event.event_id, event.action)
        return event

    def _on_retry(attempt: int, exc: Exception) -> None:
        logger.warning("audit handler failed (attempt %d), retrying: %r", attempt, exc)
        CONSUMED.labels(CONSUMER, "retried").inc()

    def _on_message(channel, method, _properties, body: bytes) -> None:
        try:
            event = apply_with_retries(
                lambda: _apply(body),
                delays=settings.retry_delays,
                # Keeps the connection's heartbeats going while it waits.
                sleep=channel.connection.sleep,
                on_retry=_on_retry,
            )
            channel.basic_ack(delivery_tag=method.delivery_tag)
            CONSUMED.labels(CONSUMER, "applied").inc()
            observe_lag(CONSUMER, event.occurred_at)
            if settings.once:
                channel.stop_consuming()
        except Exception:
            logger.exception("audit handler failed; dead-lettered to %s.dlq", settings.queue_name)
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            CONSUMED.labels(CONSUMER, "dead_lettered").inc()

    ch.basic_consume(queue=settings.queue_name, on_message_callback=_on_message)
    logger.info("audit-service consuming queue=%s", settings.queue_name)
    try:
        ch.start_consuming()
    finally:
        conn.close()


def main() -> None:
    run()


if __name__ == "__main__":
    main()
