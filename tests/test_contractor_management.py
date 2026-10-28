"""Test Script: Contractor Management Full Lifecycle Verification.
Validates:
1. Listing contractors with relations (contracts and documents).
2. Contractor registration with all extended fields (nombre_comercial, perfil_o_experiencia_resumen, bank info).
3. Querying detailed contractor info by ID.
4. Editing contractor info (PUT).
5. Attempting deletion with active contracts (expecting 400 with descriptive error).
6. Executing cascade deletion (cascade_contracts=True) and verifying clean removal.
"""
import time
import requests

BASE_URL = "http://127.0.0.1:8000/api"

def run_contractor_tests():
    print("=" * 60)
    print("TEST: Verificación del Módulo de Gestión de Contratistas")
    print("=" * 60)

    # 1. Health check
    print("\n[PASO 1] Health check del API...")
    r_health = requests.get(f"{BASE_URL}/health")
    assert r_health.status_code == 200, f"Health check falló: {r_health.text}"
    print("[OK] Backend operativo y conectado.")

    # 2. List contractors
    print("\n[PASO 2] Listar contratistas existentes...")
    r_list = requests.get(f"{BASE_URL}/contractors")
    assert r_list.status_code == 200, f"Listar falló: {r_list.text}"
    contractors = r_list.json()
    print(f"[OK] Total contratistas listados: {len(contractors)}")

    # 3. Create new contractor with all fields
    unique_suffix = int(time.time()) % 100000
    doc_num = f"901{unique_suffix}"
    new_contractor = {
        "tipo_persona": "JURIDICA",
        "tipo_documento": "NIT",
        "numero_documento": doc_num,
        "digito_verificacion": "8",
        "nombre_o_razon_social": f"INGENIERÍA AMBIENTAL Y OBRAS DEL NORTE {unique_suffix} S.A.S.",
        "nombre_comercial": f"INGE-NORTE {unique_suffix}",
        "representante_legal_nombre": "Diana Patricia Gómez Restrepo",
        "representante_legal_documento": "1037654321",
        "direccion": "Calle 49 No. 50-20 Parque Principal",
        "municipio": "Yolombó",
        "departamento": "Antioquia",
        "correo_electronico": f"contacto{unique_suffix}@ingenorte.com.co",
        "telefono": "3129876543",
        "regimen_tributario": "RESPONSABLE_IVA",
        "banco_nombre": "Bancolombia",
        "banco_tipo_cuenta": "Ahorros",
        "banco_numero_cuenta": "45678901234",
        "perfil_o_experiencia_resumen": (
            "Firma de ingeniería con más de 8 años de experiencia en saneamiento básico, "
            "optimización de plantas de tratamiento de agua potable (PTAP) y redes de distribución."
        )
    }

    print(f"\n[PASO 3] Creando contratista de prueba con documento {doc_num}...")
    r_create = requests.post(f"{BASE_URL}/contractors", json=new_contractor)
    assert r_create.status_code in [200, 201], f"Error creando contratista: {r_create.text}"
    created = r_create.json()
    contractor_id = created["id"]
    print(f"[OK] Contratista creado con ID: {contractor_id}")
    assert created["nombre_comercial"] == new_contractor["nombre_comercial"]
    assert created["perfil_o_experiencia_resumen"] == new_contractor["perfil_o_experiencia_resumen"]

    # 4. Get contractor by ID
    print(f"\n[PASO 4] Consultando detalle completo de contratista ID {contractor_id}...")
    r_get = requests.get(f"{BASE_URL}/contractors/{contractor_id}")
    assert r_get.status_code == 200, f"Error al consultar detalle: {r_get.text}"
    detail = r_get.json()
    assert detail["id"] == contractor_id
    assert detail["numero_documento"] == doc_num
    assert detail["banco_numero_cuenta"] == "45678901234"
    print("[OK] Ficha técnica completa recuperada con éxito.")

    # 5. Update contractor
    print(f"\n[PASO 5] Editando información del contratista (teléfono, banco, perfil)...")
    update_data = {
        "telefono": "6048654321",
        "correo_electronico": f"notificaciones{unique_suffix}@ingenorte.com.co",
        "banco_nombre": "Banco Davivienda",
        "banco_tipo_cuenta": "Corriente",
        "banco_numero_cuenta": "99988877700",
        "perfil_o_experiencia_resumen": "Perfil actualizado: Cobertura departamental ampliada en Antioquia y Córdoba."
    }
    r_update = requests.put(f"{BASE_URL}/contractors/{contractor_id}", json=update_data)
    assert r_update.status_code == 200, f"Error actualizando contratista: {r_update.text}"
    updated = r_update.json()
    assert updated["telefono"] == "6048654321"
    assert updated["banco_nombre"] == "Banco Davivienda"
    assert updated["banco_tipo_cuenta"] == "Corriente"
    assert "actualizado" in updated["perfil_o_experiencia_resumen"]
    print("[OK] Datos actualizados correctamente en base de datos.")

    # 6. Associate a test contract to this contractor
    print(f"\n[PASO 6] Creando contrato asociado al contratista ID {contractor_id}...")
    contract_code = f"ESP-OB-TEST-{unique_suffix}"
    contract_payload = {
        "numero_contrato": contract_code,
        "vigencia": 2026,
        "modalidad_seleccion": "INVITACION_PUBLICA",
        "tipologia": "OBRA",
        "contratista_id": contractor_id,
        "objeto": "Construcción de colector de aguas residuales sector La Cañada",
        "valor_total": 120000000.0,
        "plazo_ejecucion": 4,
        "unidad_plazo": "MESES",
        "estado": "BORRADOR"
    }
    r_cont = requests.post(f"{BASE_URL}/contracts", json=contract_payload)
    assert r_cont.status_code in [200, 201], f"Error al crear contrato: {r_cont.text}"
    contract_id = r_cont.json()["id"]
    print(f"[OK] Contrato {contract_code} (ID {contract_id}) creado y vinculado exitosamente.")

    # 7. Attempt deletion without cascade
    print(f"\n[PASO 7] Intentando eliminar contratista con contrato activo (sin parámetro de cascada)...")
    r_del_fail = requests.delete(f"{BASE_URL}/contractors/{contractor_id}")
    assert r_del_fail.status_code == 400, f"Se esperaba 400 Bad Request pero se obtuvo {r_del_fail.status_code}: {r_del_fail.text}"
    err_detail = r_del_fail.json().get("detail", "")
    assert contract_code in err_detail, f"El mensaje no menciona el contrato bloqueante: {err_detail}"
    print(f"[OK] Eliminación rechazada correctamente por dependencias activas: '{err_detail}'")

    # 8. Execute cascade deletion
    print(f"\n[PASO 8] Ejecutando eliminación en cascada (cascade_contracts=True)...")
    r_del_cascade = requests.delete(f"{BASE_URL}/contractors/{contractor_id}?cascade_contracts=true")
    assert r_del_cascade.status_code == 200, f"Error en eliminación en cascada: {r_del_cascade.text}"
    del_res = r_del_cascade.json()
    assert del_res["status"] == "success"
    assert del_res["contratos_eliminados"] == 1
    print(f"[OK] Eliminación en cascada exitosa: {del_res['mensaje']} ({del_res['contratos_eliminados']} contrato(s) eliminados)")

    # 9. Verify contractor is gone
    print(f"\n[PASO 9] Verificando que el contratista ya no exista (404)...")
    r_check_contr = requests.get(f"{BASE_URL}/contractors/{contractor_id}")
    assert r_check_contr.status_code == 404, f"Se esperaba 404 para contratista eliminado, pero dio {r_check_contr.status_code}"
    print("[OK] Confirmado 404: Contratista eliminado completamente.")

    # 10. Verify contract is also gone
    print(f"\n[PASO 10] Verificando que el contrato asociado también fue eliminado (404)...")
    r_check_c = requests.get(f"{BASE_URL}/contracts/{contract_id}")
    assert r_check_c.status_code == 404, f"Se esperaba 404 para contrato en cascada, pero dio {r_check_c.status_code}"
    print("[OK] Confirmado 404: Contrato eliminado en cascada.")

    print("\n" + "=" * 60)
    print("¡TODAS LAS PRUEBAS DE GESTIÓN DE CONTRATISTAS PASARON 100%!")
    print("=" * 60)

if __name__ == "__main__":
    run_contractor_tests()
