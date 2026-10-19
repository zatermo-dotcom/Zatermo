"""ilk.medater AI : activation par le DG, périmètre des sources, garde-fou juridique, routage cloud/local."""
import pytest

from app.ai.redact import redact
from tests.conftest import companies, new_user


@pytest.fixture
def two_projects(dg):
    ids = companies(dg)
    a = dg.post("/api/projects", json={"company_id": ids["CONST"], "code": "IA-C1", "name": "Hôpital Tiaret", "planned_end_date": "2026-01-31"})
    b = dg.post("/api/projects", json={"company_id": ids["ARCH"], "code": "IA-A1", "name": "Hôtel Oran"})
    if a.status_code == 409:  # fixture réutilisée dans la même base
        return ids
    assert a.status_code == 201 and b.status_code == 201
    return ids


def test_ai_disabled_by_default(dg, two_projects):
    u = new_user(dg, grants=[{"scope_type": "company", "scope_ref": "CONST", "actions": ["view"]}])
    r = u.post("/api/ai/ask", json={"assistant": "direction", "question": "Quels projets sont en retard ?"})
    assert r.status_code == 403


def test_ai_only_sees_authorized_data(dg, two_projects):
    u = new_user(dg, grants=[{"scope_type": "module", "scope_ref": "projects", "company_id": two_projects["CONST"], "actions": ["view"]}],
                 ai={"local_enabled": True, "cloud_enabled": False})
    r = u.post("/api/ai/ask", json={"assistant": "direction", "question": "Liste des projets en retard"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["engine"] == "local-regles"
    labels = " ".join(s["label"] for s in body["sources"])
    assert "Hôpital Tiaret" in labels and "Hôtel Oran" not in labels and "EN RETARD" in body["answer"]
    assert any("non autorisé" in m for m in body["missing_information"])


def test_ai_assistant_without_module_refused(dg, two_projects):
    u = new_user(dg, grants=[{"scope_type": "module", "scope_ref": "projects", "company_id": two_projects["CONST"], "actions": ["view"]}],
                 ai={"local_enabled": True, "cloud_enabled": False})
    assert u.post("/api/ai/ask", json={"assistant": "rh", "question": "Effectif actuel ?"}).status_code == 403


def test_legal_guard_without_verified_source(dg):
    r = dg.post("/api/ai/ask", json={"assistant": "juridique", "question": "Quel est le délai de notification d'un avenant ?"})
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "garde-fou-juridique" and "aucune référence vérifiée" in body["answer"]


def test_legal_source_cited_only_when_verified(dg):
    src = dg.post("/api/legal/sources", json={"text_type": "decret_presidentiel", "title": "Texte de test sur les avenants",
                                              "reference_number": "TEST-0001", "article": "1", "keywords": ["avenant"],
                                              "excerpt": "Extrait saisi pour le test."}).json()
    r = dg.post("/api/ai/ask", json={"assistant": "juridique", "question": "Règles applicables à un avenant"}).json()
    assert r["engine"] == "garde-fou-juridique"  # non vérifiée : jamais citée
    assert dg.post(f"/api/legal/sources/{src['id']}/verify").status_code == 422  # pas de source officielle
    # La vérification exige une source officielle ; on la renseigne directement en base pour le test.
    from app.db import SessionLocal
    from app.models import LegalSource
    with SessionLocal() as s:
        s.get(LegalSource, src["id"]).source_url = "https://www.joradp.dz/"
        s.commit()
    assert dg.post(f"/api/legal/sources/{src['id']}/verify").status_code == 200
    r = dg.post("/api/ai/ask", json={"assistant": "juridique", "question": "Règles applicables à un avenant"}).json()
    assert r["engine"] == "local-regles" and any(s["ref"] == f"legal:{src['id']}" for s in r["sources"])


def test_cloud_never_receives_confidential_data(dg, two_projects, monkeypatch):
    from app.ai import engine
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "cloud_ai_provider", "anthropic")
    monkeypatch.setattr(get_settings(), "cloud_ai_api_key", "test-key")
    calls = []
    monkeypatch.setattr(engine, "cloud_chat", lambda system, prompt: calls.append(prompt) or "Réponse [S1]")
    ids = two_projects
    party = dg.post("/api/parties", json={"company_id": ids["CONST"], "kind": "client", "name": "Client confidentiel"}).json()
    dg.post("/api/invoices", json={"company_id": ids["CONST"], "party_id": party["id"], "direction": "vente", "number": "IA-F1",
                                   "issue_date": "2026-01-01", "due_date": "2026-02-01", "amount_ht": "500000"})
    u = new_user(dg, grants=[{"scope_type": "company", "scope_ref": "CONST", "actions": ["view"]}],
                 ai={"local_enabled": True, "cloud_enabled": True})
    assert u.post("/api/ai/consent").status_code == 200
    r = u.post("/api/ai/ask", json={"assistant": "finance", "question": "Analyse détaillée des créances", "engine": "cloud",
                                    "cloud_consent": True}).json()
    assert calls == [] and r["engine"] == "local-regles"
    assert any("confidentielle" in n for n in r["notices"])
    # Sans données confidentielles et avec consentement, le cloud est utilisé, après masquage.
    r = u.post("/api/ai/ask", json={"assistant": "chantier", "question": "Rédige une synthèse, contact chef@medater.dz 0550 12 34 56",
                                    "engine": "cloud", "cloud_consent": True}).json()
    assert r["engine"] == "cloud" and len(calls) == 1
    assert "chef@medater.dz" not in calls[0] and "0550 12 34 56" not in calls[0]


def test_cloud_requires_consent(dg, two_projects, monkeypatch):
    from app.ai import engine
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "cloud_ai_provider", "anthropic")
    monkeypatch.setattr(get_settings(), "cloud_ai_api_key", "test-key")
    monkeypatch.setattr(engine, "cloud_chat", lambda *a: pytest.fail("cloud appelé sans consentement"))
    u = new_user(dg, grants=[{"scope_type": "company", "scope_ref": "CONST", "actions": ["view"]}],
                 ai={"local_enabled": True, "cloud_enabled": True})
    r = u.post("/api/ai/ask", json={"assistant": "chantier", "question": "Synthèse", "engine": "cloud", "cloud_consent": True}).json()
    assert r["engine"] == "local-regles" and any("consentement" in n for n in r["notices"])


def test_invented_citations_removed(dg, two_projects, monkeypatch):
    from app.ai import engine
    monkeypatch.setattr(engine, "ollama_available", lambda: True)
    monkeypatch.setattr(engine, "ollama_chat", lambda system, prompt: "Le projet est en retard [S1] selon [S99].")
    r = dg.post("/api/ai/ask", json={"assistant": "direction", "question": "Projets en retard"}).json()
    assert r["engine"] == "local-llm" and "[S99]" not in r["answer"] and "[S1]" in r["answer"]
    assert any("retirées" in n for n in r["notices"])


def test_redaction():
    text, n = redact("Mail a.b@x.dz, tel +213 661 23 45 67, RIB 00799999000123456789, NIF 000016001234567")
    assert n == 4 and "@" not in text and "00799999000123456789" not in text
