import requests
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

BASE_URL = "http://127.0.0.1:8000"

def test_editar_objeto_contractual():
    print("--- 1. Obtener lista de contratos existentes ---")
    r_list = requests.get(f"{BASE_URL}/api/contracts?limit=5")
    assert r_list.status_code == 200, f"Error listando contratos: {r_list.text}"
    contratos = r_list.json()
    assert len(contratos) > 0, "No hay contratos en la base de datos"
    
    target_contract = contratos[0]
    contract_id = target_contract["id"]
    original_objeto = target_contract["objeto"]
    print(f"  Contrato ID: {contract_id} ({target_contract['numero_contrato']})")
    print(f"  Objeto original: {original_objeto[:80]}...")

    # String exacto de la captura del usuario con repeticiones excesivas
    objeto_repetitivo = (
        "PRESTACION DE SERVICIOS PARA PRESTACION DE SERVICIOS PARA PRESTACION DE SERVICIOS PARA "
        "PRESTACION DE SERVICIOS PARA PRESTACION DE SERVICIOS PARA APOYO A LA GESTION DE LAS "
        "ACTIVIDADES CONTEMPLADAS EN EL PLAN DE DEL MUNICIPIO DE YOLOMBO EN LA EMPRESA DE SERVICIOS PÚBLICOS"
    )

    print("\n--- 2. PATCH /api/contracts/{id}/objeto con repeticiones del usuario ---")
    r_patch = requests.patch(
        f"{BASE_URL}/api/contracts/{contract_id}/objeto",
        json={"objeto": objeto_repetitivo}
    )
    assert r_patch.status_code == 200, f"Error en PATCH: {r_patch.text}"
    updated = r_patch.json()
    print("  Nuevo objeto guardado:", updated["objeto"])
    
    # Verificar que colapsó las repeticiones
    assert updated["objeto"].count("PRESTACION DE SERVICIOS PARA") == 1, (
        f"Debería haber solo una ocurrencia del prefijo, pero tiene: {updated['objeto']}"
    )
    assert "PLAN DEL MUNICIPIO" in updated["objeto"] or "PLAN DE DEL" not in updated["objeto"]
    print("  [OK] Repeticiones colapsadas correctamente a una sola ocurrencia.")

    print("\n--- 3. Modificación directa con texto personalizado ---")
    nuevo_objeto_manual = (
        "PRESTACION DE SERVICIOS PROFESIONALES DE APOYO A LA GESTION ADMINISTRATIVA Y OPERATIVA "
        "DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO E.S.P."
    )
    r_patch2 = requests.patch(
        f"{BASE_URL}/api/contracts/{contract_id}/objeto",
        json={"objeto": nuevo_objeto_manual}
    )
    assert r_patch2.status_code == 200
    updated2 = r_patch2.json()
    assert nuevo_objeto_manual.rstrip(".") == updated2["objeto"].rstrip(".")
    print("  Objeto final guardado:", updated2["objeto"])
    print("  [OK] Objeto personalizado guardado satisfactoriamente.")

    print("\n--- 4. Validación de Auditoría ---")
    from app.database import SessionLocal
    from app.models.audit_log import Auditoria
    db = SessionLocal()
    audit = db.query(Auditoria).filter(
        Auditoria.contrato_id == contract_id,
        Auditoria.accion == "EDICION_OBJETO"
    ).order_by(Auditoria.id.desc()).first()
    assert audit is not None, "No se encontró registro de auditoría"
    print(f"  Registro de auditoría verificado: {audit.detalle}")
    db.close()

    print("\n=======================================================")
    print(" TODAS LAS PRUEBAS DE EDICION DE OBJETO PASARON (100%)")
    print("=======================================================")

if __name__ == "__main__":
    test_editar_objeto_contractual()
