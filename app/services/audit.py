from sqlalchemy.orm import Session

from app.models.log.audit_log import AuditLog


def log_audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    """Tambahkan catatan audit ke sesi (commit dilakukan oleh pemanggil)."""
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail or {}, ip_address=ip))
