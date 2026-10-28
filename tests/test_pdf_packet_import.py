"""Automated test suite for PDF Payment Packets extraction, endpoint and duplicate prevention."""
import io
import sys
from pathlib import Path
from fastapi.testclient import TestClient

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.database import SessionLocal
from app.models.execution import PagoContrato
from app.services.payment_packet_parser import extract_payment_packet_data, format_record_to_txt_line

client = TestClient(app)

SAMPLE_PACKET_TEXT = """%PDF-1.4
EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO ESPY
COMPROBANTE DE EGRESO
CE N° 00999
Fecha Doc: 15/05/2026
Beneficiario: JUAN DAVID VARGAS ESCOBAR
Nit o Cedula: 1037589234
Rubro Presupuestal: 2.1.2.02.02.008
CONTRATO CPS-003-2026
Total de la Presente Orden: 3.300.000,00
Total Retenciones: 184.800,00
Total a Pagar: 3.115.200,00
RETENCIONES
DESCRIPCIÓN % VALOR
Industria y comercio ICA 0.60 19.800,00
Estampilla Pro Cultura 2.00 66.000,00
Tasa Pro Deporte y Recreación 2.00 66.000,00
Estampilla Pro-Hospital 1.00 33.000,00
OP N° 00999
Num Doc: 00999
FACTURA ELECTRONICA DE VENTA No. FE-9901
Concepto de este Egreso:
Pago correspondiente a honorarios de servicios profesionales prestados en el mes de mayo de 2026.
%%EOF"""

SAMPLE_PACKET_TEXT_2 = """%PDF-1.4
EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO ESPY
COMPROBANTE DE EGRESO
CE N° 00998
Fecha Doc: 20/06/2026
Beneficiario: ACUATUBOS LTDA.
Nit o Cedula: 890987654
Rubro Presupuestal: 2.3.2.02.02.005
CONTRATO CS-014-2026
Total de la Presente Orden: 11.569.423,00
Total Retenciones: 957.637,20
Total a Pagar: 10.611.785,80
RETENCIONES
DESCRIPCIÓN % VALOR
Industria y comercio ICA 0.60 69.416,54
Estampilla Pro Cultura 2.00 231.388,46
Tasa Pro Deporte y Recreación 2.00 231.388,46
OP N° 00998
FACTURA ELECTRONICA No. FAC-7721
Concepto de este Egreso:
Suministro de accesorios de tubería para acueducto municipal.
%%EOF"""

def test_extract_payment_packet_data():
    """Verify parsing of 8 columns, Egreso retenciones breakdown, estampillas and smart DB linking."""
    db = SessionLocal()
    try:
        data = extract_payment_packet_data(SAMPLE_PACKET_TEXT.encode("utf-8"), "paquete_test.pdf", db)
        assert data["codigo_egreso"] == "CE N° 00999", f"CE code mismatch: {data['codigo_egreso']}"
        assert data["codigo_contrato"] == "CPS-003-2026", f"Contract mismatch: {data['codigo_contrato']}"
        assert data["nombre_beneficiario"] == "JUAN DAVID VARGAS ESCOBAR"
        assert data["rubro_egreso"] == "2.1.2.02.02.008"
        assert data["total_orden"] == 3300000.0
        assert data["total_retencion"] == 184800.0
        assert data["total_pagar"] == 3115200.0
        assert abs(data["total_estampillas"] - 165000.0) < 1.0, f"Estampillas mismatch: {data['total_estampillas']}"
        assert len(data["retenciones_detalle"]) == 4, f"Expected 4 retenciones, found {len(data['retenciones_detalle'])}"
        assert data["contrato_id"] is not None, "Contract should be linked"
        assert data["contratista_id"] is not None, "Contractor should be linked"

        txt_line = format_record_to_txt_line(data)
        assert "CPS-003-2026,CE N° 00999" in txt_line
        assert "3300000" in txt_line
        assert "184800" in txt_line
        assert "3115200" in txt_line
        assert "Estampilla Pro Cultura" in txt_line
        print("[OK] extract_payment_packet_data extracted Egreso retenciones, estampillas ($165k) and linked correctly.")
    finally:
        db.close()

def test_import_pdf_packets_endpoint_flow(auth_client):
    """Verify the /api/execution/import-pdf-packets endpoint, duplicate blocking, and cleanup."""
    client = auth_client
    db = SessionLocal()
    try:
        # Pre-clean test vouchers if exist
        db.query(PagoContrato).filter(PagoContrato.codigo_egreso.in_(["CE N° 00999", "CE N° 00998"])).delete(synchronize_session=False)
        db.commit()

        initial_count = db.query(PagoContrato).count()

        # 1. First upload: Single file insertion
        file_payload = [
            ("files", ("paquete_1.pdf", io.BytesIO(SAMPLE_PACKET_TEXT.encode("utf-8")), "application/pdf"))
        ]
        res1 = client.post("/api/execution/import-pdf-packets", files=file_payload, data={"vigencia": 2026})
        assert res1.status_code == 200, f"Error {res1.status_code}: {res1.text}"
        data1 = res1.json()
        assert data1["success"] is True
        assert data1["inserted_count"] == 1
        assert data1["duplicates_count"] == 0
        assert len(data1["inserted"]) == 1
        assert data1["inserted"][0]["codigo_egreso"] == "CE N° 00999"
        assert "CE N° 00999" in data1["txt_content"]

        after_first_count = db.query(PagoContrato).count()
        assert after_first_count == initial_count + 1
        print("[OK] First PDF packet uploaded and inserted into database.")

        # 2. Second upload: Duplicate prevention test
        # Uploading the exact same voucher again must NOT insert it and report it in 'duplicates'
        file_payload_dup = [
            ("files", ("paquete_1_dup.pdf", io.BytesIO(SAMPLE_PACKET_TEXT.encode("utf-8")), "application/pdf"))
        ]
        res2 = client.post("/api/execution/import-pdf-packets", files=file_payload_dup, data={"vigencia": 2026})
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["inserted_count"] == 0, "Duplicate should NOT be inserted"
        assert data2["duplicates_count"] == 1, "Should be flagged as duplicate"
        assert len(data2["duplicates"]) == 1
        assert data2["duplicates"][0]["codigo_egreso"] == "CE N° 00999"
        assert "ya se encuentra registrado previamente" in data2["duplicates"][0]["motivo"]

        after_dup_count = db.query(PagoContrato).count()
        assert after_dup_count == initial_count + 1, "Database count must remain unchanged on duplicate"
        print("[OK] Duplicate prevention rule strictly verified (database count unchanged, duplicate reported).")

        # 3. Batch upload test: One new, one intra-batch duplicate
        file_payload_batch = [
            ("files", ("paquete_2_new.pdf", io.BytesIO(SAMPLE_PACKET_TEXT_2.encode("utf-8")), "application/pdf")),
            ("files", ("paquete_2_repeat.pdf", io.BytesIO(SAMPLE_PACKET_TEXT_2.encode("utf-8")), "application/pdf"))
        ]
        res3 = client.post("/api/execution/import-pdf-packets", files=file_payload_batch, data={"vigencia": 2026})
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["inserted_count"] == 1, "Only first in batch should be inserted"
        assert data3["duplicates_count"] == 1, "Second in batch should be flagged as batch duplicate"
        assert "mismo grupo de archivos adjuntos" in data3["duplicates"][0]["motivo"]

        after_batch_count = db.query(PagoContrato).count()
        assert after_batch_count == initial_count + 2
        print("[OK] Intra-batch duplicate prevention verified.")

        # 4. Overwrite duplicates test: Uploading CE N° 00999 with overwrite_duplicates=True must update record
        file_payload_overwrite = [
            ("files", ("paquete_1_overwrite.pdf", io.BytesIO(SAMPLE_PACKET_TEXT.encode("utf-8")), "application/pdf"))
        ]
        res4 = client.post(
            "/api/execution/import-pdf-packets",
            files=file_payload_overwrite,
            data={"vigencia": 2026, "overwrite_duplicates": True}
        )
        assert res4.status_code == 200
        data4 = res4.json()
        assert data4["inserted_count"] == 0
        assert data4["updated_count"] == 1, "Must update 1 existing duplicate"
        assert data4["duplicates_count"] == 0, "Should not be flagged as blocked duplicate"
        assert data4["updated"][0]["codigo_egreso"] == "CE N° 00999"

        after_overwrite_count = db.query(PagoContrato).count()
        assert after_overwrite_count == initial_count + 2, "Count must remain same after update"
        print("[OK] Overwrite duplicates functionality verified successfully.")

    finally:
        # Cleanup test records
        db.query(PagoContrato).filter(PagoContrato.codigo_egreso.in_(["CE N° 00999", "CE N° 00998"])).delete(synchronize_session=False)
        db.commit()
        db.close()
        print("[OK] Database cleaned up to original state.")

SAMPLE_PACKET_CE_00271 = """%PDF-1.4
=== PÁGINA 1 ===
REPUBLICA DE COLOMBIA
DEPARTAMENTO DE ANTIOQUIA
EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO ESPY
Nit: 811.015.112
COMPROBANTE DE EGRESO CE Nº 00271
Documentos Asignados
Num Doc. Fecha Doc. Fecha de Expedición: 25/05/2026
00226 25/05/2026
Nit o Cedula: 1.039.886.105
Beneficiario: LUIS ALEJANDRO MARIN ARBOLEDA
Concepto de este Egreso:
SUMINISTROS, MANTENIMIENTOS Y REPARACIONES PARA LAS MOTOS AL SERVICIO DE LA ESPY.
Rubro: 2.1.2.02.02.008
Total de la Presente Orden: 3.104.100,00
Total Retenciones: 344.555,10
Total a Pagar: 2.759.544,90
=== PÁGINA 2 ===
RETENCIONES
DESCRIPCIÓN % VALOR
Industria y comercio ICA 0,60 18.624,60
Estampilla Pro Cultura 2,00 62.082,00
Estampilla Pro-Hospital 1,00 31.041,00
Compras No declarantes 3,50 108.643,50
Tasa Pro Deporte y Recreación 2,00 62.082,00
Estampilla pro-juaticia familiar 2,00 62.082,00
=== PÁGINA 7 ===
CERTIFICACIÓN DE CUMPLIMIENTO Y SUPERVISIÓN CONTRACTUAL
CAROLINA GIRALDO GÓMEZ, en mi calidad de GERENTE DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ ESP, dejo constancia de que LUIS ALEJANDRO MARIN ARBOLEDA, identificado con (CC/NIT) 1.039.886.105, en cumplimiento del contrato número CS-023-2026 cuyo objeto es "SUMINISTRO. MANTENIMIENTO Y REPARACIONES DE LAS MOTOS Y MOTOCARRO DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ".
CUMPLIÓ CON:
Calidad de las especificaciones del bien o servicio
Cumplimiento de la entrega
%%EOF"""

def test_extract_ce_00271_with_supervision_certification():
    """Verify CE Nº 00271: totals, 6 retenciones and contract identification via Certificación de Supervisión."""
    db = SessionLocal()
    try:
        data = extract_payment_packet_data(SAMPLE_PACKET_CE_00271.encode("utf-8"), "CE_00271.pdf", db)
        assert data["codigo_egreso"] == "CE N° 00271"
        assert data["total_orden"] == 3104100.0
        assert abs(data["total_retencion"] - 344555.10) < 0.1
        assert abs(data["total_pagar"] - 2759544.90) < 0.1
        assert len(data["retenciones_detalle"]) == 6, f"Expected 6 retenciones, found {len(data['retenciones_detalle'])}"
        assert data["codigo_contrato"] == "CS-023-2026"
        assert data["contratista_nombre"] == "LUIS ALEJANDRO MARIN ARBOLEDA" or "LUIS ALEJANDRO" in (data["nombre_beneficiario"] or "")
        
        # Verify 6 retenciones concepts
        conceptos = [r["concepto"] for r in data["retenciones_detalle"]]
        assert any("ICA" in c for c in conceptos)
        assert any("Cultura" in c for c in conceptos)
        assert any("Hospital" in c for c in conceptos)
        assert any("Compras" in c for c in conceptos)
        assert any("Deporte" in c for c in conceptos)
        assert any("Justicia" in c or "juaticia" in c.lower() for c in conceptos)
        print("[OK] test_extract_ce_00271_with_supervision_certification passed with 6 retenciones and contract CS-023-2026.")
    finally:
        db.close()

SAMPLE_PACKET_PAGO_245 = """%PDF-1.4
=== PÁGINA 1: COMPROBANTE DE EGRESO ===
REPUBLICA DE COLOMBIA
DEPARTAMENTO DE ANTIOQUIA
EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO ESPY
Nit: 811.015.112
COMPROBANTE DE EGRESO CE Nº 00245
Documentos Asignados
Num Doc: 00204 Fecha Doc: 08/05/2026 Fecha de Expedición: 08/05/2026
Nit ó Cedula: 890.980.304-7
Beneficiario: PARROQUIA SAN LORENZO
Concepto de este Egreso:
PAGO CORRESPONDIENTE AL CONTRATO DE ARRENDAMIENTO CA-013-2026
Rubro: 2.1.2.02.02.007
Valor Rubro: 8.330.000,00
Valor Clasificador CCPET01: 8.330.000,00
Valor Clasificador CCPET02: 8.330.000,00
Valor Clasificador CCPET05: 8.330.000,00
Valor Clasificador CCPET70: 8.330.000,00
Valor Clasificador CCPET83: 8.330.000,00
Valor Clasificador CCPET84: 8.330.000,00
Total de la Presente Orden: 8.330.000,00
Total Retenciones: 199.500,00
Total a Pagar: 8.130.500,00
Valor en letras: OCHO MILLONES CIENTO TREINTA MIL QUINIENTOS PESOS M/L
Detalle de Movimiento de Bancos y Caja:
Banco Agrario de Colombia Cuenta de Ahorros 40012345 Valor: 8.130.500,00
=== PÁGINA 2: RETENCIONES DEL EGRESO ===
RETENCIONES
DESCRIPCIÓN % VALOR
Iva por Servicios Gravados 15,00 199.500,00
=== PÁGINA 3: ORDEN DE PAGO ===
ORDEN DE PAGO OP Nº 00204
Beneficiario: PARROQUIA SAN LORENZO
Nit: 890.980.304-7
Total de la Presente Orden: 8.330.000,00
Total Retenciones: 199.500,00
Total a Pagar: 8.130.500,00
Valor en letras: OCHO MILLONES TRESCIENTOS TREINTA MIL PESOS M/L
RETENCIONES
DESCRIPCIÓN % VALOR
Iva por Servicios Gravados 15,00 199.500,00
=== PÁGINA 5: FACTURA ELECTRÓNICA ===
FACTURA ELECTRÓNICA DE VENTA No. FE-1055
SUBTOTAL: 7.000.000,00
IVA 19%: 1.330.000,00
TOTAL FACTURA: 8.330.000,00
RETE/FUENTE: 0,00
RETE/IVA: 0,00
RETE/ICA: 0,00
=== PÁGINA 6: CERTIFICACIÓN DE SUPERVISIÓN ===
CERTIFICACIÓN DE CUMPLIMIENTO Y SUPERVISIÓN CONTRACTUAL
En cumplimiento del contrato número CA-013-2026 cuyo objeto es
ARRENDAMIENTO DEL BIEN INMUEBLE PARA LA ESPY.
%%EOF"""

SAMPLE_PACKET_ESTAMPILLAS = """%PDF-1.4
=== PÁGINA 1: COMPROBANTE DE EGRESO ===
EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO ESPY
COMPROBANTE DE EGRESO CE Nº 00310
Fecha de Expedición: 12/06/2026
Nit ó Cedula: 900.123.456-1
Beneficiario: CONSTRUCCIONES Y CONSULTORIAS DEL NORTE S.A.S.
Concepto de este Egreso: ACTA DE OBRA No 1 CONTRATO CO-005-2026
Rubro: 2.3.2.02.02.009
Total de la Presente Orden: 25.000.000,00
Total Retenciones: 1.650.000,00
Total a Pagar: 23.350.000,00
=== PÁGINA 2: RETENCIONES ===
RETENCIONES
DESCRIPCIÓN % VALOR
Industria y Comercio ICA 0,60 150.000,00
Estampilla Pro-Cultura 2,00 500.000,00
Bienestar del Adulto Mayor 2,00 500.000,00
Estampilla Pro-Hospital 1,00 250.000,00
Tasa Pro-Deporte 1,00 250.000,00
%%EOF"""

def test_extract_pago_245_parroquia_san_lorenzo():
    """Real test case PAGO_245.pdf (CE 00245, OP 00204, Parroquia San Lorenzo, CA-013-2026)."""
    db = SessionLocal()
    try:
        data = extract_payment_packet_data(SAMPLE_PACKET_PAGO_245.encode("utf-8"), "PAGO_245.pdf", db)
        
        assert "00245" in data["codigo_egreso"], f"CE code mismatch: {data['codigo_egreso']}"
        assert data["numero_orden_pago"] == "00204", f"OP code mismatch: {data['numero_orden_pago']}"
        assert data["codigo_contrato"] == "CA-013-2026", f"Contract mismatch: {data['codigo_contrato']}"
        assert "PARROQUIA SAN LORENZO" in data["nombre_beneficiario"].upper()
        
        # Financial validation
        assert abs(data["total_orden"] - 8330000.0) < 0.1, f"Total orden expected 8330000.0, got {data['total_orden']}"
        assert abs(data["total_retencion"] - 199500.0) < 0.1, f"Total retencion expected 199500.0, got {data['total_retencion']}"
        assert abs(data["total_pagar"] - 8130500.0) < 0.1, f"Total pagar expected 8130500.0, got {data['total_pagar']}"
        
        # Deductions classification validation
        assert abs(data.get("reteiva", 0.0) - 199500.0) < 0.1, f"Reteiva expected 199500.0, got {data.get('reteiva')}"
        assert abs(data.get("total_estampillas", 0.0) - 0.0) < 0.1, f"Estampillas should be 0, got {data.get('total_estampillas')}"
        assert abs(data.get("retefuente", 0.0) - 0.0) < 0.1
        assert abs(data.get("reteica", 0.0) - 0.0) < 0.1
        
        # Accounting equation check
        assert abs((data["total_orden"] - data["total_retencion"]) - data["total_pagar"]) < 0.1
        print("[OK] test_extract_pago_245_parroquia_san_lorenzo passed: Bruto $8.330.000, ReteIVA $199.500, Neto $8.130.500.")
    finally:
        db.close()

def test_extract_packet_con_estampillas_multiples():
    """Test case with multiple territorial stamps (Pro-Cultura, Adulto Mayor, Pro-Hospital, Pro-Deporte) and ICA."""
    db = SessionLocal()
    try:
        data = extract_payment_packet_data(SAMPLE_PACKET_ESTAMPILLAS.encode("utf-8"), "OBRA_310.pdf", db)
        
        assert abs(data["total_orden"] - 25000000.0) < 0.1
        assert abs(data["total_retencion"] - 1650000.0) < 0.1
        assert abs(data["total_pagar"] - 23350000.0) < 0.1
        
        # Territorial stamps sum: 500k + 500k + 250k + 250k = 1.500.000
        assert abs(data.get("total_estampillas", 0.0) - 1500000.0) < 0.1, f"Estampillas sum expected 1500000, got {data.get('total_estampillas')}"
        # ICA: 150.000
        assert abs(data.get("reteica", 0.0) - 150000.0) < 0.1, f"Reteica expected 150000, got {data.get('reteica')}"
        
        # Verify detail items
        assert len(data["retenciones_detalle"]) == 5
        stamp_items = [r for r in data["retenciones_detalle"] if r.get("es_estampilla")]
        assert len(stamp_items) == 4, f"Expected 4 stamp items, found {len(stamp_items)}"
        print("[OK] test_extract_packet_con_estampillas_multiples passed: Total Estampillas $1.500.000 + ICA $150.000 = $1.650.000.")
    finally:
        db.close()

if __name__ == "__main__":
    test_extract_payment_packet_data()
    test_import_pdf_packets_endpoint_flow()
    test_extract_ce_00271_with_supervision_certification()
    test_extract_pago_245_parroquia_san_lorenzo()
    test_extract_packet_con_estampillas_multiples()
    print("\nALL PDF PACKET TESTS PASSED PERFECTLY! [OK]")

