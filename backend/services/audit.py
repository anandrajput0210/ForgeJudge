import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models.judging import AuditEvent


def record_audit_event(
    db: Session,
    actor_user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
):
    audit_event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_value=(
            json.dumps(old_value)
            if old_value is not None
            else None
        ),
        new_value=(
            json.dumps(new_value)
            if new_value is not None
            else None
        ),
        timestamp=datetime.now(timezone.utc),
    )

    db.add(audit_event)

    return audit_event