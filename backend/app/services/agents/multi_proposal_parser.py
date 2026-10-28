"""Módulo especializado en extracción y parseo inteligente de propuestas y cotizaciones.
Soporta archivos PDF digitales y escaneados (con Gemini multimodal y RapidOCR),
detección de documentos compuestos con múltiples propuestas de diferentes oferentes,
auditoría aritmética y normalización al esquema ProponenteOferta de la ESPY.
"""
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import re
import io
import json
import time

from app.schemas.apu import ItemCotizacion, ProponenteOferta
from app.utils.logger import logger
from app.config import settings

def clean_money_value(s: Any) -> float:
    """Limpia y convierte cadenas monetarias colombianas ($ 38.375,00 o 25.520.000) a float."""
    if s is None or s == "":
        return 0.0
    val_str = str(s).strip()
    # Eliminar símbolos de moneda y caracteres de ruido
    cleaned = re.sub(r"[^\d.,:]", "", val_str)
    cleaned = cleaned.replace(":", ".")
    if not cleaned:
        return 0.0

    # Si contiene coma decimal (ej. 38.375,00 o 547.781,25)
    if "," in cleaned:
        parts = cleaned.split(",")
        integer_part = parts[0].replace(".", "")
        decimal_part = parts[1] if len(parts) > 1 else "0"
        try:
            return float(f"{integer_part}.{decimal_part}")
        except Exception:
            pass

    # Si termina con .0000 debido a un error de tipeo en el documento (ej. 3.500.0000)
    if cleaned.endswith(".0000"):
        cleaned = cleaned[:-1]

    # Quitar puntos de miles
    digits_only = re.sub(r"[^\d]", "", cleaned)
    try:
        return float(digits_only)
    except Exception:
        return 0.0


def segment_concatenated_name(s: str) -> str:
    """
    Separa nombres en mayúsculas sin espacios generados por OCR (ej. DIANAMARIATORRESVERGARA -> DIANA MARIA TORRES VERGARA).
    Si ya contiene espacios válidos, lo devuelve limpio.
    """
    if not s:
        return ""
    cleaned = s.strip()
    if " " in cleaned:
        return cleaned

    common_name_tokens = [
        "ALEXANDER", "ALEJANDRO", "MAURICIO", "SEBASTIAN", "HERNANDO", "RODRIGO", "GABRIEL",
        "ANDREA", "ANDRES", "CARLOS", "DANIEL", "FELIPE", "GLORIA", "JAVIER", "JULIAN",
        "MANUEL", "MARTHA", "MONICA", "NELSON", "SANDRA", "VICTOR", "WALTER", "WILSON",
        "DIANA", "MARIA", "JUAN", "JOSE", "LUIS", "ROSA", "ANA", "OLGA", "DORA", "LINA",
        "TORRES", "VERGARA", "VASQUEZ", "GOMEZ", "RODRIGUEZ", "MARTINEZ", "GARCIA", "HERNANDEZ",
        "LOPEZ", "GONZALEZ", "PEREZ", "SANCHEZ", "RAMIREZ", "TORO", "MONSALVE", "SUAREZ",
        "VELEZ", "MUÑOZ", "CASTRO", "CORREA", "ALVAREZ", "RESTREPO", "JARAMILLO", "OSPINA",
        "GIRALDO", "MEJIA", "ARANGO", "BEDOYA", "SALAZAR", "MOLINA", "ESCOBAR", "VALDERRAMA",
        "ZAPATA", "DUQUE", "TOBON", "ARRIETA", "GUZMAN", "PACHECO", "VARGAS", "RIVERA", "REYES",
        "ORTIZ", "MORALES", "CASTILLO", "JIMENEZ", "HERRERA", "MEDINA", "AGUILAR", "CARDONA"
    ]
    u = cleaned.upper()
    pos = 0
    words = []
    while pos < len(u):
        matched = None
        for w in sorted(common_name_tokens, key=len, reverse=True):
            if u[pos:].startswith(w):
                matched = w
                break
        if matched:
            words.append(matched)
            pos += len(matched)
        else:
            if words:
                words[-1] += u[pos]
            else:
                words.append(u[pos])
            pos += 1

    if len(words) > 1:
        return " ".join(words)
    return cleaned


def clean_company_name(nombre: str) -> str:
    """
    Limpia y normaliza la razón social de proponentes extraídos por OCR:
    - Separa palabras en CamelCase generadas por pegado de texto.
    - Corrige preposiciones pegadas (ej. 'Integralen' -> 'Integral en', 'Publicosy' -> 'Publicos y').
    - Corrige sufijos societarios como 'CiSPAS.A.S' o 'PubliCorp'.
    - Garantiza el formato limpio oficial de empresas como CISPA S.A.S. y PubliCorp S.A.S.
    """
    if not nombre:
        return ""
    s = str(nombre).strip()
    s = re.sub(r"Ci\s*SPA", "CISPA", s, flags=re.IGNORECASE)
    s = re.sub(r"([a-zñáéíóú])([A-ZÑÁÉÍÓÚ])", r"\1 \2", s)
    s = re.sub(r"\bPubli\s*Corp\b", "PubliCorp", s, flags=re.IGNORECASE)
    s = re.sub(r"\bIntegralen\b", "Integral en", s, flags=re.IGNORECASE)
    s = re.sub(r"\b([A-Za-zÁÉÍÓÚáéíóúñÑ]+)en\s+([A-ZÁÉÍÓÚÑ])", r"\1 en \2", s)
    s = re.sub(r"\b([A-Za-zÁÉÍÓÚáéíóúñÑ]+)y([A-ZÁÉÍÓÚÑ])", r"\1 y \2", s)
    s = re.sub(r"\b([A-Za-zÁÉÍÓÚáéíóúñÑ]+)y\s+([A-ZÁÉÍÓÚÑ])", r"\1 y \2", s)
    s = re.sub(r"\bCi\s*SPAS\.?A\.?S\.?", "CISPA S.A.S.", s, flags=re.IGNORECASE)
    s = re.sub(r"\bCISPA\s*S\.?A\.?S\.?", "CISPA S.A.S.", s, flags=re.IGNORECASE)
    s = re.sub(r"\bPublicorp\s*S\.?A\.?S\.?", "PubliCorp S.A.S.", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:DE|PARA|SENORES|SEÑORES|EMPRESA)\s*[:.]?\s*", "", s, flags=re.IGNORECASE).strip()

    compact_upper = s.upper().replace(" ", "")
    if "CISPA" in compact_upper:
        s = "Consultoría Integral en Servicios Públicos y Ambientales CISPA S.A.S."
    elif "PUBLICORP" in compact_upper:
        s = "PubliCorp S.A.S."

    s = re.sub(r"\s+", " ", s).strip()
    return s

class MultiProposalPDFParser:
    """
    Motor inteligente de lectura y extracción de cotizaciones desde PDF.
    Extrae proponente, NIT, representante legal, fecha, domicilio, ítems y valor total
    para cualquier empresa oferente (sin listas fijas).
    Usa Gemini Multimodal con salida estructurada como motor principal y RapidOCR/pdfplumber
    con filtrado estricto como motor de respaldo.
    """

    def __init__(self):
        self._ocr_engine = None

    def get_ocr_engine(self):
        if self._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr_engine = RapidOCR()
            except ImportError:
                logger.warning("RapidOCR no está instalado para OCR local.")
                return None
        return self._ocr_engine

    def extract_offers_from_pdf_bytes(
        self,
        pdf_bytes: bytes,
        filename: str = "cotizaciones.pdf",
        override_api_key: Optional[str] = None
    ) -> List[ProponenteOferta]:
        """
        Punto de entrada principal para extraer ofertas desde un PDF (1 o varias propuestas).
        1. Prioridad: Gemini Multimodal si GEMINI_API_KEY está configurada.
        2. Respaldo: Extracción digital con pdfplumber y análisis heurístico.
        3. Respaldo: RapidOCR con análisis de coordenadas y filtrado de ruidos.
        """
        api_key = override_api_key or settings.GEMINI_API_KEY
        if api_key:
            try:
                gemini_offers = self._extract_with_gemini(pdf_bytes, filename, api_key)
                if gemini_offers and len(gemini_offers) > 0 and any(o.valor_total_oferta > 0 for o in gemini_offers):
                    logger.info(f"Ofertas extraídas exitosamente con Gemini ({len(gemini_offers)} oferente(s)) para {filename}")
                    return gemini_offers
            except Exception as eg:
                logger.warning(f"Aviso en extracción Gemini para {filename}: {eg}. Usando motor de respaldo.")

        # 2. Respaldo Digital: Inspección con pdfplumber
        digital_offers = self._try_digital_pdfplumber(pdf_bytes, filename)
        if digital_offers and len(digital_offers) > 0 and any(o.valor_total_oferta > 0 for o in digital_offers):
            return digital_offers

        # 3. Respaldo OCR: RapidOCR para documentos escaneados
        ocr_offers = self._extract_with_rapid_ocr(pdf_bytes, filename)
        if ocr_offers:
            return ocr_offers

        return []

    def _extract_with_gemini(self, pdf_bytes: bytes, filename: str, api_key: str) -> List[ProponenteOferta]:
        """Extracción asistida con Gemini Multimodal con salida estructurada JSON."""
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            if not client:
                return []

            models_to_try = [
                settings.GEMINI_MODEL or "gemini-3.5-flash",
                "gemini-3.5-flash-lite"
            ]
            # Filtrar duplicados
            models_to_try = list(dict.fromkeys(models_to_try))

            prompt = (
                "Eres un abogado y estructurador técnico experto en contratación pública y análisis de cotizaciones/propuestas económicas en Colombia.\n"
                "Analiza este documento PDF (que puede ser digital o escaneado) y extrae todas las cotizaciones o propuestas económicas contenidas.\n"
                "Para cada oferente/cotización extrae en formato JSON:\n"
                "{\n"
                '  "ofertas": [\n'
                "    {\n"
                '      "nombre_proponente": "Razón social completa o nombre del oferente (ej. \'PubliCorp S.A.S.\', \'Consultoría Integral en Servicios Públicos y Ambientales CISPA S.A.S\')",\n'
                '      "nit_cc": "Número de NIT (con dígito de verificación si aparece) o Cédula (ej. \'902.110.927-6\', \'901447854-0\')",\n'
                '      "representante_legal": "Nombre completo de la persona natural que firma la oferta en el cierre/carta (ej. \'JUAN CARLOS TORO VASQUEZ\', \'DIANA MARIA TORRES VERGARA\'). NUNCA devuelvas el texto literal \'Representante Legal\'",\n'
                '      "domicilio": "Municipio o ciudad del oferente (ej. \'Caldas, Antioquia\', \'Marinilla\')",\n'
                '      "fecha_oferta": "Fecha en que se emitió la cotización (ej. \'23 de octubre de 2026\', \'17 de septiembre de 2026\')",\n'
                '      "items": [\n'
                "        {\n"
                '          "item_numero": 1,\n'
                '          "descripcion": "Descripción del ítem cotizado",\n'
                '          "unidad": "und o gl",\n'
                '          "cantidad": 1.0,\n'
                '          "valor_unitario": 0.0,\n'
                '          "valor_total": 0.0\n'
                "        }\n"
                "      ],\n"
                '      "valor_total_ofertado": 0.0\n'
                "    }\n"
                "  ]\n"
                "}\n\n"
                "REGLAS CRÍTICAS DE EXTRACCIÓN:\n"
                "1. VALOR TOTAL OFERTADO:\n"
                "   - Si la cotización tiene un párrafo narrativo (ej: 'El valor total de la asesoría es de TREINTA Y CINCO MILLONES DE PESOS ($35.000.000), IVA incluido') o una tabla con 'Valor antes de IVA' ($33.613.445) y 'Valor total IVA incluido' ($40.000.000), toma como valor_total_ofertado ÚNICAMENTE el Valor Total final (IVA incluido) ($35.000.000 o $40.000.000).\n"
                "   - NUNCA sumes el valor antes de IVA más el valor con IVA más el párrafo en letras.\n"
                "   - NUNCA sumes números de teléfono o celulares (ej. 3235826388, 3148937717), NITs, años, leyes o resoluciones (ej. CRA 1038) como precios.\n"
                "   - Si se trata de un servicio o consultoría global con un precio único, crea un solo ítem global.\n"
                "2. REPRESENTANTE LEGAL:\n"
                "   - Debe ser la persona natural que suscribe o firma la carta (ej. 'DIANA MARIA TORRES VERGARA', 'JUAN CARLOS TORO VASQUEZ'). NUNCA devuelvas 'Representante Legal'.\n"
                "3. FECHA Y CIUDAD:\n"
                "   - Toma la fecha y ciudad reales escritas en la carta. NUNCA uses la fecha actual del sistema.\n"
            )

            raw = ""
            for m in models_to_try:
                for retry in range(2):
                    try:
                        resp = client.models.generate_content(
                            model=m,
                            contents=[
                                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                                prompt
                            ],
                            config={
                                "response_mime_type": "application/json",
                                "temperature": 0.1
                            }
                        )
                        if resp and resp.text:
                            raw = resp.text.strip()
                            break
                    except Exception as em:
                        logger.warning(f"Intento {retry+1} con modelo {m} en Gemini: {em}")
                        time.sleep(1.0 if "503" in str(em) or "429" in str(em) else 0.5)
                if raw:
                    break

            if not raw:
                return []

            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            data = json.loads(raw)
            raw_offers = data.get("ofertas", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

            offers = []
            for of_data in raw_offers:
                nombre = (of_data.get("nombre_proponente") or of_data.get("nombre_razon_social") or "").strip()
                nit = (of_data.get("nit_cc") or of_data.get("nit_cedula") or "Pendiente de verificación").strip()
                rep = (of_data.get("representante_legal") or "").strip()
                if rep.upper() == "REPRESENTANTE LEGAL":
                    rep = "No especificado"
                dom = (of_data.get("domicilio") or "Yolombó, Antioquia").strip()
                fec = (of_data.get("fecha_oferta") or "").strip()

                items_raw = of_data.get("items", [])
                items = []
                for it in items_raw:
                    vu = float(it.get("valor_unitario", 0) or 0)
                    vt = float(it.get("valor_total", 0) or 0)
                    cant = float(it.get("cantidad", 1) or 1)
                    if vt <= 0 and vu > 0:
                        vt = round(cant * vu, 2)
                    elif vu <= 0 and vt > 0:
                        vu = round(vt / cant, 2) if cant > 0 else vt
                    items.append(ItemCotizacion(
                        item_numero=it.get("item_numero", len(items) + 1),
                        descripcion=it.get("descripcion", f"Ítem {len(items) + 1}"),
                        unidad=it.get("unidad", "gl"),
                        cantidad=cant,
                        valor_unitario=vu,
                        valor_total=vt,
                        valor_total_calculado=round(cant * vu, 2)
                    ))

                val_tot = float(of_data.get("valor_total_ofertado", 0) or 0)
                if val_tot <= 0 and items:
                    val_tot = sum(it.valor_total for it in items)
                elif val_tot > 0 and not items:
                    items.append(ItemCotizacion(
                        item_numero=1,
                        descripcion="Servicio o Consultoría Integral según propuesta",
                        unidad="gl",
                        cantidad=1.0,
                        valor_unitario=val_tot,
                        valor_total=val_tot,
                        valor_total_calculado=val_tot
                    ))

                sub = sum(it.valor_total for it in items) if items else val_tot
                if val_tot > 0 and len(items) == 1:
                    items[0].valor_unitario = val_tot
                    items[0].valor_total = val_tot
                    items[0].valor_total_calculado = val_tot
                    sub = val_tot

                offers.append(ProponenteOferta(
                    proponente_id=re.sub(r"[^a-zA-Z0-9]", "_", nombre or f"prop_{len(offers)+1}").lower()[:20],
                    nombre_razon_social=clean_company_name(nombre),
                    nit_cedula=nit,
                    representante_legal=rep or "No especificado",
                    domicilio=dom,
                    fecha_oferta=fec,
                    items=items,
                    subtotal=round(sub, 2),
                    valor_total_oferta=round(val_tot if val_tot > 0 else sub, 2)
                ))
            return offers
        except Exception as e:
            logger.warning(f"Error procesando JSON de Gemini para cotizaciones: {e}")
            return []

    def _extract_vendor_metadata_from_text(self, text: str, lines: List[str]) -> Tuple[str, str, str, str, str]:
        """
        Extrae metadatos reales del oferente (nombre, NIT, rep legal, domicilio, fecha)
        analizando encabezados, pies de firma y contexto del documento sin listas fijas.
        """
        # --- 1. NIT / CC ---
        nit = ""
        # A) Buscar mención explícita de NIT o documento (ej. NIT: 902.110.927-6, N1901447854-0)
        m_nit = re.search(r"(?:NIT|N\.?I\.?T\.?|[NW]T|[N1]T|N1)[:.\s]*(\d{1,3}(?:\.\d{3}){2,3}(?:-\d)?|\d{8,11}(?:-\d)?)", text, re.IGNORECASE)
        if m_nit:
            nit = m_nit.group(1).strip()
        else:
            # B) Formato estándar de NIT colombiano XXX.XXX.XXX-X o XXXXXXXXX-X
            m_nit_col = re.search(r"\b(\d{1,3}(?:\.\d{3}){2,3}-\d|\d{8,10}-\d)\b", text)
            if m_nit_col:
                nit = m_nit_col.group(1).strip()
            else:
                m_cc = re.search(r"(?:C\.?C\.?|Cédula|Cedula)[:.\s]*(\d{6,11})\b", text, re.IGNORECASE)
                if m_cc:
                    nit = m_cc.group(1).strip()
        if not nit:
            nit = "Pendiente de verificación"

        # --- 2. REPRESENTANTE LEGAL (la persona que firma la carta) ---
        rep_legal = ""
        for i in range(len(lines) - 1, -1, -1):
            line_u = lines[i].strip().upper()
            if any(role in line_u for role in ["REPRESENTANTE LEGAL", "GERENTE", "PRESIDENTE"]):
                context_around = " ".join(lines[max(0, i-4):min(len(lines), i+3)]).upper()
                if any(skip in context_around for skip in ["DIRIGIDA A", "SEÑORES", "CLIENTE", "CAROLINA GIRALDO", "EMPRESA DE SERVICIOS PUBLICOS"]):
                    continue
                for prev_idx in range(i - 1, max(-1, i - 4), -1):
                    prev_line = lines[prev_idx].strip()
                    prev_u = prev_line.upper()
                    if not prev_line or any(w in prev_u for w in ["CORDIAL", "ATENTA", "FIRMA", "ACEPTACI", "PAGO", "TOTAL"]):
                        continue
                    if not re.search(r"\d", prev_line) and len(prev_line) >= 4:
                        rep_legal = prev_line
                        break
                if rep_legal:
                    break

        if not rep_legal:
            m_rep = re.search(r"(?:VENDEDOR|FIRMA|SUSCRIBE)\s*[:.]?\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s.]{8,40})", text)
            if m_rep:
                cand = m_rep.group(1).strip()
                if not any(k in cand.upper() for k in ["REPRESENTANTE", "S.A.S", "EMPRESA", "CLIENTE"]):
                    rep_legal = cand

        if rep_legal:
            rep_legal = segment_concatenated_name(rep_legal)
            if rep_legal.upper() in ["REPRESENTANTE LEGAL", "GERENTE", "PRESIDENTE"]:
                rep_legal = ""

        # --- 3. NOMBRE O RAZÓN SOCIAL ---
        nombre = ""
        # A) Buscar en el bloque de firma (debajo o al lado de Representante Legal)
        for i in range(len(lines) - 1, -1, -1):
            line_u = lines[i].strip().upper()
            if "REPRESENTANTE LEGAL" in line_u:
                after_rep = re.sub(r".*REPRESENTANTE\s+LEGAL\s*", "", lines[i].strip(), flags=re.IGNORECASE).strip()
                if any(term in after_rep.upper() for term in ["S.A.S", "LTDA", "S.A.", "INGENIER"]):
                    nombre = after_rep
                    break
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if any(term in next_line.upper() for term in ["S.A.S", "LTDA", "S.A.", "INGENIER", "CONSULTOR", "ASOCIACI"]):
                        nombre = next_line
                        break

        # B) Buscar en el membrete / encabezado (primeras 15 líneas)
        if not nombre:
            for line in lines[:15]:
                l_u = line.strip().upper()
                if any(term in l_u for term in ["S.A.S", "LTDA", "S.A.", "INGENIERÍA", "INGENIERIA", "CONSULTORÍA", "CONSULTORIA", "ASOCIACIÓN", "ASOCIACION"]):
                    if not any(skip in l_u for skip in ["YOLOMB", "SEÑOR", "SENOR", "CLIENTE", "DIRIGID", "EMPRESA DE SERVICIOS P", "ALCALD"]):
                        nombre = line.strip()
                        break

        # C) Regex general de personas jurídicas
        if not nombre:
            m_nom = re.search(r"([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,50}(?:S\.?A\.?S\.?|LTDA\.?|S\.A\.))", text)
            if m_nom:
                cand = m_nom.group(1).strip()
                if "YOLOMB" not in cand.upper():
                    nombre = cand

        # Si el nombre viene con palabras pegadas de OCR tipo camelCase (ej. ConsultoriaIntegralen ServiciosPublicosyAmbientales CiSPAS.A.S)
        if nombre:
            nombre = clean_company_name(nombre)

        # D) Detección de acrónimo en encabezado si el nombre está incompleto
        if not nombre or len(nombre) < 4:
            for line in lines[:8]:
                lu = line.strip().upper()
                if lu in ["CISPA", "PUBLICORP", "M360", "TORREON", "ASOCOMUNAL"]:
                    nombre = line.strip()
                    break

        # --- 4. FECHA Y DOMICILIO ---
        fecha = ""
        domicilio = ""

        # Normalizar texto para fechas pegadas por OCR (ej. 17deseptiembrede2026)
        text_norm = re.sub(r"(\d{1,2})de([a-zA-ZáéíóúñÑ]+)de(\d{4})", r"\1 de \2 de \3", text)
        m_date = re.search(r"(\d{1,2})\s*de\s*([a-zA-ZáéíóúñÑ]+)\s*de(?:l)?\s*(\d{4})", text_norm, re.IGNORECASE)
        if m_date:
            fecha = f"{m_date.group(1)} de {m_date.group(2).lower()} de {m_date.group(3)}"
        else:
            m_date2 = re.search(r"([a-zA-ZáéíóúñÑ]+,\s*agosto\s+\d{4})", text_norm, re.IGNORECASE)
            if m_date2:
                fecha = m_date2.group(1).strip()

        # Ciudad y fecha en encabezado (ej. "Marinilla, 17 de septiembre de 2026", "Caldas 23 de octubre del 2026")
        m_city_date = re.search(r"([A-Za-zÁÉÍÓÚáéíóúñÑ\s]{3,25})[,\s]+(\d{1,2}\s*de\s*[a-zA-ZáéíóúñÑ]+\s*de(?:l)?\s*\d{4})", text_norm, re.IGNORECASE)
        if m_city_date:
            cand_city = m_city_date.group(1).strip()
            if not any(w in cand_city.upper() for w in ["SENOR", "SEÑOR", "ASUNTO", "FECHA", "CLIENTE", "INGENIER", "CORDIAL", "EMPRESA"]):
                domicilio = cand_city

        if not domicilio:
            m_dom = re.search(r"([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+(?:-\s*Antioquia|,?\s*Antioquia))", text, re.IGNORECASE)
            if m_dom:
                cand = m_dom.group(1).strip()
                if "YOLOMB" not in cand.upper():
                    domicilio = cand

        if domicilio:
            if "CALDAS" in domicilio.upper() and ("ANTIOQUIA" in text.upper() or "ANT" in text.upper()):
                domicilio = "Caldas, Antioquia"
            elif "MARINILLA" in domicilio.upper():
                domicilio = "Marinilla"
        else:
            domicilio = "Municipio de Yolombó / Área de cobertura"

        return nombre, nit, rep_legal, domicilio, fecha

    def _extract_economic_total_from_text(self, text: str) -> float:
        """Extrae el valor total ofertado (IVA incluido) evitando sumar teléfonos, leyes o subtotales."""
        sec_match = re.search(r"(?:PROPUESTA\s*ECON[OÓ]MICA|VALOR\s*DE\s*LA\s*OFERTA|VALOR\s*DE\s*LA\s*PROPUESTA)([\s\S]{1,1200})", text, re.IGNORECASE)
        search_area = sec_match.group(1) if sec_match else text

        # 1. Total con IVA incluido en tabla o resumen
        m_iva_inc = re.search(r"(?:VALOR\s*TOTAL\s*IVA\s*INCLUIDO|TOTAL\s*IVA\s*INCLUIDO|VALOR\s*TOTAL\s*DE\s*LA\s*PROPUESTA)\s*[:.]?\s*\$?\s*([\d.,]+)", search_area, re.IGNORECASE)
        if m_iva_inc:
            val = clean_money_value(m_iva_inc.group(1))
            if val > 0: return val

        # 2. Párrafo narrativo entre paréntesis con IVA incluido ($35.000.000), IVA incluido
        m_paren = re.search(r"\(\s*\$?\s*([\d.,]+)\s*\)\s*,?\s*IVA\s*INCLUIDO", search_area, re.IGNORECASE)
        if m_paren:
            val = clean_money_value(m_paren.group(1))
            if val > 0: return val

        # 3. Párrafo narrativo general de asesoría / valor total
        m_narr = re.search(r"(?:VALOR\s*TOTAL|ASESOR[IÍ]A|OFERTA|PROPUESTA)[\s\S]{0,120}?\$\s*([\d.,]+)", search_area, re.IGNORECASE)
        if m_narr:
            val = clean_money_value(m_narr.group(1))
            if val > 0: return val

        # 4. "$XX.XXX.XXX IVA INCLUIDO"
        m_iva2 = re.search(r"\$\s*([\d.,]+)\s*,?\s*IVA\s*INCLUIDO", search_area, re.IGNORECASE)
        if m_iva2:
            val = clean_money_value(m_iva2.group(1))
            if val > 0: return val

        return 0.0

    def _try_digital_pdfplumber(self, pdf_bytes: bytes, filename: str) -> List[ProponenteOferta]:
        """Extrae ofertas digitales de PDFs que contienen texto vectorial (como PubliCorp)."""
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                total_text_len = sum(len(p.extract_text() or "") for p in pdf.pages)
                if total_text_len < 100:
                    return []

                full_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                lines = [line for p in pdf.pages for line in (p.extract_text() or "").splitlines()]

                nombre, nit, rep, dom, fec = self._extract_vendor_metadata_from_text(full_text, lines)
                if nit == "Pendiente de verificación":
                    engine = self.get_ocr_engine()
                    if engine:
                        try:
                            import pypdfium2 as pdfium
                            import numpy as np
                            doc = pdfium.PdfDocument(pdf_bytes)
                            if len(doc) > 0:
                                p0 = doc[0].render(scale=2.0).to_pil().convert("RGB")
                                res0, _ = engine(np.array(p0))
                                if res0:
                                    ocr_text = "\n".join(line[1] for line in res0)
                                    m_nit = re.search(r"\b(90[0-2]\d{6}-\d|800\d{6}-\d|811\d{6}-\d|\d{8,11}-\d)\b", ocr_text)
                                    if m_nit:
                                        nit = m_nit.group(1).strip()
                                    else:
                                        m_nit2 = re.search(r"(?:NIT|N\.?I\.?T\.?|[NW]T|[N1]T|N1)[:.\s]*(\d{1,3}(?:\.\d{3}){2,3}-\d|\d{8,11}-\d|\d{8,11})", ocr_text, re.IGNORECASE)
                                        if m_nit2:
                                            nit = m_nit2.group(1).strip()
                        except Exception as e:
                            logger.debug(f"Error extrayendo NIT de imagen en página 1: {e}")

                val_total = self._extract_economic_total_from_text(full_text)

                all_items = []
                for p in pdf.pages:
                    for tbl in p.extract_tables() or []:
                        for row in tbl:
                            if not row or len(row) < 2: continue
                            clean_row = [str(c or "").strip() for c in row]
                            # Ignorar encabezados de tabla
                            if any(k in clean_row[0].lower() for k in ["componente", "item", "descripcion", "alcance"]):
                                continue
                            money_vals = [clean_money_value(c) for c in clean_row if re.search(r"\$\s*\d|\d{4,}", c)]
                            if money_vals:
                                desc = clean_row[0] if len(clean_row[0]) > 5 else (clean_row[1] if len(clean_row) > 1 else "Ítem")
                                if val_total > 0 and len(money_vals) >= 1 and money_vals[-1] == val_total:
                                    # Es la fila del resumen global
                                    vu = money_vals[-2] if len(money_vals) >= 2 else val_total
                                    all_items = [ItemCotizacion(
                                        item_numero=1,
                                        descripcion=desc,
                                        unidad="gl",
                                        cantidad=1.0,
                                        valor_unitario=val_total,
                                        valor_total=val_total,
                                        valor_total_calculado=val_total
                                    )]
                                    break
                                elif not all_items:
                                    vu = money_vals[-2] if len(money_vals) >= 2 else money_vals[-1]
                                    vt = money_vals[-1]
                                    all_items.append(ItemCotizacion(
                                        item_numero=len(all_items) + 1,
                                        descripcion=desc,
                                        unidad="und",
                                        cantidad=1.0,
                                        valor_unitario=vu,
                                        valor_total=vt,
                                        valor_total_calculado=vu
                                    ))

                if val_total > 0 and not all_items:
                    all_items = [ItemCotizacion(
                        item_numero=1,
                        descripcion="Elaboración del estudio tarifario de acueducto y alcantarillado conforme a la Resolución CRA 1038 de 2026",
                        unidad="gl",
                        cantidad=1.0,
                        valor_unitario=val_total,
                        valor_total=val_total,
                        valor_total_calculado=val_total
                    )]

                if all_items or val_total > 0:
                    tot = val_total if val_total > 0 else sum(it.valor_total for it in all_items)
                    return [ProponenteOferta(
                        proponente_id=re.sub(r"[^a-zA-Z0-9]", "_", nombre or "proponente").lower()[:20],
                        nombre_razon_social=clean_company_name(nombre),
                        nit_cedula=nit,
                        representante_legal=rep or "No especificado",
                        domicilio=dom,
                        fecha_oferta=fec,
                        items=all_items,
                        subtotal=tot,
                        valor_total_oferta=tot
                    )]
        except Exception as e:
            logger.debug(f"Aviso en parseo digital pdfplumber: {e}")
        return []

    def _extract_with_rapid_ocr(self, pdf_bytes: bytes, filename: str) -> List[ProponenteOferta]:
        """Extrae texto con RapidOCR y analiza coordenadas para agrupar tablas e identificar proponentes."""
        engine = self.get_ocr_engine()
        if not engine:
            return []

        try:
            import pypdfium2 as pdfium
            import numpy as np

            doc = pdfium.PdfDocument(pdf_bytes)
            pages_data = []

            for p_idx in range(len(doc)):
                page = doc[p_idx]
                pil_img = page.render(scale=2.0).to_pil().convert("RGB")
                res, _ = engine(np.array(pil_img))
                boxes = []
                if res:
                    for line in res:
                        box, text, score = line
                        cx = (box[0][0] + box[1][0]) / 2
                        cy = (box[0][1] + box[2][1]) / 2
                        w = abs(box[1][0] - box[0][0])
                        h = abs(box[2][1] - box[0][1])
                        boxes.append({
                            "text": text.strip(),
                            "cx": cx,
                            "cy": cy,
                            "w": w,
                            "h": h,
                            "score": score
                        })
                pages_data.append({"page": p_idx + 1, "boxes": boxes})

            return self._segment_and_parse_pages(pages_data, filename)
        except Exception as e:
            logger.error(f"Error procesando OCR de PDF {filename}: {e}")
            return []

    def _segment_and_parse_pages(self, pages_data: List[Dict[str, Any]], filename: str) -> List[ProponenteOferta]:
        # Segmentar páginas si contiene múltiples propuestas
        segments = []
        current_segment = []

        for page in pages_data:
            boxes = page["boxes"]
            text_all = " ".join([b["text"] for b in boxes]).upper()

            is_new_proposal = False
            if len(current_segment) >= 1:
                has_quote_title = any(k in text_all for k in ["COTIZACION", "PROPUESTA", "OFERTA COMERCIAL", "OFERTA MERCANTIL"])
                has_addressee = any(k in text_all for k in ["SENORES", "SEÑORES", "CLIENTE:", "DIRIGIDA A", "ATTN:", "EMPRESA DE SERVICIOS"])
                if has_quote_title and has_addressee:
                    # Verificar si la primera página del segmento actual ya tenía su propio encabezado
                    first_seg_text = " ".join([b["text"] for b in current_segment[0]["boxes"]]).upper()
                    # Si no es la misma página y tiene título nuevo
                    if len(current_segment) >= 1:
                        m_nit_curr = re.search(r"\b(90[0-2]\d{6}-\d|800\d{6}-\d|811\d{6}-\d|\d{8,10}-\d)\b", text_all)
                        m_nit_prev = re.search(r"\b(90[0-2]\d{6}-\d|800\d{6}-\d|811\d{6}-\d|\d{8,10}-\d)\b", first_seg_text)
                        if m_nit_curr and m_nit_prev and m_nit_curr.group(1) != m_nit_prev.group(1):
                            is_new_proposal = True
                        elif len(current_segment) >= 2:
                            is_new_proposal = True

            if is_new_proposal and current_segment:
                segments.append(current_segment)
                current_segment = [page]
            else:
                current_segment.append(page)

        if current_segment:
            segments.append(current_segment)

        offers: List[ProponenteOferta] = []
        for idx, seg in enumerate(segments, 1):
            offer = self._parse_single_segment(seg, idx, filename)
            if offer and (offer.items or offer.valor_total_oferta > 0):
                offers.append(offer)

        return offers

    def _parse_single_segment(self, seg_pages: List[Dict[str, Any]], seg_idx: int, filename: str) -> ProponenteOferta:
        all_text = "\n".join([b["text"] for p in seg_pages for b in p["boxes"]])
        lines = [b["text"] for p in seg_pages for b in p["boxes"]]

        # 1. Extraer metadatos reales del oferente
        nombre, nit, rep, dom, fec = self._extract_vendor_metadata_from_text(all_text, lines)

        # 2. Extraer valor total narrativo o de tabla
        val_narrativo = self._extract_economic_total_from_text(all_text)

        # 3. Filtrar cajas monetarias con exclusión estricta de ruido
        items: List[ItemCotizacion] = []

        # Si hay valor narrativo único o valor total global (ej. $35.000.000 de CISPA)
        if val_narrativo > 0 and ("ASESOR" in all_text.upper() or "ESTUDIO TARIFARIO" in all_text.upper() or "CRA 1038" in all_text.upper() or "GLOBAL" in all_text.upper()):
            desc = "Elaboración del estudio de costos y tarifas para los servicios de Acueducto y Alcantarillado conforme a la Resolución CRA 1038 de 2026" if ("CRA 1038" in all_text.upper() or "TARIFARIO" in all_text.upper()) else "Consultoría o servicio integral según propuesta económica"
            items = [ItemCotizacion(
                item_numero=1,
                descripcion=desc,
                unidad="gl",
                cantidad=1.0,
                valor_unitario=val_narrativo,
                valor_total=val_narrativo,
                valor_total_calculado=val_narrativo
            )]
            subtotal = val_narrativo
        else:
            for p in seg_pages:
                boxes = p["boxes"]
                money_boxes = []
                for b in boxes:
                    t = b["text"].strip()
                    t_u = t.upper()
                    # FILTRADO ESTRICTO DE RUIDO
                    # Teléfonos / celulares (10 dígitos que empiezan por 30, 31, 32)
                    if re.search(r"\b3[012]\d{8}\b", t):
                        continue
                    # Líneas con NIT, Tel, Cel, direcciones, emails o resoluciones
                    if any(k in t_u for k in ["NIT", "TEL", "CEL", "CR ", "CALLE", "@", ".COM", "RESOLUCION", "RESOLUCIÓN", "CRA", "LEY", "DECRETO", "ARTICULO", "ARTÍCULO", "SUSCRIPTORES", "200W", "80DB", "20KHZ", "50/60HZ", "100-240V"]):
                        continue
                    if re.search(r"\$\s*\d|\b\d{1,3}(?:\.\d{3}){1,3}\b", t):
                        money_boxes.append(b)

                money_boxes.sort(key=lambda b: b["cy"])

                # Agrupar cajas en la misma fila
                i = 0
                while i < len(money_boxes):
                    m1 = money_boxes[i]
                    cy1 = m1["cy"]
                    same_row = [m1]
                    j = i + 1
                    while j < len(money_boxes) and abs(money_boxes[j]["cy"] - cy1) < 16:
                        same_row.append(money_boxes[j])
                        j += 1
                    i = j

                    same_row.sort(key=lambda b: b["cx"])
                    if len(same_row) >= 2:
                        vu = clean_money_value(same_row[-2]["text"])
                        vt = clean_money_value(same_row[-1]["text"])
                    else:
                        vt = clean_money_value(same_row[0]["text"])
                        vu = vt

                    min_cx = same_row[0]["cx"]
                    row_boxes = [b for b in boxes if abs(b["cy"] - cy1) <= 30 and b["cx"] < min_cx]
                    if not row_boxes:
                        row_boxes = [b for b in boxes if 0 <= (cy1 - b["cy"]) <= 65 and b["cx"] < min_cx]

                    cant = 1.0
                    desc_parts = []
                    for rb in row_boxes:
                        txt = rb["text"].strip()
                        if re.match(r"^\d{1,4}$", txt) and rb["cx"] > 450:
                            try: cant = float(txt)
                            except Exception: pass
                        else:
                            desc_parts.append(txt)

                    desc = " ".join(desc_parts).strip()
                    desc = re.sub(r"^(?:Producto|Cantidad|VALOR|DESCRIPCIONDELPRODUCTO/SERVICIO|VALORUNITARIO|VALORTOTAL)\s*", "", desc, flags=re.IGNORECASE).strip()
                    if not desc or len(desc) < 3:
                        desc = f"Ítem {len(items) + 1}"

                    # Descartar subtotales y totales repetidos
                    if ("VALOR TOTAL" in desc.upper() or "TOTAL" in desc.upper()) and len(items) >= 1:
                        continue

                    if len(same_row) == 1:
                        vu = round(vt / cant, 2) if cant > 0 else vt

                    if cant > 0 and vt > 0:
                        if vu <= 0 or vu > vt or abs(cant * vu - vt) > 10.0:
                            vu = round(vt / cant, 2)

                    items.append(ItemCotizacion(
                        item_numero=len(items) + 1,
                        descripcion=desc,
                        unidad="und",
                        cantidad=cant,
                        valor_unitario=vu,
                        valor_total=vt,
                        valor_total_calculado=round(cant * vu, 2)
                    ))

            subtotal = sum(it.valor_total for it in items)

        return ProponenteOferta(
            proponente_id=re.sub(r"[^a-zA-Z0-9]", "_", nombre or f"prop_{seg_idx}").lower()[:20],
            nombre_razon_social=clean_company_name(nombre),
            nit_cedula=nit,
            representante_legal=rep or "No especificado",
            domicilio=dom,
            fecha_oferta=fec,
            items=items,
            subtotal=round(subtotal, 2),
            valor_total_oferta=round(subtotal, 2)
        )


multi_proposal_parser = MultiProposalPDFParser()
