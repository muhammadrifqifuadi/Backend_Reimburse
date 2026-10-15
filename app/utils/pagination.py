from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate(db: Session, stmt, skip: int, limit: int) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.scalars(stmt.offset(skip).limit(limit)).all()
    return {"items": items, "total": total, "skip": skip, "limit": limit}
