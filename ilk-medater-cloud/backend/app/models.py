"""Correspondance ORM du schéma SQL (migrations/*.sql = source de vérité).

Les valeurs par défaut sont posées par PostgreSQL (FetchedValue + eager_defaults) ; un test vérifie que
chaque colonne déclarée ici existe bien dans la base migrée.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ARRAY, BigInteger, FetchedValue, ForeignKey, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    __mapper_args__ = {"eager_defaults": True}
    type_annotation_map = {str: Text, Decimal: Numeric, dict[str, Any]: JSONB, list[str]: ARRAY(Text)}


def dflt(**kw):
    """Colonne dont la valeur par défaut est définie en SQL."""
    return mapped_column(server_default=FetchedValue(), **kw)


class Company(Base):
    __tablename__ = "companies"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str]
    name: Mapped[str]
    legal_name: Mapped[Optional[str]]
    nif: Mapped[Optional[str]]
    created_at: Mapped[datetime] = dflt()


class OrgUnit(Base):
    __tablename__ = "org_units"
    code: Mapped[str] = mapped_column(primary_key=True)
    parent_code: Mapped[Optional[str]]
    company_code: Mapped[str]
    name: Mapped[str]
    kind: Mapped[str]
    floor: Mapped[Optional[int]]
    modules: Mapped[list[str]] = dflt()
    sort: Mapped[int] = dflt()
    active: Mapped[bool] = dflt()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str]
    full_name: Mapped[str] = dflt()
    job_title: Mapped[str] = dflt()
    org_unit_code: Mapped[Optional[str]] = mapped_column(ForeignKey("org_units.code"))
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"))
    password_hash: Mapped[str]
    enabled: Mapped[bool] = dflt()
    is_group_director: Mapped[bool] = dflt()
    mfa_enabled: Mapped[bool] = dflt()
    mfa_secret_enc: Mapped[Optional[str]]
    failed_logins: Mapped[int] = dflt()
    locked_until: Mapped[Optional[datetime]]
    must_change_password: Mapped[bool] = dflt()
    password_changed_at: Mapped[Optional[datetime]]
    last_login_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = dflt()


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    code_hash: Mapped[str]
    used_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = dflt()


class SessionRow(Base):
    __tablename__ = "sessions"
    id: Mapped[Any] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=FetchedValue())
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str]
    mfa_verified: Mapped[bool] = dflt()
    created_at: Mapped[datetime] = dflt()
    last_seen_at: Mapped[datetime] = dflt()
    expires_at: Mapped[datetime]
    revoked_at: Mapped[Optional[datetime]]
    ip: Mapped[Optional[str]]
    user_agent: Mapped[Optional[str]]


class Grant(Base):
    __tablename__ = "grants"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"))
    scope_type: Mapped[str]
    scope_ref: Mapped[str]
    actions: Mapped[list[str]]
    status: Mapped[str] = dflt()
    expires_at: Mapped[Optional[datetime]]
    note: Mapped[str] = dflt()
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    granted_at: Mapped[datetime] = dflt()
    updated_at: Mapped[datetime] = dflt()
    revoked_at: Mapped[Optional[datetime]]


class AiSettings(Base):
    __tablename__ = "ai_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    local_enabled: Mapped[bool] = dflt()
    cloud_enabled: Mapped[bool] = dflt()
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = dflt()


class AiConsent(Base):
    __tablename__ = "ai_consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    policy_version: Mapped[str]
    accepted_at: Mapped[datetime] = dflt()


class AiRequest(Base):
    __tablename__ = "ai_requests"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assistant_code: Mapped[str]
    engine: Mapped[str]
    company_id: Mapped[Optional[int]]
    project_id: Mapped[Optional[int]]
    question: Mapped[str]
    answer: Mapped[str]
    sources: Mapped[Any] = mapped_column(JSONB, server_default=FetchedValue())
    redactions: Mapped[int] = dflt()
    created_at: Mapped[datetime] = dflt()


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime]
    actor_id: Mapped[Optional[int]]
    action: Mapped[str]
    resource: Mapped[str]
    company_id: Mapped[Optional[int]]
    details: Mapped[dict[str, Any]]
    ip: Mapped[Optional[str]]
    prev_hash: Mapped[str]
    hash: Mapped[str]


# ------------------------------------------------------------------ Métier
class Party(Base):
    __tablename__ = "parties"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    kind: Mapped[str]
    name: Mapped[str]
    nif: Mapped[str] = dflt()
    rc: Mapped[str] = dflt()
    wilaya: Mapped[str] = dflt()
    address: Mapped[str] = dflt()
    phone: Mapped[str] = dflt()
    email: Mapped[str] = dflt()
    notes: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    org_unit_code: Mapped[Optional[str]]
    code: Mapped[str]
    name: Mapped[str]
    kind: Mapped[str] = dflt()
    phase: Mapped[str] = dflt()
    status: Mapped[str] = dflt()
    client_id: Mapped[Optional[int]]
    wilaya: Mapped[str] = dflt()
    start_date: Mapped[Optional[date]]
    planned_end_date: Mapped[Optional[date]]
    actual_end_date: Mapped[Optional[date]]
    budget_amount: Mapped[Decimal] = dflt()
    manager_user_id: Mapped[Optional[int]]
    description: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    company_id: Mapped[int]
    name: Mapped[str]
    planned_date: Mapped[Optional[date]]
    done_date: Mapped[Optional[date]]
    status: Mapped[str] = dflt()


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    company_id: Mapped[int]
    name: Mapped[str]
    address: Mapped[str] = dflt()
    conducteur_user_id: Mapped[Optional[int]]
    start_date: Mapped[Optional[date]]
    planned_end_date: Mapped[Optional[date]]
    physical_progress: Mapped[Decimal] = dflt()
    status: Mapped[str] = dflt()
    created_at: Mapped[datetime] = dflt()


class DailyReport(Base):
    __tablename__ = "site_daily_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int]
    project_id: Mapped[int]
    company_id: Mapped[int]
    report_date: Mapped[date]
    weather: Mapped[str] = dflt()
    workforce: Mapped[int] = dflt()
    equipment: Mapped[str] = dflt()
    work_done: Mapped[str]
    incidents: Mapped[str] = dflt()
    hse_notes: Mapped[str] = dflt()
    author_id: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class SiteRisk(Base):
    __tablename__ = "site_risks"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int]
    project_id: Mapped[int]
    company_id: Mapped[int]
    title: Mapped[str]
    level: Mapped[str] = dflt()
    status: Mapped[str] = dflt()
    mitigation: Mapped[str] = dflt()
    due_date: Mapped[Optional[date]]
    created_at: Mapped[datetime] = dflt()


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    project_id: Mapped[Optional[int]]
    party_id: Mapped[Optional[int]]
    reference: Mapped[str]
    title: Mapped[str]
    kind: Mapped[str] = dflt()
    amount_ht: Mapped[Decimal] = dflt()
    tva_rate: Mapped[Decimal] = dflt()
    retention_rate: Mapped[Decimal] = dflt()
    advance_rate: Mapped[Decimal] = dflt()
    penalty_per_day_rate: Mapped[Decimal] = dflt()
    penalty_cap_rate: Mapped[Decimal] = dflt()
    signed_date: Mapped[Optional[date]]
    ods_start_date: Mapped[Optional[date]]
    duration_days: Mapped[Optional[int]]
    status: Mapped[str] = dflt()
    created_at: Mapped[datetime] = dflt()


class ContractEvent(Base):
    __tablename__ = "contract_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int]
    company_id: Mapped[int]
    kind: Mapped[str]
    reference: Mapped[str] = dflt()
    event_date: Mapped[date]
    amount_delta: Mapped[Decimal] = dflt()
    days_delta: Mapped[int] = dflt()
    description: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class Situation(Base):
    __tablename__ = "situations"
    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int]
    company_id: Mapped[int]
    number: Mapped[int]
    period_end: Mapped[date]
    cumulative_amount_ht: Mapped[Decimal]
    status: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    validated_by: Mapped[Optional[int]]
    validated_at: Mapped[Optional[datetime]]
    created_at: Mapped[datetime] = dflt()


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    party_id: Mapped[int]
    project_id: Mapped[Optional[int]]
    contract_id: Mapped[Optional[int]]
    direction: Mapped[str]
    number: Mapped[str]
    issue_date: Mapped[date]
    due_date: Mapped[Optional[date]]
    amount_ht: Mapped[Decimal]
    tva_rate: Mapped[Decimal] = dflt()
    status: Mapped[str] = dflt()
    description: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int]
    company_id: Mapped[int]
    paid_date: Mapped[date]
    amount: Mapped[Decimal]
    method: Mapped[str] = dflt()
    reference: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    supplier_id: Mapped[int]
    project_id: Mapped[Optional[int]]
    number: Mapped[str]
    order_date: Mapped[date]
    total_ht: Mapped[Decimal] = dflt()
    status: Mapped[str] = dflt()
    description: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class StockItem(Base):
    __tablename__ = "stock_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    code: Mapped[str]
    name: Mapped[str]
    unit: Mapped[str] = dflt()
    quantity: Mapped[Decimal] = dflt()
    min_quantity: Mapped[Decimal] = dflt()
    location: Mapped[str] = dflt()


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int]
    company_id: Mapped[int]
    kind: Mapped[str]
    quantity: Mapped[Decimal]
    site_id: Mapped[Optional[int]]
    reference: Mapped[str] = dflt()
    author_id: Mapped[Optional[int]]
    moved_at: Mapped[datetime] = dflt()


class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    code: Mapped[str]
    name: Mapped[str]
    category: Mapped[str] = dflt()
    status: Mapped[str] = dflt()
    site_id: Mapped[Optional[int]]
    next_maintenance_date: Mapped[Optional[date]]
    hours: Mapped[Decimal] = dflt()


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    org_unit_code: Mapped[Optional[str]]
    matricule: Mapped[str]
    full_name: Mapped[str]
    job_title: Mapped[str] = dflt()
    contract_type: Mapped[str] = dflt()
    hire_date: Mapped[Optional[date]]
    end_date: Mapped[Optional[date]]
    status: Mapped[str] = dflt()
    user_id: Mapped[Optional[int]]
    phone: Mapped[str] = dflt()
    email: Mapped[str] = dflt()


class LeaveRequest(Base):
    __tablename__ = "leave_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int]
    company_id: Mapped[int]
    kind: Mapped[str] = dflt()
    start_date: Mapped[date]
    end_date: Mapped[date]
    status: Mapped[str] = dflt()
    decided_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class QhseEvent(Base):
    __tablename__ = "qhse_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    project_id: Mapped[Optional[int]]
    site_id: Mapped[Optional[int]]
    kind: Mapped[str]
    title: Mapped[str]
    severity: Mapped[str] = dflt()
    status: Mapped[str] = dflt()
    found_date: Mapped[date]
    closed_date: Mapped[Optional[date]]
    description: Mapped[str] = dflt()
    action: Mapped[str] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    project_id: Mapped[Optional[int]]
    title: Mapped[str]
    doc_type: Mapped[str] = dflt()
    discipline: Mapped[str] = dflt()
    confidentiality: Mapped[str] = dflt()
    current_version: Mapped[int] = dflt()
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int]
    company_id: Mapped[int]
    version: Mapped[int]
    revision_label: Mapped[str] = dflt()
    filename: Mapped[str]
    content_type: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str]
    storage_path: Mapped[str]
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, server_default=FetchedValue())
    comment: Mapped[str] = dflt()
    uploaded_by: Mapped[Optional[int]]
    uploaded_at: Mapped[datetime] = dflt()


class Deliverable(Base):
    __tablename__ = "deliverables"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    company_id: Mapped[int]
    discipline: Mapped[str]
    phase: Mapped[str]
    title: Mapped[str]
    status: Mapped[str] = dflt()
    due_date: Mapped[Optional[date]]
    document_id: Mapped[Optional[int]]
    author_id: Mapped[Optional[int]]
    submitted_at: Mapped[Optional[datetime]]
    validator_id: Mapped[Optional[int]]
    validated_at: Mapped[Optional[datetime]]
    review_comment: Mapped[str] = dflt()
    created_at: Mapped[datetime] = dflt()


class CalcRun(Base):
    __tablename__ = "calc_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    company_id: Mapped[int]
    engine: Mapped[str]
    engine_version: Mapped[str]
    inputs: Mapped[dict[str, Any]]
    outputs: Mapped[dict[str, Any]]
    warnings: Mapped[Any] = mapped_column(JSONB, server_default=FetchedValue())
    author_id: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class CoordinationIssue(Base):
    __tablename__ = "coordination_issues"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int]
    company_id: Mapped[int]
    disciplines: Mapped[list[str]]
    title: Mapped[str]
    location: Mapped[str] = dflt()
    kind: Mapped[str] = dflt()
    priority: Mapped[str] = dflt()
    status: Mapped[str] = dflt()
    assigned_org_code: Mapped[Optional[str]]
    resolution: Mapped[str] = dflt()
    raised_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class LegalSource(Base):
    __tablename__ = "legal_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    text_type: Mapped[str]
    title: Mapped[str]
    reference_number: Mapped[str]
    article: Mapped[str] = dflt()
    publication_date: Mapped[Optional[date]]
    jo_reference: Mapped[str] = dflt()
    version_label: Mapped[str] = dflt()
    valid_from: Mapped[Optional[date]]
    valid_to: Mapped[Optional[date]]
    source_url: Mapped[str] = dflt()
    excerpt: Mapped[str] = dflt()
    keywords: Mapped[list[str]] = dflt()
    verified_by: Mapped[Optional[int]]
    verified_at: Mapped[Optional[datetime]]
    created_by: Mapped[Optional[int]]
    created_at: Mapped[datetime] = dflt()


class Directive(Base):
    __tablename__ = "directives"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int]
    project_id: Mapped[int]
    title: Mapped[str]
    instructions: Mapped[str]
    priority: Mapped[str] = dflt()
    due_date: Mapped[Optional[date]]
    status: Mapped[str] = dflt()
    issued_by: Mapped[int]
    issued_at: Mapped[datetime] = dflt()
    closed_by: Mapped[Optional[int]]
    closed_at: Mapped[Optional[datetime]]
    updated_at: Mapped[datetime] = dflt()


class DirectiveUpdate(Base):
    __tablename__ = "directive_updates"
    id: Mapped[int] = mapped_column(primary_key=True)
    directive_id: Mapped[int]
    company_id: Mapped[int]
    author_id: Mapped[int]
    note: Mapped[str]
    new_status: Mapped[Optional[str]]
    created_at: Mapped[datetime] = dflt()
