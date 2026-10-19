"""Règles métier : situations, factures, stock, marchés, livrables, documents."""
import io
import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import companies, new_user


@pytest.fixture
def const(dg):
    cid = companies(dg)["CONST"]
    tag = uuid.uuid4().hex[:8]
    client = dg.post("/api/parties", json={"company_id": cid, "kind": "client", "name": f"OPGI {tag}"}).json()
    supplier = dg.post("/api/parties", json={"company_id": cid, "kind": "fournisseur", "name": f"Cimenterie {tag}"}).json()
    proj = dg.post("/api/projects", json={"company_id": cid, "code": f"R{tag}", "name": "120 logements", "kind": "realisation",
                                          "client_id": client["id"]}).json()
    return {"cid": cid, "client": client["id"], "supplier": supplier["id"], "project": proj["id"], "tag": tag}


def test_situation_figures(dg, const):
    c = dg.post("/api/contracts", json={"company_id": const["cid"], "reference": f"MP-{const['tag']}", "title": "Réalisation 120 logements",
                                        "amount_ht": "10000000", "tva_rate": "19", "retention_rate": "5", "status": "en_cours"}).json()
    s1 = dg.post("/api/situations", json={"contract_id": c["id"], "number": 1, "period_end": "2026-08-31", "cumulative_amount_ht": "2000000"}).json()
    assert s1["period_ht"] == 2000000 and s1["retention"] == 100000 and s1["tva"] == 380000 and s1["net_to_pay"] == 2280000
    s2 = dg.post("/api/situations", json={"contract_id": c["id"], "number": 2, "period_end": "2026-09-30", "cumulative_amount_ht": "3500000"}).json()
    assert s2["previous_cumulative_ht"] == 2000000 and s2["period_ht"] == 1500000 and s2["financial_progress_pct"] == 35.0
    bad = dg.post("/api/situations", json={"contract_id": c["id"], "number": 3, "period_end": "2026-10-31", "cumulative_amount_ht": "1000000"})
    assert bad.status_code == 422


def test_contract_delay_and_penalty(dg, const):
    start = date.today() - timedelta(days=130)
    c = dg.post("/api/contracts", json={"company_id": const["cid"], "reference": f"MD-{const['tag']}", "title": "Marché délai",
                                        "amount_ht": "1000000", "penalty_per_day_rate": "0.1", "penalty_cap_rate": "10",
                                        "ods_start_date": str(start), "duration_days": 100, "status": "en_cours"}).json()
    dg.post("/api/contract-events", json={"contract_id": c["id"], "kind": "avenant", "event_date": str(start + timedelta(days=50)),
                                          "days_delta": 10, "amount_delta": "0"})
    sched = dg.get(f"/api/contracts/{c['id']}").json()["schedule"]
    assert sched["extension_days"] == 10 and sched["delay_days"] == 20
    assert sched["theoretical_penalty"] == pytest.approx(1000000 * 0.001 * 20)


def test_invoice_payments(dg, const):
    inv = dg.post("/api/invoices", json={"company_id": const["cid"], "party_id": const["client"], "direction": "vente", "number": f"F-{const['tag']}",
                                         "issue_date": "2026-09-01", "due_date": "2026-09-30", "amount_ht": "100000", "tva_rate": "19"}).json()
    assert inv["amount_ttc"] == 119000 and inv["balance"] == 119000 and inv["overdue"] is True
    assert dg.post("/api/payments", json={"invoice_id": inv["id"], "paid_date": "2026-10-05", "amount": "50000"}).status_code == 201
    assert dg.post("/api/payments", json={"invoice_id": inv["id"], "paid_date": "2026-10-06", "amount": "70000"}).status_code == 422
    inv = dg.get(f"/api/invoices/{inv['id']}").json()
    assert inv["balance"] == 69000 and inv["payment_status"] == "partielle"
    k = dg.get("/api/dashboard").json()
    const_k = [c for c in k["companies"] if c["code"] == "CONST"][0]["kpis"]["finance"]
    assert const_k["receivables_overdue"] >= 69000


def test_stock_movements(dg, const):
    item = dg.post("/api/stock-items", json={"company_id": const["cid"], "code": f"CIM-{const['tag']}", "name": "Ciment CPJ 42.5",
                                             "unit": "sac", "min_quantity": "100"}).json()
    assert dg.post("/api/stock-movements", json={"item_id": item["id"], "kind": "entree", "quantity": "150"}).status_code == 201
    assert dg.post("/api/stock-movements", json={"item_id": item["id"], "kind": "sortie", "quantity": "200"}).status_code == 422
    assert dg.post("/api/stock-movements", json={"item_id": item["id"], "kind": "sortie", "quantity": "60"}).status_code == 201
    item = dg.get(f"/api/stock-items/{item['id']}").json()
    assert item["quantity"] == 90 and item["below_min"] is True


def test_purchase_order_supplier_kind(dg, const):
    r = dg.post("/api/purchase-orders", json={"company_id": const["cid"], "supplier_id": const["client"], "number": f"BC-{const['tag']}",
                                              "order_date": "2026-10-10"})
    assert r.status_code == 422
    r = dg.post("/api/purchase-orders", json={"company_id": const["cid"], "supplier_id": const["supplier"], "number": f"BC-{const['tag']}",
                                              "order_date": "2026-10-10", "total_ht": "450000"})
    assert r.status_code == 201


def test_deliverable_four_eyes(dg, const):
    pid = const["project"]
    author = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(pid), "actions": ["view", "edit", "validate"]}])
    d = author.post("/api/studies/deliverables", json={"project_id": pid, "discipline": "CFO", "phase": "APD", "title": "Bilan de puissance"}).json()
    assert author.post(f"/api/studies/deliverables/{d['id']}/submit").json()["status"] == "soumis"
    assert author.post(f"/api/studies/deliverables/{d['id']}/review", json={"decision": "valide"}).status_code == 403
    reviewer = new_user(dg, grants=[{"scope_type": "project", "scope_ref": str(pid), "actions": ["validate"]}])
    assert reviewer.post(f"/api/studies/deliverables/{d['id']}/review", json={"decision": "rejete"}).status_code == 422
    r = reviewer.post(f"/api/studies/deliverables/{d['id']}/review", json={"decision": "rejete", "comment": "Réserve manquante"})
    assert r.status_code == 200 and r.json()["status"] == "rejete"


def test_calc_run_saved_and_scoped(dg, const):
    r = dg.post("/api/studies/calc/gc.column", json={"project_id": const["project"], "inputs": {"floors": 5, "tributary_area_m2": 16}})
    assert r.status_code == 200 and r.json()["outputs"]["nu_elu_kn"] > 0 and "id" in r.json()
    bad = dg.post("/api/studies/calc/gc.column", json={"project_id": const["project"], "inputs": {"floors": 0, "tributary_area_m2": 16}})
    assert bad.status_code == 422
    outsider = new_user(dg)
    assert outsider.post("/api/studies/calc/gc.column", json={"project_id": const["project"], "inputs": {"floors": 5, "tributary_area_m2": 16}}).status_code == 403


PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
IFC = (b"ISO-10303-21;\nHEADER;\nFILE_NAME('test.ifc','2026-10-19',(''),(''),'','','');\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
       b"#1=IFCPROJECT('a',$,'P',$,$,$,$,$,$);\n#2=IFCWALL('b',$,$,$,$,$,$,$,$);\n#3=IFCWALL('c',$,$,$,$,$,$,$,$);\n"
       b"#4=IFCDOOR('d',$,$,$,$,$,$,$,$,$,$,$,$);\nENDSEC;\nEND-ISO-10303-21;\n")


def test_documents_upload_controls(dg, const):
    up = lambda name, content, **kw: dg.post("/api/documents", files={"file": (name, io.BytesIO(content))},
                                              data={"title": "Doc test", "project_id": str(const["project"]), **kw})
    r = up("plan.pdf", PDF, doc_type="plan", discipline="ARCH")
    assert r.status_code == 201 and r.json()["versions"][0]["sha256"]
    assert "storage_path" not in r.json()["versions"][0]
    assert up("virus.exe", b"MZ\x90\x00").status_code == 415
    assert up("faux.pdf", b"MZ\x90\x00 pas un pdf").status_code == 415
    ifc = up("maquette.ifc", IFC, doc_type="maquette_ifc")
    meta = ifc.json()["versions"][0]["metadata"]
    assert meta["schema"] == "IFC4" and meta["counts"]["IFCWALL"] == 2 and meta["counts"]["IFCDOOR"] == 1
    doc_id = r.json()["id"]
    v2 = dg.post(f"/api/documents/{doc_id}/versions", files={"file": ("plan-b.pdf", io.BytesIO(PDF + b"\n%rev B"))}, data={"revision_label": "B"})
    assert v2.status_code == 201 and v2.json()["current_version"] == 2
    dl = dg.get(f"/api/documents/{doc_id}/versions/2/download")
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")


def test_confidential_download_needs_export(dg, const):
    r = dg.post("/api/documents", files={"file": ("contrat.pdf", io.BytesIO(PDF))},
                data={"title": "Contrat", "project_id": str(const["project"]), "confidentiality": "confidentiel"}).json()
    viewer = new_user(dg, grants=[{"scope_type": "document", "scope_ref": str(r["id"]), "actions": ["view"]}])
    assert viewer.get(f"/api/documents/{r['id']}").status_code == 200
    assert viewer.get(f"/api/documents/{r['id']}/versions/1/download").status_code == 403
    exporter = new_user(dg, grants=[{"scope_type": "document", "scope_ref": str(r["id"]), "actions": ["export"]}])
    assert exporter.get(f"/api/documents/{r['id']}/versions/1/download").status_code == 200
