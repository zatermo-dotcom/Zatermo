"""Décision de la Direction : la gestion financière de chaque filiale est séparée (aucun mélange, aucune consolidation)."""
import psycopg
import pytest

from tests.conftest import companies, new_user


def test_no_consolidation_on_dashboard(dg):
    d = dg.get("/api/dashboard").json()
    assert "consolidated_finance" not in d
    assert {c["code"] for c in d["companies"]} == {"CONST", "ARCH"}  # chaque filiale reste présentée à part


def test_finance_access_limited_to_one_company(dg):
    ids = companies(dg)
    u = new_user(dg, grants=[{"scope_type": "module", "scope_ref": "finance", "company_id": ids["CONST"], "actions": ["view", "edit"]}])
    for body in ({"scope_type": "module", "scope_ref": "finance", "company_id": ids["ARCH"]},
                 {"scope_type": "company", "scope_ref": "ARCH"},
                 {"scope_type": "org_unit", "scope_ref": "ARCH-FIN"}):
        r = dg.post("/api/admin/grants", json={"user_id": u.user_id, "actions": ["view"], **body})
        assert r.status_code == 422 and "séparée" in r.json()["detail"]
    assert u.get("/api/auth/me").json()["modules"]["finance"]["companies"] == ["CONST"]


def test_suspended_grant_does_not_open_other_company(dg):
    ids = companies(dg)
    u = new_user(dg)
    g1 = dg.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "module", "scope_ref": "finance",
                                            "company_id": ids["CONST"], "actions": ["view"]}).json()
    dg.patch(f"/api/admin/grants/{g1['id']}", json={"status": "suspended"})
    g2 = dg.post("/api/admin/grants", json={"user_id": u.user_id, "scope_type": "module", "scope_ref": "finance",
                                            "company_id": ids["ARCH"], "actions": ["view"]})
    assert g2.status_code == 422


def test_each_subsidiary_has_its_own_finance_department(dg):
    ids = companies(dg)
    units = {u["code"]: u for u in dg.get("/api/admin/catalog").json()["org_units"]}
    assert "SHARED-FIN" not in units and "SHARED-EXEC" not in units
    assert units["ARCH-FIN"]["company_code"] == "ARCH" and units["CONST-FIN"]["company_code"] == "CONST"
    r = dg.post("/api/admin/grants", json={"user_id": new_user(dg).user_id, "scope_type": "org_unit", "scope_ref": "SHARED-FIN",
                                           "company_id": ids["ARCH"], "actions": ["view"]})
    assert r.status_code == 422
    u = new_user(dg, grants=[{"scope_type": "org_unit", "scope_ref": "ARCH-FIN", "actions": ["view"]}], company="ARCH")
    assert u.get("/api/auth/me").json()["modules"]["finance"]["companies"] == ["ARCH"]
    offices = {o["code"] for o in dg.get("/api/building").json()["offices"]}
    assert "ARCH-FIN" in offices and "SHARED-FIN" not in offices


def test_database_refuses_cross_company_entries(dg, owner_db):
    ids = companies(dg)
    arch_party = dg.post("/api/parties", json={"company_id": ids["ARCH"], "kind": "client", "name": "Client cabinet séparé"}).json()
    with pytest.raises(psycopg.errors.RaiseException, match="même filiale"):
        owner_db.execute("INSERT INTO invoices(company_id, party_id, direction, number, issue_date, amount_ht) "
                         "VALUES (%s, %s, 'vente', 'X-SEP-1', '2026-10-01', 100)", (ids["CONST"], arch_party["id"]))


def test_ai_requires_company_for_finance(dg):
    ids = companies(dg)
    party = dg.post("/api/parties", json={"company_id": ids["ARCH"], "kind": "client", "name": "Client IA cabinet"}).json()
    dg.post("/api/invoices", json={"company_id": ids["ARCH"], "party_id": party["id"], "direction": "vente", "number": "IA-SEP-1",
                                   "issue_date": "2026-01-01", "due_date": "2026-02-01", "amount_ht": "1000"})
    r = dg.post("/api/ai/ask", json={"assistant": "finance", "question": "Quelles factures sont échues ?"}).json()
    assert not any(s["type"] == "facture" for s in r["sources"])
    assert any("séparés" in m for m in r["missing_information"])
    r = dg.post("/api/ai/ask", json={"assistant": "finance", "question": "Quelles factures sont échues ?", "company_id": ids["ARCH"]}).json()
    factures = [s for s in r["sources"] if s["type"] == "facture"]
    assert factures and all(s["label"] != "" for s in factures)
    inv_ids = {int(s["ref"].split(":")[1]) for s in factures}
    for i in inv_ids:
        assert dg.get(f"/api/invoices/{i}").json()["company_id"] == ids["ARCH"]
