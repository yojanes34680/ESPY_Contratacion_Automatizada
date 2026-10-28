"""
Prueba integral de entendimiento semántico y estructuración contractual
para propuestas económicas y cotizaciones reales (caso Asistymed / Dr. Nelson Molina).
"""
import sys
from pathlib import Path

# Configurar path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.database import SessionLocal
from app.models.contractor import Contratista
from app.models.document import Documento, TipoDocumento
from app.services.document_parser import parse_document_text
from app.services.composite_analyzer import composite_analyzer
from app.services.gemini_client import gemini_service
from app.services.agents.object_agent import object_agent
from app.services.agents.justification_agent import justification_agent
from app.services.agents.services_agent import ServicesContractAgent
from app.schemas.agent import (
    ObjetoGenerationInput,
    JustificacionGenerationInput,
    ContractDraftingInput
)

def test_real_proposal_understanding():
    print("=== INICIO DE PRUEBA: ENTENDIMIENTO DE PROPUESTA REAL (ASISTYMED) ===")

    pdf_path = Path(r"C:\Users\Usuario\.gemini\antigravity-ide\brain\3f428359-04c4-49ce-b520-415aa51c9d1e\.user_uploaded\media_1788985188283.pdf")
    assert pdf_path.exists(), f"El archivo PDF no existe en {pdf_path}"

    # 1. Parsear texto y OCR
    text = parse_document_text(pdf_path)
    assert len(text) > 500, "El texto extraído es demasiado corto o falló el OCR"
    print(f"[OK] Texto extraído: {len(text)} caracteres")

    # 2. Segmentador / Analizador de documentos compuestos
    subdocs = composite_analyzer.detect_subdocument_types(text)
    print(f"[OK] Subdocumentos detectados: {subdocs}")
    assert "PROPUESTA_ECONOMICA" in subdocs, "No se detectó PROPUESTA_ECONOMICA en el documento"
    assert composite_analyzer.contains_proposal_or_market_study(text), "Fallo al verificar contains_proposal_or_market_study"

    # 3. Extracción de datos del contratista y propuesta
    ext_data = gemini_service.extract_contractor_data(text)
    print(f"  - Contratista: {ext_data.nombre_o_razon_social}")
    print(f"  - Nombre Comercial: {ext_data.nombre_comercial}")
    print(f"  - Correo: {ext_data.correo_electronico}")
    print(f"  - Teléfono: {ext_data.telefono}")
    print(f"  - Valor: ${ext_data.valor_propuesto:,.2f}")
    print(f"  - Objeto sintetizado: {ext_data.objeto_propuesto}")
    print(f"  - Alcance sintetizado: {ext_data.alcance_propuesto}")
    print(f"  - Forma de pago: {ext_data.forma_pago_propuesta}")

    assert "Molina" in ext_data.nombre_o_razon_social or "Nelson" in ext_data.nombre_o_razon_social, f"Nombre incorrecto: {ext_data.nombre_o_razon_social}"
    assert ext_data.correo_electronico == "assistymed@gmail.com", f"Correo sucio o incorrecto: {ext_data.correo_electronico}"
    assert ext_data.valor_propuesto == 3193000.0, f"Valor incorrecto: {ext_data.valor_propuesto}"
    assert ext_data.regimen_tributario == "NO_RESPONSABLE_IVA", f"Régimen incorrecto: {ext_data.regimen_tributario}"
    assert ext_data.objeto_propuesto and any(k in ext_data.objeto_propuesto.lower() for k in ["ocupacional", "médic", "medic", "examen", "osteo"]), "Objeto propuesto no menciona exámenes ocupacionales"
    if ext_data.alcance_propuesto:
        assert any(k in ext_data.alcance_propuesto.lower() for k in ["osteo", "ocupacional", "examen", "laboral"]), "Alcance propuesto no detalla examen osteomuscular"
    print("[OK] Extracción de contratista y propuesta validada con éxito.")

    # 4. Agente de Objeto Contractual
    obj_input = ObjetoGenerationInput(
        tipologia="PRESTACION_SERVICIOS",
        necesidad_descripcion=ext_data.objeto_propuesto,
        contratista_nombre=ext_data.nombre_o_razon_social,
        texto_propuesta_o_estudio=text,
        lugar_ejecucion="las instalaciones y redes de la Empresa de Servicios Públicos"
    )
    obj_res = object_agent.generate_objeto(obj_input)
    print(f"  - Objeto sugerido por agente: {obj_res.objeto_sugerido}")
    print(f"  - Verbo rector: {obj_res.verbo_rector}")

    # Verificar que NO haya tautologías ni repeticiones
    assert "prestar servicios profesionales y de apoyo a la gestión técnica especializada con plena autonomía para prestar" not in obj_res.objeto_sugerido.lower(), "Detectada duplicación tautológica en el objeto"
    assert obj_res.objeto_sugerido.count("Empresa de Servicios Públicos") <= 1, "Repetición innecesaria del nombre de la entidad"
    assert obj_res.verbo_rector in ("Realizar", "Prestar"), f"Verbo rector esperado 'Realizar' o 'Prestar', obtenido '{obj_res.verbo_rector}'"
    print("[OK] Objeto contractual riguroso y sin duplicaciones validado.")

    # 5. Agente de Justificación del Estudio Previo con soporte en BD
    db = SessionLocal()
    try:
        # Registrar documento en BD si no existe
        doc = db.query(Documento).filter(Documento.nombre_archivo_original == "media_1788985188283.pdf").first()
        if not doc:
            doc = Documento(
                nombre_archivo_original="media_1788985188283.pdf",
                nombre_archivo_almacenado="media_1788985188283.pdf",
                ruta_relativa=str(pdf_path),
                tamano_bytes=pdf_path.stat().st_size,
                tipo_documento=TipoDocumento.PROPUESTA,
                mime_type="application/pdf",
                datos_extraidos_json={}
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

        just_input = JustificacionGenerationInput(
            document_ids=[doc.id],
            tipologia="PRESTACION_SERVICIOS",
            modalidad="CONTRATACION_DIRECTA",
            necesidad_contexto=obj_res.objeto_sugerido,
            contratista_nombre=ext_data.nombre_o_razon_social,
            valor_estimado=ext_data.valor_propuesto
        )
        just_res = justification_agent.generate_justificacion(just_input, db=db)
        print("  - Justificación generada:")
        print(just_res.justificacion_estudio_previo[:300] + "...")

        assert "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER" in just_res.justificacion_estudio_previo
        assert "142 de 1994" in just_res.justificacion_estudio_previo, "Falta fundamentación de la Ley 142 de 1994"
        assert "209 de la Constitución" in just_res.justificacion_estudio_previo or "función administrativa" in just_res.justificacion_estudio_previo.lower()
        print("[OK] Justificación de Estudio Previo contextualizada validada bajo las 4 secciones oficiales.")

        # 6. Agente de Prestación de Servicios (Drafting de Objetivos y Obligaciones)
        services_agent = ServicesContractAgent()
        draft_input = ContractDraftingInput(
            tipologia="PRESTACION_SERVICIOS",
            modalidad="CONTRATACION_DIRECTA",
            necesidad_descripcion=obj_res.objeto_sugerido,
            alcance_esperado=ext_data.alcance_propuesto,
            valor_estimado=ext_data.valor_propuesto,
            plazo=1,
            unidad_plazo="MESES"
        )
        draft_res = services_agent.fallback_generator(draft_input)
        print(f"  - Objetivo General: {draft_res.objetivo_general}")
        print("  - Objetivos Específicos Medibles:")
        for obj in draft_res.objetivos_especificos:
            print(f"    * {obj}")

        assert len(draft_res.objetivos_especificos) >= 3, "Deben generarse al menos 3 objetivos específicos"
        assert not any("de la disponibilidad" in o.lower() for o in draft_res.objetivos_especificos), "Contiene texto genérico roto"
        assert all(o.split()[0].endswith(('ar', 'er', 'ir')) for o in draft_res.objetivos_especificos), "Todos los objetivos deben iniciar con verbo en infinitivo"
        print("[OK] Objetivos específicos derivados de la propuesta validados con éxito bajo el estándar de la ESPY.")

    finally:
        db.close()

    print("\n=== TODAS LAS PRUEBAS DE ENTENDIMIENTO DE PROPUESTA PASARON EXITOSAMENTE (100%) ===")

if __name__ == "__main__":
    test_real_proposal_understanding()
