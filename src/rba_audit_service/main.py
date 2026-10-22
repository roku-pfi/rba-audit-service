from __future__ import annotations

import logging

import pika
from rba_contracts import DecisionMadeEvent
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from rba_audit_service.config import Settings, get_settings
from rba_audit_service.db import Base, already_stored, row_from_event

logger = logging.getLogger(__name__)


def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    engine = create_engine(settings.database_url, future=True)
    if settings.init_on_startup:
        Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    params = pika.URLParameters(settings.rabbitmq_url)
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.exchange_declare(exchange=settings.exchange_name, exchange_type="topic", durable=True)
    ch.queue_declare(queue=settings.queue_name, durable=True)
    ch.queue_bind(
        queue=settings.queue_name,
        exchange=settings.exchange_name,
        routing_key=settings.routing_key,
    )
    ch.basic_qos(prefetch_count=1)

    def _on_message(channel, method, _properties, body: bytes) -> None:
        try:
            event = DecisionMadeEvent.model_validate_json(body)
            with factory() as session:
                if already_stored(session, event.event_id):
                    logger.info("skip duplicate event_id=%s", event.event_id)
                else:
                    session.add(row_from_event(event))
                    session.commit()
                    logger.info("audited event_id=%s action=%s", event.event_id, event.action)
            channel.basic_ack(delivery_tag=method.delivery_tag)
            if settings.once:
                channel.stop_consuming()
        except Exception:
            logger.exception("audit handler failed")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

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
