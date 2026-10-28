"""Agente Especializado en la Justificación del Estudio Previo (Ley 142/1994).
Exige de forma obligatoria e indispensable el documento en PDF o DOCX
del Estudio de Mercado o la Propuesta Económica del contratista.
"""
import re
from typing import Optional, List, Tuple
from pathlib import Path
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document import Documento, TipoDocumento
from app.schemas.agent import JustificacionGenerationInput, JustificacionGenerationResult
from app.services.document_parser import parse_document_text
from app.services.composite_analyzer import composite_analyzer
from app.services.gemini_client import gemini_service
from app.utils.logger import logger

class JustificationAgent:
    """
    Agente que elabora la justificación integral del Estudio Previo para una Empresa de Servicios Públicos.
    Garantiza el cumplimiento estricto del requerimiento documental (Propuesta o Estudio de Mercado).
    """

    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
    KEYWORD_PATTERNS = [
        "propuesta", "cotizacion", "cotización", "oferta", 
        "estudio de mercado", "estudio_mercado", "analisis de precios", "presupuesto"
    ]

    def validate_and_extract_source_document(
        self, 
        document_ids: List[int], 
        db: Session
    ) -> Tuple[Documento, str, str]:
        """
        Valida que exista al menos un documento PDF/DOCX correspondiente a
        Estudio de Mercado o Propuesta Económica, y extrae su texto.
        Soporta archivos individuales y expedientes compuestos (varios documentos en un solo PDF).
        Retorna (documento_orm, texto_extraido, tipo_detectado).
        """
        if not document_ids:
            raise ValueError(
                "Para elaborar la justificación del estudio previo es indispensable adjuntar el documento en PDF o DOCX "
                "del Estudio de Mercado o la Propuesta Económica del contratista."
            )

        found_doc: Optional[Documento] = None
        extracted_text: str = ""
        detected_type: str = "PROPUESTA"

        # Fase 1: Buscar con estricta prioridad de PROPUESTA/COTIZACIÓN sobre ESTUDIO_MERCADO
        # PROHIBICIÓN ESTRICTA: Excluir terminantemente CDP, RUT, CEDULA, CAMARA DE COMERCIO o ANTECEDENTES
        candidate_docs = []
        excluded_names = ["cdp", "disponibilidad", "presupuestal", "rut", "cedula", "cédula", "camara", "cámara", "antecedentes", "banco", "certificacion_bancaria", "certificación_bancaria"]
        for doc_id in document_ids:
            doc = db.query(Documento).filter(Documento.id == doc_id).first()
            if not doc:
                continue

            ext = Path(doc.nombre_archivo_original).suffix.lower()
            if ext not in self.ALLOWED_EXTENSIONS:
                continue

            name_lower = doc.nombre_archivo_original.lower()
            if any(ex in name_lower for ex in excluded_names):
                continue

            candidate_docs.append(doc)

        # Prioridad 1: Buscar documento clasificado expresamente como PROPUESTA o con palabras clave de cotización/propuesta/oferta
        for doc in candidate_docs:
            name_lower = doc.nombre_archivo_original.lower()
            is_propuesta = (
                doc.tipo_documento == TipoDocumento.PROPUESTA
                or any(k in name_lower for k in ["propuesta", "cotizacion", "cotización", "oferta"])
            )
            is_mercado = doc.tipo_documento == TipoDocumento.ESTUDIO_MERCADO or "estudio" in name_lower or "mercado" in name_lower
            if is_propuesta and not is_mercado:
                found_doc = doc
                detected_type = "PROPUESTA"
                break

        # Prioridad 2: Si no hubo propuesta explícita, buscar cualquier candidato válido (incluyendo estudio de mercado)
        if not found_doc:
            for doc in candidate_docs:
                name_lower = doc.nombre_archivo_original.lower()
                is_propuesta_type = doc.tipo_documento in (TipoDocumento.PROPUESTA, TipoDocumento.ESTUDIO_MERCADO)
                has_keyword = any(k in name_lower for k in self.KEYWORD_PATTERNS)

                if is_propuesta_type or has_keyword:
                    found_doc = doc
                    if doc.tipo_documento == TipoDocumento.ESTUDIO_MERCADO or "estudio" in name_lower or "mercado" in name_lower:
                        detected_type = "ESTUDIO_MERCADO"
                    else:
                        detected_type = "PROPUESTA"
                    break

        # Fase 2: Si no se identificó por nombre/tipo (ej. archivo nombrado 'expediente.pdf' o 'documentos.pdf'),
        # inspeccionar el contenido interno de los documentos candidatos con composite_analyzer
        if not found_doc:
            for doc in candidate_docs:
                full_path = settings.BASE_DIR / doc.ruta_relativa
                if not full_path.exists():
                    continue

                raw_text = parse_document_text(full_path)
                if not raw_text or not raw_text.strip():
                    continue

                # Analizar si contiene sección de propuesta o estudio de mercado adentro
                if composite_analyzer.contains_proposal_or_market_study(raw_text):
                    found_doc = doc
                    subdocs = composite_analyzer.detect_subdocument_types(raw_text)
                    if "ESTUDIO_MERCADO" in subdocs:
                        detected_type = "ESTUDIO_MERCADO"
                        isolated = composite_analyzer.extract_subdocument_text(raw_text, "ESTUDIO_MERCADO")
                    else:
                        detected_type = "PROPUESTA"
                        isolated = composite_analyzer.extract_subdocument_text(raw_text, "PROPUESTA_ECONOMICA")
                    
                    extracted_text = isolated or raw_text
                    logger.info(f"Subsección de {detected_type} identificada exitosamente dentro del archivo compuesto '{doc.nombre_archivo_original}'.")
                    break

        if not found_doc:
            raise ValueError(
                "Para elaborar la justificación del estudio previo es indispensable adjuntar el documento en PDF o DOCX "
                "del Estudio de Mercado o la Propuesta Económica del contratista (incluso fusionado dentro de un PDF único). "
                "Verifique los archivos cargados."
            )

        # Si aún no tenemos extracted_text, extraerlo del documento encontrado
        if not extracted_text:
            full_path = settings.BASE_DIR / found_doc.ruta_relativa
            if not full_path.exists():
                raise ValueError(f"El archivo físico '{found_doc.nombre_archivo_original}' no se encuentra en el servidor.")

            raw_text = parse_document_text(full_path)
            if not raw_text or not raw_text.strip():
                raise ValueError(
                    f"No se pudo extraer texto legible del documento '{found_doc.nombre_archivo_original}'. "
                    "Asegúrese de que no esté protegido o vacío."
                )

            # Si es un documento compuesto, extraer preferentemente la sección de propuesta
            isolated = composite_analyzer.extract_subdocument_text(raw_text, "PROPUESTA_ECONOMICA")
            extracted_text = isolated or raw_text

        return found_doc, extracted_text, detected_type

    @staticmethod
    def _extract_technical_proposal_details(doc_text: str, context: Optional[str] = None) -> dict:
        """
        Extrae datos clave de la propuesta o cotización: ubicación, plazo,
        especificaciones técnicas (diámetros, tuberías, válvulas, excavaciones, insumos, etc.).
        """
        text = f"{context or ''}\n{doc_text}"
        
        # 1. Ubicación o sector
        m_loc = re.search(r"(?:sector|ubicaci[oó]n|lugar|zona|vereda|barrio|planta|sede)\s*[:\-]?\s*([^\n\.,;]+)", text, re.IGNORECASE)
        if m_loc and len(m_loc.group(1).strip()) > 3 and "definir" not in m_loc.group(1).lower():
            ubicacion = m_loc.group(1).strip()
            if "yolombó" not in ubicacion.lower():
                ubicacion = f"{ubicacion} en el Municipio de Yolombó (Antioquia)"
        elif "ptap" in text.lower():
            ubicacion = "la Planta de Tratamiento de Agua Potable (PTAP) de la ESPY en el Municipio de Yolombó"
        elif "ptar" in text.lower():
            ubicacion = "la Planta de Tratamiento de Aguas Residuales (PTAR) de la ESPY en el Municipio de Yolombó"
        else:
            ubicacion = "el sector urbano y redes matrices del sistema en el Municipio de Yolombó (Antioquia)"

        # 2. Plazo
        m_plazo = re.search(r"(?:plazo|duraci[oó]n|vigencia|tiempo\s+de\s+ejecuci[oó]n)\s*[:\-]?\s*(\d+\s*(?:mes(?:es)?|d[ií]as?|semanas?))", text, re.IGNORECASE)
        plazo = m_plazo.group(1).strip().lower() if m_plazo else None

        # 3. Detección de especificaciones técnicas
        diametros = re.findall(r"\b(?:\d+/\d+|\d+(?:\.\d+)?)\s*(?:\"|pulgadas?|mm)\b", text, re.IGNORECASE)
        diam_str = ", ".join(list(dict.fromkeys(diametros))[:3]) if diametros else None

        has_rde = bool(re.search(r"rde\s*\d+", text, re.IGNORECASE))
        has_valvula = bool(re.search(r"v[aá]lvula", text, re.IGNORECASE))
        has_excavacion = bool(re.search(r"excavaci[oó]n|rotura|demolici[oó]n|lleno|pavimento", text, re.IGNORECASE))
        has_quimicos = bool(re.search(r"coagulante|policloruro|sulfato|cloro|qu[ií]mico|cal\s+hidratada", text, re.IGNORECASE))
        has_medico = bool(re.search(r"m[eé]dic|salud\s+ocupacional|osteomuscular|visiometr|audiometr|espirometr|psicosensom|sg-sst", text, re.IGNORECASE))

        return {
            "ubicacion": ubicacion,
            "plazo": plazo,
            "diametros": diam_str,
            "has_rde": has_rde,
            "has_valvula": has_valvula,
            "has_excavacion": has_excavacion,
            "has_quimicos": has_quimicos,
            "has_medico": has_medico
        }

    def generate_justificacion(
        self,
        input_data: JustificacionGenerationInput,
        db: Session,
        override_api_key: Optional[str] = None
    ) -> JustificacionGenerationResult:
        """
        Ejecuta el agente para estructurar la sección DESCRIPCIÓN DE LA NECESIDAD A SATISFACER
        para el Estudio Previo de la EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P.
        Aplica estrictamente la Regla de Oro, la fórmula del Párrafo 2 basada en el Objeto,
        y el Párrafo 3 condicional según el Tipo de Contrato.
        """
        from app.utils.necesidad_builder import build_descripcion_necesidad

        doc_orm, doc_text, detected_type = self.validate_and_extract_source_document(input_data.document_ids, db)

        # Inferencia automática de tipología a partir del texto de la propuesta
        from app.utils.contract_prefix_helper import infer_contract_tipologia
        detected_tip, is_conexo = infer_contract_tipologia(
            propuesta_text=doc_text,
            cdp_text="",
            current_tipologia=input_data.tipologia
        )
        if detected_tip and detected_tip != input_data.tipologia:
            input_data.tipologia = detected_tipo

        # Determinar el objeto base
        objeto_contrato = (
            getattr(input_data, "objeto", None)
            or input_data.necesidad_contexto
            or "satisfacer los requerimientos técnicos y operativos de la Empresa de Servicios Públicos"
        ).strip()
        tipo_contrato = (input_data.tipologia or "PRESTACION_SERVICIOS").upper().strip()

        system_instruction = (
            "Rol y Objetivo del Agente:\n"
            "Eres un abogado y estructurador técnico experto en contratación de Empresas de Servicios Públicos Domiciliarios "
            "(Ley 142 de 1994) para la ESPY. Tu misión es redactar el apartado 'DESCRIPCIÓN DE LA NECESIDAD A SATISFACER' "
            "de los Estudios Previos, logrando un texto profundo, técnico, fluido y jurídicamente blindado.\n\n"
            "REGLA ESTILÍSTICA CRÍTICA:\n"
            "NUNCA copies textualmente las frases de estas instrucciones (no uses 'NO' en mayúsculas ni repitas fórmulas robóticas "
            "como 'surge la necesidad imperiosa'). Redacta siempre en prosa administrativa formal, fluida y natural, integrando los párrafos de manera orgánica.\n\n"
            "Paso 1: Análisis Inteligente del Insumo (PDF, DOCX o Texto)\n"
            "Identifica en cuál de estos dos escenarios te encuentras:\n"
            "- ESCENARIO A (Propuesta Detallada): El documento contiene múltiples actividades o bienes específicos (3 o más ítems).\n"
            "  Acción: Aplica la Regla de Inclusión Total. Es obligatorio incluir el 100% de las actividades o bienes en el texto final sin resumir ni omitir ninguno.\n"
            "- ESCENARIO B (Cotización Escueta o de Una Sola Línea): El documento solo menciona un concepto general o un único ítem global "
            "(ejemplo: 'Mantenimiento a todo costo de herramientas', 'Arrendamiento de vehículo', 'Suministro de papelería').\n"
            "  Acción: ¡PROHIBIDO dejar una sola viñeta minimalista! Si la cotización es de una sola línea, activa el Desglose Técnico Deductivo: "
            "conserva el ítem principal tal cual viene en la cotización, pero desglosa debajo de él (en al menos 4 o 5 viñetas técnicas) las labores operativas "
            "lógicas e inherentes que conlleva cumplir ese ítem (ej. diagnóstico técnico del estado y operatividad, rutinas de mantenimiento preventivo y correctivo, "
            "suministro e instalación de repuestos/insumos a todo costo requeridos, calibración, pruebas de funcionamiento y entrega formal certificada a satisfacción).\n\n"
            "REGLA DE DISCRIMINACIÓN ESTRICTA (PROHIBIDO CONFUNDIR TÍTULOS CON ACTIVIDADES):\n"
            "- Extrae EXCLUSIVAMENTE las actividades operativas reales o los bienes e insumos cotizados.\n"
            "- Está TERMINANTEMENTE PROHIBIDO incluir como viñetas de la necesidad encabezados o títulos de secciones (ej. 'INFORMACIÓN GENERAL DEL PROCESO', 'Objeto Contractual:', 'Criterio de Selección Aplicado', 'Modalidad de Selección', 'Fecha del Estudio', 'Marco Jurídico'), nombres de oferentes o cuadros comparativos ni textos de evaluación económica.\n\n"
            "Paso 2: Estructura de Redacción (4 Párrafos / Secciones Orgánicas):\n"
            "El texto 'justificacion_estudio_previo' DEBE iniciar obligatoriamente con el título en mayúsculas:\n"
            "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER\n\n"
            "1. Contextualización Operativa Real (Párrafo 1 y 2): Explica la obligación misional de la ESPY (Ley 142 de 1994) conectándola inmediatamente con la realidad operativa del contrato. Explica detalladamente para qué se usan esos equipos, bienes o servicios en el día a día del municipio (ej. atención de daños en redes de acueducto, reparaciones de alcantarillado, labores de ornato y aseo, desgaste natural por uso intensivo en campo y exposición a condiciones climáticas) y cuál es el riesgo operativo si no se contrata (parálisis del servicio, riesgos laborales para los operarios, daño patrimonial de los activos).\n"
            "REGLA DE ORO TEMÁTICA: Prohibido terminantemente mencionar 'acueducto y alcantarillado' si el contrato trata sobre aseo, PGIRS o labores administrativas, y viceversa.\n\n"
            "2. Justificación de Insuficiencia Interna (Párrafo de Insuficiencia / Brecha Interna):\n"
            "   - SI el contrato es de Prestación de Servicios, Apoyo a la Gestión, Mantenimiento, Consultoría u Obra, DEBES insertar TEXTUALMENTE este párrafo exacto sin alterar ni recortar ninguna palabra:\n"
            "     'Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente, con disponibilidad de tiempo exclusivo o con la experticia técnica específica para asumir directamente las labores requeridas; razón por la cual resulta necesario acudir a la contratación externa con el fin de garantizar los principios de eficacia, economía y celeridad de la función administrativa consagrados en el artículo 209 de la Constitución Política.'\n"
            "   - SI el contrato es de Suministro o Compraventa de bienes/insumos, DEBES insertar TEXTUALMENTE esta variante exacta adaptada a inventario sin alterar ni recortar ninguna palabra:\n"
            "     'Actualmente, la ESPY presenta agotamiento en las existencias de su almacén y no produce por sí misma los bienes, materiales e insumos requeridos para el desarrollo normal de sus operaciones; razón por la cual resulta necesario acudir a la contratación externa de suministro con el fin de garantizar los principios de eficacia, economía y celeridad de la función administrativa consagrados en el artículo 209 de la Constitución Política.'\n\n"
            "3. Alcance Técnico de la Necesidad (Sección de Viñetas): Introduce de manera formal las actividades o bienes que la entidad necesita cubrir para satisfacer la necesidad, aplicando la regla del Escenario A (100% de ítems sin omitir) o del Escenario B (Desglose Técnico Deductivo en al menos 4-5 viñetas) según corresponda.\n\n"
            "4. Cierre Constitucional y Legal (Párrafo Final): Concluye articulando la necesidad con los principios de la función administrativa (Art. 209 C.P.: eficacia, economía, celeridad) y el control de los recursos públicos, sustentando que esta contratación es el mecanismo idóneo para garantizar la continuidad del servicio público.\n\n"
            "Regla de Tono OBLIGATORIA:\n"
            "NUNCA redactes en primera persona ni menciones 'el contratista propone', 'el documento dice' o 'la propuesta indica'. "
            "Todo debe estar redactado desde la perspectiva de la entidad: 'La ESPY requiere...', 'Es necesario ejecutar...', 'Se precisa adquirir...'."
        )

        nivel_ext = getattr(input_data, "nivel_extension", "MEDIA") or "MEDIA"
        instr_adic = getattr(input_data, "instrucciones_adicionales", None)
        prop_items = getattr(input_data, "propuesta_items", None)

        user_prompt = (
            f"DATOS CONTRACTUALES EXACTOS (EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P.):\n"
            f"- [OBJETO DEL CONTRATO]: {objeto_contrato}\n"
            f"- [TIPO DE CONTRATO]: {tipo_contrato}\n"
            f"- [NIVEL DE EXTENSIÓN SOLICITADO]: {nivel_ext}\n"
            f"- [INSTRUCCIONES ADICIONALES DEL USUARIO]: {instr_adic or 'Ninguna'}\n"
            f"- Modalidad de Selección: {input_data.modalidad or 'Contratación Directa'}\n"
            f"- Contratista / Proponente: {input_data.contratista_nombre or 'Contratista Seleccionado'}\n"
            f"- Presupuesto Estimado / Cotizado: ${int(round(input_data.valor_estimado)):,}".replace(",", ".") + " COP\n"
            f"- Contexto Operativo: {input_data.necesidad_contexto or objeto_contrato}\n\n"
            f"DOCUMENTO SOPORTE OBLIGATORIO ({detected_type} - {doc_orm.nombre_archivo_original}):\n"
            f"{doc_text[:8500]}\n\n"
            f"INSTRUCCIÓN FINAL OBLIGATORIA:\n"
            f"Redacta la sección DESCRIPCIÓN DE LA NECESIDAD A SATISFACER conforme al nivel de extensión '{nivel_ext}', "
            f"evaluando si aplica Escenario A (Inclusión Total) o Escenario B (Desglose Técnico Deductivo en al menos 4-5 viñetas operativas inherentes). "
            f"Aplica rigurosamente la Regla de Oro temática y la regla de no copiar frases acartonadas ni robóticas."
        )

        def fallback_generator() -> JustificacionGenerationResult:
            val_fmt = f"${int(round(input_data.valor_estimado)):,}".replace(",", ".") if input_data.valor_estimado else "$3.193.000 COP"
            contratista = input_data.contratista_nombre or "el contratista seleccionado"

            # Construir dinámicamente la justificación con el nivel de extensión solicitado
            texto_justificacion = build_descripcion_necesidad(
                objeto=objeto_contrato,
                tipologia=tipo_contrato,
                contexto_adicional=doc_text,
                nivel_extension=nivel_ext,
                instrucciones_adicionales=instr_adic,
                propuesta_items=prop_items
            )

            tipo_upper = tipo_contrato
            if "OBRA" in tipo_upper:
                analisis_econ = (
                    f"Análisis de precios unitarios y presupuesto oficial conforme a la propuesta de obra civil '{doc_orm.nombre_archivo_original}' "
                    f"presentada por {contratista}, determinando la razonabilidad económica del valor estimado en {val_fmt} acorde con las tarifas del sector."
                )
                fundamento_ley = "Artículo 31 Ley 142 de 1994, concordante con Arts. 2053 a 2062 del Código Civil, RAS-2017 (Res. 0330/2017 MVCT) y Arts. 209 y 267 C.P."
                marco_tipo = (
                    "RÉGIMEN DE OBRA: Ley 142 de 1994 (Arts. 31 y 32), Código Civil (Arts. 2053 a 2062 - obra material y Art. 2060 num. 3 - responsabilidad decenal/estabilidad 5 años), "
                    "Reglamento Técnico del Sector Agua Potable y Saneamiento Básico RAS (Res. 0330/2017 MVCT), NSR-10, SG-SST en Construcción (Dec. 1072/2015, Res. 0312/2019, Res. 4272/2021 alturas, Res. 0491/2020 espacios confinados) y Estatuto Tributario Arts. 462-1 y 468-3 (A.I.U.)."
                )
            elif "SUMINISTRO" in tipo_upper:
                analisis_econ = (
                    f"Verificación de cotizaciones y precios de mercado de bienes e insumos conforme al documento soporte '{doc_orm.nombre_archivo_original}', "
                    f"estableciendo que el valor presupuestado en {val_fmt} es competitivo y asegura la debida economía del gasto institucional."
                )
                fundamento_ley = "Artículo 31 Ley 142 de 1994, concordante con Arts. 968 a 980 del Código de Comercio y Arts. 209 y 267 C.P."
                marco_tipo = (
                    "RÉGIMEN DE SUMINISTRO: Ley 142 de 1994 (Arts. 31 y 32), Código de Comercio (Arts. 968 a 980 - suministro mercantil y Arts. 905 y ss. - compraventa mercantil), "
                    "Protección de Calidad del Agua (Dec. 1575/2007 y Res. 2115/2007 para sustancias químicas de potabilización), Sistema Globalmente Armonizado SGA (Dec. 1496/2018 para MSDS) y normas técnicas NTC/AWWA/ISO 4064."
                )
            else:
                analisis_econ = (
                    f"Verificación de honorarios y razonabilidad de mercado con base en la propuesta económica '{doc_orm.nombre_archivo_original}' "
                    f"presentada por {contratista}, estableciendo que el monto estimado de {val_fmt} es razonable y congruente con el mercado."
                )
                fundamento_ley = "Artículo 31 Ley 142 de 1994, concordante con Arts. 2053 y ss. del Código Civil y Arts. 209 y 267 C.P."
                marco_tipo = (
                    "RÉGIMEN DE PRESTACIÓN DE SERVICIOS: Ley 142 de 1994 (Arts. 31 y 32), Código Civil (Arts. 2053 a 2069 - servicios inmateriales), "
                    "CST Art. 23 e inexistencia de subordinación laboral (Sentencias C-614/09 y C-171/12), afiliación obligatoria a Seguridad Social Integral (Ley 100/1993, Ley 797/2003, Dec. 1072/2015, Dec. 1273/2018 - IBC 40%) y Art. 8 Ley 80/1993 (Sentencia C-066/97)."
                )

            return JustificacionGenerationResult(
                justificacion_estudio_previo=texto_justificacion,
                documento_soporte_usado=doc_orm.nombre_archivo_original,
                tipo_documento_detectado=detected_type,
                analisis_conveniencia_economica=analisis_econ,
                fundamento_juridico_ley_142=fundamento_ley,
                marco_juridico_tipologia=marco_tipo
            )

        result = gemini_service.generate_agent_structured_draft(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            schema_class=JustificacionGenerationResult,
            fallback_factory=fallback_generator,
            override_api_key=override_api_key
        )
        return result

justification_agent = JustificationAgent()
