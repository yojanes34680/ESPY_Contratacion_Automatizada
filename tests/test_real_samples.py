import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend").resolve()))

from app.services.document_parser import parse_document_text
from app.services.composite_analyzer import composite_analyzer
from app.services.gemini_client import gemini_service

def test_samples():
    rut_path = Path("backend/storage/uploads/8b3b65879f_RUT.pdf")
    propuesta_path = Path("backend/storage/uploads/0b037d4e4b_PROPUESTA ECONOMICA.pdf")
    cdp_path = Path("backend/storage/uploads/0a1048a37a_CDP.pdf")

    print(f"RUT exists: {rut_path.exists()}")
    print(f"Propuesta exists: {propuesta_path.exists()}")
    print(f"CDP exists: {cdp_path.exists()}")

    # 1. Parse RUT
    text_rut = parse_document_text(rut_path)
    data_rut = gemini_service.extract_contractor_data(text_rut, "RUT")
    print("\n--- EXTRACTED RUT DATA ---")
    print(f"NIT: {data_rut.numero_documento}, DV: {data_rut.digito_verificacion}")
    print(f"Razon Social: {data_rut.nombre_o_razon_social}")
    print(f"Rep Legal: {data_rut.representante_legal_nombre} (CC: {data_rut.representante_legal_documento})")
    print(f"Direccion: {data_rut.direccion}")
    print(f"Municipio: {data_rut.municipio}, Depto: {data_rut.departamento}")
    print(f"Email: {data_rut.correo_electronico}")
    print(f"Telefono: {data_rut.telefono}")
    print(f"Regimen: {data_rut.regimen_tributario}")

    assert data_rut.numero_documento == "901176522", f"Expected 901176522, got {data_rut.numero_documento}"
    assert data_rut.digito_verificacion == "7", f"Expected 7, got {data_rut.digito_verificacion}"
    assert "SERVICIOS" in (data_rut.nombre_o_razon_social or ""), f"Expected SERVICIOS, got {data_rut.nombre_o_razon_social}"
    assert "EDWARD" in (data_rut.representante_legal_nombre or "").upper(), f"Expected EDWARD, got {data_rut.representante_legal_nombre}"
    assert data_rut.representante_legal_documento == "1017128843", f"Expected 1017128843, got {data_rut.representante_legal_documento}"
    assert "GIRARDOTA" in (data_rut.municipio or "").upper(), f"Expected Girardota, got {data_rut.municipio}"

    assert data_rut.telefono == "6045906870", f"Expected 6045906870, got {data_rut.telefono}"

    # 2. Parse Propuesta
    text_prop = parse_document_text(propuesta_path)
    data_prop = gemini_service.extract_contractor_data(text_prop, "PROPUESTA_ECONOMICA")
    print("\n--- EXTRACTED PROPUESTA DATA ---")
    print(f"Valor: {data_prop.valor_propuesto}")
    print(f"Banco: {data_prop.banco_nombre}, Tipo: {data_prop.banco_tipo_cuenta}, No: {data_prop.banco_numero_cuenta}")
    print(f"Objeto: {data_prop.objeto_propuesto}")
    print(f"Actividades ({len(data_prop.actividades_propuesta)}):")
    for a in data_prop.actividades_propuesta:
        print(f"  * {a}")

    assert data_prop.valor_propuesto == 8043100.0, f"Expected 8043100.0, got {data_prop.valor_propuesto}"
    assert data_prop.banco_nombre == "Bancolombia", f"Expected Bancolombia, got {data_prop.banco_nombre}"
    assert data_prop.banco_numero_cuenta == "01493153630", f"Expected 01493153630, got {data_prop.banco_numero_cuenta}"
    assert len(data_prop.actividades_propuesta) >= 3, f"Expected >= 3 activities, got {len(data_prop.actividades_propuesta)}"

    # 3. Parse CDP
    text_cdp = parse_document_text(cdp_path)
    data_cdp = gemini_service.extract_contractor_data(text_cdp, "CDP")
    print("\n--- EXTRACTED CDP DATA ---")
    print(f"CDP No: {data_cdp.cdp_numero}")
    print(f"CDP Fecha: {data_cdp.cdp_fecha}")
    print(f"CDP Rubro: {data_cdp.cdp_rubro} ({data_cdp.cdp_rubro_nombre})")
    print(f"CDP Valor: {data_cdp.cdp_valor}")
    print(f"CDP Objeto: {data_cdp.cdp_objeto}")

    assert data_cdp.numero_documento is None or data_cdp.numero_documento != "811015112", "CDP issuing entity NIT must not be contractor NIT"
    assert data_cdp.cdp_numero in ["00217", "00216", "217", "216"], f"Expected CDP 00216, got {data_cdp.cdp_numero}"
    assert data_cdp.cdp_valor == 20000000.0, f"Expected 20000000.0, got {data_cdp.cdp_valor}"
    assert "2.3.2.02.02.005" in (data_cdp.cdp_rubro or ""), f"Expected rubro 2.3.2.02.02.005, got {data_cdp.cdp_rubro}"

    # 4. Multi-document Consolidation Test
    from app.routers.agents import extract_multiple_documents_data
    from app.database import SessionLocal
    from app.models.document import Documento, TipoDocumento, CategoriaDocumento

    db = SessionLocal()
    try:
        doc_ids = []
        for path, tipo, name in [
            (rut_path, TipoDocumento.RUT, "RUT.pdf"),
            (propuesta_path, TipoDocumento.PROPUESTA, "PROPUESTA ECONOMICA.pdf"),
            (cdp_path, TipoDocumento.OTRO, "CDP.pdf")
        ]:
            d = db.query(Documento).filter(Documento.nombre_archivo_almacenado == path.name).first()
            if not d:
                d = Documento(
                    nombre_archivo_original=name,
                    nombre_archivo_almacenado=path.name,
                    ruta_relativa=str(path.relative_to(Path("backend/storage")) if "backend/storage" in str(path) else path.name),
                    tipo_documento=tipo,
                    categoria=CategoriaDocumento.SOPORTE_CONTRATISTA,
                    tamano_bytes=path.stat().st_size if path.exists() else (path.with_suffix(".ocr.txt").stat().st_size if path.with_suffix(".ocr.txt").exists() else 1024)
                )
                db.add(d)
                db.commit()
                db.refresh(d)
            doc_ids.append(d.id)

        from app.routers.agents import MultiDocExtractRequest
        res = extract_multiple_documents_data(MultiDocExtractRequest(document_ids=doc_ids), db=db)
        c = res["consolidated"]
        print("\n--- CONSOLIDATED MULTI-DOC RESULT ---")
        print(f"NIT: {c.numero_documento}-{c.digito_verificacion} | Razon Social: {c.nombre_o_razon_social}")
        print(f"Rep Legal: {c.representante_legal_nombre} (CC: {c.representante_legal_documento})")
        print(f"Municipio: {c.municipio}, Depto: {c.departamento}")
        print(f"CDP: No. {c.cdp_numero} | Fecha: {c.cdp_fecha} | Rubro: {c.cdp_rubro} | Valor: {c.cdp_valor}")
        print(f"Propuesta: Valor ${c.valor_propuesto} | Banco: {c.banco_nombre} {c.banco_tipo_cuenta} {c.banco_numero_cuenta}")
        print(f"Actividades ({len(c.actividades_propuesta)}): {c.actividades_propuesta[:2]}...")

        assert c.numero_documento == "901176522", f"Expected 901176522, got {c.numero_documento}"
        assert c.digito_verificacion == "7", f"Expected 7, got {c.digito_verificacion}"
        assert c.representante_legal_documento == "1017128843", f"Expected 1017128843, got {c.representante_legal_documento}"
        assert c.cdp_numero in ["00216", "00217", "216", "217"], f"Expected CDP 00216, got {c.cdp_numero}"
        assert c.cdp_valor == 20000000.0, f"Expected 20000000.0, got {c.cdp_valor}"
        assert c.valor_propuesto == 8043100.0, f"Expected 8043100.0, got {c.valor_propuesto}"
        assert c.banco_nombre == "Bancolombia", f"Expected Bancolombia, got {c.banco_nombre}"
        assert c.banco_numero_cuenta == "01493153630", f"Expected 01493153630, got {c.banco_numero_cuenta}"
        assert len(c.actividades_propuesta) == 5, f"Expected 5 activities, got {len(c.actividades_propuesta)}"

    finally:
        db.close()

    print("\n========================================================")
    print("ALL REAL SAMPLES EXTRACTION & CONSOLIDATION TESTS PASSED WITH 100% ACCURACY!")
    print("========================================================")

if __name__ == "__main__":
    test_samples()
