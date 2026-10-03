import uuid

from app.services import document_service
from app.workers.broker import broker


@broker.task(task_name="ingest_document")
async def ingest_document(document_id: str) -> None:
    await document_service.ingest(uuid.UUID(document_id))
