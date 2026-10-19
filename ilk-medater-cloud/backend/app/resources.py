"""Déclaration des ressources métier (schémas d'entrée, module d'autorisation, rattachements)."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from .crud import Parent, Resource
from .models import (Contract, ContractEvent, CoordinationIssue, DailyReport, Employee, Equipment, Invoice,
                     LeaveRequest, Milestone, Party, Payment, Project, PurchaseOrder, QhseEvent, Site, SiteRisk,
                     Situation, StockItem, StockMovement)

Txt = Annotated[str, Field(max_length=200)]
LongTxt = Annotated[str, Field(max_length=5000)]
Money = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]


class _M(BaseModel):
    model_config = {"extra": "forbid"}


# ------------------------------------------------------------------ CRM
class PartyIn(_M):
    company_id: int
    kind: Literal["client", "fournisseur", "sous-traitant", "partenaire", "administration"]
    name: Annotated[str, Field(min_length=2, max_length=200)]
    nif: Txt = ""
    rc: Txt = ""
    wilaya: Txt = ""
    address: Txt = ""
    phone: Txt = ""
    email: Txt = ""
    notes: LongTxt = ""


class PartyPatch(_M):
    name: Optional[Annotated[str, Field(min_length=2, max_length=200)]] = None
    nif: Optional[Txt] = None
    rc: Optional[Txt] = None
    wilaya: Optional[Txt] = None
    address: Optional[Txt] = None
    phone: Optional[Txt] = None
    email: Optional[Txt] = None
    notes: Optional[LongTxt] = None


# ------------------------------------------------------------------ Projets
Phase = Literal["ESQ", "APS", "APD", "DCE", "EXE", "CHANTIER", "RECEPTION", "CLOS"]
PStatus = Literal["prospect", "en_cours", "suspendu", "receptionne", "clos"]


class ProjectIn(_M):
    company_id: int
    code: Annotated[str, Field(min_length=2, max_length=40)]
    name: Annotated[str, Field(min_length=2, max_length=200)]
    org_unit_code: Optional[str] = None
    kind: Literal["etude", "realisation", "mixte"] = "etude"
    phase: Phase = "ESQ"
    status: PStatus = "en_cours"
    client_id: Optional[int] = None
    wilaya: Txt = ""
    start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    budget_amount: Money = Decimal(0)
    manager_user_id: Optional[int] = None
    description: LongTxt = ""


class ProjectPatch(_M):
    name: Optional[Annotated[str, Field(min_length=2, max_length=200)]] = None
    org_unit_code: Optional[str] = None
    phase: Optional[Phase] = None
    status: Optional[PStatus] = None
    client_id: Optional[int] = None
    wilaya: Optional[Txt] = None
    start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    budget_amount: Optional[Money] = None
    manager_user_id: Optional[int] = None
    description: Optional[LongTxt] = None


def _project_out(s, obj: Project, d: dict) -> dict:
    today = date.today()
    d["late"] = bool(obj.planned_end_date and obj.planned_end_date < today and obj.status not in ("receptionne", "clos"))
    return d


class MilestoneIn(_M):
    project_id: int
    name: Annotated[str, Field(min_length=2, max_length=200)]
    planned_date: Optional[date] = None
    status: Literal["a_faire", "en_cours", "fait", "en_retard"] = "a_faire"


class MilestonePatch(_M):
    name: Optional[Txt] = None
    planned_date: Optional[date] = None
    done_date: Optional[date] = None
    status: Optional[Literal["a_faire", "en_cours", "fait", "en_retard"]] = None


# ------------------------------------------------------------------ Chantiers
class SiteIn(_M):
    project_id: int
    name: Annotated[str, Field(min_length=2, max_length=200)]
    address: Txt = ""
    conducteur_user_id: Optional[int] = None
    start_date: Optional[date] = None
    planned_end_date: Optional[date] = None
    status: Literal["installation", "en_cours", "arrete", "receptionne"] = "installation"


class SitePatch(_M):
    name: Optional[Txt] = None
    address: Optional[Txt] = None
    conducteur_user_id: Optional[int] = None
    planned_end_date: Optional[date] = None
    physical_progress: Optional[Annotated[Decimal, Field(ge=0, le=100)]] = None
    status: Optional[Literal["installation", "en_cours", "arrete", "receptionne"]] = None


class DailyReportIn(_M):
    site_id: int
    report_date: date
    weather: Txt = ""
    workforce: Annotated[int, Field(ge=0, le=5000)] = 0
    equipment: LongTxt = ""
    work_done: Annotated[str, Field(min_length=3, max_length=5000)]
    incidents: LongTxt = ""
    hse_notes: LongTxt = ""


class RiskIn(_M):
    site_id: int
    title: Annotated[str, Field(min_length=3, max_length=200)]
    level: Literal["faible", "moyen", "eleve", "critique"] = "moyen"
    mitigation: LongTxt = ""
    due_date: Optional[date] = None


class RiskPatch(_M):
    level: Optional[Literal["faible", "moyen", "eleve", "critique"]] = None
    status: Optional[Literal["ouvert", "maitrise", "clos"]] = None
    mitigation: Optional[LongTxt] = None
    due_date: Optional[date] = None


# ------------------------------------------------------------------ Contrats / marchés
class ContractIn(_M):
    company_id: int
    project_id: Optional[int] = None
    party_id: Optional[int] = None
    reference: Annotated[str, Field(min_length=2, max_length=80)]
    title: Annotated[str, Field(min_length=2, max_length=300)]
    kind: Literal["marche_public", "marche_prive", "sous_traitance", "etudes", "fourniture"] = "marche_public"
    amount_ht: Money = Decimal(0)
    tva_rate: Rate = Decimal(19)
    retention_rate: Rate = Decimal(5)
    advance_rate: Rate = Decimal(0)
    penalty_per_day_rate: Annotated[Decimal, Field(ge=0, le=10, max_digits=7, decimal_places=4)] = Decimal(0)
    penalty_cap_rate: Rate = Decimal(10)
    signed_date: Optional[date] = None
    ods_start_date: Optional[date] = None
    duration_days: Optional[Annotated[int, Field(gt=0, le=10000)]] = None
    status: Literal["en_preparation", "en_cours", "suspendu", "receptionne", "clos", "resilie"] = "en_preparation"


class ContractPatch(_M):
    title: Optional[Txt] = None
    party_id: Optional[int] = None
    amount_ht: Optional[Money] = None
    tva_rate: Optional[Rate] = None
    retention_rate: Optional[Rate] = None
    advance_rate: Optional[Rate] = None
    penalty_per_day_rate: Optional[Annotated[Decimal, Field(ge=0, le=10)]] = None
    penalty_cap_rate: Optional[Rate] = None
    signed_date: Optional[date] = None
    ods_start_date: Optional[date] = None
    duration_days: Optional[Annotated[int, Field(gt=0, le=10000)]] = None
    status: Optional[Literal["en_preparation", "en_cours", "suspendu", "receptionne", "clos", "resilie"]] = None


class ContractEventIn(_M):
    contract_id: int
    kind: Literal["ods_demarrage", "ods_arret", "ods_reprise", "avenant", "reclamation", "mise_en_demeure",
                  "reception_provisoire", "reception_definitive", "autre"]
    reference: Txt = ""
    event_date: date
    amount_delta: Annotated[Decimal, Field(max_digits=16, decimal_places=2)] = Decimal(0)
    days_delta: Annotated[int, Field(ge=-10000, le=10000)] = 0
    description: LongTxt = ""


class SituationIn(_M):
    contract_id: int
    number: Annotated[int, Field(ge=1, le=999)]
    period_end: date
    cumulative_amount_ht: Money


class SituationPatch(_M):
    cumulative_amount_ht: Optional[Money] = None
    status: Optional[Literal["brouillon", "soumise", "validee", "payee", "rejetee"]] = None


def _situation_before(s, p, obj: Situation) -> None:
    prev = s.scalar(select(func.max(Situation.cumulative_amount_ht)).where(
        Situation.contract_id == obj.contract_id, Situation.number < obj.number, Situation.status != "rejetee"))
    if prev is not None and obj.cumulative_amount_ht < prev:
        raise HTTPException(422, "Le cumul d'une situation ne peut pas être inférieur au cumul précédent")


def situation_figures(s, obj: Situation) -> dict:
    """Décompte d'une situation : montant de la période, retenue de garantie, TVA, net à payer.

    Formules (paramètres du marché) :
      période HT = cumul HT − cumul HT de la situation précédente non rejetée
      retenue    = période HT × taux de retenue de garantie
      TVA        = période HT × taux TVA
      net        = période HT − retenue + TVA
    Le remboursement d'avance et les révisions de prix ne sont pas encore modélisés (signalé dans la réponse).
    """
    c = s.get(Contract, obj.contract_id)
    prev = s.scalar(select(func.max(Situation.cumulative_amount_ht)).where(
        Situation.contract_id == obj.contract_id, Situation.number < obj.number, Situation.status != "rejetee")) or Decimal(0)
    period = obj.cumulative_amount_ht - prev
    retention = (period * c.retention_rate / 100).quantize(Decimal("0.01"))
    tva = (period * c.tva_rate / 100).quantize(Decimal("0.01"))
    contract_total = c.amount_ht + (s.scalar(select(func.coalesce(func.sum(ContractEvent.amount_delta), 0)).where(
        ContractEvent.contract_id == c.id, ContractEvent.kind == "avenant")) or 0)
    return {"previous_cumulative_ht": float(prev), "period_ht": float(period), "retention": float(retention),
            "tva": float(tva), "net_to_pay": float(period - retention + tva),
            "financial_progress_pct": float(obj.cumulative_amount_ht / contract_total * 100) if contract_total else None,
            "not_modelled": ["remboursement de l'avance", "révision / actualisation des prix"]}


def _situation_out(s, obj, d):
    d.update(situation_figures(s, obj))
    return d


def contract_schedule(s, c: Contract) -> dict:
    """Délais et pénalités théoriques d'un marché (indicatif, à confirmer par le service des marchés)."""
    events = s.scalars(select(ContractEvent).where(ContractEvent.contract_id == c.id).order_by(ContractEvent.event_date)).all()
    extension = sum(e.days_delta for e in events if e.kind in ("avenant", "ods_reprise", "autre"))
    stopped = 0
    stop_start = None
    for e in events:
        if e.kind == "ods_arret":
            stop_start = e.event_date
        elif e.kind == "ods_reprise" and stop_start:
            stopped += (e.event_date - stop_start).days
            stop_start = None
    today = date.today()
    if stop_start:
        stopped += (today - stop_start).days
    out = {"ods_start_date": c.ods_start_date, "duration_days": c.duration_days, "extension_days": extension,
           "stopped_days": stopped, "planned_end_date": None, "delay_days": 0, "theoretical_penalty": 0.0,
           "warning": "Calcul indicatif : vérifier les clauses du CCAP/CCAG applicable et les ODS signés."}
    if c.ods_start_date and c.duration_days:
        from datetime import timedelta
        end = c.ods_start_date + timedelta(days=c.duration_days + extension + stopped)
        out["planned_end_date"] = end
        received = next((e.event_date for e in events if e.kind == "reception_provisoire"), None)
        ref = received or today
        delay = max(0, (ref - end).days)
        out["delay_days"] = delay
        total = c.amount_ht + sum(e.amount_delta for e in events if e.kind == "avenant")
        penalty = total * c.penalty_per_day_rate / 100 * delay
        cap = total * c.penalty_cap_rate / 100
        out["theoretical_penalty"] = float(min(penalty, cap).quantize(Decimal("0.01")))
        out["penalty_capped"] = penalty > cap
    return out


def _contract_out(s, obj, d):
    d["schedule"] = contract_schedule(s, obj)
    return d


# ------------------------------------------------------------------ Finances
class InvoiceIn(_M):
    company_id: int
    party_id: int
    project_id: Optional[int] = None
    contract_id: Optional[int] = None
    direction: Literal["vente", "achat"]
    number: Annotated[str, Field(min_length=1, max_length=60)]
    issue_date: date
    due_date: Optional[date] = None
    amount_ht: Money
    tva_rate: Rate = Decimal(19)
    status: Literal["brouillon", "emise"] = "emise"
    description: LongTxt = ""


class InvoicePatch(_M):
    due_date: Optional[date] = None
    status: Optional[Literal["brouillon", "emise", "annulee"]] = None
    description: Optional[LongTxt] = None


def invoice_figures(s, inv: Invoice) -> dict:
    ttc = (inv.amount_ht * (1 + inv.tva_rate / 100)).quantize(Decimal("0.01"))
    paid = s.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == inv.id)) or Decimal(0)
    balance = ttc - paid if inv.status != "annulee" else Decimal(0)
    overdue = bool(inv.due_date and inv.due_date < date.today() and balance > 0)
    return {"amount_ttc": float(ttc), "paid": float(paid), "balance": float(balance), "overdue": overdue,
            "days_overdue": (date.today() - inv.due_date).days if overdue else 0,
            "payment_status": "annulee" if inv.status == "annulee" else ("payee" if balance <= 0 else ("partielle" if paid > 0 else "impayee"))}


def _invoice_out(s, obj, d):
    d.update(invoice_figures(s, obj))
    return d


class PaymentIn(_M):
    invoice_id: int
    paid_date: date
    amount: Annotated[Decimal, Field(gt=0, max_digits=16, decimal_places=2)]
    method: Literal["virement", "cheque", "especes", "compensation"] = "virement"
    reference: Txt = ""


def _payment_before(s, p, obj: Payment) -> None:
    inv = s.get(Invoice, obj.invoice_id)
    if inv.status != "emise":
        raise HTTPException(422, "Paiement possible uniquement sur une facture émise")
    if Decimal(str(invoice_figures(s, inv)["balance"])) < obj.amount:
        raise HTTPException(422, "Le paiement dépasse le solde de la facture")


# ------------------------------------------------------------------ Achats, stock, matériel
class PurchaseOrderIn(_M):
    company_id: int
    supplier_id: int
    project_id: Optional[int] = None
    number: Annotated[str, Field(min_length=1, max_length=60)]
    order_date: date
    total_ht: Money = Decimal(0)
    status: Literal["brouillon", "validee"] = "brouillon"
    description: LongTxt = ""


class PurchaseOrderPatch(_M):
    total_ht: Optional[Money] = None
    status: Optional[Literal["brouillon", "validee", "livree", "annulee"]] = None
    description: Optional[LongTxt] = None


def _po_before(s, p, obj: PurchaseOrder) -> None:
    sup = s.get(Party, obj.supplier_id)
    if sup and sup.kind not in ("fournisseur", "sous-traitant"):
        raise HTTPException(422, "Le tiers doit être un fournisseur ou un sous-traitant")


class StockItemIn(_M):
    company_id: int
    code: Annotated[str, Field(min_length=1, max_length=40)]
    name: Annotated[str, Field(min_length=2, max_length=200)]
    unit: Annotated[str, Field(max_length=20)] = "u"
    min_quantity: Annotated[Decimal, Field(ge=0)] = Decimal(0)
    location: Txt = ""


class StockItemPatch(_M):
    name: Optional[Txt] = None
    unit: Optional[Annotated[str, Field(max_length=20)]] = None
    min_quantity: Optional[Annotated[Decimal, Field(ge=0)]] = None
    location: Optional[Txt] = None


def _stock_out(s, obj, d):
    d["below_min"] = obj.quantity < obj.min_quantity
    return d


class StockMovementIn(_M):
    item_id: int
    kind: Literal["entree", "sortie", "ajustement"]
    quantity: Annotated[Decimal, Field(max_digits=14, decimal_places=3)]
    site_id: Optional[int] = None
    reference: Txt = ""

    @model_validator(mode="after")
    def _sign(self):
        if self.kind in ("entree", "sortie") and self.quantity <= 0:
            raise ValueError("La quantité d'une entrée ou d'une sortie doit être positive")
        return self


def _movement_before(s, p, obj: StockMovement) -> None:
    item = s.scalar(select(StockItem).where(StockItem.id == obj.item_id).with_for_update())
    delta = obj.quantity if obj.kind == "entree" else (-obj.quantity if obj.kind == "sortie" else obj.quantity)
    if item.quantity + delta < 0:
        raise HTTPException(422, f"Stock insuffisant ({item.quantity} {item.unit} disponibles)")
    item.quantity = item.quantity + delta


class EquipmentIn(_M):
    company_id: int
    code: Annotated[str, Field(min_length=1, max_length=40)]
    name: Annotated[str, Field(min_length=2, max_length=200)]
    category: Txt = ""
    status: Literal["disponible", "affecte", "maintenance", "hors_service"] = "disponible"
    site_id: Optional[int] = None
    next_maintenance_date: Optional[date] = None


class EquipmentPatch(_M):
    status: Optional[Literal["disponible", "affecte", "maintenance", "hors_service"]] = None
    site_id: Optional[int] = None
    next_maintenance_date: Optional[date] = None
    hours: Optional[Annotated[Decimal, Field(ge=0)]] = None


# ------------------------------------------------------------------ RH
class EmployeeIn(_M):
    company_id: int
    org_unit_code: Optional[str] = None
    matricule: Annotated[str, Field(min_length=1, max_length=40)]
    full_name: Annotated[str, Field(min_length=2, max_length=200)]
    job_title: Txt = ""
    contract_type: Literal["CDI", "CDD", "stage", "journalier", "consultant"] = "CDI"
    hire_date: Optional[date] = None
    end_date: Optional[date] = None
    phone: Txt = ""
    email: Txt = ""


class EmployeePatch(_M):
    org_unit_code: Optional[str] = None
    job_title: Optional[Txt] = None
    contract_type: Optional[Literal["CDI", "CDD", "stage", "journalier", "consultant"]] = None
    end_date: Optional[date] = None
    status: Optional[Literal["actif", "suspendu", "sorti"]] = None
    phone: Optional[Txt] = None
    email: Optional[Txt] = None


def _employee_before(s, p, obj: Employee) -> None:
    from .authz import company_ids, org_units
    if obj.org_unit_code:
        unit = org_units(s).get(obj.org_unit_code)
        if not unit:
            raise HTTPException(422, "Département inconnu")
        if unit.company_code != "GROUP" and company_ids(s)[unit.company_code] != obj.company_id:
            raise HTTPException(422, "Le département appartient à l'autre filiale")


class LeaveIn(_M):
    employee_id: int
    kind: Literal["conge_annuel", "maladie", "recuperation", "sans_solde", "autre"] = "conge_annuel"
    start_date: date
    end_date: date


class LeavePatch(_M):
    status: Literal["demandee", "acceptee", "refusee", "annulee"]


# ------------------------------------------------------------------ QHSE
class QhseIn(_M):
    company_id: int
    project_id: Optional[int] = None
    site_id: Optional[int] = None
    kind: Literal["non_conformite", "inspection", "incident", "accident", "observation"]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    severity: Literal["mineure", "majeure", "critique"] = "mineure"
    found_date: date
    description: LongTxt = ""
    action: LongTxt = ""


class QhsePatch(_M):
    severity: Optional[Literal["mineure", "majeure", "critique"]] = None
    status: Optional[Literal["ouvert", "action_en_cours", "clos"]] = None
    closed_date: Optional[date] = None
    action: Optional[LongTxt] = None


# ------------------------------------------------------------------ Coordination (synthèse MEP / BIM)
DISCIPLINES = ("ARCH", "GC", "CFO", "CFA", "FIRE", "PLUMB", "HVAC", "AIR", "COORD", "LEGAL", "GEN")


class IssueIn(_M):
    project_id: int
    disciplines: list[Literal[DISCIPLINES]] = Field(min_length=1)  # type: ignore[valid-type]
    title: Annotated[str, Field(min_length=3, max_length=200)]
    location: Txt = ""
    kind: Literal["conflit", "reservation", "incoherence", "question"] = "conflit"
    priority: Literal["basse", "normale", "haute", "bloquante"] = "normale"
    assigned_org_code: Optional[str] = None


class IssuePatch(_M):
    status: Optional[Literal["ouvert", "en_cours", "resolu", "clos"]] = None
    priority: Optional[Literal["basse", "normale", "haute", "bloquante"]] = None
    assigned_org_code: Optional[str] = None
    resolution: Optional[LongTxt] = None


RESOURCES = [
    Resource("parties", Party, "crm", PartyIn, PartyPatch, filters=("company_id", "kind"), order_by=Party.name),
    Resource("projects", Project, "projects", ProjectIn, ProjectPatch, same_company={"client_id": Party},
             filters=("company_id", "status", "phase", "org_unit_code"), order_by=Project.code, serialize=_project_out),
    Resource("milestones", Milestone, "projects", MilestoneIn, MilestonePatch,
             parent=Parent("project_id", Project, ("company_id", "project_id")), filters=("project_id",),
             order_by=Milestone.planned_date, author_field=None),
    Resource("sites", Site, "sites", SiteIn, SitePatch, parent=Parent("project_id", Project, ("company_id", "project_id")),
             filters=("company_id", "project_id", "status"), author_field=None),
    Resource("daily-reports", DailyReport, "sites", DailyReportIn, None,
             parent=Parent("site_id", Site, ("company_id", "project_id")), filters=("site_id", "project_id"),
             order_by=DailyReport.report_date.desc(), author_field="author_id"),
    Resource("site-risks", SiteRisk, "sites", RiskIn, RiskPatch, parent=Parent("site_id", Site, ("company_id", "project_id")),
             filters=("site_id", "project_id", "status"), author_field=None),
    Resource("contracts", Contract, "contracts", ContractIn, ContractPatch,
             same_company={"party_id": Party, "project_id": Project}, filters=("company_id", "project_id", "status"),
             author_field=None, serialize=_contract_out),
    Resource("contract-events", ContractEvent, "contracts", ContractEventIn, None,
             parent=Parent("contract_id", Contract, ("company_id",)), filters=("company_id", "contract_id", "kind"),
             order_by=ContractEvent.event_date),
    Resource("situations", Situation, "contracts", SituationIn, SituationPatch,
             parent=Parent("contract_id", Contract, ("company_id",)), filters=("company_id", "contract_id", "status"),
             order_by=(Situation.contract_id, Situation.number), before_create=_situation_before, serialize=_situation_out,
             validate_on_status=("validee", "rejetee", "payee")),
    Resource("invoices", Invoice, "finance", InvoiceIn, InvoicePatch,
             same_company={"party_id": Party, "project_id": Project, "contract_id": Contract},
             filters=("company_id", "direction", "party_id", "project_id", "status"), order_by=Invoice.issue_date.desc(),
             serialize=_invoice_out, validate_on_status=("annulee",)),
    Resource("payments", Payment, "finance", PaymentIn, None, parent=Parent("invoice_id", Invoice, ("company_id",)),
             filters=("company_id", "invoice_id"), order_by=Payment.paid_date.desc(), before_create=_payment_before),
    Resource("purchase-orders", PurchaseOrder, "procurement", PurchaseOrderIn, PurchaseOrderPatch,
             same_company={"supplier_id": Party, "project_id": Project}, filters=("company_id", "status", "project_id"),
             order_by=PurchaseOrder.order_date.desc(), before_create=_po_before, validate_on_status=("validee",)),
    Resource("stock-items", StockItem, "procurement", StockItemIn, StockItemPatch, filters=("company_id",),
             order_by=StockItem.code, author_field=None, serialize=_stock_out),
    Resource("stock-movements", StockMovement, "procurement", StockMovementIn, None,
             parent=Parent("item_id", StockItem, ("company_id",)), same_company={"site_id": Site}, filters=("item_id",),
             order_by=StockMovement.moved_at.desc(), author_field="author_id", before_create=_movement_before),
    Resource("equipment", Equipment, "equipment", EquipmentIn, EquipmentPatch, same_company={"site_id": Site},
             filters=("company_id", "status", "site_id"), order_by=Equipment.code, author_field=None),
    Resource("employees", Employee, "hr", EmployeeIn, EmployeePatch, filters=("company_id", "org_unit_code", "status"),
             order_by=Employee.full_name, author_field=None, before_create=_employee_before),
    Resource("leave-requests", LeaveRequest, "hr", LeaveIn, LeavePatch,
             parent=Parent("employee_id", Employee, ("company_id",)), filters=("employee_id", "status"),
             order_by=LeaveRequest.start_date.desc(), author_field=None, validate_on_status=("acceptee", "refusee")),
    Resource("qhse-events", QhseEvent, "qhse", QhseIn, QhsePatch, same_company={"project_id": Project, "site_id": Site},
             filters=("company_id", "project_id", "site_id", "status", "kind"), order_by=QhseEvent.found_date.desc()),
    Resource("coordination-issues", CoordinationIssue, "studies", IssueIn, IssuePatch,
             parent=Parent("project_id", Project, ("company_id", "project_id")), filters=("project_id", "status"),
             author_field="raised_by"),
]
