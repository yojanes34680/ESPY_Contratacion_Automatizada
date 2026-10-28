"""Automated test script for Composite / Multi-Document PDF extraction (RUT + Propuesta + Banco)
and verification of justification_agent and object_agent.
"""
import sys
from pathlib import Path

# Configurar encoding UTF-8 en stdout para Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal, engine, Base
from app.models.document import Documento, TipoDocumento
from app.models.contractor import Contratista
from app.services.composite_analyzer import composite_analyzer
from app.services.gemini_client import gemini_service
from app.services.agents.justification_agent import justification_agent
from app.services.agents.object_agent import object_agent
from app.schemas.agent import JustificacionGenerationInput, ObjetoGenerationInput

MOCK_COMPOSITE_TEXT = """
=== PÁGINA 1 ===
REPÚBLICA DE COLOMBIA
DIAN - DIRECCIÓN DE IMPUESTOS Y ADUANAS NACIONALES
FORMULARIO 001 - REGISTRO ÚNICO TRIBUTARIO (RUT)
5. Número de identificación tributaria (NIT): 901234567
6. DV: 8
24. Tipo de contribuyente: Persona jurídica
35. Razón social: HIDROSERVICIOS Y CONSTRUCCIONES DEL ORIENTE S.A.S.
39. Departamento: Antioquia
40. Ciudad / Municipio: Medellín
41. Dirección principal: CALLE 50 # 45-30 OFICINA 402
42. Correo electrónico: contratacion@hidroservicios.com.co
44. Teléfono 1: 3109876543
46. Actividad económica principal: 4220
53. Responsabilidades: 48 - Impuesto sobre las ventas - IVA
98. Representación legal: CARLOS ALBERTO MARIN GOMEZ
CÉDULA REP: 71234567

=== PÁGINA 2 ===
BANCO BANCOLOMBIA
CERTIFICACIÓN BANCARIA
Bancolombia certifica que HIDROSERVICIOS Y CONSTRUCCIONES DEL ORIENTE S.A.S.
es titular de la CUENTA DE AHORROS NÚMERO 10293847561
la cual se encuentra activa y a satisfacción.
Fecha de expedición: 15 de enero de 2026.

=== PÁGINA 3 ===
HIDROSERVICIOS Y CONSTRUCCIONES DEL ORIENTE S.A.S.
NIT: 901.234.567-8
PROPUESTA ECONÓMICA Y TÉCNICA
Señores:
EMPRESA DE SERVICIOS PÚBLICOS DOMICILIARIOS (ESP)

OBJETO DE LA PROPUESTA:
Prestar los servicios especializados de mantenimiento electromecánico y calibración de bombas sumergibles en la estación de bombeo de agua residual de la ESP.

ALCANCE DE LA PROPUESTA:
Inspección periódica de bombas sumergibles, calibración de variadores de velocidad, reemplazo de rodamientos y entrega de informes técnicos mensuales con pruebas operativas.

CONDICIONES ECONÓMICAS:
VALOR TOTAL DE LA PROPUESTA: $ 48.000.000 COP
(CUARENTA Y OCHO MILLONES DE PESOS M/CTE)

PLAZO DE EJECUCIÓN: 6 MESES

FORMA DE PAGO:
Pagos mensuales vencidos previa entrega del informe técnico mensual y visto bueno del supervisor de la ESP.
"""

def test_composite_pdf_extraction():
    print("================================================================")
    print("1. PROBANDO COMPOSITE ANALYZER (DETECCIÓN Y SEGMENTACIÓN)")
    print("================================================================")
    detected_types = composite_analyzer.detect_subdocument_types(MOCK_COMPOSITE_TEXT)
    print(f"Subdocumentos detectados en texto compuesto: {detected_types}")
    assert "RUT" in detected_types, "Fallo: No detectó el RUT"
    assert "PROPUESTA_ECONOMICA" in detected_types, "Fallo: No detectó la Propuesta Económica"
    assert "CERTIFICACION_BANCARIA" in detected_types, "Fallo: No detectó la Certificación Bancaria"
    print("✓ Detección de subdocumentos exitosa: RUT, Propuesta y Banco identificados.")

    pages = composite_analyzer.segment_by_pages(MOCK_COMPOSITE_TEXT)
    print(f"Páginas segmentadas: {len(pages)}")
    assert len(pages) == 3, f"Se esperaban 3 páginas, se obtuvieron {len(pages)}"
    assert "RUT" in pages[0]["tipos_detectados"], "Página 1 debe ser RUT"
    assert "CERTIFICACION_BANCARIA" in pages[1]["tipos_detectados"], "Página 2 debe ser Banco"
    assert "PROPUESTA_ECONOMICA" in pages[2]["tipos_detectados"], "Página 3 debe ser Propuesta"
    print("✓ Segmentación de páginas exitosa.")

    print("\n================================================================")
    print("2. PROBANDO EXTRACTOR HEURÍSTICO AVANZADO DEL RUT Y PROPUESTA")
    print("================================================================")
    extracted = gemini_service._heuristic_contractor_extraction(MOCK_COMPOSITE_TEXT)
    print(f"Tipo Persona: {extracted.tipo_persona}")
    print(f"Tipo Documento: {extracted.tipo_documento}")
    print(f"NIT: {extracted.numero_documento} - DV: {extracted.digito_verificacion}")
    print(f"Nombre / Razón Social: {extracted.nombre_o_razon_social}")
    print(f"Representante Legal: {extracted.representante_legal_nombre} (Doc: {extracted.representante_legal_documento})")
    print(f"Dirección: {extracted.direccion}")
    print(f"Municipio: {extracted.municipio}")
    print(f"Departamento: {extracted.departamento}")
    print(f"Correo: {extracted.correo_electronico}")
    print(f"Teléfono: {extracted.telefono}")
    print(f"Actividad CIIU: {extracted.actividad_economica_ciiu}")
    print(f"Régimen Tributario: {extracted.regimen_tributario}")
    print(f"Banco: {extracted.banco_nombre} ({extracted.banco_tipo_cuenta} No. {extracted.banco_numero_cuenta})")
    print(f"Valor Propuesto: ${extracted.valor_propuesto:,.2f}")
    print(f"Plazo Propuesto: {extracted.plazo_propuesto} {extracted.unidad_plazo_propuesto}")
    print(f"Objeto Propuesto: {extracted.objeto_propuesto}")
    print(f"Alcance Propuesto: {extracted.alcance_propuesto}")
    print(f"Forma de Pago: {extracted.forma_pago_propuesta}")

    assert extracted.tipo_persona == "JURIDICA", "Debe ser persona jurídica"
    assert extracted.numero_documento == "901234567", f"NIT incorrecto: {extracted.numero_documento}"
    assert extracted.digito_verificacion == "8", f"DV incorrecto: {extracted.digito_verificacion}"
    assert "HIDROSERVICIOS" in extracted.nombre_o_razon_social.upper(), "Razón social incorrecta"
    assert extracted.regimen_tributario == "RESPONSABLE_IVA", f"Régimen incorrecto: {extracted.regimen_tributario}"
    assert extracted.valor_propuesto == 48000000.0, f"Valor propuesto incorrecto: {extracted.valor_propuesto}"
    assert extracted.plazo_propuesto == 6, f"Plazo propuesto incorrecto: {extracted.plazo_propuesto}"
    assert extracted.unidad_plazo_propuesto == "MESES", f"Unidad plazo incorrecta: {extracted.unidad_plazo_propuesto}"
    assert "CARLOS ALBERTO" in (extracted.representante_legal_nombre or "").upper(), "Representante legal incorrecto"
    assert extracted.banco_nombre == "Bancolombia", f"Banco incorrecto: {extracted.banco_nombre}"
    assert extracted.banco_tipo_cuenta == "Ahorros", f"Tipo cuenta incorrecto: {extracted.banco_tipo_cuenta}"
    assert "10293847561" in (extracted.banco_numero_cuenta or ""), f"Número cuenta incorrecto: {extracted.banco_numero_cuenta}"
    print("✓ Extracción heurística de RUT, Propuesta y Banco 100% precisa.")

    print("\n================================================================")
    print("3. PROBANDO JUSTIFICATION_AGENT CON EXPEDIENTE COMPUESTO (GENERIC FILENAME)")
    print("================================================================")
    db = SessionLocal()
    try:
        # Crear archivo temporal con nombre genérico que NO dice 'propuesta'
        test_file = backend_dir / "uploads" / "expediente_completo_unificado.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(MOCK_COMPOSITE_TEXT)

        # Crear registro en BD como tipo OTRO
        doc_record = Documento(
            contratista_id=None,
            nombre_archivo_original="expediente_completo_unificado.pdf", # Archivo llamado genéricamente
            nombre_archivo_almacenado="expediente_completo_unificado.txt",
            ruta_relativa="uploads/expediente_completo_unificado.txt",
            tipo_documento=TipoDocumento.OTRO,
            tamano_bytes=len(MOCK_COMPOSITE_TEXT)
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)

        # Probar que justification_agent identifica la propuesta DENTRO del archivo
        found_doc, extracted_txt, detected_type = justification_agent.validate_and_extract_source_document([doc_record.id], db)
        print(f"Documento identificado: {found_doc.nombre_archivo_original}")
        print(f"Tipo detectado internamente: {detected_type}")
        print(f"Longitud texto propuesta extraído: {len(extracted_txt)} caracteres")
        assert detected_type == "PROPUESTA", f"Se esperaba PROPUESTA, se obtuvo {detected_type}"
        assert "48.000.000" in extracted_txt, "La sección aislada debe contener la propuesta económica"

        # Generar Justificación del Estudio Previo
        input_data = JustificacionGenerationInput(
            document_ids=[doc_record.id],
            tipologia="PRESTACION_SERVICIOS",
            necesidad_contexto="mantenimiento de bombas sumergibles",
            contratista_nombre=extracted.nombre_o_razon_social,
            valor_estimado=extracted.valor_propuesto
        )
        res_just = justification_agent.generate_justificacion(input_data, db)
        print("\n--- JUSTIFICACIÓN GENERADA ---")
        print(res_just.justificacion_estudio_previo[:300] + "...")
        assert res_just.documento_soporte_usado == "expediente_completo_unificado.pdf"
        assert "48,000,000.00" in res_just.justificacion_estudio_previo or "48.000.000" in res_just.justificacion_estudio_previo
        print("✓ JustificationAgent procesó exitosamente el PDF compuesto con nombre genérico.")

        print("\n================================================================")
        print("4. PROBANDO OBJECT_AGENT CON EXPEDIENTE COMPUESTO")
        print("================================================================")
        obj_input = ObjetoGenerationInput(
            document_ids=[doc_record.id],
            tipologia="PRESTACION_SERVICIOS",
            contratista_nombre=extracted.nombre_o_razon_social,
            necesidad_descripcion="Prestar servicios especializados para la ESP"
        )
        res_obj = object_agent.generate_objeto(obj_input, db)
        print(f"Objeto sugerido: {res_obj.objeto_sugerido}")
        print(f"Alcance sintetizado: {res_obj.alcance_sintetizado}")
        assert res_obj.verbo_rector == "Prestar"
        assert "bombas sumergibles" in res_obj.objeto_sugerido.lower()
        print("✓ ObjectAgent estructuró el objeto y alcance a partir de la propuesta en el PDF compuesto.")

        # Limpiar doc de prueba
        db.delete(doc_record)
        db.commit()
        if test_file.exists():
            test_file.unlink()

    finally:
        db.close()

    print("\n================================================================")
    print("¡TODAS LAS PRUEBAS DE EXTRACCIÓN MULTIDOCUMENTO PASARON CON ÉXITO!")
    print("================================================================")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    test_composite_pdf_extraction()
