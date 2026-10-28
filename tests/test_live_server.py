import urllib.request
import json

def test_live():
    base = "http://127.0.0.1:8000"
    
    # 1. Summary
    res = urllib.request.urlopen(f"{base}/api/execution/summary?vigencia=2026")
    summary = json.loads(res.read().decode("utf-8"))
    assert summary["conteo_comprobantes"] == 148
    assert summary["total_ejecutado"] == 843400523.86
    print("[OK] /api/execution/summary live: 148 vouchers, $843,400,523.86 executed")

    # 2. Contractors list
    res = urllib.request.urlopen(f"{base}/api/execution/contractors?vigencia=2026")
    contractors = json.loads(res.read().decode("utf-8"))
    assert len(contractors) > 0
    print(f"[OK] /api/execution/contractors live: {len(contractors)} contractors")

    # 3. Specific contractor dossier
    cid = contractors[0]["id"]
    res = urllib.request.urlopen(f"{base}/api/execution/contractors/{cid}?vigencia=2026")
    dossier = json.loads(res.read().decode("utf-8"))
    assert dossier["id"] == cid
    print(f"[OK] /api/execution/contractors/{cid} live: {dossier['nombre_o_razon_social']} ({dossier['porcentaje_ejecucion']}%)")

    # 4. Contracts execution list
    res = urllib.request.urlopen(f"{base}/api/execution/contracts?vigencia=2026")
    contracts = json.loads(res.read().decode("utf-8"))
    assert len(contracts) > 0
    print(f"[OK] /api/execution/contracts live: {len(contracts)} contracts")

    # 5. Specific contract execution detail
    ct_id = contracts[0]["id"]
    res = urllib.request.urlopen(f"{base}/api/execution/contracts/{ct_id}")
    ct_detail = json.loads(res.read().decode("utf-8"))
    assert ct_detail["contrato"]["id"] == ct_id
    print(f"[OK] /api/execution/contracts/{ct_id} live: {ct_detail['contrato']['numero_contrato']}")

    # 6. Payments search & list
    res = urllib.request.urlopen(f"{base}/api/execution/payments?vigencia=2026&limit=1000")
    payments = json.loads(res.read().decode("utf-8"))
    assert len(payments) == 148
    print(f"[OK] /api/execution/payments live: {len(payments)} vouchers retrieved")

    # 7. CSV Export
    res = urllib.request.urlopen(f"{base}/api/execution/export?vigencia=2026")
    csv_bytes = res.read()
    assert len(csv_bytes) > 1000
    print(f"[OK] /api/execution/export live: CSV exported ({len(csv_bytes)} bytes)")

    # 8. Frontend static mount
    res = urllib.request.urlopen(f"{base}/app/")
    html = res.read().decode("utf-8")
    assert "nav-execution" in html
    assert "tab-execution" in html
    assert "import-pdf-dropzone" in html
    assert "tab-btn-import-pdf" in html
    print("[OK] Frontend UI /app/ serving correctly with Execution dashboard tab and PDF Packet Center")

    print("\n>>> ALL LIVE HTTP CHECKS PASSED PERFECTLY! [OK]")

if __name__ == "__main__":
    test_live()
