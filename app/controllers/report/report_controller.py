from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import Role, Status
from app.models.auth.user import User
from app.models.log.audit_log import AuditLog
from app.models.masterdata.department import Department
from app.models.masterdata.expense_category import ExpenseCategory
from app.models.reimbursement.reimbursement import Reimbursement
from app.models.reimbursement.reimbursement_item import ReimbursementItem
from app.controllers.reimbursement.reimbursement_controller import _LOAD, apply_filters
from app.services import export_excel
from datetime import datetime, time, timedelta


def _f(v) -> float:
    return float(v or 0)


def _date_conds(date_from, date_to):
    conds = []
    if date_from:
        conds.append(Reimbursement.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        conds.append(Reimbursement.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    return conds


def summary(db: Session, date_from, date_to, department_id) -> dict:
    conds = _date_conds(date_from, date_to)
    if department_id:
        conds.append(Reimbursement.department_id == department_id)

    by_status = db.execute(
        select(
            Reimbursement.status, func.count(Reimbursement.id), func.sum(Reimbursement.total_claimed),
            func.sum(Reimbursement.total_approved), func.sum(Reimbursement.total_payable),
        ).where(*conds, Reimbursement.status != Status.DRAFT).group_by(Reimbursement.status)
    ).all()

    by_category = db.execute(
        select(
            ExpenseCategory.code, ExpenseCategory.name, func.count(ReimbursementItem.id),
            func.sum(ReimbursementItem.amount_idr), func.sum(ReimbursementItem.amount_approved),
        )
        .join(ReimbursementItem, ReimbursementItem.category_id == ExpenseCategory.id)
        .join(Reimbursement, Reimbursement.id == ReimbursementItem.reimbursement_id)
        .where(*conds, Reimbursement.status.in_(Status.ACTIVE))
        .group_by(ExpenseCategory.code, ExpenseCategory.name)
        .order_by(func.sum(ReimbursementItem.amount_idr).desc())
    ).all()

    by_department = db.execute(
        select(Department.code, Department.name, func.count(Reimbursement.id),
               func.sum(Reimbursement.total_claimed), func.sum(Reimbursement.total_approved))
        .join(Reimbursement, Reimbursement.department_id == Department.id)
        .where(*conds, Reimbursement.status.in_(Status.ACTIVE))
        .group_by(Department.code, Department.name)
        .order_by(func.sum(Reimbursement.total_claimed).desc())
    ).all()

    awaiting = db.execute(
        select(func.count(Reimbursement.id), func.sum(Reimbursement.total_payable))
        .where(*conds, Reimbursement.status == Status.APPROVED_FINANCE)
    ).one()
    flagged = db.scalar(select(func.count(Reimbursement.id)).where(*conds, Reimbursement.status.in_(Status.ACTIVE), Reimbursement.has_policy_flag.is_(True)))

    return {
        "by_status": [{"status": s, "count": c, "total_claimed": _f(a), "total_approved": _f(b), "total_payable": _f(p)} for s, c, a, b, p in by_status],
        "by_category": [{"code": c, "name": n, "items": i, "total_claimed": _f(a), "total_approved": _f(b)} for c, n, i, a, b in by_category],
        "by_department": [{"code": c, "name": n, "claims": i, "total_claimed": _f(a), "total_approved": _f(b)} for c, n, i, a, b in by_department],
        "awaiting_payment": {"count": awaiting[0], "total": _f(awaiting[1])},
        "flagged_claims": flagged or 0,
    }


def export_claims(db: Session, user: User, status, department_id, date_from, date_to, ip) -> bytes:
    stmt = select(Reimbursement).where(Reimbursement.status != Status.DRAFT).order_by(Reimbursement.id).options(*_LOAD)
    stmt = apply_filters(stmt, status=status, department_id=department_id, date_from=date_from, date_to=date_to)
    claims = db.scalars(stmt).all()
    reveal = user.role == Role.FINANCE  # nomor rekening penuh hanya untuk finance
    if reveal:
        db.add(AuditLog(user_id=user.id, action="export_with_account_numbers", entity="reimbursement",
                        detail={"count": len(claims)}, ip_address=ip))
        db.commit()
    return export_excel.build_export(claims, reveal)
