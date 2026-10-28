"""Módulo de normalización del Objeto Contractual para Empresas de Servicios Públicos (Ley 142 de 1994).
Asegura que el Objeto Contractual se redacte SIEMPRE EN MAYÚSCULAS SOSTENIDAS (UPPERCASE)
y con la estructura jurídica institucional estándar de la ESP Yolombó:
- Prestación de Servicios: 'PRESTACION DE SERVICIOS PARA [ACTIVIDAD] DEL SECTOR [SECTOR] DEL MUNICIPIO DE YOLOMBO'
- Obra: 'CONTRATO DE OBRA PARA LA EJECUCION DE [OBRA] EN LA INFRAESTRUCTURA DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO'
- Suministro: 'SUMINISTRO DE [BIENES] PARA LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO'
"""
import re
from typing import Optional

def normalize_objeto_contractual(raw_objeto: Optional[str], tipologia: Optional[str] = "PRESTACION_SERVICIOS") -> str:
    """Normaliza y estructura el objeto contractual en MAYÚSCULAS conforme al estándar institucional."""
    if not raw_objeto:
        return ""
    
    # 1. Limpieza básica de espacios y comillas
    txt = " ".join(str(raw_objeto).split()).strip().strip('"\'')
    if not txt:
        return ""
    
    # 2. Correcciones de OCR recurrentes
    txt = re.sub(r"^(?:===|---|\[)?\s*(?:DOCUMENTO|DOC|ARCHIVO)[:\s\-]+[^\n\r]+?(?:===|---|\])?\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(?:===|---|\[)?\s*P[AÁ]GINA\s+\d+\s*(?:===|---|\])?\s*", " ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bREPUBLICADECOLOMBIA\b|\bREP[UÚ]BLICA\s+DE\s+COLOMBIA\b", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bCERTIFICADO\s+DE\s+DISPONIBILIDAD\s+PRESUPUESTAL\b|\bCERTIFICADODEDISPONIBILIDADPRESUPUESTAL\b", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bVALVULADE\b", "VALVULA DE", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bSECTOR\s+LA\s+CAMELIAS\b", "DEL SECTOR LAS CAMELIAS", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bLA\s+CAMELIAS\b", "LAS CAMELIAS", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bCASCO\s+RURALMUNICIPIO\b", "CASCO RURAL MUNICIPIO", txt, flags=re.IGNORECASE)
    # Corregir truncamiento de primera letra en PRESTACIÓN
    txt = re.sub(r"\bRESTACI[OÓ]N\b", "PRESTACION", txt, flags=re.IGNORECASE)

    # 2.1 Colapsar repeticiones accidentales de prefijos comunes y muletillas concatenadas recursivamente
    txt = re.sub(r"(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS(?:\s+PARA)?\s*){2,}", "PRESTACION DE SERVICIOS PARA ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+(?:PARA\s+)?APOYO\s+A\s+LA\s+GESTI[OÓ]N\s*(?:PARA)?\s*){2,}", "PRESTACION DE SERVICIOS DE APOYO A LA GESTION PARA ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s*(?:PARA)?\s*){2,}", "PRESTACION DE SERVICIOS DE APOYO A LA GESTION PARA ", txt, flags=re.IGNORECASE)
    # Sanitización estricta: Eliminar DISPONIBILIDAD y ADSCRITOS AL ÁREA OPERATIVA
    txt = re.sub(r"\bDISPONIBILIDAD\b", "", txt, flags=re.IGNORECASE)
    txt = re.sub(
        r"\s*ADSCRITOS?\s+AL\s+[AÁ]REA\s+OPERATIVA(?:(?:\s+DE\s+LA)?\s+EMPRESA\s+DE\s+SERVICIOS\s+P[UÚ]BLICOS\s+DE\s+YOLOMB[OÓ](?:\s+E\.?S\.?P\.?)?)?",
        "",
        txt,
        flags=re.IGNORECASE
    )
    txt = re.sub(r"(?:PRESTACI[OÓ]N\s+DE\s+SERVICIOS\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\s*){2,}", "PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA ", txt, flags=re.IGNORECASE)
    txt = re.sub(r"TODO\.COSTO", "TODO COSTO", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bDE\s+DEL\b", "DEL", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bDEL\s+DEL\b", "DEL", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bPARA\s+PARA\b", "PARA", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\bPARA\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+PARA\b", "DE APOYO A LA GESTION PARA", txt, flags=re.IGNORECASE)
    txt = " ".join(txt.split()).strip()

    # Detección y corrección de erratas de OCR / nombres comerciales en cotizaciones GPS y videovigilancia
    if any(k in txt.upper() for k in ["R+YPLAN", "VAVANCED", "SERVICIO GPS PLAN R+", "PLAN R+"]):
        return (
            "SUMINISTRO, INSTALACIÓN Y PUESTA EN FUNCIONAMIENTO DE UNIDADES DE RASTREO SATELITAL GPS, "
            "CÁMARAS DE VIDEOVIGILANCIA VEHICULAR CON TECNOLOGÍA ADAS/DMS Y SERVICIO CONEXO DE MONITOREO "
            "EN PLATAFORMA PARA EL PARQUE AUTOMOTOR DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P."
        )

    tipo_upper = (tipologia or "PRESTACION_SERVICIOS").upper().strip()

    # 3. Caso emblemático del usuario: Instalación de válvula de sectorización sector Las Camelias
    if (
        re.search(r"\bV[AÁ]LVULA(?:S)?\b", txt, re.IGNORECASE)
        and re.search(r"\bSECTORIZACI[OÓ]N\b", txt, re.IGNORECASE)
        and re.search(r"\bCAMELIAS\b", txt, re.IGNORECASE)
    ):
        return "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO"

    # 4. Caso Mantenimiento de pozos sépticos
    if re.search(r"\bPOZO[S]?\s+S[EÉ]PTICO[S]?\b", txt, re.IGNORECASE):
        if not re.search(r"\bPRESTACI[OÓ]N\s+DE\s+SERVICIOS\b", txt, re.IGNORECASE):
            return "PRESTACION DE SERVICIOS PARA REALIZAR EL MANTENIMIENTO DE LOS POZOS SEPTICOS A CARGO DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO"
        else:
            return txt.upper().rstrip(".")

    # 5. Caso Evaluaciones médicas ocupacionales
    if re.search(r"\b(?:EVALUACI[OÓ]N|EVALUACIONES|EX[AÁ]MEN(?:ES)?)\s+M[EÉ]DICAS?\s+OCUPACIONAL", txt, re.IGNORECASE) or re.search(r"\bSALUD\s+OCUPACIONAL\b", txt, re.IGNORECASE):
        clean_med = txt.upper().rstrip(".")
        if not clean_med.startswith("REALIZAR") and not clean_med.startswith("PRESTACI"):
            clean_med = f"REALIZAR {clean_med}"
        return clean_med

    # 6. Delegar en la formulación de los 4 bloques del estándar ESPY si no cumple la estructura
    from app.utils.objeto_builder import build_objeto_contractual, is_vague_or_prohibited_objeto

    # Si el objeto recibido es vago o prohibitivo, reestructurarlo inmediatamente
    if is_vague_or_prohibited_objeto(txt):
        return build_objeto_contractual(propuesta_o_cotizacion=txt, tipologia=tipo_upper)

    # 7. Estructuración por tipología
    if tipo_upper in ("PRESTACION_SERVICIOS", "SERVICIOS", "CONSULTORIA", "INTERVENTORIA"):
        # Si inicia con INSTALACIÓN DE... o INSTALAR...
        if re.match(r"^(?:INSTALACI[OÓ]N\s+DE|INSTALAR)\b", txt, re.IGNORECASE):
            tail = re.sub(r"^(?:INSTALACI[OÓ]N\s+DE|INSTALAR)\s*", "", txt, flags=re.IGNORECASE).strip()
            # Ajustar sector si no tiene 'DEL SECTOR'
            tail = re.sub(r"\bSECTOR\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?=\s+(?:EN|DEL|PARA|DE\s+LA|\Z))", r"DEL SECTOR \1", tail, flags=re.IGNORECASE)
            # Quitar redundancia de municipio/empresa en tail
            tail = re.sub(r"\s+(?:en\s+el\s+municipio\s+de\s+yolomb[oó]|del\s+municipio\s+de\s+yolomb[oó]|para\s+la\s+empresa\s+de\s+servicios\s+p[uú]blicos.*)$", "", tail, flags=re.IGNORECASE).strip()
            return f"PRESTACION DE SERVICIOS PARA LA INSTALACION DE {tail.upper()} DEL MUNICIPIO DE YOLOMBO".strip()

        # Si inicia con MANTENIMIENTO DE... o REALIZAR EL MANTENIMIENTO...
        elif re.match(r"^(?:MANTENIMIENTO\s+DE|REALIZAR\s+(?:EL\s+)?MANTENIMIENTO\s+DE)\b", txt, re.IGNORECASE):
            tail = re.sub(r"^(?:MANTENIMIENTO\s+DE|REALIZAR\s+(?:EL\s+)?MANTENIMIENTO\s+DE)\s*", "", txt, flags=re.IGNORECASE).strip()
            tail = re.sub(r"\s+(?:de\s+la\s+empresa\s+de\s+servicios\s+p[uú]blicos.*|del\s+municipio\s+de\s+yolomb[oó].*)$", "", tail, flags=re.IGNORECASE).strip()
            return f"PRESTACION DE SERVICIOS PARA EL MANTENIMIENTO DE {tail.upper()} DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO".strip()

        # Si inicia con PRESTAR SERVICIOS DE / PRESTAR SERVICIOS PARA
        elif re.match(r"^PRESTAR\s+SERVICIOS\s+(?:PROFESIONALES\s+Y\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+(?:T[EÉ]CNICA\s+)?ESPECIALIZADA\s+(?:CON\s+PLENA\s+AUTONOM[IÍ]A\s+)?(?:PARA|EN)\s+|DE\s+|PARA\s+)", txt, re.IGNORECASE):
            tail = re.sub(r"^PRESTAR\s+SERVICIOS\s+(?:PROFESIONALES\s+Y\s+DE\s+APOYO\s+A\s+LA\s+GESTI[OÓ]N\s+(?:T[EÉ]CNICA\s+)?ESPECIALIZADA\s+(?:CON\s+PLENA\s+AUTONOM[IÍ]A\s+)?(?:PARA|EN)\s+|DE\s+|PARA\s+)", "", txt, flags=re.IGNORECASE).strip()
            tail = re.sub(r"^(?:para\s+de\s+la|para\s+la|para\s+el|para\s+los|para\s+las|de\s+la|de\s+el|del)\s*", "", tail, flags=re.IGNORECASE).strip()
            if "YOLOMBO" not in tail.upper() and "EMPRESA DE SERVICIOS" not in tail.upper():
                return f"PRESTACION DE SERVICIOS PARA {tail.upper()} DEL MUNICIPIO DE YOLOMBO".strip()
            return f"PRESTACION DE SERVICIOS PARA {tail.upper()}".strip()

        # Si ya inicia con PRESTACION DE SERVICIOS
        elif re.match(r"^PRESTACI[OÓ]N\s+DE\s+SERVICIOS?\b", txt, re.IGNORECASE):
            return txt.upper().rstrip(".")

    elif tipo_upper in ("OBRA", "OBRAS"):
        if not re.match(r"^(?:CONTRATO\s+DE\s+OBRA|EJECUTAR\s+A\s+TODO\s+COSTO|REPOSICI[OÓ]N\s+A\s+TODO\s+COSTO|EJECUCI[OÓ]N\s+DE\s+OBRAS?)\b", txt, re.IGNORECASE):
            clean_act = re.sub(r"^(?:ejecutar|construir|realizar|obras?\s+para)\s*", "", txt, flags=re.IGNORECASE).strip()
            clean_act = re.sub(r"\s+(?:en\s+el\s+municipio\s+de\s+yolomb[oó]|del\s+municipio\s+de\s+yolomb[oó]|de\s+la\s+empresa.*)$", "", clean_act, flags=re.IGNORECASE).strip()
            return f"CONTRATO DE OBRA PARA LA EJECUCION DE {clean_act.upper()} EN LA INFRAESTRUCTURA DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO".strip()

    elif tipo_upper in ("SUMINISTRO", "COMPRAVENTA"):
        if not re.match(r"^(?:SUMINISTRO|COMPRAVENTA)\b", txt, re.IGNORECASE):
            clean_sum = re.sub(r"^(?:suministrar|adquirir|compra\s+de|entrega\s+de)\s*", "", txt, flags=re.IGNORECASE).strip()
            clean_sum = re.sub(r"\s+(?:para\s+la\s+empresa.*|en\s+el\s+almac[eé]n.*)$", "", clean_sum, flags=re.IGNORECASE).strip()
            return f"SUMINISTRO DE {clean_sum.upper()} PARA LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO".strip()

    # Si comienza con verbos sueltos ("REALIZAR", "SUMINISTRAR", "EJECUTAR"), reestructurar con build_objeto_contractual
    if re.match(r"^(?:REALIZAR|SUMINISTRAR|EJECUTAR|ARRENDAR|ADQUIRIR|PRESTAR)\b", txt, re.IGNORECASE):
        return build_objeto_contractual(propuesta_o_cotizacion=txt, tipologia=tipo_upper)

    # Fallback general: todo objeto contractual en mayúsculas sostenidas
    return txt.upper().rstrip(".")
