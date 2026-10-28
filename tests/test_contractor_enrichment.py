"""
Test Suite: Enriquecimiento y Completitud Automática de Contratistas con Documentación Suministrada.
Verifica que al suministrar documentos o datos para contratistas existentes:
1. Se evalúen correctamente los campos faltantes (/missing-fields).
2. Se enriquezcan y actualicen de forma no destructiva los datos de contacto, fiscales y bancarios (/enrich-from-docs).
3. Se garantice la no-destructividad: valores válidos preexistentes no son sobreescritos por campos vacíos.
4. Se registre la trazabilidad de auditoría de cada actualización.
5. Se vincule la información en el flujo de contratación (/extract-multiple-documents y /create-contractor-from-docs).
"""
import os
import sys
import uuid

# Agregar backend a sys.path
sys.path.insert(0, os.path.abspath("backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.contractor import Contratista, TipoPersona, TipoDocumento, RegimenTributario
from app.models.audit_log import Auditoria
from app.services.contractor_enrichment import (
    get_missing_contractor_fields,
    enrich_contractor,
    is_empty_or_placeholder
)

client = TestClient(app)

def clean_contractor_by_doc(db, doc_num):
    existing = db.query(Contratista).filter(Contratista.numero_documento == doc_num).first()
    if existing:
        db.delete(existing)
        db.commit()

def run_tests():
    print("=================================================================")
    print(" INICIANDO PRUEBAS DE ENRIQUECIMIENTO Y COMPLETITUD DE CONTRATISTAS")
    print("=================================================================")

    # 1. Test is_empty_or_placeholder
    print("\n[1] Verificando detección de comodines y valores vacíos...")
    assert is_empty_or_placeholder(None) is True
    assert is_empty_or_placeholder("") is True
    assert is_empty_or_placeholder("   ") is True
    assert is_empty_or_placeholder("sin dirección") is True
    assert is_empty_or_placeholder("Sin Direccion") is True
    assert is_empty_or_placeholder("Colombia") is True
    assert is_empty_or_placeholder("Bogotá D.C.") is True
    assert is_empty_or_placeholder("Cundinamarca") is True
    assert is_empty_or_placeholder("No registrado") is True
    assert is_empty_or_placeholder("Carrera 20 # 10-15") is False
    assert is_empty_or_placeholder("3101234567") is False
    print("  -> OK: Detección de comodines y cadenas vacías verificada.")

    # 2. Test get_missing_contractor_fields y endpoint /missing-fields
    print("\n[2] Verificando evaluación de campos faltantes (/missing-fields)...")
    doc_1 = "999888777"
    db = SessionLocal()
    try:
        clean_contractor_by_doc(db, doc_1)

        test_c = Contratista(
            tipo_persona=TipoPersona.NATURAL,
            tipo_documento=TipoDocumento.CC,
            numero_documento=doc_1,
            nombre_o_razon_social="CONTRATISTA INCOMPLETO TEST",
            direccion="Sin dirección",
            municipio="Colombia",
            correo_electronico=None,
            telefono=None,
            banco_numero_cuenta=None
        )
        db.add(test_c)
        db.commit()
        db.refresh(test_c)

        missing = get_missing_contractor_fields(test_c)
        missing_keys = [m["key"] for m in missing]

        assert "telefono" in missing_keys
        assert "correo_electronico" in missing_keys
        assert "direccion" in missing_keys
        assert "municipio" in missing_keys
        assert "banco_numero_cuenta" in missing_keys

        # Probar endpoint GET /api/contractors/{id}/missing-fields
        response = client.get(f"/api/contractors/{test_c.id}/missing-fields")
        assert response.status_code == 200
        data = response.json()
        assert data["contractor_id"] == test_c.id
        assert data["is_complete"] is False
        assert data["total_missing"] >= 4
        print(f"  -> OK: {data['total_missing']} campos faltantes detectados correctamente.")
    finally:
        clean_contractor_by_doc(db, doc_1)
        db.close()

    # 3. Test enriquecimiento no destructivo y auditoría
    print("\n[3] Verificando enriquecimiento no destructivo y auditoría...")
    doc_2 = "1122334455"
    db = SessionLocal()
    try:
        clean_contractor_by_doc(db, doc_2)

        c = Contratista(
            tipo_persona=TipoPersona.JURIDICA,
            tipo_documento=TipoDocumento.NIT,
            numero_documento=doc_2,
            digito_verificacion=None,
            nombre_o_razon_social="CONTRATISTA ENRIQUECIMIENTO TEST S.A.S.",
            direccion="Calle 10 # 5-20",  # Válida preexistente
            municipio="Yolombó",
            correo_electronico=None,
            telefono=None,
            banco_nombre=None,
            banco_numero_cuenta=None
        )
        db.add(c)
        db.commit()
        db.refresh(c)

        new_data = {
            "telefono": "3119876543",
            "correo_electronico": "enriquecido@espy.gov.co",
            "digito_verificacion": "8",
            "direccion": "Sin dirección",  # Comodín: NO debe sobreescribir la válida existente
            "banco_nombre": "Bancolombia",
            "banco_tipo_cuenta": "Ahorros",
            "banco_numero_cuenta": "9876543210"
        }

        res = enrich_contractor(c, new_data, db, source_desc="RUT DIAN Cargado")
        assert "telefono" in res["campos_actualizados"]
        assert "correo_electronico" in res["campos_actualizados"]
        assert "digito_verificacion" in res["campos_actualizados"]
        assert "banco_numero_cuenta" in res["campos_actualizados"]
        assert "direccion" not in res["campos_actualizados"], "La dirección válida previa no debió sobreescribirse"

        db.refresh(c)
        assert c.telefono == "3119876543"
        assert c.correo_electronico == "enriquecido@espy.gov.co"
        assert c.digito_verificacion == "8"
        assert c.direccion == "Calle 10 # 5-20"
        assert c.banco_nombre == "Bancolombia"
        assert c.banco_numero_cuenta == "9876543210"
        print("  -> OK: Campos actualizados y no-destructividad confirmada.")

        # Verificar auditoría
        audit = db.query(Auditoria).filter(
            Auditoria.accion == "ENRIQUECIMIENTO_CONTRATISTA"
        ).order_by(Auditoria.id.desc()).first()
        assert audit is not None
        assert "CONTRATISTA ENRIQUECIMIENTO TEST" in audit.detalle
        print("  -> OK: Registro de trazabilidad en Auditoría verificado.")

        # Endpoint POST /api/contractors/{id}/enrich-from-docs con manual_data
        api_res = client.post(
            f"/api/contractors/{c.id}/enrich-from-docs",
            json={
                "document_ids": [],
                "manual_data": {
                    "telefono": "3119876543",
                    "departamento": "Antioquia"
                }
            }
        )
        assert api_res.status_code == 200
        json_data = api_res.json()
        assert json_data["status"] == "success"
        assert "departamento" in json_data["enrichment_summary"]["campos_actualizados"]
        print("  -> OK: Endpoint /api/contractors/{id}/enrich-from-docs verificado.")
    finally:
        clean_contractor_by_doc(db, doc_2)
        db.close()

    # 4. Test /api/agents/create-contractor-from-docs actualiza contratista existente
    print("\n[4] Verificando actualización de contratista existente en flujo de contratación...")
    doc_3 = "888777666"
    db = SessionLocal()
    try:
        clean_contractor_by_doc(db, doc_3)

        c = Contratista(
            tipo_persona=TipoPersona.NATURAL,
            tipo_documento=TipoDocumento.CC,
            numero_documento=doc_3,
            nombre_o_razon_social="CONTRATISTA PREEXISTENTE",
            direccion="Sin dirección",
            telefono=None,
            correo_electronico=None
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        original_id = c.id

        payload = {
            "document_ids": [],
            "contratista_data": {
                "tipo_persona": "JURIDICA",
                "tipo_documento": "NIT",
                "numero_documento": doc_3,
                "nombre_o_razon_social": "CONTRATISTA PREEXISTENTE ACTUALIZADO S.A.S.",
                "telefono": "3154443322",
                "correo_electronico": "actualizado@gmail.com",
                "direccion": "Calle Principal 20",
                "municipio": "Yolombó",
                "departamento": "Antioquia",
                "digito_verificacion": "1"
            }
        }
        res = client.post("/api/agents/create-contractor-from-docs", json=payload)
        assert res.status_code == 200
        res_data = res.json()

        # Debe conservar el mismo ID (no se duplica el contratista)
        assert res_data["id"] == original_id
        assert res_data["telefono"] == "3154443322"
        assert res_data["correo_electronico"] == "actualizado@gmail.com"
        assert res_data["direccion"] == "Calle Principal 20"
        assert res_data["digito_verificacion"] == "1"

        db.refresh(c)
        assert c.id == original_id
        assert c.telefono == "3154443322"
        print("  -> OK: Contratista existente enriquecido sin duplicar registro (ID consistente).")
    finally:
        clean_contractor_by_doc(db, doc_3)
        db.close()

    print("\n=================================================================")
    print(" ¡TODAS LAS PRUEBAS DE ENRIQUECIMIENTO DE CONTRATISTAS PASARON! ")
    print("=================================================================")

if __name__ == "__main__":
    run_tests()
