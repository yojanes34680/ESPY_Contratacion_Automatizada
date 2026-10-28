"""Analizador y segmentador de documentos compuestos (Multi-document PDF / DOCX).
Identifica si un único archivo contiene múltiples documentos fusionados
(ej: RUT de la DIAN + Cédula + Propuesta Económica / Cotización + Certificación Bancaria)
y segmenta su contenido para que los agentes y extractores procesen cada sección adecuadamente.
"""
import re
from typing import List, Dict, Optional, Tuple
from app.utils.logger import logger

class CompositeDocumentAnalyzer:
    """
    Detecta y extrae subdocumentos dentro de archivos compuestos en contratación colombiana.
    """

    # Patrones de identificación por tipo de documento
    PATTERNS = {
        "RUT": [
            r"REGISTRO\s+[UÚ]NICO\s+TRIBUTARIO",
            r"FORMULARIO\s+001",
            r"REP[UÚ]BLICA\s+DE\s+COLOMBIA[\s\S]{1,100}DIAN",
            r"DIAN[\s\S]{1,50}RUT",
            r"5\.\s*N[uú]mero\s*de\s*identificaci[oó]n\s*tributaria",
            r"24\.\s*Tipo\s*de\s*contribuyente",
            r"35\.\s*Raz[oó]n\s*social",
            r"41\.\s*Direcci[oó]n\s*principal",
            r"53\.\s*Responsabilidades",
            r"46\.\s*Actividad\s*econ[oó]mica"
        ],
        "CDP": [
            r"CERTIFICADO\s+DE\s+DISPONIBILIDAD\s+PRESUPUESTAL",
            r"CERTIFICADODEDISPONIBILIDADPRESUPUESTAL",
            r"DISPONIBILIDAD\s+PRESUPUESTAL",
            r"\bCDP\s*(?:N[oOº°\.]*)?\s*\d+",
            r"Objeto\s+de\s+la\s+Disponibilidad",
            r"Valor\s+Rubro",
            r"CCPET\d+"
        ],
        "PROPUESTA_ECONOMICA": [
            r"PROPUESTA\s+ECON[OÓ]MICA",
            r"PROPUESTA\s+T[EÉ]CNICA\s+Y\s+ECON[OÓ]MICA",
            r"PROPUESTA\s+COMERCIAL",
            r"COTIZACI[OÓ]N(?:\s+DE\s+SERVICIOS|\s+COMERCIAL|\s+N[oO\.]|\s+PRECIOS)?",
            r"OFERTA\s+ECON[OÓ]MICA",
            r"OFERTA\s+COMERCIAL",
            r"OFERTA\s+(?:PARA|DE)\s+",
            r"OFERTA\s*N[oOº°\.]*",
            r"COSTO\s+TOTAL",
            r"COSTOTOTALDELAPROPUESTA",
            r"VALORCOSTODIRECTO",
            r"DESCRIPCI[OÓ]N\s+(?:DEL\s+)?PROYECTO",
            r"NOMBRE\s+(?:DEL\s+)?PROYECTO",
            r"PLAZO\s+EJECUCI[OÓ]N",
            r"PRESUPUESTO[\s\S]{1,60}VALOR\s+(?:UNITARIO|PARCIAL)",
            r"OBJETO\s+Y\s+ALCANCE\s+DE\s+LA\s+PROPUESTA",
            r"VALOR\s+DE\s+LA\s+PROPUESTA",
            r"VALOR\s+TOTAL\s+DE\s+LA\s+(?:PROPUESTA|OFERTA|COTIZACI[OÓ]N)",
            r"CONDICIONES\s+ECON[OÓ]MICAS",
            r"CONDICIONES\s*(?:DE\s*LA)?\s*OFERTA",
            r"CONDICIONESDELAOFERTA",
            r"VALIDEZ\s*(?:DE\s*LA)?\s*OFERTA",
            r"INVERSI[OÓ]N\s*TOTAL",
            r"VALOR\s*(?:X|POR)\s*PERSONA",
            r"VALOR\s*(?:UNITARIO|TOTAL)",
            r"PRESUPUESTO\s+(?:OFERTADO|COTIZADO|ESTIMADO)",
            r"ALCANCE\s+DE\s+LA\s+PROPUESTA",
            r"FORMA\s+DE\s+PAGO\s*[:\n]",
            r"PLAZO\s+DE\s+EJECUCI[OÓ]N\s*[:\n]",
            r"Dando\s+respuesta\s+a\s+la\s+solicitud[\s\S]{1,60}valor",
            r"le\s+env[ií]o\s+el\s+valor\s+de",
            r"CONCEPTO[\s\S]{1,60}(?:VALOR|PERSONAS|CANTIDAD|TOTAL)",
            r"exento\s+de\s+iva",
            r"incluye\s+el\s+domicilio",
            r"ex[aá]menes\s+m[eé]dicos\s+ocupacionales",
            r"SUCCI[OÓ]N\s+Y\s+DISPOSICI[OÓ]N",
            r"RETIRO\s+MANUAL\s+DE\s+SEDIMENTOS",
            r"MANTENIMIENTO\s+DE\s+SISTEMA\s+S[EÉ]PTICO",
            r"INSTALACI[OÓ]N\s+DE\s+V[AÁ]LVULA"
        ],
        "ESTUDIO_MERCADO": [
            r"ESTUDIO\s+DE\s+MERCADO",
            r"SONDEO\s+DE\s+MERCADO",
            r"AN[AÁ]LISIS\s+DE\s+PRECIOS\s+DE\s+MERCADO",
            r"AN[AÁ]LISIS\s+DEL\s+SECTOR"
        ],
        "CEDULA": [
            r"C[EÉ]DULA\s+DE\s+CIUDADAN[IÍ]A",
            r"REP[UÚ]BLICA\s+DE\s+COLOMBIA[\s\S]{1,60}IDENTIFICACI[OÓ]N\s+PERSONAL",
            r"REGISTRADUR[IÍ]A\s+NACIONAL\s+DEL\s+ESTADO\s+CIVIL",
            r"N[UÚ]MERO\s+[0-9\.\s]{6,12}[\s\S]{1,40}APELLIDOS",
            r"APELLIDOS[\s\S]{1,40}NOMBRES[\s\S]{1,40}NACIONALIDAD"
        ],
        "CERTIFICACION_BANCARIA": [
            r"CERTIFICACI[OÓ]N\s+BANCARIA",
            r"CERTIFICADO\s+BANCARIO",
            r"CERTIFICA\s+QUE[\s\S]{1,150}(?:CUENTA\s+DE\s+AHORROS|CUENTA\s+CORRIENTE)",
            r"TITULAR\s+DE\s+LA\s+CUENTA",
            r"(?:CUENTA\s+DE\s+AHORROS|CUENTA\s+CORRIENTE)\s+N[UÚ]MERO"
        ],
        "CAMARA_COMERCIO": [
            r"C[AÁ]MARA\s+DE\s+COMERCIO",
            r"CERTIFICADO\s+DE\s+EXISTENCIA\s+Y\s+REPRESENTACI[OÓ]N\s+LEGAL",
            r"MATR[IÍ]CULA\s+MERCANTIL\s+N[OÓ]"
        ],
        "ANTECEDENTES": [
            r"PROCURADUR[IÍ]A\s+GENERAL\s+DE\s+LA\s+NACI[OÓ]N",
            r"CONTRALOR[IÍ]A\s+GENERAL\s+DE\s+LA\s+REP[UÚ]BLICA",
            r"POLIC[IÍ]A\s+NACIONAL[\s\S]{1,50}ANTECEDENTES",
            r"CERTIFICADO\s+DE\s+ANTECEDENTES"
        ]
    }

    def detect_subdocument_types(self, text: str) -> List[str]:
        """
        Analiza el texto y retorna la lista de tipos de subdocumentos presentes.
        Ej: ["RUT", "PROPUESTA_ECONOMICA"]
        """
        if not text or not text.strip():
            return []

        detected = []
        for doc_type, regex_list in self.PATTERNS.items():
            for pattern in regex_list:
                if re.search(pattern, text, re.IGNORECASE):
                    detected.append(doc_type)
                    break
        return detected

    def contains_proposal_or_market_study(self, text: str) -> bool:
        """
        Verifica rápidamente si el texto contiene una propuesta económica o estudio de mercado.
        """
        detected = self.detect_subdocument_types(text)
        return "PROPUESTA_ECONOMICA" in detected or "ESTUDIO_MERCADO" in detected

    def segment_by_pages(self, text: str) -> List[Dict[str, any]]:
        """
        Divide el texto en páginas usando los delimitadores '=== PÁGINA X ==='
        o '--- PAGINA X ---' y categoriza cada página.
        """
        # Expresión para buscar delimitadores de página
        page_splits = re.split(r"(?:===|---)\s*P[AÁ]GINA\s+(\d+)\s*(?:===|---)", text, flags=re.IGNORECASE)
        
        # Si no hay delimitadores de página, tratar el texto completo como bloque 1
        if len(page_splits) <= 1:
            detected_types = self.detect_subdocument_types(text)
            return [{
                "pagina_inicio": 1,
                "pagina_fin": 1,
                "texto": text,
                "tipos_detectados": detected_types
            }]

        pages = []
        # page_splits tiene la estructura: [preambulo, num_pag1, texto1, num_pag2, texto2, ...]
        i = 1
        while i < len(page_splits):
            try:
                page_num = int(page_splits[i])
            except ValueError:
                page_num = (i // 2) + 1
            
            page_text = page_splits[i + 1] if (i + 1) < len(page_splits) else ""
            detected_types = self.detect_subdocument_types(page_text)
            pages.append({
                "pagina": page_num,
                "texto": page_text,
                "tipos_detectados": detected_types
            })
            i += 2

        return pages

    def extract_subdocument_text(self, text: str, target_type: str) -> Optional[str]:
        """
        Aísla y extrae el fragmento de texto correspondiente al subdocumento deseado.
        target_type: 'RUT', 'PROPUESTA_ECONOMICA', 'ESTUDIO_MERCADO', 'CEDULA', etc.
        """
        if not text:
            return None

        # Si el texto tiene estructura de páginas
        pages = self.segment_by_pages(text)
        matched_pages_text = []

        for p in pages:
            tipos = p.get("tipos_detectados", [])
            if target_type in tipos:
                matched_pages_text.append(p.get("texto", ""))

        if matched_pages_text:
            return "\n\n".join(matched_pages_text).strip()

        # Si no se encontró por página individual, verificar si el texto global lo tiene
        if target_type == "PROPUESTA_ECONOMICA" and self.contains_proposal_or_market_study(text):
            # Buscar el punto de inicio de la propuesta en el texto
            for pattern in self.PATTERNS["PROPUESTA_ECONOMICA"]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start_idx = max(0, match.start() - 100)
                    return text[start_idx:].strip()

        if target_type == "RUT":
            for pattern in self.PATTERNS["RUT"]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start_idx = max(0, match.start() - 50)
                    prop_match = re.search(r"PROPUESTA\s+ECON[OÓ]MICA|COTIZACI[OÓ]N|OFERTA", text[start_idx:], re.IGNORECASE)
                    if prop_match:
                        end_idx = start_idx + prop_match.start()
                        return text[start_idx:end_idx].strip()
                    return text[start_idx:start_idx + 15000].strip()

        if target_type == "CDP":
            for pattern in self.PATTERNS["CDP"]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    start_idx = max(0, match.start() - 50)
                    return text[start_idx:start_idx + 8000].strip()

        return None

composite_analyzer = CompositeDocumentAnalyzer()
