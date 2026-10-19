"""Moteur d'autorisations — refus par défaut, moindre privilège, évalué côté serveur à chaque requête.

Règles (documentées dans docs/AUTORISATIONS.md) :
  * Directeur général du groupe : tous les droits, sur les deux filiales. Lui seul attribue des autorisations.
  * Un compte neuf n'a aucun droit métier.
  * company  (filiale)      : tous les modules de la filiale.
  * org_unit (département)  : les modules du département, dans la filiale du département
                              (pour un service commun, la filiale est précisée dans l'autorisation).
  * module                  : un module d'une filiale (ex. finance de eurl medater).
  * project                 : le projet et ses données rattachées (chantiers, études, documents, QHSE).
  * document                : un document précis.
  Actions : view, edit, validate, export. Toute action accordée implique la consultation (view).
  Une autorisation suspendue, révoquée ou expirée ne donne rien.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import false, or_, select, true
from sqlalchemy.orm import Session

from .models import AiSettings, Company, Grant, OrgUnit, User

MODULES = {
    "crm": "Clients et fournisseurs",
    "projects": "Projets",
    "sites": "Chantiers",
    "studies": "Études et coordination",
    "documents": "Documents et BIM",
    "finance": "Finances",
    "procurement": "Achats et stocks",
    "equipment": "Parc matériel",
    "hr": "Ressources humaines",
    "contracts": "Contrats et marchés",
    "qhse": "Qualité et HSE",
    "legal": "Base juridique",
}
PROJECT_BOUND = {"projects", "sites", "studies", "documents", "qhse"}
ACTIONS = ("view", "edit", "validate", "export")


class _OrgCache:
    units: dict[str, OrgUnit] | None = None
    companies: dict[str, int] | None = None

    @classmethod
    def load(cls, s: Session) -> None:
        if cls.units is None:
            units = s.scalars(select(OrgUnit)).all()
            for u in units:
                s.expunge(u)
            cls.units = {u.code: u for u in units}
            cls.companies = {c.code: c.id for c in s.scalars(select(Company)).all()}

    @classmethod
    def clear(cls) -> None:
        cls.units = None
        cls.companies = None


def org_units(s: Session) -> dict[str, OrgUnit]:
    _OrgCache.load(s)
    return _OrgCache.units  # type: ignore[return-value]


def company_ids(s: Session) -> dict[str, int]:
    _OrgCache.load(s)
    return _OrgCache.companies  # type: ignore[return-value]


def _implies(granted: list[str], action: str) -> bool:
    return action in granted or (action == "view" and bool(granted))


@dataclass
class Principal:
    user: User
    session_id: object = None
    grants: list[Grant] = field(default_factory=list)
    ai: AiSettings | None = None
    _units: dict[str, OrgUnit] = field(default_factory=dict)
    _companies: dict[str, int] = field(default_factory=dict)

    @property
    def id(self) -> int:
        return self.user.id

    @property
    def is_director(self) -> bool:
        return bool(self.user.is_group_director)

    # -------------------------------------------------------------- calcul des périmètres
    def companies_for(self, module: str, action: str) -> set[int] | None:
        """Filiales où le module est entièrement accessible. None = toutes (Directeur)."""
        if self.is_director:
            return None
        out: set[int] = set()
        for g in self.grants:
            if not _implies(g.actions, action):
                continue
            if g.scope_type == "company" and g.company_id:
                out.add(g.company_id)
            elif g.scope_type == "module" and g.scope_ref == module and g.company_id:
                out.add(g.company_id)
            elif g.scope_type == "org_unit":
                unit = self._units.get(g.scope_ref)
                if unit and module in (unit.modules or []):
                    cid = self._companies.get(unit.company_code) or g.company_id
                    if cid:
                        out.add(cid)
        return out

    def projects_for(self, module: str, action: str) -> set[int]:
        if module not in PROJECT_BOUND:
            return set()
        return {int(g.scope_ref) for g in self.grants if g.scope_type == "project" and _implies(g.actions, action)}

    def documents_for(self, action: str) -> set[int]:
        return {int(g.scope_ref) for g in self.grants if g.scope_type == "document" and _implies(g.actions, action)}

    def can(self, module: str, action: str, company_id: int | None, project_id: int | None = None,
            document_id: int | None = None) -> bool:
        if self.is_director:
            return True
        comps = self.companies_for(module, action)
        if company_id is not None and company_id in comps:
            return True
        if project_id is not None and project_id in self.projects_for(module, action):
            return True
        if document_id is not None and module == "documents" and document_id in self.documents_for(action):
            return True
        return False

    def require(self, module: str, action: str, company_id: int | None, project_id: int | None = None,
                document_id: int | None = None) -> None:
        if not self.can(module, action, company_id, project_id, document_id):
            raise HTTPException(403, "Accès refusé : autorisation du Directeur général requise")

    def has_module_anywhere(self, module: str, action: str = "view") -> bool:
        if self.is_director:
            return True
        return bool(self.companies_for(module, action)) or bool(self.projects_for(module, action)) or (
            module == "documents" and bool(self.documents_for(action)))

    def scope_clause(self, model, module: str, action: str = "view"):
        """Clause SQL limitant une requête aux lignes autorisées (pour les listes)."""
        if self.is_director:
            return true()
        comps = self.companies_for(module, action)
        conds = []
        if comps:
            conds.append(model.company_id.in_(comps))
        projs = self.projects_for(module, action)
        if projs and hasattr(model, "project_id"):
            conds.append(model.project_id.in_(projs))
        if projs and model.__tablename__ == "projects":
            conds.append(model.id.in_(projs))
        if module == "documents" and model.__tablename__ == "documents":
            docs = self.documents_for(action)
            if docs:
                conds.append(model.id.in_(docs))
        return or_(*conds) if conds else false()

    # -------------------------------------------------------------- IA
    @property
    def ai_local(self) -> bool:
        return bool(self.ai and self.ai.local_enabled)

    @property
    def ai_cloud(self) -> bool:
        return bool(self.ai and self.ai.cloud_enabled)

    def capabilities(self) -> dict:
        """Résumé des modules accessibles, utilisé par l'interface et le siège 3D (l'API reste l'autorité)."""
        ids = {v: k for k, v in self._companies.items()}
        mods = {}
        for m in MODULES:
            comps = self.companies_for(m, "view")
            mods[m] = {
                "all_companies": comps is None,
                "companies": sorted(ids.get(c, str(c)) for c in (comps or [])),
                "projects": sorted(self.projects_for(m, "view")),
                "edit": self.is_director or bool(self.companies_for(m, "edit") or self.projects_for(m, "edit")),
                "validate": self.is_director or bool(self.companies_for(m, "validate") or self.projects_for(m, "validate")),
            }
            mods[m]["any"] = bool(mods[m]["all_companies"] or mods[m]["companies"] or mods[m]["projects"]
                                  or (m == "documents" and self.documents_for("view")))
        return {"modules": mods, "ai_local": self.ai_local, "ai_cloud": self.ai_cloud}


def load_principal(s: Session, user: User, session_id=None) -> Principal:
    now = datetime.now(timezone.utc)
    grants = []
    if not user.is_group_director:
        grants = list(s.scalars(select(Grant).where(
            Grant.user_id == user.id, Grant.status == "active",
            or_(Grant.expires_at.is_(None), Grant.expires_at > now))).all())
    return Principal(user=user, session_id=session_id, grants=grants, ai=s.get(AiSettings, user.id),
                     _units=org_units(s), _companies=company_ids(s))
