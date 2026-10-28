"""Agente Especializado en la Generación del Objeto Contractual (Ley 142/1994).
Formula automáticamente el objeto en infinitivo, técnico y riguroso a partir
del Estudio de Mercado, Propuesta Económica o parámetros suministrados,
permitiendo al usuario modificarlo y ajustarlo a su total gusto.
"""
from typing import Optional, List
from pathlib import Path
from sqlalchemy.orm import Session
import re

from app.config import settings
from app.models.document import Documento, TipoDocumento
from app.schemas.agent import ObjetoGenerationInput, ObjetoGenerationResult
from app.services.document_parser import parse_document_text
from app.services.composite_analyzer import composite_analyzer
from app.services.gemini_client import gemini_service
from app.utils.object_normalizer import normalize_objeto_contractual
from app.utils.logger import logger

class ObjectAgent:
    """
    Agente formulador del Objeto Contractual para Empresas de Servicios Públicos.
    Asegura estructuración sintáctica correcta: Verbo en infinitivo + Bien/Servicio + Delimitación.
    """

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

    def extract_context_from_docs(self, document_ids: List[int], db: Session) -> str:
        """Extrae el contenido textual relevante de los documentos asociados, priorizando la propuesta económica."""
        extracted_chunks = []
        for doc_id in document_ids:
            doc = db.query(Documento).filter(Documento.id == doc_id).first()
            if not doc:
                continue
            ext = Path(doc.nombre_archivo_original).suffix.lower()
            if ext in self.ALLOWED_EXTENSIONS:
                name_lower = doc.nombre_archivo_original.lower()
                excluded_names = ["cdp", "disponibilidad", "presupuestal", "rut", "cedula", "cédula", "camara", "cámara", "antecedentes", "banco", "certificacion_bancaria", "certificación_bancaria"]
                if any(ex in name_lower for ex in excluded_names):
                    continue

                full_path = settings.BASE_DIR / doc.ruta_relativa
                if full_path.exists():
                    try:
                        txt = parse_document_text(full_path)
                        if txt:
                            # Si es un documento compuesto, extraer con prioridad la sección de propuesta
                            prop_section = composite_analyzer.extract_subdocument_text(txt, "PROPUESTA_ECONOMICA")
                            if not prop_section:
                                prop_section = composite_analyzer.extract_subdocument_text(txt, "ESTUDIO_MERCADO")

                            if prop_section:
                                extracted_chunks.append(f"{prop_section[:10000]}")
                            else:
                                # Verificar que no sea texto exclusivo de CDP o RUT
                                sub_types = composite_analyzer.detect_subdocument_types(txt)
                                if "CDP" in sub_types and "PROPUESTA_ECONOMICA" not in sub_types:
                                    continue
                                if "RUT" in sub_types and "PROPUESTA_ECONOMICA" not in sub_types:
                                    continue
                                extracted_chunks.append(f"{txt[:8000]}")
                    except Exception as e:
                        logger.warning(f"No se pudo parsear texto de {doc.nombre_archivo_original}: {e}")
        return "\n\n".join(extracted_chunks)

    def generate_objeto(
        self,
        input_data: ObjetoGenerationInput,
        db: Optional[Session] = None,
        override_api_key: Optional[str] = None
    ) -> ObjetoGenerationResult:
        """
        Formula el Objeto Contractual sugerido con soporte de LLM o fallback determinista.
        """
        doc_text = input_data.texto_propuesta_o_estudio or ""
        if not doc_text and input_data.document_ids and db:
            doc_text = self.extract_context_from_docs(input_data.document_ids, db)

        # Inferencia automática de tipología a partir del texto de la propuesta
        from app.utils.contract_prefix_helper import infer_contract_tipologia
        detected_tipo, is_conexo = infer_contract_tipologia(
            propuesta_text=doc_text,
            cdp_text="",
            current_tipologia=input_data.tipologia
        )
        if detected_tipo and detected_tipo != input_data.tipologia:
            input_data.tipologia = detected_tipo

        system_instruction = (
            "Actúa como un abogado experto en contratación de la Empresa de Servicios Públicos de Yolombó E.S.P. "
            "Redacta ÚNICAMENTE el OBJETO CONTRACTUAL en un solo párrafo en mayúsculas sostenidas (máximo 40 palabras), "
            "basándote exclusivamente en la actividad o bien real de la propuesta del contratista.\n"
            "REGLAS ESTRICTAS:\n"
            "- NUNCA repitas palabras, frases ni conectores (prohibido repetir 'PRESTACIÓN DE SERVICIOS', 'APOYO A LA GESTIÓN' o 'ADSCRITOS AL ÁREA OPERATIVA' más de una vez).\n"
            "- NUNCA uses frases comodín como 'LABORES TÉCNICAS ESPECIALIZADAS EN LA INFRAESTRUCTURA OPERATIVA' ni 'ACTIVIDADES TÉCNICAS REQUERIDAS'. Menciona con nombre propio qué se va a hacer o comprar (ej. mantenimiento de herramientas eléctricas, sensibilización puerta a puerta del PGIRS, suministro de químicos, etc.).\n"
            "- Entrega una oración limpia, gramaticalmente perfecta y sin texto adicional."
        )

        user_prompt = (
            f"DATOS Y CONTEXTO REAL DE ENTRADA PARA EL OBJETO CONTRACTUAL:\n"
            f"- Tipología contractual: {input_data.tipologia}\n"
            f"- Necesidad o actividad informada: {input_data.necesidad_descripcion or 'No especificada'}\n"
            f"- Contratista: {input_data.contratista_nombre or 'Contratista Suministrado'}\n"
            f"- Lugar / Ámbito: {input_data.lugar_ejecucion}\n\n"
            f"TEXTO EXTRAÍDO DEL DOCUMENTO DE PROPUESTA / COTIZACIÓN / ESTUDIO:\n"
            f"{doc_text[:6000] if doc_text else (input_data.necesidad_descripcion or 'No se adjuntó texto de propuesta')}\n\n"
            f"Instrucción: Genera única y exclusivamente el Objeto Contractual en mayúsculas sostenidas, sin repetir ninguna palabra o frase, mencionando la labor o bien real."
        )

        def fallback_generator() -> ObjetoGenerationResult:
            from app.utils.objeto_builder import build_objeto_contractual
            tipologia = input_data.tipologia.upper().strip()
            necesidad = (input_data.necesidad_descripcion or "").strip()

            # 1. Extraer datos estructurados del documento con máxima prioridad
            extracted_obj_from_doc = None
            extracted_alc_from_doc = None
            if doc_text:
                doc_extracted = gemini_service.extract_contractor_data(doc_text)
                if doc_extracted.objeto_propuesto:
                    extracted_obj_from_doc = doc_extracted.objeto_propuesto
                if doc_extracted.alcance_propuesto:
                    extracted_alc_from_doc = doc_extracted.alcance_propuesto

                if not extracted_obj_from_doc:
                    match_obj = re.search(
                        r"(?:objeto(?:\s+de\s+la\s+(?:oferta|propuesta|cotizaci[oó]n|contrataci[oó]n))?|prop[oó]sito)[:\s]+([^\n\r\.\;]{10,300})",
                        doc_text,
                        re.IGNORECASE
                    )
                    if match_obj:
                        extracted_obj_from_doc = match_obj.group(1).strip()

                if not extracted_alc_from_doc:
                    match_alc = re.search(
                        r"(?:alcance(?:\s+de\s+la\s+propuesta)?|especificaciones(?:\s+t[eé]cnicas)?|entregables|actividades(?:\s+a\s+desarrollar)?)[:\s]+([^\n\r]{15,350})",
                        doc_text,
                        re.IGNORECASE
                    )
                    if match_alc:
                        extracted_alc_from_doc = match_alc.group(1).strip()

            # Construir objeto aplicando la fórmula estructural obligatoria sin plantillas quemadas
            # Prioridad 1: Objeto extraído del texto real del PDF subido
            insumo_principal = extracted_obj_from_doc or necesidad
            objeto_final = build_objeto_contractual(
                propuesta_o_cotizacion=insumo_principal,
                tipologia=tipologia,
                necesidad_descripcion=necesidad,
                contexto=doc_text[:1000] if doc_text else None
            )

            # Obtener verbo rector simbólico para el esquema
            if objeto_final.startswith("SUMINISTRO") or objeto_final.startswith("COMPRAVENTA"):
                verbo = "Suministrar"
            elif objeto_final.startswith("EJECUCIÓN") or "OBRA" in objeto_final:
                verbo = "Ejecutar"
            elif objeto_final.startswith("ARRENDAMIENTO"):
                verbo = "Arrendar"
            else:
                verbo = "Prestar"

            return ObjetoGenerationResult(
                objeto_sugerido=objeto_final,
                verbo_rector=verbo,
                alcance_sintetizado=extracted_alc_from_doc or "Ejecución técnica y operativa conforme a la propuesta y especificaciones institucionales de la ESPY.",
                justificacion_tecnica_objeto="Objeto contractual estructurado conforme a la actividad real de la propuesta, sin redundancias ni repeticiones."
            )

        result = gemini_service.generate_agent_structured_draft(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            schema_class=ObjetoGenerationResult,
            fallback_factory=fallback_generator,
            override_api_key=override_api_key
        )
        if result and getattr(result, "objeto_sugerido", None):
            result.objeto_sugerido = normalize_objeto_contractual(result.objeto_sugerido, input_data.tipologia)
        return result

object_agent = ObjectAgent()
