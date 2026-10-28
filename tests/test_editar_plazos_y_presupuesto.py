import requests
import json
import sys
import os

BASE_URL = "http://127.0.0.1:8000"

def test_editar_plazos_y_presupuesto():
    print("--- 1. Obtener lista de contratos ---")
    r = requests.get(f"{BASE_URL}/api/contracts?limit=5")
    assert r.status_code == 200, f"Error obteniendo contratos: {r.text}"
    contratos = r.json()
    assert len(contratos) > 0, "No hay contratos para probar"
    c = contratos[0]
    c_id = c["id"]
    print(f"  Probando contrato ID {c_id}: {c['numero_contrato']}")

    print("\n--- 2. Actualizar Plazos y Supervisión (PUT /api/contracts/{id}) ---")
    payload_plazos = {
        "plazo_ejecucion": 3,
        "unidad_plazo": "MESES",
        "plazo_texto": "3 meses",
        "prorroga_1": "1 mes prorrogado",
        "supervisor_nombre": "CAROLINA GIRALDO GOMEZ",
        "supervisor_cargo": "GERENTE GENERAL",
        "supervisor_documento": "1152451796",
        "supervisor_tipo_documento": "CC"
    }
    r_put1 = requests.put(f"{BASE_URL}/api/contracts/{c_id}", json=payload_plazos)
    assert r_put1.status_code == 200, f"Error actualizando plazos: {r_put1.text}"
    updated1 = r_put1.json()
    assert updated1["plazo_ejecucion"] == 3
    assert updated1["prorroga_1"] == "1 mes prorrogado"
    assert updated1["supervisor_nombre"] == "CAROLINA GIRALDO GOMEZ"
    assert updated1["supervisor_documento"] == "1152451796"
    print("  [OK] Plazos y Supervisión guardados y verificados.")

    print("\n--- 3. Actualizar Presupuesto, CDP, Rubro y CCPET ---")
    payload_budget = {
        "cdp_numero": "00245",
        "cdp_fecha": "2026-10-02",
        "cdp_rubro": "2.3.2.02.02.009",
        "rp_numero": "00123",
        "metadatos_agente": {
            "cdp_numero": "00245",
            "cdp_fecha": "2026-10-02",
            "cdp_valor": 4800000.0,
            "cdp_rubro": "2.3.2.02.02.009",
            "cdp_rubro_nombre": "SERVICIOS PARA LA COMUNIDAD, SOCIALES Y PERSONALES",
            "cdp_clasificadores": [
                "CCPET01 (CPC V2.1 AC): 94900 Otros servicios de proteccion del medio ambiente",
                "CCPET70 (SERVICIOS): 23313 Convenio PGIRS"
            ],
            "cdp_texto_completo": "00245, expedido el 2 de octubre de 2026, por valor de $4.800.000, con cargo al Rubro 2.3.2.02.02.009"
        }
    }
    r_put2 = requests.put(f"{BASE_URL}/api/contracts/{c_id}", json=payload_budget)
    assert r_put2.status_code == 200, f"Error actualizando presupuesto: {r_put2.text}"
    updated2 = r_put2.json()
    assert updated2["cdp_numero"] == "00245"
    assert updated2["cdp_rubro"] == "2.3.2.02.02.009"
    assert updated2["rp_numero"] == "00123"
    meta = updated2.get("metadatos_agente", {})
    assert meta.get("cdp_valor") == 4800000.0
    assert meta.get("cdp_rubro_nombre") == "SERVICIOS PARA LA COMUNIDAD, SOCIALES Y PERSONALES"
    assert len(meta.get("cdp_clasificadores", [])) == 2
    print("  [OK] Presupuesto, CDP y CCPET guardados y verificados.")

    print("\n=======================================================")
    print(" TODAS LAS PRUEBAS DE PLAZOS Y PRESUPUESTO PASARON (100%)")
    print("=======================================================")

if __name__ == "__main__":
    test_editar_plazos_y_presupuesto()
