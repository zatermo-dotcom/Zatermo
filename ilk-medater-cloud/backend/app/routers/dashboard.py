"""Organigramme, plan du siège 3D et tableaux de bord — calculés uniquement sur les données autorisées."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from ..authz import MODULES, Principal, company_ids, org_units
from ..db import get_db
from ..deps import current
from ..models import (Company, Contract, CoordinationIssue, Deliverable, Employee, Invoice, LeaveRequest, Payment,
                      Project, PurchaseOrder, QhseEvent, Site, SiteRisk, StockItem)
from ..resources import contract_schedule

router = APIRouter(tags=["dashboard"])

# Bureau du siège -> module ouvert au clic (le reste des modules du département est accessible depuis le bureau).
PRIMARY_MODULE = {"SHARED-EXEC": "dashboard", "SHARED-FIN": "finance", "SHARED-HR": "hr", "SHARED-LEGAL": "legal",
                  "SHARED-IT": "admin", "SHARED-AI": "assistant", "CONST-DIR": "dashboard", "ARCH-DIR": "dashboard",
                  "CONST-TECH": "projects", "CONST-SITE": "sites", "CONST-PROC": "procurement", "CONST-EST": "contracts",
                  "CONST-QHSE": "qhse", "CONST-FIN": "finance", "CONST-HR": "hr", "CONST-PARC": "equipment",
                  "CONST-DOC": "documents", "CONST-LEGAL": "contracts", "ARCH-ARC": "studies", "ARCH-GC": "studies",
                  "ARCH-LEGAL": "legal", "ARCH-MEP": "studies"}


@router.get("/org")
def organisation(p: Principal = Depends(current), s: Session = Depends(get_db)):
    units = sorted(org_units(s).values(), key=lambda u: u.sort)
    comps = s.scalars(select(Company).order_by(Company.id)).all()
    return {"group": "ilk.medater groupe",
            "companies": [{"id": c.id, "code": c.code, "name": c.name} for c in comps],
            "units": [{"code": u.code, "parent": u.parent_code, "company_code": u.company_code, "name": u.name,
                       "kind": u.kind, "floor": u.floor, "modules": u.modules} for u in units]}


@router.get("/building")
def building(p: Principal = Depends(current), s: Session = Depends(get_db)):
    """Bureaux du siège virtuel avec l'état d'accès de l'utilisateur (l'API reste seule juge à l'ouverture)."""
    cids = company_ids(s)
    offices = []
    for u in sorted(org_units(s).values(), key=lambda u: u.sort):
        if u.kind in ("group", "subsidiary"):
            continue
        cid = cids.get(u.company_code)
        primary = PRIMARY_MODULE.get(u.code) or (u.modules[0] if u.modules else None)
        if primary in MODULES:
            comps = p.companies_for(primary, "view")
            proj_ids = p.projects_for(primary, "view")
            proj_comps = set(s.scalars(select(Project.company_id).where(Project.id.in_(proj_ids)))) if proj_ids else set()
            accessible = comps is None or (cid in comps if cid else bool(comps)) or (cid in proj_comps if cid else bool(proj_comps))
        elif primary == "admin":
            accessible = p.is_director
        elif primary == "assistant":
            accessible = p.ai_local or p.ai_cloud
        else:  # tableau de bord : au moins un module visible dans la filiale
            accessible = p.is_director or any(
                (cid in (p.companies_for(m, "view") or set())) if cid else bool(p.companies_for(m, "view")) for m in MODULES)
        offices.append({"code": u.code, "name": u.name, "floor": u.floor, "kind": u.kind, "company_code": u.company_code,
                        "parent": u.parent_code, "module": primary, "modules": u.modules, "accessible": bool(accessible)})
    return {"floors": [{"level": 0, "name": "RDC — Direction générale et services communs"},
                       {"level": 1, "name": "R+1 — eurl medater"}, {"level": 2, "name": "R+2 — cabinet ILK"}],
            "offices": offices}


def _company_kpis(s: Session, p: Principal, cid: int) -> dict:
    today = date.today()
    k: dict = {}
    if p.can("projects", "view", cid):
        row = s.execute(select(
            func.count().filter(Project.status == "en_cours"),
            func.count().filter(and_(Project.planned_end_date < today, Project.status.notin_(["receptionne", "clos"]))),
            func.coalesce(func.sum(Project.budget_amount).filter(Project.status == "en_cours"), 0),
        ).where(Project.company_id == cid)).one()
        k["projects"] = {"active": row[0], "late": row[1], "active_budget": float(row[2])}
    if p.can("sites", "view", cid):
        row = s.execute(select(func.count(), func.coalesce(func.avg(Site.physical_progress), 0)).where(
            Site.company_id == cid, Site.status.in_(["installation", "en_cours"]))).one()
        risks = s.scalar(select(func.count()).select_from(SiteRisk).where(
            SiteRisk.company_id == cid, SiteRisk.status == "ouvert", SiteRisk.level.in_(["eleve", "critique"])))
        k["sites"] = {"active": row[0], "avg_progress": round(float(row[1]), 1), "high_risks_open": risks}
    if p.can("finance", "view", cid):
        paid = select(Payment.invoice_id, func.sum(Payment.amount).label("paid")).group_by(Payment.invoice_id).subquery()
        ttc = Invoice.amount_ht * (1 + Invoice.tva_rate / 100)
        bal = ttc - func.coalesce(paid.c.paid, 0)
        rows = s.execute(select(
            Invoice.direction, func.coalesce(func.sum(bal), 0),
            func.coalesce(func.sum(case((Invoice.due_date < today, bal), else_=0)), 0),
        ).outerjoin(paid, paid.c.invoice_id == Invoice.id).where(
            Invoice.company_id == cid, Invoice.status == "emise").group_by(Invoice.direction)).all()
        f = {"receivables": 0.0, "receivables_overdue": 0.0, "payables": 0.0, "payables_overdue": 0.0}
        for direction, total, overdue in rows:
            key = "receivables" if direction == "vente" else "payables"
            f[key], f[key + "_overdue"] = round(float(total), 2), round(float(overdue), 2)
        k["finance"] = f
    if p.can("contracts", "view", cid):
        contracts = s.scalars(select(Contract).where(Contract.company_id == cid, Contract.status == "en_cours")).all()
        sched = [contract_schedule(s, c) for c in contracts]
        k["contracts"] = {"active": len(contracts), "amount_ht": float(sum(c.amount_ht for c in contracts)),
                          "late": sum(1 for x in sched if x["delay_days"] > 0),
                          "theoretical_penalties": round(sum(x["theoretical_penalty"] for x in sched), 2)}
    if p.can("procurement", "view", cid):
        k["procurement"] = {
            "stock_below_min": s.scalar(select(func.count()).select_from(StockItem).where(
                StockItem.company_id == cid, StockItem.quantity < StockItem.min_quantity)),
            "orders_to_validate": s.scalar(select(func.count()).select_from(PurchaseOrder).where(
                PurchaseOrder.company_id == cid, PurchaseOrder.status == "brouillon"))}
    if p.can("hr", "view", cid):
        k["hr"] = {"active_employees": s.scalar(select(func.count()).select_from(Employee).where(
                       Employee.company_id == cid, Employee.status == "actif")),
                   "leave_pending": s.scalar(select(func.count()).select_from(LeaveRequest).where(
                       LeaveRequest.company_id == cid, LeaveRequest.status == "demandee"))}
    if p.can("qhse", "view", cid):
        k["qhse"] = {"open": s.scalar(select(func.count()).select_from(QhseEvent).where(
                         QhseEvent.company_id == cid, QhseEvent.status != "clos")),
                     "accidents_30d": s.scalar(select(func.count()).select_from(QhseEvent).where(
                         QhseEvent.company_id == cid, QhseEvent.kind == "accident",
                         QhseEvent.found_date >= today - timedelta(days=30)))}
    if p.can("studies", "view", cid):
        k["studies"] = {"to_validate": s.scalar(select(func.count()).select_from(Deliverable).where(
                            Deliverable.company_id == cid, Deliverable.status == "soumis")),
                        "open_issues": s.scalar(select(func.count()).select_from(CoordinationIssue).where(
                            CoordinationIssue.company_id == cid, CoordinationIssue.status.in_(["ouvert", "en_cours"])))}
    return k


@router.get("/dashboard")
def dashboard(p: Principal = Depends(current), s: Session = Depends(get_db)):
    comps = s.scalars(select(Company).order_by(Company.id)).all()
    out = []
    for c in comps:
        k = _company_kpis(s, p, c.id)
        if k:
            out.append({"company_id": c.id, "code": c.code, "name": c.name, "kpis": k})
    consolidated = None
    if len(out) == len(comps) and all("finance" in x["kpis"] for x in out):
        consolidated = {key: round(sum(x["kpis"]["finance"][key] for x in out), 2)
                        for key in ("receivables", "receivables_overdue", "payables", "payables_overdue")}
    return {"companies": out, "consolidated_finance": consolidated,
            "note": "Indicateurs calculés uniquement sur les modules autorisés ; la consolidation financière exige l'accès finance aux deux filiales."}
