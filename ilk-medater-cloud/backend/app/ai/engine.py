"""Orchestration ilk.medater AI : collecte des sources autorisées, routage local/cloud, citations vérifiées."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..authz import Principal
from ..config import get_settings
from ..models import (AiConsent, Contract, CoordinationIssue, Deliverable, Directive, Document, Employee, Invoice, LeaveRequest,
                      Project, QhseEvent, Site, SiteRisk)
from ..resources import contract_schedule, invoice_figures
from ..routers.legal import search_sources
from .assistants import Assistant
from .providers import ProviderUnavailable, cloud_chat, ollama_available, ollama_chat
from .redact import redact

STOP = {"pour", "avec", "dans", "quels", "quelles", "quel", "quelle", "sont", "est-ce", "comment", "combien", "liste",
        "donne", "moi", "les", "des", "une", "sur", "par", "qui", "que", "quoi", "notre", "nos", "leur", "projet", "projets"}
CONFIDENTIAL_TYPES = {"finance", "hr"}


@dataclass
class Src:
    id: str
    type: str
    ref: str
    label: str
    text: str
    confidential: bool = False


@dataclass
class Answer:
    engine: str
    answer: str
    sources: list[Src]
    missing: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    redactions: int = 0


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def keywords(question: str) -> list[str]:
    words = re.findall(r"[\w'-]{4,}", question.lower())
    return [w for w in words if _norm(w) not in STOP][:8]


def collect(s: Session, p: Principal, a: Assistant, question: str, company_id: int | None, project_id: int | None) -> tuple[list[Src], list[str]]:
    """Interroge uniquement les modules de l'assistant ET autorisés pour l'utilisateur."""
    srcs: list[Src] = []
    missing: list[str] = []
    kw = keywords(question)
    qn = _norm(question)

    def add(type_, ref, label, text, conf=False):
        srcs.append(Src(f"S{len(srcs) + 1}", type_, ref, label, text, conf))

    def scoped(model, module):
        q = select(model).where(p.scope_clause(model, module, "view"))
        if company_id and hasattr(model, "company_id"):
            q = q.where(model.company_id == company_id)
        if project_id and hasattr(model, "project_id"):
            q = q.where(model.project_id == project_id)
        return q

    allowed = [m for m in a.modules if p.has_module_anywhere(m)]
    for m in a.modules:
        if m not in allowed:
            missing.append(f"Module « {m} » non autorisé pour votre compte : données non consultées.")

    if "projects" in allowed:
        q = scoped(Project, "projects")
        if project_id:
            q = select(Project).where(Project.id == project_id, p.scope_clause(Project, "projects"))
        elif kw:
            q = q.where(or_(*[Project.name.ilike(f"%{w}%") for w in kw], *[Project.code.ilike(f"%{w}%") for w in kw])) \
                if not any(x in qn for x in ("retard", "tous", "liste", "portefeuille", "en cours")) else q
        for pr in s.scalars(q.order_by(Project.planned_end_date.nulls_last()).limit(12)):
            late = pr.planned_end_date and pr.planned_end_date < date.today() and pr.status not in ("receptionne", "clos")
            add("projet", f"project:{pr.id}", f"{pr.code} — {pr.name}",
                f"Projet {pr.code} « {pr.name} » ; phase {pr.phase} ; statut {pr.status} ; fin prévue {pr.planned_end_date or 'non renseignée'}"
                f"{' (EN RETARD)' if late else ''} ; budget {pr.budget_amount} DA ; wilaya {pr.wilaya or 'non renseignée'}.")
    if "projects" in allowed:
        for dv in s.scalars(scoped(Directive, "projects").where(Directive.status.notin_(["cloturee", "annulee"]))
                            .order_by(Directive.due_date.nulls_last()).limit(10)):
            late = dv.due_date and dv.due_date < date.today() and dv.status != "realisee"
            add("directive DG", f"directive:{dv.id}", dv.title,
                f"Directive de la Direction générale « {dv.title} » (projet #{dv.project_id}) ; priorité {dv.priority} ; statut {dv.status} ; "
                f"échéance {dv.due_date or 'non fixée'}{' (EN RETARD)' if late else ''}.")
    if "sites" in allowed:
        for st in s.scalars(scoped(Site, "sites").order_by(Site.id.desc()).limit(8)):
            risks = s.scalar(select(func.count()).select_from(SiteRisk).where(SiteRisk.site_id == st.id, SiteRisk.status == "ouvert"))
            add("chantier", f"site:{st.id}", st.name,
                f"Chantier « {st.name} » ; avancement physique {st.physical_progress} % ; statut {st.status} ; "
                f"fin prévue {st.planned_end_date or 'non renseignée'} ; risques ouverts : {risks}.")
    if "studies" in allowed:
        for d in s.scalars(scoped(Deliverable, "studies").where(Deliverable.status.in_(["brouillon", "soumis", "rejete"]))
                           .order_by(Deliverable.due_date.nulls_last()).limit(10)):
            add("livrable", f"deliverable:{d.id}", d.title,
                f"Livrable {d.discipline}/{d.phase} « {d.title} » ; statut {d.status} ; échéance {d.due_date or 'non renseignée'}.")
        for ci in s.scalars(scoped(CoordinationIssue, "studies").where(CoordinationIssue.status.in_(["ouvert", "en_cours"])).limit(8)):
            add("coordination", f"issue:{ci.id}", ci.title,
                f"Point de coordination « {ci.title} » ({', '.join(ci.disciplines)}) ; priorité {ci.priority} ; statut {ci.status} ; lieu {ci.location or 'non précisé'}.")
    if "contracts" in allowed:
        for c in s.scalars(scoped(Contract, "contracts").where(Contract.status.in_(["en_cours", "suspendu"])).limit(8)):
            sc = contract_schedule(s, c)
            add("marché", f"contract:{c.id}", f"{c.reference} — {c.title}",
                f"Marché {c.reference} « {c.title} » ; montant {c.amount_ht} DA HT ; fin contractuelle recalculée {sc['planned_end_date'] or 'non calculable'} ; "
                f"retard {sc['delay_days']} j ; pénalités théoriques {sc['theoretical_penalty']} DA (indicatif).")
    finance_comps = p.companies_for("finance", "view")
    if "finance" in allowed and company_id is None and (finance_comps is None or len(finance_comps) > 1):
        allowed.remove("finance")
        missing.append("Finances non consultées : les comptes d'eurl medater et du cabinet ILK sont séparés, "
                       "préciser la filiale concernée pour toute question financière.")
    if "finance" in allowed:
        rows = []
        for inv in s.scalars(scoped(Invoice, "finance").where(Invoice.status == "emise", Invoice.direction == "vente").limit(200)):
            f = invoice_figures(s, inv)
            if f["balance"] > 0:
                rows.append((f["days_overdue"], inv, f))
        rows.sort(key=lambda r: -r[0])
        for days, inv, f in rows[:10]:
            add("facture", f"invoice:{inv.id}", f"Facture {inv.number}",
                f"Facture {inv.number} du {inv.issue_date} ; solde {f['balance']} DA TTC ; échéance {inv.due_date or 'non renseignée'} ; "
                f"{'en retard de ' + str(days) + ' j' if f['overdue'] else 'non échue'}.", conf=True)
        if not rows:
            missing.append("Aucune facture client avec solde ouvert dans votre périmètre.")
    if "hr" in allowed:
        q = scoped(Employee, "hr")
        n = s.scalar(select(func.count()).select_from(q.where(Employee.status == "actif").subquery()))
        pend = s.scalar(select(func.count()).select_from(scoped(LeaveRequest, "hr").where(LeaveRequest.status == "demandee").subquery()))
        add("rh", "hr:summary", "Synthèse RH", f"Effectif actif : {n} ; demandes de congé en attente : {pend}.", conf=True)
    if "qhse" in allowed:
        for e in s.scalars(scoped(QhseEvent, "qhse").where(QhseEvent.status != "clos").limit(8)):
            add("qhse", f"qhse:{e.id}", e.title, f"{e.kind} « {e.title} » ; gravité {e.severity} ; statut {e.status} ; constaté le {e.found_date}.")
    if "documents" in allowed and kw:
        for d in s.scalars(scoped(Document, "documents").where(or_(*[Document.title.ilike(f"%{w}%") for w in kw])).limit(6)):
            add("document", f"document:{d.id}", d.title, f"Document « {d.title} » ({d.doc_type}, {d.discipline}), version {d.current_version}, "
                f"confidentialité {d.confidentiality}.", conf=d.confidentiality != "interne")
    if "legal" in allowed:
        for ls in search_sources(s, kw):
            add("référence juridique", f"legal:{ls.id}", f"{ls.text_type} {ls.reference_number}" + (f", art. {ls.article}" if ls.article else ""),
                f"{ls.title} — {ls.text_type} n° {ls.reference_number}" + (f", article {ls.article}" if ls.article else "")
                + f" ; publié le {ls.publication_date or 'date non saisie'} ; {ls.jo_reference or 'JO non saisi'} ; version : {ls.version_label or 'non précisée'} ; "
                f"source : {ls.source_url or ls.jo_reference} ; extrait vérifié : {ls.excerpt[:1200]}")
    return srcs[:30], missing


def complex_request(question: str) -> bool:
    qn = _norm(question)
    return len(question) > 280 or any(w in qn for w in ("redige", "rediger", "memoire", "analyse", "synthese detaillee", "courrier"))


def has_consent(s: Session, p: Principal) -> bool:
    v = get_settings().ai_policy_version
    return bool(s.scalar(select(AiConsent.id).where(AiConsent.user_id == p.id, AiConsent.policy_version == v)))


def _context(srcs: list[Src]) -> str:
    return "\n".join(f"[{x.id}] ({x.type}) {x.text}" for x in srcs) or "(aucune source disponible)"


def _check_citations(text: str, srcs: list[Src]) -> tuple[str, list[str]]:
    valid = {x.id for x in srcs}
    cited = set(re.findall(r"\[(S\d+)\]", text))
    notices = []
    bad = cited - valid
    if bad:
        for b in bad:
            text = text.replace(f"[{b}]", "[source inexistante retirée]")
        notices.append("Des citations ne correspondant à aucune source ont été retirées : vérifier la réponse.")
    if srcs and not (cited & valid):
        notices.append("La réponse ne cite aucune source : elle doit être vérifiée avant usage.")
    return text, notices


def _rules_answer(a: Assistant, srcs: list[Src]) -> str:
    if not srcs:
        return "Aucune donnée autorisée ne correspond à la question dans votre périmètre."
    lines = [f"Éléments trouvés dans les données autorisées ({len(srcs)}) :"]
    lines += [f"- {x.text} [{x.id}]" for x in srcs[:15]]
    if a.engines:
        lines.append("Pour un dimensionnement, utiliser les moteurs : " + ", ".join(a.engines) + ".")
    return "\n".join(lines)


def answer(s: Session, p: Principal, a: Assistant, question: str, company_id: int | None, project_id: int | None,
           pref: str, consent: bool) -> Answer:
    cfg = get_settings()
    srcs, missing = collect(s, p, a, question, company_id, project_id)
    notices: list[str] = []

    if a.legal_strict and not any(x.type == "référence juridique" for x in srcs):
        return Answer("garde-fou-juridique",
                      "La base juridique ne contient aucune référence vérifiée et en vigueur correspondant à cette question. "
                      "Je ne peux pas donner de réponse juridique sans source officielle vérifiable (texte, article, date, version, source). "
                      "Faites saisir et vérifier les textes applicables par le juriste dans « Base juridique », puis reposez la question.",
                      srcs, missing + ["Références juridiques vérifiées correspondant à la question."])

    cloud_allowed = p.ai_cloud and cfg.cloud_configured
    confidential = [x for x in srcs if x.confidential or x.type in CONFIDENTIAL_TYPES]
    use_cloud = False
    if pref == "cloud" or (pref == "auto" and complex_request(question)):
        if not cloud_allowed:
            if pref == "cloud":
                notices.append("IA cloud non autorisée pour votre compte ou non configurée : traitement local.")
        elif not (consent and has_consent(s, p)):
            notices.append("IA cloud : consentement non donné pour cette demande, traitement local.")
        elif confidential:
            notices.append(f"{len(confidential)} source(s) confidentielle(s) (finance, RH, documents confidentiels) : "
                           "aucun envoi vers le cloud, traitement local.")
        else:
            use_cloud = True
    if not use_cloud and not p.ai_local:
        return Answer("refus", "L'IA locale n'est pas activée pour votre compte (activation par le Directeur général).", srcs, missing, notices)

    prompt = (f"Question : {question}\n\nSources autorisées :\n{_context(srcs)}\n\n"
              "Réponds à partir de ces sources uniquement, cite [S#], puis termine par « Informations manquantes : … ».")
    redactions = 0
    if use_cloud:
        prompt, redactions = redact(prompt)
        try:
            text = cloud_chat(a.system_prompt, prompt)
            text, extra = _check_citations(text, srcs)
            return Answer("cloud", text, srcs, missing, notices + extra, redactions)
        except ProviderUnavailable as e:
            notices.append(f"{e} : bascule en traitement local.")
            prompt = (f"Question : {question}\n\nSources autorisées :\n{_context(srcs)}\n\n"
                      "Réponds à partir de ces sources uniquement, cite [S#], puis termine par « Informations manquantes : … ».")
    if ollama_available():
        try:
            text = ollama_chat(a.system_prompt, prompt)
            text, extra = _check_citations(text, srcs)
            return Answer("local-llm", text, srcs, missing, notices + extra)
        except ProviderUnavailable as e:
            notices.append(str(e))
    notices.append("Modèle local indisponible : réponse factuelle construite par règles, sans génération.")
    return Answer("local-regles", _rules_answer(a, srcs), srcs, missing, notices)
