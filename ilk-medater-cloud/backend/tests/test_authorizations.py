"""Règle absolue : refus par défaut, seul le DG attribue, isolation entre filiales, granularité, expiration."""
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import companies, new_user


@pytest.fixture
def setup(dg):
    """Un projet et un tiers dans chaque filiale."""
    ids = companies(dg)
    data = {}
    for code in ("CONST", "ARCH"):
        sfx = datetime.now().strftime("%H%M%S%f")
        party = dg.post("/api/parties", json={"company_id": ids[code], "kind": "client", "name": f"Client {code} {sfx}"}).json()
        proj = dg.post("/api/projects", json={"company_id": ids[code], "code": f"P{sfx}", "name": f"Projet {code}",
                                              "client_id": party["id"], "kind": "mixte"}).json()
        data[code] = {"company": ids[code], "party": party["id"], "project": proj["id"]}
    return data


def test_new_account_has_zero_rights(dg, setup):
    u = new_user(dg)
    me = u.get("/api/auth/me").json()
    assert not any(m["any"] for m in me["modules"].values())
    assert me["ai_local"] is False and me["ai_cloud"] is False
    assert u.get("/api/projects").json() == []
    assert u.get("/api/invoices").json() == []
    assert u.get(f"/api/projects/{setup['CONST']['project']}").status_code == 403
    assert u.post("/api/projects", json={"company_id": setup["CONST"]["company"], "code": "X1", "name": "Interdit"}).status_code == 403
    assert u.get("/api/dashboard").json()["companies"] == []
    assert all(not o["accessible"] for o in u.get("/api/building").json()["offices"])


def test_company_grant_is_isolated(dg, setup):
    u = new_user(dg, grants=[{"scope_type": "company", "scope_ref": "CONST", "actions": ["view", "edit"]}])
    ids = {p["id"] for p in u.get("/api/projects").json()}
    assert setup["CONST"]["project"] in ids and setup["ARCH"]["project"] not in ids
    assert u.get(f"/api/projects/{setup['ARCH']['project']}").status_code == 403
    assert u.post("/api/projects", json={"company_id": setup["ARCH"]["company"], "code": "ZZ", "name": "Autre filiale"}).status_code == 403
    # Référence croisée : un client du cabinet ILK ne peut pas être facturé par eurl medater
    r = u.post("/api/invoices", json={"company_id": setup["CONST"]["company"], "party_id": setup["ARCH"]["party"],
                                      "direction": "vente", "number": "F-X", "issue_date": "2026-10-01", "amount_ht": "100"})
    assert r.status_code == 422 and "autre filiale" in r.json()["detail"]
    dash = u.get("/api/dashboard").json()
    assert [c["code"] for c in dash["companies"]] == ["CONST"] and "consolidated_finance" not in dash


def test_view_only_cannot_edit(dg, setup):
    u = new_user(dg, grants=[{"scope_type": "module", "scope_ref": "projects", "company_id": setup["CONST"]["company"], "actions": ["view"]}])
    assert u.get(f"/api/projects/{setup['CONST']['project']}").status_code == 200
    assert u.patch(f"/api/projects/{setup['CONST']['project']}", json={"name": "Modifié"}).status_code == 403
    assert u.get("/api/invoices").json() == []  # module finance non accordé


def test_project_grant_covers_project_data_only(dg, setup):
    pid = setup["CONST"]["project"]
    site = dg.post("/api/sites", json={"project_id": pid, "name": "Chantier A"}).json()
    other = dg.post("/api/projects", json={"company_id": setup["CONST"]["company"], "code": "AUTRE" + str(pid), "name": "Autre"}).json()
    u = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(pid), "actions": ["view", "edit"]}])
    assert {p["id"] for p in u.get("/api/projects").json()} == {pid}
    assert [s["id"] for s in u.get("/api/sites").json()] == [site["id"]]
    assert u.post("/api/daily-reports", json={"site_id": site["id"], "report_date": "2026-10-19", "work_done": "Coulage dalle R+1"}).status_code == 201
    assert u.post("/api/sites", json={"project_id": other["id"], "name": "Hors périmètre"}).status_code == 403
    offices = {o["code"]: o["accessible"] for o in u.get("/api/building").json()["offices"]}
    assert offices["CONST-SITE"] is True and offices["ARCH-ARC"] is False and offices["ARCH-FIN"] is False
    assert u.post("/api/invoices", json={"company_id": setup["CONST"]["company"], "party_id": setup["CONST"]["party"],
                                         "direction": "vente", "number": "F-P", "issue_date": "2026-10-01", "amount_ht": "1"}).status_code == 403


def test_org_unit_grant(dg, setup):
    # Département de filiale : la filiale est implicite
    u = new_user(dg, grants=[{"scope_type": "org_unit", "scope_ref": "CONST-FIN", "actions": ["view"]}])
    caps = u.get("/api/auth/me").json()["modules"]
    assert caps["finance"]["companies"] == ["CONST"] and caps["contracts"]["companies"] == ["CONST"]
    assert caps["hr"]["any"] is False and caps["projects"]["any"] is False
    # Plus de service commun porteur de données : RH par filiale
    r = dg.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "org_unit", "scope_ref": "SHARED-HR",
                                           "company_id": setup["CONST"]["company"], "actions": ["view"]})
    assert r.status_code == 422
    r = dg.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "org_unit", "scope_ref": "CONST-HR", "actions": ["view"]})
    assert r.status_code == 201
    assert u.get("/api/auth/me").json()["modules"]["hr"]["companies"] == ["CONST"]


def test_suspend_expire_revoke(dg, setup):
    u = new_user(dg, company="ARCH")
    g = dg.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "company", "scope_ref": "ARCH", "actions": ["view"]}).json()
    assert len(u.get("/api/projects").json()) >= 1
    dg.patch(f"/api/admin/grants/{g['id']}", json={"status": "suspended"})
    assert u.get("/api/projects").json() == []
    dg.patch(f"/api/admin/grants/{g['id']}", json={"status": "active"})
    assert len(u.get("/api/projects").json()) >= 1
    soon = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    assert dg.patch(f"/api/admin/grants/{g['id']}", json={"expires_at": soon}).status_code == 200
    import time
    time.sleep(2.5)
    assert u.get("/api/projects").json() == []
    dg.patch(f"/api/admin/grants/{g['id']}", json={"clear_expiry": True})
    assert dg.patch(f"/api/admin/grants/{g['id']}", json={"status": "revoked"}).status_code == 200
    assert u.get("/api/projects").json() == []
    assert dg.patch(f"/api/admin/grants/{g['id']}", json={"status": "active"}).status_code == 409


def test_grant_validation(dg, setup):
    u = new_user(dg)
    base = {"user_id": u.user_id, "actions": ["view"]}
    assert dg.post("/api/admin/grants", json={**base, "scope_type": "module", "scope_ref": "inconnu", "company_id": 1}).status_code == 422
    assert dg.post("/api/admin/grants", json={**base, "scope_type": "module", "scope_ref": "finance"}).status_code == 422
    assert dg.post("/api/admin/grants", json={**base, "scope_type": "project", "scope_ref": "999999"}).status_code == 422
    assert dg.post("/api/admin/grants", json={**base, "scope_type": "company", "scope_ref": "CONST", "actions": ["delete"]}).status_code == 422
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert dg.post("/api/admin/grants", json={**base, "scope_type": "company", "scope_ref": "CONST", "expires_at": past}).status_code == 422
    director_id = [x for x in dg.get("/api/admin/users").json() if x["is_group_director"]][0]["id"]
    assert dg.post("/api/admin/grants", json={**base, "user_id": director_id, "scope_type": "company", "scope_ref": "CONST"}).status_code == 422


def test_validate_action_required(dg, setup):
    cid = setup["CONST"]["company"]
    contract = dg.post("/api/contracts", json={"company_id": cid, "reference": "M-" + str(setup["CONST"]["project"]), "title": "Marché test",
                                               "amount_ht": "1000000", "status": "en_cours"}).json()
    editor = new_user(dg, grants=[{"scope_type": "module", "scope_ref": "contracts", "company_id": cid, "actions": ["view", "edit"]}])
    sit = editor.post("/api/situations", json={"contract_id": contract["id"], "number": 1, "period_end": "2026-09-30",
                                                "cumulative_amount_ht": "200000"})
    assert sit.status_code == 201
    assert editor.patch(f"/api/situations/{sit.json()['id']}", json={"status": "validee"}).status_code == 403
    validator = new_user(dg, grants=[{"scope_type": "module", "scope_ref": "contracts", "company_id": cid, "actions": ["validate"]}])
    assert validator.patch(f"/api/situations/{sit.json()['id']}", json={"status": "validee"}).status_code == 200
