"""Documents et BIM : téléversement contrôlé, versionnement, empreinte SHA-256, métadonnées IFC.

Contrôles à l'envoi : extension autorisée, signature binaire (« magic bytes ») cohérente, taille maximale,
nom de fichier assaini, stockage hors de la racine web sous un nom dérivé du hash (jamais du nom fourni).
Téléchargement : action « view » pour un document interne, « export » pour un document confidentiel ou secret.
"""
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..authz import Principal
from ..config import get_settings
from ..crud import row_dict
from ..db import get_db
from ..deps import client_ip, current
from ..models import Document, DocumentVersion, Project

router = APIRouter(prefix="/documents", tags=["documents"])

# extension -> (type MIME servi, signatures acceptées ; None = texte vérifié autrement)
ALLOWED = {
    ".pdf": ("application/pdf", [b"%PDF-"]),
    ".png": ("image/png", [b"\x89PNG\r\n\x1a\n"]),
    ".jpg": ("image/jpeg", [b"\xff\xd8\xff"]),
    ".jpeg": ("image/jpeg", [b"\xff\xd8\xff"]),
    ".dwg": ("application/acad", [b"AC10", b"AC1.", b"AC2."]),
    ".dxf": ("application/dxf", None),
    ".ifc": ("application/x-step", [b"ISO-10303-21"]),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", [b"PK\x03\x04"]),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", [b"PK\x03\x04"]),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", [b"PK\x03\x04"]),
    ".csv": ("text/csv", None),
    ".txt": ("text/plain", None),
}
IFC_ENTITIES = ("IFCPROJECT", "IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY", "IFCSPACE", "IFCWALL", "IFCWALLSTANDARDCASE",
                "IFCSLAB", "IFCCOLUMN", "IFCBEAM", "IFCDOOR", "IFCWINDOW", "IFCSTAIR", "IFCROOF", "IFCPIPESEGMENT",
                "IFCDUCTSEGMENT", "IFCCABLECARRIERSEGMENT", "IFCFLOWTERMINAL", "IFCDISTRIBUTIONELEMENT")


def _safe_name(name: str) -> str:
    base = os.path.basename(name or "fichier")
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" .")
    return base[:150] or "fichier"


def _check_signature(ext: str, head: bytes) -> None:
    sigs = ALLOWED[ext][1]
    if sigs is None:
        try:
            # Le bloc lu peut couper un caractère multioctet à la fin : on ignore les 3 derniers octets.
            head[:-3].decode("utf-8") if len(head) >= 4096 else head.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(415, "Fichier texte invalide (UTF-8 attendu)")
        if b"\x00" in head:
            raise HTTPException(415, "Fichier texte invalide")
        return
    if ext == ".dwg":
        if not head.startswith(b"AC") or not head[2:6].isdigit():
            raise HTTPException(415, "Le contenu ne correspond pas à un fichier DWG")
        return
    if not any(head.startswith(sig) for sig in sigs):
        raise HTTPException(415, f"Le contenu ne correspond pas à l'extension {ext}")


def ifc_metadata(path: Path) -> dict:
    """Lecture en flux de l'en-tête et comptage des entités principales (sans dépendance externe)."""
    meta: dict = {"schema": None, "counts": {}}
    counts = {e: 0 for e in IFC_ENTITIES}
    pattern = re.compile(rb"=\s*(IFC[A-Z0-9]+)\s*\(")
    with open(path, "rb") as fh:
        for raw in fh:
            line = raw.strip()
            if line.startswith(b"FILE_SCHEMA"):
                m = re.search(rb"'([^']+)'", line)
                meta["schema"] = m.group(1).decode(errors="replace") if m else None
            elif line.startswith(b"FILE_NAME"):
                meta["file_name_header"] = line[:300].decode(errors="replace")
            m = pattern.search(line)
            if m:
                ent = m.group(1).decode()
                if ent in counts:
                    counts[ent] += 1
    meta["counts"] = {k: v for k, v in counts.items() if v}
    return meta


def _store(upload: UploadFile, company_id: int) -> tuple[Path, str, int, str, dict]:
    cfg = get_settings()
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, f"Type de fichier non autorisé ({ext or 'sans extension'})")
    limit = cfg.max_upload_mb * 1024 * 1024
    root = Path(cfg.documents_dir)
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    head = b""
    fd, tmp_name = tempfile.mkstemp(dir=root / "tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := upload.file.read(1024 * 1024):
                if not head:
                    head = chunk[:4096]
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"Fichier trop volumineux (maximum {cfg.max_upload_mb} Mo)")
                h.update(chunk)
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "Fichier vide")
        _check_signature(ext, head)
        digest = h.hexdigest()
        final = root / str(company_id) / digest[:2] / f"{digest}{ext}"
        final.parent.mkdir(parents=True, exist_ok=True)
        if final.exists():
            os.remove(tmp_name)
        else:
            os.replace(tmp_name, final)
        meta = ifc_metadata(final) if ext == ".ifc" else {}
        return final, digest, size, ALLOWED[ext][0], meta
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def _doc_out(s: Session, d: Document) -> dict:
    out = row_dict(d)
    out["versions"] = [{k: v for k, v in row_dict(v).items() if k != "storage_path"} for v in s.scalars(
        select(DocumentVersion).where(DocumentVersion.document_id == d.id).order_by(DocumentVersion.version.desc()))]
    return out


@router.get("")
def list_documents(project_id: Optional[int] = None, company_id: Optional[int] = None, discipline: Optional[str] = None,
                   p: Principal = Depends(current), s: Session = Depends(get_db)):
    q = select(Document).where(p.scope_clause(Document, "documents")).order_by(Document.id.desc()).limit(500)
    if project_id:
        q = q.where(Document.project_id == project_id)
    if company_id:
        q = q.where(Document.company_id == company_id)
    if discipline:
        q = q.where(Document.discipline == discipline)
    return [_doc_out(s, d) for d in s.scalars(q)]


@router.post("", status_code=201)
def create_document(request: Request, file: UploadFile = File(...), title: str = Form(..., min_length=2, max_length=200),
                    company_id: Optional[int] = Form(None), project_id: Optional[int] = Form(None),
                    doc_type: Literal["plan", "maquette_ifc", "note_calcul", "rapport", "cctp", "contrat", "courrier", "photo", "autre"] = Form("autre"),
                    discipline: str = Form("GEN", max_length=10),
                    confidentiality: Literal["interne", "confidentiel", "secret"] = Form("interne"),
                    revision_label: str = Form("", max_length=20), comment: str = Form("", max_length=500),
                    p: Principal = Depends(current), s: Session = Depends(get_db)):
    if project_id:
        proj = s.get(Project, project_id)
        if not proj:
            raise HTTPException(404, "Projet introuvable")
        company_id = proj.company_id
    if not company_id:
        raise HTTPException(422, "Préciser le projet ou la filiale")
    p.require("documents", "edit", company_id, project_id)
    path, digest, size, ctype, meta = _store(file, company_id)
    doc = Document(company_id=company_id, project_id=project_id, title=title, doc_type=doc_type, discipline=discipline,
                   confidentiality=confidentiality, current_version=1, created_by=p.id)
    s.add(doc)
    s.flush()
    s.add(DocumentVersion(document_id=doc.id, company_id=company_id, version=1, revision_label=revision_label,
                          filename=_safe_name(file.filename), content_type=ctype, size_bytes=size, sha256=digest,
                          storage_path=str(path), metadata_=meta, comment=comment, uploaded_by=p.id))
    audit(s, p.id, "document.created", f"document:{doc.id}", company_id=company_id,
          details={"sha256": digest, "size": size}, ip=client_ip(request))
    s.commit()
    return _doc_out(s, doc)


@router.post("/{doc_id}/versions", status_code=201)
def add_version(doc_id: int, request: Request, file: UploadFile = File(...), revision_label: str = Form("", max_length=20),
                comment: str = Form("", max_length=500), p: Principal = Depends(current), s: Session = Depends(get_db)):
    doc = s.scalar(select(Document).where(Document.id == doc_id).with_for_update())
    if not doc:
        raise HTTPException(404, "Document introuvable")
    p.require("documents", "edit", doc.company_id, doc.project_id, doc.id)
    path, digest, size, ctype, meta = _store(file, doc.company_id)
    doc.current_version += 1
    s.add(DocumentVersion(document_id=doc.id, company_id=doc.company_id, version=doc.current_version,
                          revision_label=revision_label, filename=_safe_name(file.filename), content_type=ctype,
                          size_bytes=size, sha256=digest, storage_path=str(path), metadata_=meta, comment=comment,
                          uploaded_by=p.id))
    audit(s, p.id, "document.version_added", f"document:{doc.id}", company_id=doc.company_id,
          details={"version": doc.current_version, "sha256": digest}, ip=client_ip(request))
    s.commit()
    return _doc_out(s, doc)


@router.get("/{doc_id}")
def get_document(doc_id: int, p: Principal = Depends(current), s: Session = Depends(get_db)):
    doc = s.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document introuvable")
    p.require("documents", "view", doc.company_id, doc.project_id, doc.id)
    return _doc_out(s, doc)


@router.get("/{doc_id}/versions/{version}/download")
def download(doc_id: int, version: int, request: Request, p: Principal = Depends(current), s: Session = Depends(get_db)):
    doc = s.get(Document, doc_id)
    if not doc:
        raise HTTPException(404, "Document introuvable")
    action = "view" if doc.confidentiality == "interne" else "export"
    p.require("documents", action, doc.company_id, doc.project_id, doc.id)
    v = s.scalar(select(DocumentVersion).where(DocumentVersion.document_id == doc_id, DocumentVersion.version == version))
    if not v or not Path(v.storage_path).is_file():
        raise HTTPException(404, "Version introuvable")
    audit(s, p.id, "document.downloaded", f"document:{doc.id}", company_id=doc.company_id,
          details={"version": version}, ip=client_ip(request))
    s.commit()
    return FileResponse(v.storage_path, media_type=v.content_type, filename=v.filename,
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})
