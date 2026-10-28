"""Comprehensive test suite for the Contract Execution and Payments Module."""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.execution import PagoContrato
from app.models.contract import Contrato
from app.models.contractor import Contratista

client = TestClient(app)

def test_execution_database_integrity():
    """Verify that all 148 payment records are seeded and correctly linked with retenciones."""
    db = SessionLocal()
    try:
        count = db.query(PagoContrato).count()
        assert count == 148, f"Expected 148 payments, found {count}"

        # Verify linkages
        with_contract = db.query(PagoContrato).filter(PagoContrato.contrato_id.isnot(None)).count()
        with_contractor = db.query(PagoContrato).filter(PagoContrato.contratista_id.isnot(None)).count()
        assert with_contract == 148, f"Expected 148 linked to contracts, found {with_contract}"
        assert with_contractor == 148, f"Expected 148 linked to contractors, found {with_contractor}"

        # Check total sums
        from sqlalchemy import func
        total_orden = float(db.query(func.sum(PagoContrato.total_orden)).scalar() or 0)
        total_ret = float(db.query(func.sum(PagoContrato.total_retencion)).scalar() or 0)
        total_estampillas = float(db.query(func.sum(PagoContrato.total_estampillas)).scalar() or 0)
        total_pagar = float(db.query(func.sum(PagoContrato.total_pagar)).scalar() or 0)

        assert abs(total_orden - 843400523.86) < 0.1, f"Total orden mismatch: {total_orden}"
        assert abs(total_ret - 56290367.10) < 0.1, f"Total retencion mismatch: {total_ret}"
        assert abs(total_estampillas - 35080106.30) < 0.1, f"Total estampillas mismatch: {total_estampillas}"
        assert abs(total_pagar - 787110156.76) < 0.1, f"Total pagar mismatch: {total_pagar}"

        # Verify all 148 have retenciones_detalle populated
        with_ret_details = db.query(PagoContrato).filter(PagoContrato.retenciones_detalle.isnot(None)).count()
        assert with_ret_details == 148, f"Expected 148 with retenciones_detalle, found {with_ret_details}"
    finally:
        db.close()

def test_execution_summary_endpoint():
    """Verify the /api/execution/summary endpoint returns complete metrics with estampillas and breakdown."""
    res = client.get("/api/execution/summary?vigencia=2026")
    assert res.status_code == 200
    data = res.json()
    assert data["total_contratos"] > 0
    assert data["conteo_comprobantes"] == 148
    assert abs(data["total_ejecutado"] - 843400523.86) < 1.0
    assert abs(data["total_retenciones"] - 56290367.10) < 1.0
    assert abs(data["total_estampillas"] - 35080106.30) < 1.0
    assert abs(data["total_neto_pagado"] - 787110156.76) < 1.0
    assert data["porcentaje_ejecucion_global"] > 40.0
    assert len(data["rubros"]) > 0
    assert len(data["meses"]) > 0
    assert len(data["top_contratistas"]) > 0
    assert "retenciones_breakdown" in data
    assert len(data["retenciones_breakdown"]) >= 5
    # Verify estampillas flag is present in breakdown
    estampillas_items = [it for it in data["retenciones_breakdown"] if it["es_estampilla"]]
    assert len(estampillas_items) >= 4

def test_execution_contractors_endpoint():
    """Verify the /api/execution/contractors endpoint."""
    res = client.get("/api/execution/contractors?vigencia=2026")
    assert res.status_code == 200
    contractors = res.json()
    assert len(contractors) > 0
    
    # Check that highest executed contractor is at the top
    assert contractors[0]["total_ejecutado"] >= contractors[-1]["total_ejecutado"]
    assert "total_estampillas" in contractors[0]

    # Pick first contractor and test detail endpoint
    first_id = contractors[0]["id"]
    res_detail = client.get(f"/api/execution/contractors/{first_id}?vigencia=2026")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["id"] == first_id
    assert "total_estampillas" in detail
    assert "contratos" in detail
    assert "pagos" in detail

def test_execution_contracts_endpoint():
    """Verify the /api/execution/contracts endpoint."""
    res = client.get("/api/execution/contracts?vigencia=2026")
    assert res.status_code == 200
    contracts = res.json()
    assert len(contracts) > 0
    assert "total_estampillas" in contracts[0]
    
    first_cid = contracts[0]["id"]
    res_ct_detail = client.get(f"/api/execution/contracts/{first_cid}")
    assert res_ct_detail.status_code == 200
    ct_data = res_ct_detail.json()
    assert "contrato" in ct_data
    assert "metricas" in ct_data
    assert "total_estampillas" in ct_data["metricas"]
    assert "pagos" in ct_data

def test_execution_payments_endpoint():
    """Verify the /api/execution/payments endpoint with search and pagination."""
    res = client.get("/api/execution/payments?limit=10")
    assert res.status_code == 200
    pagos = res.json()
    assert len(pagos) == 10
    assert "total_estampillas" in pagos[0]
    assert "retenciones_detalle" in pagos[0]
    
    # Search by voucher code
    sample_ce = pagos[0]["codigo_egreso"]
    res_search = client.get(f"/api/execution/payments?query={sample_ce}")
    assert res_search.status_code == 200
    search_results = res_search.json()
    assert len(search_results) >= 1
    assert search_results[0]["codigo_egreso"] == sample_ce

def test_execution_export_csv():
    """Verify CSV export of execution payments includes total estampillas and detailed retentions."""
    res = client.get("/api/execution/export?vigencia=2026")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    lines = res.text.strip().split("\n")
    assert len(lines) >= 149  # 1 header + 148 rows
    header = lines[0]
    assert "Total Estampillas" in header
    assert "Retenciones Detalladas" in header

if __name__ == "__main__":
    test_execution_database_integrity()
    print("[OK] Database integrity passed (148/148 payments, $35.08M estampillas, exact sums verified)")
    test_execution_summary_endpoint()
    print("[OK] Execution summary endpoint passed with retenciones_breakdown")
    test_execution_contractors_endpoint()
    print("[OK] Contractors execution endpoint passed")
    test_execution_contracts_endpoint()
    print("[OK] Contracts execution endpoint passed")
    test_execution_payments_endpoint()
    print("[OK] Payments search & pagination endpoint passed")
    test_execution_export_csv()
    print("[OK] CSV export passed with estampillas columns")
    print("\nALL EXECUTION TESTS PASSED SUCCESSFULLY! [OK]")
