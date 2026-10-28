"""
Paso 1: Extractor estructurado del documento mediante Gemini LLM.
Extrae objeto, tipo_contrato y los ítems concretos que la entidad paga,
ignorando marco jurídico, principios, firmas, garantías y cláusulas administrativas.
"""
import json
import re
from typing import Optional
from app.config import settings
from app.utils.logger import logger
from .schemas import DocumentExtractionResult, DocumentItem
from .texto import normalize_text

def extract_document_structure(
    estudio_previo_text: str,
    propuesta_economica_text: str = "",
    override_api_key: Optional[str] = None,
    objeto_hint: str = ""
) -> DocumentExtractionResult:
    """
    Realiza una llamada a Gemini para extraer de forma limpia y estructurada
    los ítems y el objeto de la contratación. Si Gemini no está disponible o falla,
    aplica una extracción determinística de respaldo sin romper el flujo.
    """
    client = None
    key = override_api_key or settings.GEMINI_API_KEY
    if key:
        try:
            from google import genai
            client = genai.Client(api_key=key)
        except Exception as e:
            logger.warning(f"[UNSPSC Extractor] No se pudo inicializar google-genai Client: {e}")

    # Paso 3: Propuesta primero, luego estudio previo. Límite hasta 60.000 caracteres.
    # Si hay que recortar, se recorta el estudio previo, NUNCA la propuesta económica.
    propuesta_clean = (propuesta_economica_text or "").strip()
    estudio_clean = (estudio_previo_text or "").strip()
    max_chars = 60000

    if len(propuesta_clean) + len(estudio_clean) > max_chars:
        espacio_estudio = max(0, max_chars - len(propuesta_clean) - 300)
        estudio_clean = estudio_clean[:espacio_estudio]

    texto_analisis = ""
    if propuesta_clean:
        texto_analisis += f"=== PROPUESTA ECONÓMICA ===\n{propuesta_clean}\n\n"
    if estudio_clean:
        texto_analisis += f"=== ESTUDIO PREVIO ===\n{estudio_clean}"

    if client:
        system_instruction = (
            "Eres un estructurador técnico y jurídico experto en contratación estatal de Colombia (Ley 142 de 1994 y Ley 80 de 1993).\n"
            "Tu tarea es analizar el texto suministrado (Propuesta Económica y/o Estudio Previo) y extraer EXCLUSIVAMENTE "
            "los bienes, obras o servicios que la entidad realmente paga o adquiere.\n\n"
            "INSTRUCCIONES ESTRICTAS:\n"
            "1. 'objeto': Extrae EXCLUSIVAMENTE qué es lo que se contrata (el núcleo del objeto contractual sustantivo). "
            "Está TERMINANTEMENTE PROHIBIDO incluir fórmulas procesales o de relleno administrativo como "
            "'Seleccionar a la persona natural o jurídica que ofrezca las mejores condiciones para el contrato de...' o 'Contratar a la persona natural o jurídica...'. "
            "Si el documento contiene 'Seleccionar a la persona natural o jurídica que ofrezca las mejores condiciones para el contrato de \"...\"', "
            "extrae ÚNICAMENTE el texto que está entre comillas o después de 'contrato de'. "
            "NUNCA cortes el objeto en el primer salto de línea; captura el párrafo completo hasta el siguiente encabezado.\n"
            "2. 'tipo_contrato': Clasifica en: 'suministro', 'obra', 'servicios', 'consultoria' o 'mixto'.\n"
            "3. 'items': Lista cada uno de los ítems o actividades concretas a contratar:\n"
            "   - 'descripcion': Qué se compra o contrata en palabras directas y técnicas (ej. 'tapas para cajas de medidor de agua', 'baretas de madera plástica', 'instalación y mano de obra').\n"
            "   - 'naturaleza': Decide la naturaleza mirando cada ítem individualmente, NO el contrato global. "
            "Mano de obra, visitas técnicas, instalación, transporte, asesoría, consultoría: 'servicio'. "
            "Productos con medidas, dimensiones, cantidades o materiales: 'bien'. "
            "En contratos 'a todo costo', el contratista suministra materiales y mano de obra, por lo que existen ítems de ambos tipos ('bien' y 'servicio').\n"
            "   - 'cita_literal': Frase o renglón EXACTO del documento donde aparece el ítem.\n"
            "   - 'terminos_catalogo': Lista de 2 a 4 nombres o términos genéricos con los que un catálogo de productos o servicios llamaría ese ítem "
            "(por ejemplo: para 'parales estacón 8x8x115' generar ['postes', 'postes de plástico', 'perfiles plásticos']; para 'visita técnica' generar ['servicios de inspección técnica', 'servicios de ingeniería']).\n"
            "4. REGLA DE ORO NEGATIVA (PROHIBIDO EXTRAER BASURA):\n"
            "   - IGNORA por completo el marco jurídico, citas de leyes, principios de la función administrativa (moralidad, igualdad, publicidad).\n"
            "   - IGNORA obligaciones generales del contratista (presentar informes, pagar seguridad social, pólizas, garantías, responder por daños).\n"
            "   - IGNORA aspectos tributarios (Retefuente, ICA, declaraciones), firmas, nombres de personas, cédulas, números de cuenta bancaria o plazos de ejecución.\n"
            "   - Si la propuesta económica o estudio previo contiene una tabla o listado de ítems/cantidades, cada fila o viñeta de producto o servicio técnico es un ítem."
        )

        try:
            prompt = f"Analiza el siguiente documento y genera la extracción estructurada en JSON:\n\n{texto_analisis}"
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": DocumentExtractionResult,
                    "temperature": 0.1,
                    "system_instruction": system_instruction
                }
            )
            if response.text:
                res_clean = response.text.strip()
                if res_clean.startswith("```json"):
                    res_clean = res_clean.split("```json", 1)[1].split("```", 1)[0].strip()
                elif res_clean.startswith("```"):
                    res_clean = res_clean.split("```", 1)[1].split("```", 1)[0].strip()
                data = json.loads(res_clean)
                data["uso_ia"] = True
                return DocumentExtractionResult(**data)
        except Exception as e:
            logger.warning(f"[UNSPSC Extractor] Falló extracción con Gemini: {e}. Activando respaldo determinístico.")

    # Respaldo determinístico sin Gemini
    return _deterministic_fallback_extractor(estudio_previo_text, propuesta_economica_text, objeto_hint=objeto_hint)

def _deterministic_fallback_extractor(estudio_previo: str, propuesta: str, objeto_hint: str = "") -> DocumentExtractionResult:
    """Extrae objeto e ítems mediante heurísticas de formato de tabla/viñetas si el LLM no responde."""
    objeto = (objeto_hint or "").strip()
    if not objeto:
        # Buscar objeto literal en el estudio previo (captura multi-línea)
        m_obj = re.search(
            r"(?:OBJETO(?:\s+DEL\s+CONTRATO)?|CL[AÁ]USULA\s+(?:PRIMERA|1)[^\n]*OBJETO)\s*[:\-]?\s*([\s\S]*?)(?=(?:\n\s*(?:TIPO\s+DE\s+CONTRATO|OBJETIVO|ALCANCE|PLAZO|VALOR|PRESUPUESTO|LUGAR|DESCRIPCI[OÓ]N|JUSTIFICACI[OÓ]N|FUNDAMENTO|REQUISITOS|SUPERVISI[OÓ]N|\d+\.\s+[A-ZÁÉÍÓÚÑ]{4,})|\n\s*\n\s*\n|\Z))",
            estudio_previo,
            re.IGNORECASE
        )
        if m_obj:
            raw_block = m_obj.group(1).strip()
            objeto = " ".join(raw_block.split())
        elif propuesta:
            m_obj_p = re.search(
                r"(?:OBJETO(?:\s+DEL\s+CONTRATO)?)\s*[:\-]?\s*([\s\S]*?)(?=(?:\n\s*(?:ALCANCE|PLAZO|VALOR|VALOR\s+TOTAL|\d+\.\s+[A-ZÁÉÍÓÚÑ]{4,})|\n\s*\n|\Z))",
                propuesta,
                re.IGNORECASE
            )
            if m_obj_p:
                objeto = " ".join(m_obj_p.group(1).split())

    if objeto:
        objeto = re.split(r"(?:1\.|2\.|PLAZO|VALOR|LUGAR|PRESUPUESTO|JUSTIFICACI[OÓ]N|DESCRIPCI[OÓ]N)", objeto, flags=re.IGNORECASE)[0].strip()
        objeto = re.sub(r"^[:\-\s]+", "", objeto).strip()

    # Paso 2: Limpiar frases de relleno administrativo ("Seleccionar a la persona...", "Contratar a la persona...")
    if objeto and re.search(r"^(?:seleccionar|contratar|elegir)\s+a\s+la\s+persona", objeto, re.IGNORECASE):
        # 1. Buscar texto sustantivo entre comillas
        m_quoted = re.search(r'(?:para\s+el\s+contrato\s+de|contrato\s+de)?\s*["“\'«]([^"”\'»]{8,500})["”\'»]', objeto, re.IGNORECASE)
        if m_quoted:
            objeto = m_quoted.group(1).strip()
        else:
            # 2. Buscar lo que sigue tras 'contrato de'
            m_after = re.search(r'(?:para\s+el\s+contrato\s+de|contrato\s+de)\s*(.+)', objeto, re.IGNORECASE)
            if m_after:
                objeto = m_after.group(1).strip().strip('"“”\'«»')

    # Paso 3: Respaldo por título del Estudio Previo o Asunto de la Propuesta si objeto quedó trunco o < 12 palabras
    is_truncated = not objeto or len(objeto.split()) < 12 or bool(re.search(r'mejores\s+condiciones\s*$', objeto, re.IGNORECASE))
    if is_truncated:
        # A. Título en mayúsculas tras ESTUDIOS PREVIOS
        m_title = re.search(r'ESTUDIOS\s+PREVIOS[^\n\r]*\n+([A-ZÁÉÍÓÚÑ0-9\s,\.\-“”"\'/]{10,400})', estudio_previo)
        title_found = ""
        if m_title:
            lines = [l.strip() for l in m_title.group(1).splitlines() if l.strip() and not any(k in l.lower() for k in ["justificacion", "conveniencia", "espy", "pagina", "empresa de servicios"])]
            if lines:
                title_found = " ".join(lines[:3]).strip()
        
        # B. Asunto de la propuesta económica
        asunto_found = ""
        if propuesta:
            m_asunto = re.search(r'ASUNTO\s*[:\-]?\s*([^\n\r]+)', propuesta, re.IGNORECASE)
            if m_asunto:
                asunto_found = m_asunto.group(1).strip()
                asunto_found = re.sub(r'^(?:cotizaci[oó]n|propuesta\s+econ[oó]mica)\s+(?:para|de)\s*', '', asunto_found, flags=re.IGNORECASE).strip()

        best_substantive = title_found or asunto_found
        if best_substantive:
            if objeto and not re.search(r'^(?:seleccionar|contratar)\s+a\s+la\s+persona', objeto, re.IGNORECASE):
                objeto = f"{objeto} - {best_substantive}".strip()
            else:
                objeto = best_substantive

    if not objeto:
        objeto = "CONTRATACIÓN DE BIENES O SERVICIOS PARA LA ESPY"

    # Determinar tipo
    comb = f"{objeto} {estudio_previo[:500]}".lower()
    if any(k in comb for k in ["suministro", "compraventa", "adquisicion", "compra", "adquirir", "dotacion", "insumos", "elementos", "materiales", "medidores", "papeleria", "hipoclorito"]):
        tipo = "suministro"
    elif any(k in comb for k in ["obra", "obras", "construccion", "adecuacion", "reparacion"]):
        tipo = "obra"
    elif any(k in comb for k in ["consultoria", "interventoria", "estudios"]):
        tipo = "consultoria"
    else:
        tipo = "servicios"

    # Extraer ítems desde líneas de propuesta o viñetas
    items = []
    fuente = propuesta if propuesta.strip() else estudio_previo
    lineas = [l.strip() for l in fuente.split("\n") if l.strip()]

    legal_junk = [
        "contrato de", "declaraciones tributarias", "retefuente", "rendir cuentas",
        "seguridad social", "poliza", "garantia", "supervisor", "liquidacion", "plazo",
        "firma", "cedula", "nit", "telefono", "correo", "banco", "cuenta",
        "ausencia de", "riesgo inmediato", "riesgo de", "incumplimiento de", "carencia de",
        "falta de", "vulnerabilidad", "deficiencia", "durabilidad en ambientes",
        "bajo mantenimiento y costos", "resistencia estructural", "sostenibilidad ambiental",
        "seguridad del trabajador", "obligaciones generales", "no se requieren polizas",
        "no se requieren pólizas"
    ]

    service_kw = ["mano de obra", "visita tecnica", "visita técnica", "instalacion", "instalación", "transporte", "asesoria", "asesoría", "consultoria", "consultoría", "mantenimiento", "capacitacion", "capacitación", "operacion", "operación", "servicio"]

    for linea in lineas:
        l_lower = linea.lower()
        norm_lin = normalize_text(linea)
        # Ignora cualquier línea que sea el encabezado de la tabla de cotización
        if "descripcion" in norm_lin and ("cant" in norm_lin or "cantidad" in norm_lin):
            continue
        # Ignora cualquier línea que contenga palabras del membrete de Asocomunal o de la ESPY
        if any(w in norm_lin for w in ["autonomia", "compromiso", "asocomunal", "yolombo", "personeria", "gobernacion", "antioquia"]) or re.search(r'\bnit\b', norm_lin):
            continue
        if any(lj in l_lower for lj in legal_junk):
            continue
        # Filas de tabla o viñetas numéricas
        if re.match(r'^(?:[0-9]{1,2}[\.\-\)]|\*|\-|•)\s+([A-Za-z0-9].+)', linea) or ("|" in linea and not "item" in l_lower and not "descripcion" in l_lower) or re.search(r'\b(?:cant|cantidad|\$|dias|días)\b', l_lower):
            clean_item = re.sub(r'^(?:[0-9]{1,2}[\.\-\)]|\*|\-|•)\s*', '', linea).strip()
            if "|" in clean_item:
                parts = [p.strip() for p in clean_item.split("|") if p.strip()]
                desc_cand = [p for p in parts if len(p) > 5 and not re.match(r'^\$?[\d\.,]+$', p)]
                if desc_cand:
                    clean_item = desc_cand[0]

            clean_item = re.sub(r'[\s\-\|]+(?:cant|cantidad)\s*[:\-]?\s*\d*\s*$', '', clean_item, flags=re.IGNORECASE).strip()
            clean_item = re.sub(r'[\s\-\|]+total\s*[:\$]?\s*[\d\.,]*.*$', '', clean_item, flags=re.IGNORECASE).strip()

            if len(clean_item) >= 4:
                item_low = clean_item.lower()
                # Paso 4: Naturaleza por ítem, no por contrato
                if any(sk in item_low for sk in service_kw):
                    nat = "servicio"
                elif tipo == "obra" and any(ok in item_low for ok in ["demolicion", "excavacion", "pavimento", "construccion", "concreto"]):
                    nat = "obra"
                elif any(char.isdigit() for char in item_low) or any(bk in item_low for bk in ["tornillo", "paral", "bareta", "estiba", "tubo", "lamina", "lámina", "poste", "valvula", "válvula", "medidor", "caja", "cajilla", "tapa", "resma", "papel", "quimico", "químico", "tanque", "almacenamiento"]):
                    nat = "bien"
                else:
                    nat = "bien" if tipo == "suministro" else "servicio"

                items.append(DocumentItem(
                    descripcion=clean_item,
                    naturaleza=nat,
                    cita_literal=linea[:150],
                    terminos_catalogo=[]
                ))

    # Si no se extrajeron ítems, descomponer el objeto
    if not items and objeto:
        nat = "bien" if tipo == "suministro" else "servicio"
        items.append(DocumentItem(
            descripcion=objeto,
            naturaleza=nat,
            cita_literal=objeto,
            terminos_catalogo=[]
        ))

    return DocumentExtractionResult(
        objeto=objeto,
        tipo_contrato=tipo,
        items=items
    )
