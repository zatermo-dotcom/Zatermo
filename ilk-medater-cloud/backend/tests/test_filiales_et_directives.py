"""Gestion séparée de A à Z : un intervenant appartient à une seule filiale ; directives de la Direction générale par projet."""
import psycopg
import pytest

from tests.conftest import companies, make_client, new_user


@pytest.fixture
def projs(dg):
    import uuid
    ids = companies(dg)
    out = {}
    for code in ("CONST", "ARCH"):
        r = dg.post("/api/projects", json={"company_id": ids[code], "code": f"D{uuid.uuid4().hex[:6]}", "name": f"Projet {code}"})
        assert r.status_code == 201
        out[code] = r.json()["id"]
    return ids, out


def test_account_requires_company_and_matching_department(dg):
    ids = companies(dg)
    base = {"full_name": "Sans filiale", "temporary_password": "Temporaire-2026!"}
    assert dg.post("/api/admin/users", json={**base, "email": "sansfiliale@ilk-medater.dz"}).status_code == 422
    r = dg.post("/api/admin/users", json={**base, "email": "mauvaisdep@ilk-medater.dz", "company_id": ids["CONST"], "org_unit_code": "ARCH-GC"})
    assert r.status_code == 422 and "autre filiale" in r.json()["detail"]
    r = dg.post("/api/admin/users", json={**base, "email": "dgdept@ilk-medater.dz", "company_id": ids["CONST"], "org_unit_code": "SHARED-EXEC"})
    assert r.status_code == 422


def test_no_access_outside_own_company(dg, projs, owner_db):
    ids, p = projs
    u = new_user(dg, company="ARCH")
    for body in ({"scope_type": "company", "scope_ref": "CONST"}, {"scope_type": "project", "scope_ref": str(p["CONST"])},
                 {"scope_type": "org_unit", "scope_ref": "CONST-SITE"}, {"scope_type": "module", "scope_ref": "hr", "company_id": ids["CONST"]}):
        r = dg.post("/api/admin/grants", json={"user_id": u.user_id, "actions": ["view"], **body})
        assert r.status_code == 422 and "Filiales séparées" in r.json()["detail"]
    assert dg.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "project", "scope_ref": str(p["ARCH"]),
                                              "actions": ["view"]}).status_code == 201
    # La base refuse aussi, même si l'API était contournée
    did = owner_db.execute("SELECT id FROM users WHERE is_group_director").fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException, match="Filiales séparées"):
        owner_db.execute("INSERT INTO grants(user_id, company_id, scope_type, scope_ref, actions, granted_by, changed_by) "
                         "VALUES (%s, %s, 'company', %s, '{view}', %s, %s)", (u.user_id, ids["CONST"], str(ids["CONST"]), did, did))


def test_changing_company_requires_revoking_grants(dg, projs):
    ids, p = projs
    u = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(p["CONST"]), "actions": ["view"]}])
    assert dg.patch(f"/api/admin/users/{u.user_id}", json={"company_id": ids["ARCH"]}).status_code == 409
    g = [x for x in dg.get("/api/admin/users").json() if x["id"] == u.user_id][0]["grants"][0]
    dg.patch(f"/api/admin/grants/{g['id']}", json={"status": "revoked"})
    assert dg.patch(f"/api/admin/users/{u.user_id}", json={"company_id": ids["ARCH"]}).status_code == 200
    assert u.get("/api/auth/me").json()["company_id"] == ids["ARCH"]


def test_only_director_sees_both(dg, projs):
    ids, p = projs
    u = new_user(dg, grants=[{"scope_type": "company", "scope_ref": "CONST", "actions": ["view", "edit"]}])
    assert {c["code"] for c in u.get("/api/dashboard").json()["companies"]} == {"CONST"}
    assert {c["code"] for c in dg.get("/api/dashboard").json()["companies"]} == {"CONST", "ARCH"}
    offices = {o["code"]: o["accessible"] for o in u.get("/api/building").json()["offices"]}
    assert offices["SHARED-EXEC"] is False and offices["CONST-DIR"] is True and offices["ARCH-DIR"] is False
    assert not any(o["code"] in ("SHARED-HR", "SHARED-LEGAL", "SHARED-FIN") for o in dg.get("/api/building").json()["offices"])


def test_directive_lifecycle(dg, projs):
    ids, p = projs
    chef = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(p["CONST"]), "actions": ["view", "edit"]}])
    lecteur = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(p["CONST"]), "actions": ["view"]}])
    autre = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(p["ARCH"]), "actions": ["view", "edit"]}], company="ARCH")
    # Seule la Direction générale émet
    assert chef.post("/api/directives", json={"project_id": p["CONST"], "title": "Interdit", "instructions": "x" * 5}).status_code == 403
    d = dg.post("/api/directives", json={"project_id": p["CONST"], "title": "Accélérer le gros œuvre bloc A",
                                         "instructions": "Renforcer l'équipe de coffrage et livrer la dalle R+3 avant le 15/11.",
                                         "priority": "haute", "due_date": "2026-11-15"}).json()
    assert d["status"] == "emise" and d["company_id"] == ids["CONST"]
    # Visibilité : équipe du projet oui, autre filiale non
    assert [x["id"] for x in chef.get("/api/directives").json()] == [d["id"]]
    assert autre.get("/api/directives").json() == []
    assert autre.get(f"/api/directives/{d['id']}").status_code == 403
    # Compte rendu par l'équipe
    assert lecteur.post(f"/api/directives/{d['id']}/updates", json={"note": "Lu", "new_status": "accusee"}).status_code == 403
    assert chef.post(f"/api/directives/{d['id']}/updates", json={"note": "Reçue, équipe renforcée lundi", "new_status": "accusee"}).status_code == 201
    assert chef.post(f"/api/directives/{d['id']}/updates", json={"note": "Dalle coulée", "new_status": "realisee"}).json()["status"] == "realisee"
    assert chef.post(f"/api/directives/{d['id']}/updates", json={"note": "Je clôture", "new_status": "cloturee"}).status_code == 403
    # Clôture par la Direction générale
    r = dg.post(f"/api/directives/{d['id']}/updates", json={"note": "Constaté sur site, clôturé", "new_status": "cloturee"}).json()
    assert r["status"] == "cloturee" and [u["new_status"] for u in r["updates"]] == ["accusee", "realisee", "cloturee"]
    assert "Direction générale" in r["updates"][-1]["author"]
    assert chef.post(f"/api/directives/{d['id']}/updates", json={"note": "Ajout", "new_status": "en_cours"}).status_code == 409


def test_directive_db_guard(dg, projs, owner_db):
    ids, p = projs
    u = new_user(dg)
    with pytest.raises(psycopg.errors.RaiseException, match="Direction générale"):
        owner_db.execute("INSERT INTO directives(company_id, project_id, title, instructions, issued_by) VALUES (%s,%s,'t','i',%s)",
                         (ids["CONST"], p["CONST"], u.user_id))
    did = owner_db.execute("SELECT id FROM users WHERE is_group_director").fetchone()[0]
    with pytest.raises(psycopg.errors.RaiseException, match="filiale"):
        owner_db.execute("INSERT INTO directives(company_id, project_id, title, instructions, issued_by) VALUES (%s,%s,'t','i',%s)",
                         (ids["CONST"], p["ARCH"], did))


def test_directives_on_dashboard_and_ai(dg, projs):
    ids, p = projs
    dg.post("/api/directives", json={"project_id": p["ARCH"], "title": "Rendre l'APD hôtel", "instructions": "Rendu complet au client.",
                                     "due_date": "2026-01-15"})
    arch = [c for c in dg.get("/api/dashboard").json()["companies"] if c["code"] == "ARCH"][0]
    assert arch["kpis"]["directives"]["open"] >= 1 and arch["kpis"]["directives"]["overdue"] >= 1
    r = dg.post("/api/ai/ask", json={"assistant": "direction", "question": "Quelles directives sont en retard ?"}).json()
    assert any(s["type"] == "directive DG" for s in r["sources"])
