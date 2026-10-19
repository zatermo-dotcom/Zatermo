"""Fabrique de routes CRUD sécurisées pour les modules métier.

Chaque ressource déclare :
  * son module d'autorisation (finance, sites, …) ;
  * comment déterminer sa filiale et son projet (directement ou via un parent) ;
  * les références qui doivent appartenir à la même filiale (isolation inter-filiales) ;
  * les champs modifiables.
Pas de suppression : les enregistrements se clôturent ou s'annulent (traçabilité).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .audit import audit
from .authz import Principal
from .db import get_db
from .deps import client_ip, current


def row_dict(obj) -> dict[str, Any]:
    out = {}
    for attr in inspect(obj).mapper.column_attrs:
        v = getattr(obj, attr.key)
        if isinstance(v, Decimal):
            v = float(v)
        out[attr.key.rstrip("_")] = v
    return out


@dataclass
class Parent:
    field: str            # champ de la ressource (ex. site_id)
    model: Any            # modèle parent
    copy: tuple = ()      # champs copiés depuis le parent (ex. ("project_id", "company_id"))


@dataclass
class Resource:
    name: str
    model: Any
    module: str
    create_schema: type[BaseModel]
    patch_schema: Optional[type[BaseModel]] = None
    parent: Optional[Parent] = None
    same_company: dict[str, Any] = field(default_factory=dict)   # champ -> modèle référencé
    filters: tuple[str, ...] = ()
    order_by: Any = None
    author_field: Optional[str] = "created_by"
    before_create: Optional[Callable[[Session, Principal, Any], None]] = None
    serialize: Optional[Callable[[Session, Any, dict], dict]] = None
    validate_on_status: tuple[str, ...] = ()   # statuts dont le passage exige l'action « validate »


def _company_project(r: Resource, obj) -> tuple[int, Optional[int]]:
    return obj.company_id, getattr(obj, "project_id", None)


def _check_refs(s: Session, r: Resource, obj) -> None:
    for fld, model in r.same_company.items():
        ref = getattr(obj, fld, None)
        if ref is None:
            continue
        target = s.get(model, ref)
        if not target:
            raise HTTPException(422, f"{fld} : référence introuvable")
        if getattr(target, "company_id", obj.company_id) != obj.company_id:
            raise HTTPException(422, f"{fld} : la référence appartient à une autre filiale")


def _out(s: Session, r: Resource, obj) -> dict:
    d = row_dict(obj)
    return r.serialize(s, obj, d) if r.serialize else d


def build_router(r: Resource) -> APIRouter:
    router = APIRouter(prefix=f"/{r.name}", tags=[r.module])
    M = r.model

    @router.get("")
    def list_rows(request: Request, p: Principal = Depends(current), s: Session = Depends(get_db), limit: int = 500):
        q = select(M).where(p.scope_clause(M, r.module, "view"))
        for f in r.filters:
            v = request.query_params.get(f)
            if v not in (None, ""):
                col = getattr(M, f)
                q = q.where(col == (int(v) if v.lstrip("-").isdigit() and f.endswith("_id") else v))
        order = r.order_by if r.order_by is not None else M.id.desc()
        q = q.order_by(*(order if isinstance(order, (list, tuple)) else [order])).limit(min(limit, 2000))
        return [_out(s, r, o) for o in s.scalars(q)]

    @router.get("/{row_id}")
    def get_row(row_id: int, p: Principal = Depends(current), s: Session = Depends(get_db)):
        obj = s.get(M, row_id)
        if not obj:
            raise HTTPException(404, "Introuvable")
        cid, pid = _company_project(r, obj)
        p.require(r.module, "view", cid, pid, row_id if r.module == "documents" else None)
        return _out(s, r, obj)

    @router.post("", status_code=201)
    def create_row(data: r.create_schema, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):  # type: ignore[valid-type]
        values = data.model_dump()
        if r.parent:
            parent = s.get(r.parent.model, values.get(r.parent.field))
            if not parent:
                raise HTTPException(422, f"{r.parent.field} : référence introuvable")
            for c in r.parent.copy:
                values[c] = getattr(parent, c) if c != "project_id" or hasattr(parent, "project_id") else parent.id
        obj = M(**values)
        if r.author_field:
            setattr(obj, r.author_field, p.id)
        if getattr(obj, "company_id", None) is None:
            raise HTTPException(422, "Filiale non déterminée")
        p.require(r.module, "edit", obj.company_id, getattr(obj, "project_id", None))
        if r.validate_on_status and getattr(obj, "status", None) in r.validate_on_status:
            p.require(r.module, "validate", obj.company_id, getattr(obj, "project_id", None))
        _check_refs(s, r, obj)
        if r.before_create:
            r.before_create(s, p, obj)
        s.add(obj)
        try:
            s.flush()
        except IntegrityError as e:
            s.rollback()
            raise HTTPException(409, "Conflit : doublon ou référence invalide") from e
        audit(s, p.id, f"{r.name}.created", f"{r.name}:{obj.id}", company_id=obj.company_id, ip=client_ip(request))
        s.commit()
        return _out(s, r, obj)

    if r.patch_schema:
        @router.patch("/{row_id}")
        def patch_row(row_id: int, data: r.patch_schema, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):  # type: ignore[valid-type]
            obj = s.get(M, row_id)
            if not obj:
                raise HTTPException(404, "Introuvable")
            cid, pid = _company_project(r, obj)
            changes = data.model_dump(exclude_unset=True)
            validating = bool(r.validate_on_status) and changes.get("status") in r.validate_on_status
            if validating:
                p.require(r.module, "validate", cid, pid)
            if not validating or set(changes) != {"status"}:
                # Une validation seule n'exige que « validate » ; toute autre modification exige « edit ».
                p.require(r.module, "edit", cid, pid)
            for k, v in changes.items():
                setattr(obj, k, v)
            _check_refs(s, r, obj)
            try:
                s.flush()
            except IntegrityError as e:
                s.rollback()
                raise HTTPException(409, "Conflit : doublon ou référence invalide") from e
            audit(s, p.id, f"{r.name}.updated", f"{r.name}:{obj.id}", company_id=cid,
                  details={k: (str(v) if isinstance(v, (date, datetime, Decimal)) else v) for k, v in changes.items()},
                  ip=client_ip(request))
            s.commit()
            return _out(s, r, obj)

    return router
