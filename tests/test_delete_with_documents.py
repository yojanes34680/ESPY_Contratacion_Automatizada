"""Test contract deletion when contract has associated documents."""
import time
import requests

BASE_URL = "http://127.0.0.1:8000/api"

def test_delete_with_docs(auth_client):
    # 1. Health check
    r = auth_client.get("/api/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"

    # 2. Create a fresh contract and upload a document to it, then delete
    unique_suffix = int(time.time()) % 100000
    contractor_data = {
        "tipo_persona": "NATURAL",
        "tipo_documento": "CC",
        "numero_documento": f"10{unique_suffix}",
        "nombre_o_razon_social": f"INGENIERO PRUEBA {unique_suffix}",
        "correo_electronico": f"ing{unique_suffix}@gmail.com",
        "telefono": "3001234567"
    }
    r_c = auth_client.post("/api/contractors", json=contractor_data)
    cid = r_c.json()["id"]

    c_data = {
        "numero_contrato": f"ESP-PS-DOC-{unique_suffix}",
        "vigencia": 2026,
        "tipologia": "PRESTACION_SERVICIOS",
        "contratista_id": cid,
        "objeto": "Asesoría técnica especializada para el sistema de acueducto",
        "valor_total": 5000000.0,
        "plazo_ejecucion": 3,
        "unidad_plazo": "MESES",
        "estado": "BORRADOR"
    }
    r_cont = auth_client.post("/api/contracts", json=c_data)
    created_contract = r_cont.json()
    new_id = created_contract["id"]

    # Upload a document to this contract
    files = {'file': ('propuesta_test.pdf', b'%PDF-1.4 test document dummy content', 'application/pdf')}
    data = {'contrato_id': str(new_id), 'tipo_documento': 'PROPUESTA'}
    r_upload = auth_client.post("/api/documents/upload", files=files, data=data)
    assert r_upload.status_code in [200, 201], f"Upload failed: {r_upload.text}"

    # Sync to Excel
    r_sync = auth_client.post(f"/api/excel/sync/{new_id}")
    assert r_sync.status_code == 200

    # Now delete the contract
    r_del = auth_client.delete(f"/api/contracts/{new_id}")
    assert r_del.status_code == 200, f"Delete failed: {r_del.status_code} - {r_del.text}"

    # Verify it is gone
    r_verify = auth_client.get(f"/api/contracts/{new_id}")
    assert r_verify.status_code == 404


if __name__ == "__main__":
    test_delete_with_docs()
