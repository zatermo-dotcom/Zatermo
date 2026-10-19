"""Écriture du journal d'audit via la fonction SQL audit_append (chaînage SHA-256, ajout seul)."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def audit(s: Session, actor_id: int | None, action: str, resource: str = "", company_id: int | None = None,
          details: dict[str, Any] | None = None, ip: str | None = None) -> None:
    """Ajoute un événement dans la transaction courante (annulé si la transaction échoue)."""
    s.execute(
        text("SELECT audit_append(:a, :act, :res, :c, CAST(:d AS jsonb), :ip)"),
        {"a": actor_id, "act": action, "res": resource, "c": company_id,
         "d": json.dumps(details or {}, ensure_ascii=False, default=str), "ip": ip},
    )
