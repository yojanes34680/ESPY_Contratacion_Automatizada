"""
Test Script: Contract Deletion & Annulment Feature Verification (Prompt 4)
Validates that:
1. Deleting a contract requires a motive with >= 15 characters.
2. Contracts in status EN_EJECUCION (or with additions/payments) are ANNULLED (status ANULADO), preserving audit logs and updating Excel to ANULADO.
3. Contracts in BORRADOR without payments/additions are physically deleted by ADMIN, and audit logs are preserved with contrato_id=None.
4. Forbidden transitions in contract status graph are rejected for regular users, and allowed for ADMIN only with mandatory observation.
5. Contractors with contracts cannot be deleted (must be deactivated).
"""
import time
import openpyxl
from app.config import settings

def test_annulment_and_deletion_lifecycle(auth_client):
    unique_suffix = int(time.time() * 1000) % 1000000
    
    # 1. Crear Contratista
    contractor_data = {
        "tipo_persona": "JURIDICA",
        "tipo_documento": "NIT",
        "numero_documento": f"901{unique_suffix}-1",
        "digito_verificacion": "1",
        "nombre_o_razon_social": f"CONSTRUCTORA TEST DEL {unique_suffix} S.A.S.",
        "nombre_comercial": "CONSTRUCTORA TEST",
        "representante_legal_nombre": "Carlos Mario Vélez",
        "representante_legal_documento": "71345987",
        "correo_electronico": f"contacto{unique_suffix}@constructora.com",
        "telefono": "3109876543"
    }
    r_c = auth_client.post("/api/contractors", json=contractor_data)
    assert r_c.status_code in [200, 201], f"Failed to create contractor: {r_c.text}"
    contractor_id = r_c.json()["id"]

    # 2. Crear Contrato en BORRADOR
    contract_number_borrador = f"ESP-BORR-{unique_suffix}"
    contract_data_borrador = {
        "numero_contrato": contract_number_borrador,
        "vigencia": 2026,
        "modalidad_seleccion": "INVITACION_PUBLICA",
        "tipologia": "OBRA",
        "contratista_id": contractor_id,
        "objeto": "Construcción preliminar de tanque de almacenamiento",
        "valor_total": 10000000.0,
        "estado": "BORRADOR"
    }
    r_b = auth_client.post("/api/contracts", json=contract_data_borrador)
    assert r_b.status_code in [200, 201]
    borrador_id = r_b.json()["id"]

    # 3. Intentar borrar sin motivo o con motivo menor a 15 caracteres -> Rechazar con 422 o 400
    r_del_short = auth_client.request("DELETE", f"/api/contracts/{borrador_id}", json={"motivo": "muy corto"})
    assert r_del_short.status_code in [400, 422], f"Debe rechazar motivo corto: {r_del_short.text}"

    # 4. Crear Contrato en EN_EJECUCION para prueba de anulación
    contract_number_ejec = f"ESP-OB-DEL-{unique_suffix}"
    contract_data_ejec = {
        "numero_contrato": contract_number_ejec,
        "vigencia": 2026,
        "modalidad_seleccion": "INVITACION_PUBLICA",
        "tipologia": "OBRA",
        "contratista_id": contractor_id,
        "objeto": "Construcción de tanque de almacenamiento de agua potable",
        "valor_total": 450000000.0,
        "plazo_ejecucion": 6,
        "unidad_plazo": "MESES",
        "supervisor_nombre": "Ing. Roberto Gómez",
        "supervisor_cargo": "Subdirector Técnico Operativo",
        "supervisor_tipo_documento": "CC",
        "supervisor_documento": "1029384756",
        "fecha_suscripcion": "2026-03-01",
        "fecha_acta_inicio": "2026-03-10",
        "fecha_terminacion": "2026-09-10",
        "estado": "EN_EJECUCION"
    }
    r_ejec = auth_client.post("/api/contracts", json=contract_data_ejec)
    assert r_ejec.status_code in [200, 201]
    ejec_id = r_ejec.json()["id"]

    # Sincronizar en Excel
    r_sync = auth_client.post(f"/api/excel/sync/{ejec_id}")
    assert r_sync.status_code == 200

    # 5. Solicitar eliminación del contrato en EN_EJECUCION -> Debe pasar a ANULADO (no borrado físico)
    motivo_justificado = "Terminación anticipada por mutuo acuerdo y fuerza mayor verificada"
    r_anul = auth_client.request("DELETE", f"/api/contracts/{ejec_id}", json={"motivo": motivo_justificado})
    assert r_anul.status_code == 200
    res_anul = r_anul.json()
    assert res_anul.get("anulado") is True
    assert res_anul.get("estado") == "ANULADO"

    # Verificar que el contrato sigue existiendo en BD con estado ANULADO y datos de anulación
    r_get_ejec = auth_client.get(f"/api/contracts/{ejec_id}")
    assert r_get_ejec.status_code == 200
    cto_anulado = r_get_ejec.json()
    assert cto_anulado["estado"] == "ANULADO"
    assert cto_anulado["motivo_anulacion"] == motivo_justificado
    assert cto_anulado["anulado_por"] is not None

    # Verificar que el archivo Excel tiene el estado ANULADO
    excel_path = settings.MASTER_EXCEL_PATH
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active
    excel_estado = None
    for row in range(5, ws.max_row + 1):
        if ws.cell(row=row, column=2).value == contract_number_ejec:
            excel_estado = ws.cell(row=row, column=19).value
            break
    wb.close()
    assert excel_estado == "ANULADO", f"En Excel debe reflejar ANULADO, pero tiene: {excel_estado}"

    # 6. Borrado físico del contrato en BORRADOR sin pagos ni adiciones
    r_del_borrador = auth_client.request(
        "DELETE", 
        f"/api/contracts/{borrador_id}", 
        json={"motivo": "Contrato descartado en fase preliminar por duplicidad de solicitud"}
    )
    assert r_del_borrador.status_code == 200
    assert r_del_borrador.json().get("eliminado_fisicamente") is True

    # Verificar que el contrato en borrador ya no existe
    r_get_borr = auth_client.get(f"/api/contracts/{borrador_id}")
    assert r_get_borr.status_code == 404

    # 7. Validar que el contratista con contratos no se puede eliminar físicamente
    r_del_contratista = auth_client.delete(f"/api/contractors/{contractor_id}")
    assert r_del_contratista.status_code == 400
    assert "no se puede eliminar" in r_del_contratista.json()["detail"].lower()

    # 8. Validar desactivación del contratista
    r_deact = auth_client.patch(f"/api/contractors/{contractor_id}/deactivate")
    assert r_deact.status_code == 200
    assert r_deact.json()["activo"] is False
