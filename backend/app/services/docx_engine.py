"""Word (.docx) template assembly engine for public utility contracts (ESP). Preserves exact styling, tables, margins, and typography."""
import re
import os
import shutil
import calendar
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from app.config import settings
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.document import Documento, TipoDocumento, CategoriaDocumento
from app.utils.num_to_words import numero_a_letras_cop
from app.utils.objective_normalizer import normalize_objetivos_especificos, format_single_objective
from app.utils.necesidad_builder import build_descripcion_necesidad
from app.utils.logger import logger

# Mapeo oficial de plantillas Word (.docx)
CUSTOM_TEMPLATE_MAPPING = {
    # 1. Estudios Previos
    "ESTUDIO_PREVIO_SERVICIOS": "custom_plantilla_estudio_previo_servicios.docx",
    "ESTUDIO_PREVIO_SUMINISTRO": "custom_plantilla_estudio_previo_suministro.docx",
    # 2. Minutas de Contrato
    "MINUTA_SERVICIOS": "custom_plantilla_minuta_servicios.docx",
    "MINUTA_SUMINISTRO": "custom_plantilla_minuta_suministro.docx",
    # 3. Actas y Modificaciones
    "ACTA_INICIO": "custom_plantilla_acta_inicio.docx",
    "ADICION": "custom_plantilla_adicion_contrato.docx",
    # Alias de compatibilidad legacy:
    "ESTUDIO_PREVIO": "custom_plantilla_estudio_previo.docx",
    "MINUTA": "custom_plantilla_minuta_contrato.docx",
}

DEFAULT_TEMPLATE_MAPPING = {
    # 1. Estudios Previos
    "ESTUDIO_PREVIO_SERVICIOS": "plantilla_estudio_previo_servicios.docx",
    "ESTUDIO_PREVIO_SUMINISTRO": "plantilla_estudio_previo_suministro.docx",
    # 2. Minutas de Contrato
    "MINUTA_SERVICIOS": "plantilla_minuta_servicios.docx",
    "MINUTA_SUMINISTRO": "plantilla_minuta_suministro.docx",
    # 3. Actas y Modificaciones
    "ACTA_INICIO": "plantilla_acta_inicio.docx",
    "ADICION": "plantilla_adicion_contrato.docx",
    # Alias de compatibilidad legacy:
    "ESTUDIO_PREVIO": "plantilla_estudio_previo.docx",
    "MINUTA": "plantilla_minuta_contrato.docx",
}

TEMPLATE_METADATA = {
    "ESTUDIO_PREVIO_SERVICIOS": {
        "nombre": "Estudio Previo - Prestación de Servicios",
        "descripcion": "Estudio de conveniencia y necesidad para contratos de servicios profesionales o apoyo a la gestión (Ley 142/1994, Art. 23 CST y SG-SST).",
        "categoria": "ESTUDIOS_PREVIOS",
        "categoria_nombre": "Estudios Previos",
        "icono": "📄",
        "modalidad": "PRESTACION_SERVICIOS"
    },
    "ESTUDIO_PREVIO_SUMINISTRO": {
        "nombre": "Estudio Previo - Suministro",
        "descripcion": "Estudio de necesidad, costeo y requerimientos técnicos para suministro de insumos, materiales y equipos de acueducto y alcantarillado.",
        "categoria": "ESTUDIOS_PREVIOS",
        "categoria_nombre": "Estudios Previos",
        "icono": "📦",
        "modalidad": "SUMINISTRO"
    },
    "MINUTA_SERVICIOS": {
        "nombre": "Minuta de Contrato - Prestación de Servicios",
        "descripcion": "Documento contractual formal para servicios inmateriales, honorarios, pagos contra informe y aportes a seguridad social con plena autonomía técnica.",
        "categoria": "MINUTAS",
        "categoria_nombre": "Minutas de Contrato",
        "icono": "📑",
        "modalidad": "PRESTACION_SERVICIOS"
    },
    "MINUTA_SUMINISTRO": {
        "nombre": "Minuta de Contrato - Suministro",
        "descripcion": "Contrato mercantil de suministro (C.Co. arts. 968-980), condiciones de entrega en almacén ESPY, garantías de fábrica, calidad y vicios ocultos.",
        "categoria": "MINUTAS",
        "categoria_nombre": "Minutas de Contrato",
        "icono": "🚚",
        "modalidad": "SUMINISTRO"
    },
    "ACTA_INICIO": {
        "nombre": "Acta de Inicio de Ejecución",
        "descripcion": "Formalización de fecha de inicio, aprobación de pólizas, verificación de CDP/RP y designación oficial de supervisión técnica de la ESP.",
        "categoria": "ACTAS_Y_ADICIONES",
        "categoria_nombre": "Actas y Modificaciones",
        "icono": "🏁",
        "modalidad": "GENERAL"
    },
    "ADICION": {
        "nombre": "Minuta / Acta de Adición a Contrato",
        "descripcion": "Modificación formal al contrato para incremento de valor presupuestal (CDP), prórroga en plazo y fijación del nuevo valor total acumulado.",
        "categoria": "ACTAS_Y_ADICIONES",
        "categoria_nombre": "Actas y Modificaciones",
        "icono": "➕",
        "modalidad": "ADICION"
    }
}

def normalize_placeholder_key(key: str) -> str:
    """Normaliza una clave de marcador removiendo acentos, caracteres especiales y convirtiendo espacios a guiones bajos."""
    import unicodedata
    if not key:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(key))
    no_accents = "".join([c for c in nfkd if not unicodedata.combining(c)])
    cleaned = re.sub(r"[\s\-\/\.]+", "_", no_accents.strip().upper())
    # Normalizar sufijos plurales/singulares comunes
    if cleaned in ("OBJETIVO_ESPECIFICOS", "OBJETIVO_ESPECIFICO", "OBJETIVOS_ESPECIFICO", "OBJETIVOS_ESPECIFICOS"):
        cleaned = "OBJETIVOS_ESPECIFICOS"
    elif cleaned in ("OBJETIVOS_GENERAL", "OBJETIVO_GENERALES", "OBJETIVOS_GENERALES", "OBJETIVO_GENERAL"):
        cleaned = "OBJETIVO_GENERAL"
    elif cleaned in ("OBLIGACIONES_DEL_CONTRATISTA", "OBLIGACIONES_CONTRATISTA", "OBLIGACIONES_DE_EL_CONTRATISTA"):
        cleaned = "OBLIGACIONES"
    elif cleaned in (
        "OBLIGACIONES_DE_LA_EMPRESA", "OBLIGACIONES_EMPRESA", "OBLIGACIONES_ESP",
        "OBLIGACIONES_DE_EMPRESA", "OBLIGACIONES_ENTIDAD", "OBLIGACIONES_DE_LA_ENTIDAD",
        "OBLIGACIONES_CONTRATANTE", "OBLIGACIONES_DE_LA_CONTRATANTE"
    ):
        cleaned = "OBLIGACIONES_EMPRESA"
    elif cleaned in (
        "TIPO_DE_CONTRATO", "TIPO_DEL_CONTRATO", "TIPO_CONTRATO", 
        "TIPO_CONTRACTUAL", "TIPOLOGIA_CONTRACTUAL", "TIPOLOGIA_CONTRATO", 
        "TIPOLOGIA"
    ):
        cleaned = "TIPO_DE_CONTRATO"
    return cleaned

PLACEHOLDER_REGEX = r"(\{\{\s*([A-Za-z0-9_\-\sÁÉÍÓÚáéíóúñÑ/.]+?)\s*\}\})"

def inspect_docx_placeholders(file_path: Path) -> List[str]:
    """
    Inspecciona un archivo .docx y extrae la lista ordenada y única de marcadores {{VARIABLE}} encontrados.
    Soporta variables con espacios, guiones y tildes (ej. {{OBJETIVOS GENERAL}}, {{OBJETIVOS ESPECIFICOS}}).
    """
    if not file_path.exists():
        return []
    try:
        doc = docx.Document(str(file_path))
        placeholders = set()
        
        # Párrafos del cuerpo
        for p in doc.paragraphs:
            for _, key_raw in re.findall(PLACEHOLDER_REGEX, p.text):
                placeholders.add(key_raw.strip().upper())
                
        # Tablas
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for _, key_raw in re.findall(PLACEHOLDER_REGEX, p.text):
                            placeholders.add(key_raw.strip().upper())
                            
        # Encabezados y pies
        for s in doc.sections:
            for p in s.header.paragraphs:
                for _, key_raw in re.findall(PLACEHOLDER_REGEX, p.text):
                    placeholders.add(key_raw.strip().upper())
            for p in s.footer.paragraphs:
                for _, key_raw in re.findall(PLACEHOLDER_REGEX, p.text):
                    placeholders.add(key_raw.strip().upper())
                    
        return sorted(list(placeholders))
    except Exception as e:
        logger.error(f"Error inspeccionando marcadores en {file_path}: {e}")
        return []

def get_active_template_path(template_type: str) -> Tuple[Path, bool]:
    """
    Retorna la ruta de la plantilla activa y un booleano indicando si es personalizada (True) u oficial por defecto (False).
    """
    norm = template_type.upper().strip()
    create_default_templates_if_missing()
    
    # Manejo de compatibilidad para alias legacy
    if norm == "ESTUDIO_PREVIO":
        custom_ep = settings.CUSTOM_TEMPLATES_DIR / "custom_plantilla_estudio_previo.docx"
        if custom_ep.exists() and custom_ep.stat().st_size > 0:
            return custom_ep, True
        norm = "ESTUDIO_PREVIO_SERVICIOS"
    elif norm == "MINUTA":
        custom_min = settings.CUSTOM_TEMPLATES_DIR / "custom_plantilla_minuta_contrato.docx"
        if custom_min.exists() and custom_min.stat().st_size > 0:
            return custom_min, True
        norm = "MINUTA_SERVICIOS"

    if norm not in DEFAULT_TEMPLATE_MAPPING:
        raise ValueError(f"Tipo de plantilla desconocido: {template_type}")

    custom_name = CUSTOM_TEMPLATE_MAPPING[norm]
    custom_path = settings.CUSTOM_TEMPLATES_DIR / custom_name
    if custom_path.exists() and custom_path.stat().st_size > 0:
        return custom_path, True

    default_name = DEFAULT_TEMPLATE_MAPPING[norm]
    default_path = settings.TEMPLATES_DIR / default_name
    return default_path, False

def get_template_status(template_type: str) -> Dict[str, Any]:
    """Retorna los metadatos y estado actual de una plantilla (personalizada o predeterminada)."""
    norm = template_type.upper().strip()
    active_path, is_custom = get_active_template_path(norm)
    meta = TEMPLATE_METADATA.get(norm, {"nombre": norm, "descripcion": ""})
    
    placeholders = inspect_docx_placeholders(active_path)
    stat = active_path.stat()
    last_mod = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "tipo": norm,
        "nombre": meta.get("nombre", norm),
        "descripcion": meta.get("descripcion", ""),
        "categoria": meta.get("categoria", "GENERAL"),
        "categoria_nombre": meta.get("categoria_nombre", "Modelos Generales"),
        "icono": meta.get("icono", "📄"),
        "modalidad": meta.get("modalidad", "GENERAL"),
        "is_custom": is_custom,
        "archivo_nombre": active_path.name,
        "tamano_bytes": stat.st_size,
        "ultima_modificacion": last_mod,
        "placeholders_detectados": placeholders,
        "download_url": f"/api/templates/download-active/{norm}"
    }

def get_all_templates_status() -> List[Dict[str, Any]]:
    """Retorna el estado de todas las 6 plantillas oficiales organizadas por categorías."""
    create_default_templates_if_missing()
    keys = [
        "ESTUDIO_PREVIO_SERVICIOS",
        "ESTUDIO_PREVIO_SUMINISTRO",
        "MINUTA_SERVICIOS",
        "MINUTA_SUMINISTRO",
        "ACTA_INICIO",
        "ADICION"
    ]
    return [get_template_status(t) for t in keys]

def convert_doc_to_docx_if_needed(temp_file_path: Path) -> Path:
    """Si el archivo es un formato binario legado .doc, lo convierte automáticamente a .docx usando Word COM."""
    if temp_file_path.suffix.lower() == ".doc":
        docx_path = temp_file_path.with_suffix(".docx")
        try:
            import subprocess
            ps_script = f"""
            $word = New-Object -ComObject Word.Application
            $word.Visible = $false
            $doc = $word.Documents.Open('{temp_file_path.resolve()}')
            $doc.SaveAs2('{docx_path.resolve()}', 16)
            $doc.Close()
            $word.Quit()
            """
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True, text=True, timeout=20)
            if docx_path.exists() and docx_path.stat().st_size > 0:
                logger.info(f"Plantilla .doc convertida exitosamente a .docx: {docx_path}")
                return docx_path
        except Exception as e:
            logger.error(f"No se pudo convertir .doc a .docx: {e}")
    return temp_file_path

def save_custom_template(template_type: str, file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Guarda un archivo de plantilla personalizada (.docx o .doc) subido por el usuario."""
    norm = template_type.upper().strip()
    if norm not in CUSTOM_TEMPLATE_MAPPING:
        raise ValueError(f"Tipo de plantilla no soportado: {template_type}")

    target_filename = CUSTOM_TEMPLATE_MAPPING[norm]
    target_path = settings.CUSTOM_TEMPLATES_DIR / target_filename
    settings.CUSTOM_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    suffix = Path(filename).suffix.lower() if filename else ".docx"
    temp_path = settings.CUSTOM_TEMPLATES_DIR / f"temp_{target_filename}{suffix}"

    # Guardar en archivo temporal
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

    # Si es formato .doc legado, convertir a .docx
    if suffix == ".doc":
        converted = convert_doc_to_docx_if_needed(temp_path)
        if converted.exists() and converted.suffix.lower() == ".docx":
            if target_path.exists():
                try:
                    target_path.unlink()
                except Exception:
                    pass
            converted.replace(target_path)
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
        else:
            if temp_path.exists():
                temp_path.unlink()
            raise ValueError("El archivo cargado está en formato Word 97-2003 (.doc) y no pudo ser convertido automáticamente a .docx. Por favor guárdelo como .docx en Word e intente de nuevo.")
    else:
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                pass
        temp_path.replace(target_path)

    # Validar que sea un docx legítimo
    try:
        docx.Document(str(target_path))
    except Exception as e:
        if target_path.exists():
            try:
                target_path.unlink()
            except Exception:
                pass
        raise ValueError(f"El archivo cargado no es un documento Word (.docx) válido o está dañado: {e}")

    logger.info(f"Plantilla personalizada '{target_filename}' guardada exitosamente.")
    return get_template_status(norm)

def reset_custom_template(template_type: str) -> bool:
    """Elimina la plantilla personalizada y restaura el modelo oficial por defecto."""
    norm = template_type.upper().strip()
    if norm not in CUSTOM_TEMPLATE_MAPPING:
        raise ValueError(f"Tipo de plantilla no soportado: {template_type}")

    target_filename = CUSTOM_TEMPLATE_MAPPING[norm]
    target_path = settings.CUSTOM_TEMPLATES_DIR / target_filename
    if target_path.exists():
        target_path.unlink()
        logger.info(f"Plantilla personalizada '{target_filename}' eliminada. Restablecido a modelo base.")
        return True
    return False

def replace_placeholder_in_paragraph(p, placeholder: str, replacement_text: str):
    """
    Reemplaza todas las ocurrencias de `placeholder` en un párrafo preservando
    el formato de los runs, soportando placeholders divididos en múltiples runs
    sin alterar los runs ajenos al marcador.
    """
    if not placeholder or not p.runs:
        return

    replacement = str(replacement_text) if replacement_text is not None else ""

    while True:
        full_text = "".join(r.text for r in p.runs)
        pos = full_text.find(placeholder)
        if pos == -1:
            break

        ph_len = len(placeholder)
        start_char = pos
        end_char = pos + ph_len

        # Localizar los runs que abarcan [start_char, end_char)
        cur_pos = 0
        first_run_idx = None
        last_run_idx = None
        first_offset = 0
        last_offset = 0

        for idx, run in enumerate(p.runs):
            r_len = len(run.text)
            r_start = cur_pos
            r_end = cur_pos + r_len

            if r_start <= start_char < r_end:
                first_run_idx = idx
                first_offset = start_char - r_start

            if r_start < end_char <= r_end:
                last_run_idx = idx
                last_offset = end_char - r_start
                break

            cur_pos = r_end

        if first_run_idx is None or last_run_idx is None:
            # Fallback seguro
            for run in p.runs:
                if placeholder in run.text:
                    run.text = run.text.replace(placeholder, replacement)
            break

        if first_run_idx == last_run_idx:
            # Caso 1: El placeholder está enteramente contenido dentro de un solo run
            r = p.runs[first_run_idx]
            r.text = r.text[:first_offset] + replacement + r.text[last_offset:]
        else:
            # Caso 2: El placeholder está dividido entre múltiples runs contiguos
            # 1. En el primer run, conservar lo que estaba antes del placeholder y añadir el replacement
            first_run = p.runs[first_run_idx]
            first_run.text = first_run.text[:first_offset] + replacement

            # 2. Vaciar los runs intermedios
            for mid_idx in range(first_run_idx + 1, last_run_idx):
                p.runs[mid_idx].text = ""

            # 3. En el último run, conservar solo lo que está después del final del placeholder
            last_run = p.runs[last_run_idx]
            last_run.text = last_run.text[last_offset:]

def insert_paragraph_after(current_p, text: str, style=None):
    """Inserta un nuevo párrafo con formato de viñeta inmediatamente después de current_p, garantizando letra Arial tamaño 12."""
    new_p_elm = OxmlElement("w:p")
    current_p._element.addnext(new_p_elm)
    new_p = docx.text.paragraph.Paragraph(new_p_elm, current_p._parent)
    new_p.text = text
    new_p.paragraph_format.left_indent = Inches(0.25)
    new_p.paragraph_format.space_after = Pt(3)
    if style:
        try:
            new_p.style = style
        except Exception:
            pass
    for r in new_p.runs:
        r.font.name = "Arial"
        r.font.size = Pt(12)
    return new_p

def replace_placeholders_in_document(doc: docx.Document, context: Dict[str, Any]):
    """
    Recorre todos los párrafos y tablas del documento Word reemplazando las variables {{CLAVE}}.
    Soporta sinónimos, variaciones de mayúsculas/minúsculas, tildes y espacios (ej. {{ CONTRATISTA }},
    {{OBJETIVOS GENERAL}}, {{OBJETIVOS ESPECIFICOS}}, {{OBLIGACIONES}}), manejando tanto strings simples como listas
    de viñetas estructuradas que pueden ubicarse solas o tras un encabezado con salto de línea.
    """
    # Construir mapa de búsqueda exhaustivo
    norm_context: Dict[str, Any] = {}
    for k, v in context.items():
        k_upper = re.sub(r"\s+", " ", str(k).strip().upper())
        norm_context[k_upper] = v
        
        # Con espacios a guiones bajos
        k_und = re.sub(r"[\s\-]+", "_", k_upper)
        norm_context[k_und] = v
        
        # Con guiones bajos a espacios
        k_spc = re.sub(r"[_\-]+", " ", k_upper)
        norm_context[k_spc] = v
        
        # Normalizado sin tildes
        k_norm = normalize_placeholder_key(k_upper)
        if k_norm:
            norm_context[k_norm] = v
            norm_context[k_norm.replace("_", " ")] = v
            
        # Variantes específicas para AÑO / ANO / ANIO
        if "AÑO" in k_upper or "ANO" in k_upper:
            norm_context[k_upper.replace("AÑO", "ANO")] = v
            norm_context[k_upper.replace("ANO", "AÑO")] = v
            norm_context[k_upper.replace("AÑO", "ANIO")] = v

    def get_context_val(raw_k: str):
        cleaned = re.sub(r"\s+", " ", raw_k.strip()).upper()
        if cleaned in norm_context:
            return norm_context[cleaned]
        
        und = re.sub(r"[\s\-]+", "_", cleaned)
        if und in norm_context:
            return norm_context[und]
            
        spc = re.sub(r"[_\-]+", " ", cleaned)
        if spc in norm_context:
            return norm_context[spc]
            
        norm = normalize_placeholder_key(cleaned)
        if norm in norm_context:
            return norm_context[norm]
        if norm.replace("_", " ") in norm_context:
            return norm_context[norm.replace("_", " ")]
            
        # Variantes de AÑO / ANO / ANIO
        if "AÑO" in cleaned:
            c_ano = cleaned.replace("AÑO", "ANO")
            if c_ano in norm_context:
                return norm_context[c_ano]
        if "ANO" in cleaned:
            c_anno = cleaned.replace("ANO", "AÑO")
            if c_anno in norm_context:
                return norm_context[c_anno]

        # Si termina en S o sin S (singular/plural)
        if cleaned.endswith("S") and cleaned[:-1] in norm_context:
            return norm_context[cleaned[:-1]]
        if not cleaned.endswith("S") and (cleaned + "S") in norm_context:
            return norm_context[cleaned + "S"]
            
        return None

    # Pre-procesamiento: Evitar duplicación de prefijos (ej. CPS-{{NUMERO_CONTRATO}} cuando el valor ya es 'CS-054-2026', 'CO-...', 'CA-...', o 'CPS-...')
    num_val = str(norm_context.get("NUMERO_CONTRATO") or norm_context.get("CONTRATO") or "").strip()
    if num_val:
        has_official_prefix = any(num_val.upper().startswith(pfx) for pfx in ("CPS-", "CS-", "CO-", "CA-", "CC-", "CI-"))
        if has_official_prefix:
            all_prefixes = ("CPS-", "CS-", "CO-", "CA-", "CC-", "CI-", "CPS", "CS", "CO", "CA", "CC", "CI")
            for pfx in all_prefixes:
                pfx_clean = pfx if pfx.endswith("-") else f"{pfx}-"
                candidate_tags = (
                    f"{pfx_clean}{{{{NUMERO_CONTRATO}}}}",
                    f"{pfx_clean}{{{{CONTRATO}}}}",
                    f"{pfx_clean}{{{{NUMERO_DE_CONTRATO}}}}",
                    f"{pfx}{{{{NUMERO_CONTRATO}}}}",
                    f"{pfx}{{{{CONTRATO}}}}",
                )
                for tag in candidate_tags:
                    for p_iter in list(doc.paragraphs):
                        if tag in p_iter.text:
                            replace_placeholder_in_paragraph(p_iter, tag, num_val)
                    for table_iter in doc.tables:
                        for row_iter in table_iter.rows:
                            for cell_iter in row_iter.cells:
                                for p_iter in list(cell_iter.paragraphs):
                                    if tag in p_iter.text:
                                        replace_placeholder_in_paragraph(p_iter, tag, num_val)
                    for s_iter in doc.sections:
                        for hp_iter in s_iter.header.paragraphs:
                            if tag in hp_iter.text:
                                replace_placeholder_in_paragraph(hp_iter, tag, num_val)

    # Pre-procesamiento: Reescritura dinámica de la cláusula de OBLIGACIONES DE LA EMPRESA
    # Si la plantilla contiene la cláusula con texto estático legacy (ej: "SEXTA. OBLIGACIONES DE LA EMPRESA: LA EMPRESA facilitará...")
    # sin el marcador dinámico, reescribirlo para que contenga {{OBLIGACIONES_EMPRESA}} y se expanda con la lista adaptada a la tipología.
    for p_emp in doc.paragraphs:
        t_upper = p_emp.text.upper()
        if "OBLIGACIONES DE LA EMPRESA" in t_upper or "OBLIGACIONES DE LA ESP" in t_upper or "OBLIGACIONES DE LA ENTIDAD" in t_upper:
            if "{{OBLIGACIONES_EMPRESA}}" not in p_emp.text and "{{OBLIGACIONES DE LA EMPRESA}}" not in p_emp.text and "{{OBLIGACIONES_ESP}}" not in p_emp.text:
                m_cl = re.search(r"^(.*?OBLIGACIONES\s+DE\s+LA\s+(?:EMPRESA|ESP|ENTIDAD)[^\:\.]*[\:\.]?\s*)(.*)$", p_emp.text, re.IGNORECASE | re.DOTALL)
                if m_cl:
                    hdr = m_cl.group(1).strip()
                    if not hdr.endswith(":"):
                        hdr += ":"
                    p_emp.text = f"{hdr}\n{{{{OBLIGACIONES_EMPRESA}}}}"
                else:
                    p_emp.text = f"OBLIGACIONES DE LA EMPRESA:\n{{{{OBLIGACIONES_EMPRESA}}}}"

    last_obligations_paragraph = None
    # 1. Párrafos en el cuerpo del documento
    for p in list(doc.paragraphs):
        matches = re.findall(PLACEHOLDER_REGEX, p.text)
        for full_match, key_raw in matches:
            val = get_context_val(key_raw)
            if val is not None:
                if isinstance(val, list):
                    is_oblig = any(k in key_raw.upper() for k in ["OBLIGACION", "OBLIGACIÓN"])
                    remaining_text = p.text.replace(full_match, "").rstrip("\r\n ")
                    if not remaining_text:
                        # El párrafo contenía únicamente el marcador (ej: {{OBJETIVOS ESPECIFICOS}} solo)
                        cur = p
                        for item in val:
                            cur = insert_paragraph_after(cur, f"• {str(item).strip()}", p.style)
                            if is_oblig:
                                last_obligations_paragraph = cur
                        try:
                            p._element.getparent().remove(p._element)
                        except Exception:
                            pass
                    else:
                        # El párrafo contiene texto encabezado antes del marcador (ej: 'QUINTA. OBLIGACIONES... se obliga a:\n{{OBLIGACIONES}}')
                        for r in p.runs:
                            if full_match in r.text:
                                r.text = r.text.replace(full_match, "").rstrip("\r\n ")
                        if full_match in p.text:
                            p.text = p.text.replace(full_match, "").rstrip("\r\n ")
                        cur = p
                        for item in val:
                            cur = insert_paragraph_after(cur, f"• {str(item).strip()}", p.style)
                            if is_oblig:
                                last_obligations_paragraph = cur
                else:
                    replace_placeholder_in_paragraph(p, full_match, str(val if val is not None else ""))

    # 2. Tablas del documento
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in list(cell.paragraphs):
                    matches = re.findall(PLACEHOLDER_REGEX, p.text)
                    for full_match, key_raw in matches:
                        val = get_context_val(key_raw)
                        if val is not None:
                            if isinstance(val, list):
                                p.text = p.text.replace(full_match, "")
                                for item in val:
                                    new_p = cell.add_paragraph(f"• {str(item).strip()}")
                                    new_p.paragraph_format.space_after = Pt(2)
                                    for r in new_p.runs:
                                        r.font.name = "Arial"
                                        r.font.size = Pt(12)
                                if not p.text.strip() and len(cell.paragraphs) > 1:
                                    try:
                                        p._element.getparent().remove(p._element)
                                    except Exception:
                                        pass
                            else:
                                replace_placeholder_in_paragraph(p, full_match, str(val if val is not None else ""))

    # 3. Encabezados y pies de página
    for section in doc.sections:
        for header_p in section.header.paragraphs:
            for full_match, key_raw in re.findall(PLACEHOLDER_REGEX, header_p.text):
                val = get_context_val(key_raw)
                if val is not None and not isinstance(val, list):
                    replace_placeholder_in_paragraph(header_p, full_match, str(val))

        for footer_p in section.footer.paragraphs:
            for full_match, key_raw in re.findall(PLACEHOLDER_REGEX, footer_p.text):
                val = get_context_val(key_raw)
                if val is not None and not isinstance(val, list):
                    replace_placeholder_in_paragraph(footer_p, full_match, str(val))

    # Limpieza final: Evitar signos de pesos dobles si la plantilla ya tenía '$' antes del marcador
    def _clean_double_dollar(p_obj):
        if "$$" in p_obj.text or "$ $" in p_obj.text:
            for r in p_obj.runs:
                if "$$" in r.text or "$ $" in r.text:
                    r.text = r.text.replace("$$", "$").replace("$ $", "$")
            if "$$" in p_obj.text or "$ $" in p_obj.text:
                full_t = p_obj.text.replace("$$", "$").replace("$ $", "$")
                if len(p_obj.runs) == 1:
                    p_obj.runs[0].text = full_t

    for p in doc.paragraphs:
        _clean_double_dollar(p)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    _clean_double_dollar(p)
    for s in doc.sections:
        for hp in s.header.paragraphs:
            _clean_double_dollar(hp)
        for fp in s.footer.paragraphs:
            _clean_double_dollar(fp)

    # Armonización y Regla de Oro: Evitar que textos estáticos de plantillas legacy
    # mencionen 'acueducto y alcantarillado' si el objeto contractual es de PGIRS, Aseo, o Administrativo
    raw_obj = str(context.get("OBJETO") or "").lower()
    is_pgirs_aseo = bool(re.search(r"\b(?:pgirs|aseo|residuos?|reciclaje|barrido|limpieza|ambiental|educaci[oó]n\s+ambiental|aprovechamiento)\b", raw_obj))
    has_acueducto_specific = bool(re.search(r"\b(?:acueducto|alcantarillado|ptap|ptar|potabilizaci[oó]n|agua\s+potable|v[aá]lvula)\b", raw_obj))

    is_gps_supply = bool(re.search(r"\b(?:gps|adas|dms|videovigilancia|telemetr[ií]a|parque\s+automotor|veh[ií]culos?)\b", raw_obj))

    def _sanitize_golden_rule(p_obj):
        t = p_obj.text
        if "reparación oportuna, eficiente y en términos de economía del acueducto y alcantarillado" in t:
            if is_gps_supply:
                new_t = t.replace(
                    "reparación oportuna, eficiente y en términos de economía del acueducto y alcantarillado a cargo de la ESP YOLOMBO",
                    "el aprovisionamiento, dotación tecnológica y fortalecimiento operativo oportuno, eficiente y en términos de economía de los procesos técnicos y del parque automotor a cargo de la ESP YOLOMBO"
                ).replace(
                    "reparación oportuna, eficiente y en términos de economía del acueducto y alcantarillado",
                    "el aprovisionamiento, dotación tecnológica y fortalecimiento operativo oportuno, eficiente y en términos de economía de los procesos técnicos y del parque automotor"
                )
            elif is_pgirs_aseo and not has_acueducto_specific:
                new_t = t.replace(
                    "reparación oportuna, eficiente y en términos de economía del acueducto y alcantarillado",
                    "ejecución oportuna, eficiente y técnica de las actividades del servicio de aseo y del PGIRS"
                ).replace(
                    "del acueducto y alcantarillado a cargo de la ESP",
                    "del servicio de aseo y el PGIRS a cargo de la ESP"
                ).replace(
                    "usuarios del sistema de acueducto",
                    "usuarios y la salubridad pública de la comunidad"
                ).replace(
                    "contrato de suministro da cumplimiento a tales objetivos",
                    "presente contrato da cumplimiento a tales objetivos"
                )
            else:
                new_t = t.replace(
                    "reparación oportuna, eficiente y en términos de economía del acueducto y alcantarillado a cargo de la ESP YOLOMBO",
                    "el aprovisionamiento, dotación tecnológica y fortalecimiento operativo oportuno, eficiente y en términos de economía de los procesos técnicos y del parque automotor a cargo de la ESP YOLOMBO"
                )
            if new_t != t:
                p_obj.text = new_t

    for p in doc.paragraphs:
        _sanitize_golden_rule(p)
    # Estandarización tipográfica institucional: Letra tipo Arial tamaño 12 en todo el contenido textual
    enforce_arial_12_typography(doc)

    return {"last_obligations_paragraph": last_obligations_paragraph}

def enforce_arial_12_typography(doc: docx.Document):
    """
    Aplica rigurosamente la regla tipográfica institucional:
    Todo el contenido escrito agregado al documento debe ser en letra tipo 'Arial' tamaño 12 (12pt).
    Preserva negritas y cursivas existentes, pero uniforma la fuente y el puntaje.
    """
    # 1. Párrafos en el cuerpo del documento
    for p in doc.paragraphs:
        for r in p.runs:
            r.font.name = "Arial"
            r.font.size = Pt(12)
            # Asegurar en XML w:rFonts para Word
            rPr = r._r.get_or_add_rPr()
            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is None:
                rFonts = OxmlElement('w:rFonts')
                rPr.append(rFonts)
            rFonts.set(qn('w:ascii'), 'Arial')
            rFonts.set(qn('w:hAnsi'), 'Arial')
            rFonts.set(qn('w:cs'), 'Arial')

    # 2. Celdas de tablas
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.name = "Arial"
                        r.font.size = Pt(12)
                        rPr = r._r.get_or_add_rPr()
                        rFonts = rPr.find(qn('w:rFonts'))
                        if rFonts is None:
                            rFonts = OxmlElement('w:rFonts')
                            rPr.append(rFonts)
                        rFonts.set(qn('w:ascii'), 'Arial')
                        rFonts.set(qn('w:hAnsi'), 'Arial')
                        rFonts.set(qn('w:cs'), 'Arial')

def format_cop_currency(amount: Any) -> str:
    """
    Formatea un valor numérico a pesos colombianos (COP) estándar con puntos como separadores de miles y sin comas.
    Ejemplo: 9400083.0 -> '$9.400.083'
    """
    if amount is None or amount == "":
        return "$0"
    try:
        val_float = float(amount)
        val_int = int(round(val_float))
        formatted = f"{val_int:,}".replace(",", ".")
        return f"${formatted}"
    except Exception:
        return str(amount)

MESES_SPANISH = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

def format_date_spanish(date_val: Any, default: str = "") -> str:
    """
    Formatea una fecha (date, datetime, o str) al formato estándar en español para contratación pública:
    '<día> de <mes_en_letras_minúscula> de <año>', por ejemplo '15 de octubre de 2026'.
    Si el valor es None o no es una fecha válida, retorna 'default' (o el valor en string si default es vacío).
    """
    if not date_val:
        return default

    if isinstance(date_val, (date, datetime)):
        mes = MESES_SPANISH.get(date_val.month, "")
        return f"{date_val.day} de {mes} de {date_val.year}"

    val_str = str(date_val).strip()
    if not val_str or val_str.lower() in ("none", "null", "undefined"):
        return default

    # Si ya contiene formato en español "de <mes> de", devolver tal cual
    if re.search(r"\bde\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s+de\b", val_str, re.IGNORECASE):
        return val_str

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            d_obj = datetime.strptime(val_str[:10], fmt).date()
            mes = MESES_SPANISH.get(d_obj.month, "")
            return f"{d_obj.day} de {mes} de {d_obj.year}"
        except Exception:
            pass

    return default if default else val_str

def build_contract_context(contrato: Contrato) -> Dict[str, Any]:
    """Construye el diccionario exhaustivo de variables con sinónimos para plantillas .docx."""
    c = getattr(contrato, "contratista", None)
    valor_tot = getattr(contrato, "valor_total", 0.0) or 0.0
    valor_ini = getattr(contrato, "valor_inicial", None)
    if valor_ini is None:
        valor_ini = valor_tot

    valor_cop = format_cop_currency(valor_tot)
    valor_ini_cop = format_cop_currency(valor_ini)
    valor_letras = getattr(contrato, "valor_en_letras", None) or numero_a_letras_cop(valor_tot)

    # Identificación legal
    meta_dict = getattr(contrato, "metadatos_agente", {}) or {}
    if not isinstance(meta_dict, dict):
        meta_dict = {}

    if c:
        raw_tipo_per = getattr(getattr(c, "tipo_persona", None), "value", str(getattr(c, "tipo_persona", "NATURAL") or "NATURAL")).upper()
        is_juridica = "JURIDICA" in raw_tipo_per or "EMPRESA" in raw_tipo_per
        raw_doc = str(getattr(c, 'numero_documento', '') or '').strip()
        clean_doc = re.sub(r"-\d+$", "", raw_doc).strip()

        if is_juridica:
            dv = getattr(c, "digito_verificacion", None)
            if not dv and clean_doc:
                from app.services.rut_parser import calculate_dian_dv
                dv = calculate_dian_dv(clean_doc)
            nit_con_dv = f"{clean_doc}-{dv}" if dv else clean_doc
            doc_tipo = "NIT"
            doc_tipo_num = f"NIT {nit_con_dv}"
            cedula_o_nit = nit_con_dv
        else:
            # PERSONA NATURAL: La información de la cédula se carga al contrato sin el dígito de verificación
            doc_tipo = getattr(c.tipo_documento, "value", str(c.tipo_documento)) if hasattr(c, "tipo_documento") and c.tipo_documento else "CC"
            if doc_tipo == "NIT":
                doc_tipo = "CC"
            doc_tipo_num = f"{doc_tipo} {clean_doc}"
            cedula_o_nit = clean_doc

        contratista_nom = str(getattr(c, "nombre_o_razon_social", "CONTRATISTA") or "CONTRATISTA").upper()
    else:
        raw_tipo_per = str(meta_dict.get("tipo_persona") or meta_dict.get("contratista_tipo_persona") or "NATURAL").upper()
        is_juridica = "JURIDICA" in raw_tipo_per or "EMPRESA" in raw_tipo_per
        raw_doc = str(getattr(contrato, "contratista_identificacion", "Por definir")).strip()
        clean_doc = re.sub(r"-\d+$", "", raw_doc).strip()

        if is_juridica:
            dv = meta_dict.get("digito_verificacion")
            nit_con_dv = f"{clean_doc}-{dv}" if dv else raw_doc
            doc_tipo = "NIT"
            doc_tipo_num = f"NIT {nit_con_dv}" if not raw_doc.startswith("NIT") else raw_doc
            cedula_o_nit = nit_con_dv
        else:
            # PERSONA NATURAL: La cédula se carga al contrato sin el dígito de verificación
            doc_tipo = "CC"
            doc_tipo_num = f"CC {clean_doc}" if not raw_doc.startswith("CC") else re.sub(r"-\d+$", "", raw_doc)
            cedula_o_nit = clean_doc

        contratista_nom = str(getattr(contrato, "contratista_nombre", "CONTRATISTA")).upper()

    supervisor_nom = getattr(contrato, "supervisor_nombre", None) or "Director(a) Técnico y Operativo"
    supervisor_car = getattr(contrato, "supervisor_cargo", None) or "Supervisor Designado"
    supervisor_dep = getattr(contrato, "supervisor_dependencia", None) or "Área Técnica de la ESP"
    supervisor_tipo = getattr(contrato, "supervisor_tipo_documento", None) or "CC"
    supervisor_num = getattr(contrato, "supervisor_documento", None) or "Por definir"
    supervisor_doc_full = f"{supervisor_tipo} {supervisor_num}" if getattr(contrato, "supervisor_documento", None) else "Por definir"

    # Inferencia inteligente de tipología y normalización oficial
    from app.utils.contract_prefix_helper import infer_contract_tipologia, normalize_contract_code
    prop_ctx = f"{contrato.objeto or ''} {contrato.justificacion_necesidad or ''}".strip()
    cdp_ctx = f"{getattr(contrato, 'cdp_rubro', '') or ''} {meta_dict.get('cdp_rubro_nombre', '') or ''} {meta_dict.get('cdp_texto_completo', '') or ''}".strip()
    raw_tipo = getattr(contrato.tipologia, "value", str(contrato.tipologia or "PRESTACION_SERVICIOS"))
    
    inferred_tipo, _ = infer_contract_tipologia(
        propuesta_text=prop_ctx,
        cdp_text=cdp_ctx,
        current_tipologia=raw_tipo
    )
    if inferred_tipo and inferred_tipo != raw_tipo and raw_tipo in ("PRESTACION_SERVICIOS", "", None):
        # Actualizar contrato con tipología detectada
        tipo_str = inferred_tipo
    else:
        tipo_str = str(raw_tipo or "PRESTACION_SERVICIOS").upper()

    # Normalizar número de contrato si aplica
    if getattr(contrato, "numero_contrato", None):
        contrato.numero_contrato = normalize_contract_code(contrato.numero_contrato, tipo_str, getattr(contrato, "vigencia", None))

    # Normalización del Objeto Contractual bajo el estándar de la ESPY (4 bloques en mayúsculas sostenidas)
    from app.utils.object_normalizer import normalize_objeto_contractual
    objeto_norm = normalize_objeto_contractual(getattr(contrato, "objeto", "") or "", tipo_str)
    if objeto_norm:
        contrato.objeto = objeto_norm

    # Reemplazo específico para cotizaciones de GPS / videovigilancia vehicular
    if any(k in (contrato.objeto or "").upper() for k in ["R+YPLAN", "VAVANCED", "SERVICIO GPS PLAN R+", "PLAN R+"]):
        contrato.objeto = (
            "SUMINISTRO, INSTALACIÓN Y PUESTA EN FUNCIONAMIENTO DE UNIDADES DE RASTREO SATELITAL GPS, "
            "CÁMARAS DE VIDEOVIGILANCIA VEHICULAR CON TECNOLOGÍA ADAS/DMS Y SERVICIO CONEXO DE MONITOREO "
            "EN PLATAFORMA PARA EL PARQUE AUTOMOTOR DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P."
        )

    # Objetivos del Contrato (General y Específicos) con generador estructurado de la ESPY
    from app.utils.objetivos_builder import build_objetivo_general, build_objetivos_especificos, is_prohibited_objective

    raw_especificos = getattr(contrato, "objetivos_especificos", None) or []
    if isinstance(raw_especificos, list):
        obj_especificos = [str(x).strip() for x in raw_especificos if str(x).strip()]
    elif isinstance(raw_especificos, str):
        obj_especificos = [re.sub(r"^(?:[•\-\*]|\d+[\.\)]\s*)\s*", "", line.strip()).strip() for line in raw_especificos.split("\n") if line.strip()]
    else:
        obj_especificos = []

    # Filtrar objetivos prohibidos (trámites administrativos o frases comodín)
    clean_especificos = [o for o in obj_especificos if not is_prohibited_objective(o)]

    obj_general_raw = (getattr(contrato, "objetivo_general", None) or "").strip()
    # Si el objetivo general está vacío, o incrusta objeto en mayúsculas o frase genérica tipo "Cumplir a cabalidad" o errores de OCR
    is_invalid_general = (
        not obj_general_raw
        or "PRESTACIÓN DE SERVICIOS" in obj_general_raw
        or "cumplir a cabalidad" in obj_general_raw.lower()
        or "actividades técnicas y operativas requeridas para" in obj_general_raw.lower()
        or bool(re.search(r"\b(?:plan\s*r\+|devideo|vavanced)\b", obj_general_raw, re.IGNORECASE))
        or obj_general_raw == (contrato.objeto or "")
    )
    if is_invalid_general:
        obj_general = build_objetivo_general(
            objeto=contrato.objeto or "",
            tipologia=tipo_str,
            contexto=contrato.justificacion_necesidad or ""
        )
    else:
        obj_general = format_single_objective(obj_general_raw)

    # Si no hay objetivos específicos técnicos válidos o son menos de 3, generarlos técnicamente
    if len(clean_especificos) < 3:
        obj_especificos = build_objetivos_especificos(
            objeto=contrato.objeto or "",
            tipologia=tipo_str,
            items_propuesta=clean_especificos or None,
            contexto=contrato.justificacion_necesidad or ""
        )
    else:
        obj_especificos = normalize_objetivos_especificos(clean_especificos)


    # Obligaciones del Contratista (Minuta y Estudio Previo) con fallbacks por tipología
    raw_minuta = getattr(contrato, "obligaciones_minuta", None) or []
    if isinstance(raw_minuta, list):
        oblig_minuta = [str(x).strip() for x in raw_minuta if str(x).strip()]
    elif isinstance(raw_minuta, str):
        oblig_minuta = [re.sub(r"^(?:[•\-\*]|\d+[\.\)]\s*)\s*", "", line.strip()).strip() for line in raw_minuta.split("\n") if line.strip()]
    else:
        oblig_minuta = []

    raw_ep = getattr(contrato, "obligaciones_estudio_previo", None) or []
    if isinstance(raw_ep, list):
        oblig_ep = [str(x).strip() for x in raw_ep if str(x).strip()]
    elif isinstance(raw_ep, str):
        oblig_ep = [re.sub(r"^(?:[•\-\*]|\d+[\.\)]\s*)\s*", "", line.strip()).strip() for line in raw_ep.split("\n") if line.strip()]
    else:
        oblig_ep = []

    raw_empresa = getattr(contrato, "obligaciones_empresa", None) or []
    if isinstance(raw_empresa, list):
        oblig_empresa = [str(x).strip() for x in raw_empresa if str(x).strip()]
    elif isinstance(raw_empresa, str):
        oblig_empresa = [re.sub(r"^(?:[•\-\*]|\d+[\.\)]\s*)\s*", "", line.strip()).strip() for line in raw_empresa.split("\n") if line.strip()]
    else:
        oblig_empresa = []

    # Descartar obligaciones residuales de taller si el contrato trata de GPS o telemetría o no es taller
    is_gps_contract = any(k in (contrato.objeto or "").lower() for k in ["gps", "telemetr", "adas", "dms", "videovigilancia", "parque automotor"])
    tool_terms = ["desensamble integral", "devanados", "rodamientos", "aislamiento dieléctrico", "aislamiento dielectrico"]
    if is_gps_contract or "SUMINISTRO" in tipo_str:
        if any(any(term in o.lower() for term in tool_terms) for o in oblig_minuta):
            oblig_minuta = []
        if any(any(term in o.lower() for term in tool_terms) for o in oblig_ep):
            oblig_ep = []
        if any(any(term in o.lower() for term in ["herramientas a intervenir", "desensamble", "devanados", "rodamientos"]) for o in oblig_empresa):
            oblig_empresa = []

    # Fallback cruzado: si falta alguna, tomar de la otra
    if not oblig_minuta and oblig_ep:
        oblig_minuta = list(oblig_ep)
    if not oblig_ep and oblig_minuta:
        oblig_ep = list(oblig_minuta)

    # Definición exhaustiva de obligaciones estándar y de blindaje jurídico por tipología (Ley 142/1994)
    tipo_str = contrato.tipologia.value if hasattr(contrato.tipologia, 'value') else str(contrato.tipologia)
    tipo_str = str(tipo_str or "PRESTACION_SERVICIOS").upper()

    default_oblig_minuta = []
    default_oblig_ep = []
    default_oblig_empresa = []

    if "OBRA" in tipo_str:
        default_oblig_minuta = [
            "Ejecutar la totalidad de las obras civiles con estricto apego a los planos, especificaciones técnicas de la ESP, normas sismorresistentes NSR-10 y Reglamento RAS-2017 (Res. 0330/2017 MVCT).",
            "Disponer de manera permanente en el frente de trabajo de un Ingeniero Residente de Obra debidamente matriculado y con dedicación exclusiva a la ejecución del proyecto.",
            "Diligenciar diariamente y mantener actualizada la bitácora o libro oficial de obra en conjunto con la interventoría/supervisión técnica, consignando avances, personal, maquinaria e incidencias.",
            "Suministrar materiales certificados de primera calidad (tuberías, accesorios, concretos, agregados), aportando certificados de conformidad y ensayos de laboratorio a costo del contratista.",
            "Implementar rigurosamente el Sistema de Gestión de Seguridad y Salud en el Trabajo (SG-SST) conforme al Decreto 1072 de 2015, dotando a los trabajadores de EPP/EPI y cobertura en Riesgo V de ARL.",
            "Instalar cerramientos perimetrales de seguridad, señalización preventiva reglamentaria diurna y nocturna y ejecutar el Plan de Manejo de Tránsito (PMT) aprobado.",
            "Ejecutar el Plan de Manejo Ambiental (PMA) y la gestión integral de Residuos de Construcción y Demolición (RCD - Res. 1257 de 2021), disponiendo escombros solo en sitios legalmente certificados.",
            "Efectuar a su costa las pruebas técnicas de presión hidrostática, estanqueidad, desinfección de redes y ensayos de resistencia de concretos bajo supervisión técnica.",
            "Responder civil, penal y patrimonialmente por los daños y perjuicios causados a predios colindantes, redes existentes de servicios o a terceros, manteniendo indemne a la ESP.",
            "Constituir, prorrogar y mantener vigentes todas las garantías contractuales exigidas (cumplimiento, salarios, estabilidad de obra decenal y responsabilidad civil extracontractual).",
            "Elaborar y entregar a la ESP los planos récord definitivos (As-Built) en medio digital editable (DWG/CAD) y PDF, junto con las memorias de cálculo y manuales de operación.",
            "Suscribir oportunamente en debida forma el Acta de Inicio, Actas Parciales de Obra con memorias de cálculo, Acta de Recibo Final y Acta de Liquidación Definitiva del contrato."
        ]
        default_oblig_ep = [
            "Realizar visita técnica obligatoria al sitio de las obras para constatar topografía, accesibilidad, interferencias de redes de servicios y condiciones del terreno.",
            "Presentar el presupuesto oficial desglosado con análisis detallado de precios unitarios (APU) y porcentaje desglosado de A.I.U. (Administración, Imprevistos y Utilidad).",
            "Entregar el cronograma de ejecución física y financiera detallado (diagrama Gantt o CPM) con su respectiva ruta crítica, debidamente firmado por el Director de Obra.",
            "Acreditar la disponibilidad de maquinaria pesada, equipos certificados y herramientas requeridas para el rendimiento óptimo del frente de trabajo.",
            "Aportar las hojas de vida y matrículas profesionales vigentes del Director de Obra y Residente de Obra con sus antecedentes de COPNIA vigentes.",
            "Formular y presentar el Plan de Manejo Ambiental (PMA) y el Plan de Manejo de Tránsito (PMT) articulado con las autoridades municipales.",
            "Acreditar el cumplimiento del SG-SST y presentar las constancias de afiliación a seguridad social en Riesgo V de ARL para el personal operativo.",
            "Presentar el plan de calidad de materiales e insumos con los protocolos de ensayos de laboratorio y certificados de fábrica."
        ]
        default_oblig_empresa = [
            "Designar oportunamente la Interventoría o Supervisión Técnica y Administrativa que ejercerá el control, seguimiento y vigilancia de la ejecución de la obra.",
            "Efectuar la entrega real y material de la zona, frentes de trabajo y predios requeridos para la ejecución de las obras mediante la suscripción del Acta de Entrega de Terreno.",
            "Tramitar oportunamente los permisos institucionales y coordinar las suspensiones programadas del servicio público necesarias para empalmes o intervenciones de redes.",
            "Revisar, aprobar y tramitar para pago las actas parciales de obra debidamente suscritas por el contratista y la interventoría/supervisión dentro de los plazos establecidos.",
            "Suministrar oportunamente al contratista los planos generales, memorias de diseño y especificaciones técnicas oficiales requeridas para la ejecución de la obra.",
            "Suscribir oportunamente las Actas de Inicio, Suspensión, Reinicio, Modificación, Recibo Final y Liquidación Definitiva del contrato.",
            "Revisar y recibir los planos récord (As-Built), memorias técnicas y manuales de operación entregados por el contratista al término de la obra."
        ]
    elif "SUMINISTRO" in tipo_str:
        default_oblig_minuta = [
            "Efectuar la entrega de la totalidad de los bienes en la bodega principal o Almacén General de la ESP bajo condición DDP (Delivered Duty Paid), asumiendo todos los costos de fletes, embalaje, seguros, peajes y descargue.",
            "Suministrar bienes totalmente nuevos, de primera calidad, de fabricación reciente (no saldos ni remanufacturados), empacados y rotulados conforme a la normativa vigente.",
            "Aportar junto con cada despacho las remisiones, fichas técnicas, certificados de control de calidad de fábrica, certificados de calibración y hojas de seguridad en español.",
            "Suscribir el Acta de Entrada al Almacén y Recibo a Satisfacción conjuntamente con el Jefe de Almacén y el Supervisor del contrato tras la verificación física, conteo y prueba técnica.",
            "Reemplazar por su cuenta y riesgo, dentro de un término perentorio máximo de cuarenta y ocho (48) horas hábiles, cualquier elemento averiado, defectuoso o no conforme con las especificaciones.",
            "Otorgar garantía técnica formal de fábrica por un periodo mínimo de doce (12) meses contados a partir del recibo a satisfacción, amparando defectos de fabricación y vicios ocultos (Art. 934 C.Co.).",
            "Garantizar la disponibilidad de repuestos legítimos, consumibles y servicio técnico autorizado durante la vigencia de la garantía técnica del producto.",
            "Entregar los manuales técnicos de instalación, operación y mantenimiento en idioma español junto con las cartas de garantía debidamente suscritas.",
            "Brindar la capacitación o transferencia tecnológica necesaria al personal operativo de la ESP en el manejo e instalación adecuada de los bienes suministrados si se requiere.",
            "Acreditar oportunamente la afiliación y pago de aportes al Sistema de Seguridad Social Integral y parafiscales como condición previa para el trámite de cada factura y desembolso de pago.",
            "Mantener indemne a la ESP frente a cualquier reclamación de terceros por infracción de patentes, licencias, marcas, derechos de autor o daños atribuibles a defectos del producto.",
            "Suscribir oportunamente en debida forma el Acta de Inicio (si aplica), actas de entrega parcial y el Acta de Liquidación Final del contrato."
        ]
        default_oblig_ep = [
            "Presentar catálogo comercial y fichas técnicas oficiales del fabricante detallando especificaciones, tolerancias y materiales para cada ítem a suministrar.",
            "Adjuntar certificados vigentes de conformidad de producto con normas técnicas oficiales (NTC, AWWA, ASTM, ISO o equivalentes).",
            "Presentar el cronograma de despacho y entrega en el Almacén General de la ESP, detallando fechas de remisión y lotes.",
            "Aportar hojas de datos de seguridad (MSDS / SGA - Decreto 1496 de 2018) y protocolos de almacenamiento seguro si se trata de químicos, reactivos o sustancias peligrosas.",
            "Acreditar la idoneidad y representación autorizada del fabricante o distribuidor mayorista en Colombia.",
            "Entregar la carta de compromiso de garantía técnica de fábrica no inferior a un (1) año y disponibilidad de repuestos por un término mínimo de cinco (5) años.",
            "Acreditar el cumplimiento de aportes al Sistema de Seguridad Social Integral y parafiscales de su personal.",
            "Disponer de los medios de transporte idóneos con pólizas de mercancías vigentes para la entrega DDP en las bodegas de la entidad."
        ]
        default_oblig_empresa = [
            "Designar al Supervisor del contrato y coordinar con el responsable del Almacén General la recepción física y técnica de los bienes.",
            "Recibir a satisfacción los bienes suministrados que cumplan estrictamente con las especificaciones técnicas pactadas y suscribir el Acta de Entrada al Almacén dentro de las cuarenta y ocho (48) horas siguientes a la entrega.",
            "Informar por escrito y de manera motivada al contratista sobre cualquier inconformidad, faltante, avería o defecto en los bienes entregados para su inmediata reposición.",
            "Facilitar el acceso logístico adecuado a las instalaciones y bodegas de la empresa para el descargue seguro y custodia de los elementos suministrados.",
            "Tramitar oportunamente el pago del valor convenido, previa radicación de la factura electrónica reglamentaria con el cumplimiento de requisitos legales y visto bueno de supervisión.",
            "Suscribir el Acta de Liquidación del contrato una vez verificada la entrega total de los bienes y el cumplimiento de las garantías técnicas."
        ]
    elif "ARRENDAMIENTO" in tipo_str:
        default_oblig_minuta = [
            "Destinar el bien inmueble única y exclusivamente para los fines operativos, administrativos o institucionales acordados en el contrato.",
            "Mantener y conservar el inmueble en buen estado de funcionamiento, asumiendo oportunamente las reparaciones locativas que le correspondan conforme a la ley.",
            "Efectuar el pago oportuno de los cánones de arrendamiento en los términos, plazos y cuentas bancarias convenidas.",
            "Permitir la inspección periódica del inmueble por parte del supervisor designado por la ESP para verificar su estado y destinación.",
            "Abstenerse de subarrendar, ceder o gravar total o parcialmente el contrato o la tenencia del inmueble sin autorización previa, expresa y por escrito de la ESP.",
            "Efectuar oportunamente el pago de los servicios públicos domiciliarios a su cargo y remitir las constancias de pago al supervisor.",
            "No realizar modificaciones estructurales o reformas en el inmueble sin la debida autorización previa y por escrito de la entidad arrendadora.",
            "Restituir formalmente el inmueble a la ESP al vencimiento del plazo contractual en el mismo estado en que fue recibido, salvo el deterioro natural por el uso legítimo, mediante acta de entrega y recibo final."
        ]
        default_oblig_ep = [
            "Verificar las condiciones físicas, estructurales, jurídicas y de saneamiento del bien inmueble objeto del arrendamiento.",
            "Aportar el certificado de tradición y libertad con fecha de expedición no mayor a 30 días y comprobantes de paz y salvo de impuestos y servicios.",
            "Presentar inventario detallado del estado inicial del inmueble con registro fotográfico para el acta de entrega.",
            "Establecer el protocolo de mantenimiento preventivo y correctivo de las instalaciones locativas."
        ]
        default_oblig_empresa = [
            "Hacer entrega material del bien inmueble en la fecha convenida, en adecuado estado de servicio, seguridad y sanidad, mediante acta suscrita con inventario detallado.",
            "Garantizar el goce pacífico del bien durante todo el tiempo del contrato, amparando al arrendatario frente a turbaciones de derecho o pretensiones de terceros.",
            "Asumir oportunamente las reparaciones necesarias mayores o estructurales no locativas y las derivadas de fuerza mayor o vicios ocultos de construcción.",
            "Efectuar oportunamente el pago de los cánones de arrendamiento en los términos y plazos pactados (cuando la ESP actúe en calidad de arrendataria).",
            "Designar al supervisor institucional para coordinar la verificación periódica del estado del inmueble y el cumplimiento de las condiciones contractuales.",
            "Recibir formalmente el inmueble a la terminación del contrato mediante acta de entrega y restitución suscrita conjuntamente por las partes."
        ]
    else:
        # PRESTACION_SERVICIOS / CONSULTORIA
        default_oblig_minuta = [
            "Ejecutar el objeto del contrato y las actividades acordadas con plena autonomía técnica, administrativa, directiva y financiera, sin subordinación laboral, utilizando sus propios medios y conocimientos especializados bajo el régimen de la Ley 142 de 1994 y el Artículo 23 del CST.",
            "Cumplir a cabalidad con el cronograma, plazos de entrega y especificaciones técnicas aprobadas por la ESP, garantizando la más alta calidad, diligencia y pericia profesional en el desarrollo del servicio.",
            "Acatar de manera diligente las instrucciones, requerimientos técnicos y directrices impartidas por el supervisor designado por la ESP, facilitando en todo momento el control, inspección y vigilancia de los servicios.",
            "Asistir y participar activamente en las reuniones de seguimiento, comités técnicos o mesas de trabajo programadas por la entidad o la supervisión para evaluar el avance del objeto contractual.",
            "Presentar mensualmente a la supervisión, dentro de los primeros cinco (5) días hábiles de cada mes, un informe detallado de las actividades desarrolladas acompañado de las evidencias documentales, memorias, registros fotográficos y entregables pactados, como requisito previo para la expedición del certificado de cumplimiento y trámite de pago.",
            "Acreditar previa y obligatoriamente ante la supervisión, para el trámite de cada pago y para la liquidación contractual, la afiliación y pago oportuno de aportes al Sistema de Seguridad Social Integral (Salud, Pensión y ARL en el nivel de riesgo correspondiente al servicio), calculados sobre un IBC no inferior al 40% del valor mensualizado del contrato, en cumplimiento de la Ley 100 de 1993, Ley 789 de 2002 y Decreto 1273 de 2018.",
            "Cumplir estrictamente las normas, políticas y estándares del Sistema de Gestión de Seguridad y Salud en el Trabajo (SG-SST) de la ESP (Decreto 1072 de 2015 y Resolución 0312 de 2019), utilizando permanentemente y en óptimo estado los Elementos de Protección Personal (EPP/EPI) reglamentarios.",
            "Reportar inmediatamente por escrito al supervisor cualquier incidente, accidente laboral, condición de riesgo operativo o emergencia sobreviniente en la ejecución de las actividades contratadas.",
            "Guardar absoluta reserva, custodia y confidencialidad sobre la información técnica, administrativa, financiera, operativa y bases de datos de usuarios de la ESP a la que tenga acceso, absteniéndose de divulgarla o usarla para fines ajenos al contrato, dando estricto cumplimiento a la Ley 1581 de 2012 de Protección de Datos Personales (Habeas Data).",
            "Responder por el cuidado, custodia, mantenimiento y buen uso de los elementos, herramientas, equipos o documentación que la ESP le suministre para facilitar el servicio, debiendo restituirlos en igual estado a la terminación del contrato, salvo el desgaste natural por el uso legítimo.",
            "Responder civil, fiscal y disciplinariamente por los daños o perjuicios que por culpa, impericia, negligencia o dolo ocasione a la ESP o a terceros en la ejecución contractual, debiendo mantener indemne a la entidad frente a cualquier reclamación judicial, extrajudicial o laboral.",
            "Obrar con estricta lealtad, buena fe, ética y transparencia en cumplimiento del Estatuto Anticorrupción (Leyes 1474 de 2011 y 2195 de 2022), absteniéndose de ofrecer o recibir dádivas o prebendas, y declarando inmediatamente cualquier inhabilidad o conflicto de interés sobreviniente.",
            "Ceder de manera total, definitiva y exclusiva a favor de la ESP todos los derechos patrimoniales de autor sobre estudios, informes, diagnósticos, bases de datos o productos intelectuales desarrollados en ejecución del contrato.",
            "Suscribir oportunamente en debida forma el Acta de Inicio, las Actas Parciales de Recibo o Avance y el Acta de Liquidación Final del contrato en coordinación con la supervisión técnica."
        ]
        default_oblig_ep = [
            "Acreditar la idoneidad profesional, técnica o de experiencia requerida para la ejecución del servicio, aportando hoja de vida con soportes académicos, tarjeta o matrícula profesional vigente (si aplica), certificados de experiencia y antecedentes fiscales, disciplinarios y judiciales vigentes.",
            "Presentar a la supervisión de la ESP, dentro de los cinco (5) días hábiles siguientes al acta de inicio, el plan de trabajo detallado y el cronograma de ejecución de actividades.",
            "Disponer de los medios técnicos, tecnológicos, informáticos, equipos y herramientas propias requeridas para el cabal y oportuno desarrollo del objeto contratado.",
            "Estructurar y presentar los informes de actividades, diagnósticos y entregables técnicos conforme a las metodologías, formatos y estándares de calidad institucionales de la ESP.",
            "Atender, subsanar y corregir oportunamente las observaciones formuladas por la supervisión sobre los borradores o entregables presentados, dentro del plazo que ésta determine.",
            "Tramitar y presentar la constancia de afiliación activa al Sistema General de Seguridad Social Integral (Salud, Pensión y ARL) con anterioridad a la fecha del acta de inicio.",
            "Participar en las capacitaciones o inducciones de Seguridad y Salud en el Trabajo (SG-SST) y acatar los protocolos de prevención de riesgos laborales y ambientales de la entidad.",
            "Asistir puntualmente a los comités técnicos y mesas de trabajo convocadas por la supervisión para la revisión y seguimiento de los avances contractuales.",
            "Constituir y presentar oportunamente para aprobación de la ESP las pólizas de garantía requeridas, manteniéndolas vigentes durante todo el plazo de ejecución y su liquidación.",
            "Obtener el paz y salvo técnico, administrativo y documental de la supervisión como requisito previo e indispensable para el trámite de liquidación final del contrato."
        ]
        default_oblig_empresa = [
            "Designar al Supervisor del contrato para que ejerza el control, seguimiento, vigilancia y verificación técnica y administrativa del cumplimiento del objeto pactado.",
            "Facilitar al contratista el acceso a la información, documentos, dependencias e insumos estrictamente necesarios para el cabal desarrollo de las actividades contratadas.",
            "Pagar oportunamente el valor de los honorarios o compensación económica pactada, previo cumplimiento de los requisitos legales, aprobación del informe de actividades y verificación de aportes a la seguridad social (PILA).",
            "Revisar oportunamente los informes técnicos, entregables y cuentas de cobro o facturas presentadas por el contratista y expedir las certificaciones de cumplimiento dentro de los términos establecidos.",
            "Coordinar y atender las reuniones periódicas de seguimiento y comités técnicos programados para evaluar el avance y calidad de los servicios contratados.",
            "Respetar la autonomía técnica, administrativa y directiva del contratista en la ejecución del objeto contractual, absteniéndose de impartir órdenes que impliquen subordinación laboral.",
            "Suscribir oportunamente en debida forma el Acta de Inicio y el Acta de Liquidación Final del contrato una vez culminadas las obligaciones y verificado el paz y salvo integral."
        ]

    # Enriquecer o generar las obligaciones del contratista con el generador estructurado de la ESPY
    from app.utils.obligaciones_builder import build_obligaciones_contratista

    # Si vienen vacías o con una sola línea escueta, utilizar build_obligaciones_contratista
    if not oblig_minuta or len(oblig_minuta) <= 2 or not oblig_ep or len(oblig_ep) <= 2:
        propuesta_items = []
        if getattr(contrato, "objetivos_especificos", None):
            propuesta_items = [str(x) for x in contrato.objetivos_especificos]
        generated_oblig = build_obligaciones_contratista(
            objeto=contrato.objeto or "",
            tipologia=tipo_str,
            items_propuesta=propuesta_items or (oblig_minuta if len(oblig_minuta) > 1 else None),
            contexto_adicional=contrato.justificacion_necesidad or contrato.objeto or ""
        )
        if not oblig_minuta or len(oblig_minuta) <= 2:
            oblig_minuta = generated_oblig["obligaciones_minuta"]
        if not oblig_ep or len(oblig_ep) <= 2:
            oblig_ep = generated_oblig["obligaciones_estudio_previo"]
    elif len(oblig_minuta) <= 6:
        # Preservar las obligaciones específicas existentes y anexar las cláusulas generales de blindaje
        combined = list(oblig_minuta)
        for gen_ob in default_oblig_minuta:
            is_dup = False
            for existing in combined:
                for kw in ["seguridad social", "sg-sst", "confidencialidad", "habeas data", "supervisor", "indemne", "anticorrupción", "derechos patrimoniales", "acta de liquidación", "autonomía técnica"]:
                    if kw in gen_ob.lower() and kw in existing.lower():
                        is_dup = True
                        break
                if is_dup:
                    break
            if not is_dup and gen_ob not in combined:
                combined.append(gen_ob)
        oblig_minuta = combined

    if len(oblig_ep) <= 6:
        combined_ep = list(oblig_ep)
        for gen_ep in default_oblig_ep:
            is_dup = False
            for existing in combined_ep:
                for kw in ["idoneidad", "cronograma", "medios técnicos", "formatos y estándares", "subsanar", "seguridad social", "sg-sst", "comités técnicos", "pólizas", "paz y salvo"]:
                    if kw in gen_ep.lower() and kw in existing.lower():
                        is_dup = True
                        break
                if is_dup:
                    break
            if not is_dup and gen_ep not in combined_ep:
                combined_ep.append(gen_ep)
        oblig_ep = combined_ep


    # Enriquecer o generar las obligaciones de la empresa con el generador dinámico de la ESPY
    from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa, build_forma_pago_clausula

    plazo_txt = f"{getattr(contrato, 'plazo_ejecucion', None) or getattr(contrato, 'plazo_meses', 1)} {getattr(getattr(contrato, 'unidad_plazo', None), 'value', str(getattr(contrato, 'unidad_plazo', 'meses') or 'meses')).lower()}"
    p_persona = "JURIDICA" if (getattr(getattr(contrato, "contratista", None), "tipo_persona", None) and str(getattr(getattr(contrato, "contratista", None), "tipo_persona", "")).upper() in ["JURIDICA", "JURÍDICA", "NIT"]) else "NATURAL"

    # Generar obligaciones de la empresa dinámicas
    dinamic_oblig_empresa = build_obligaciones_empresa(
        objeto=contrato.objeto or "",
        tipologia=tipo_str,
        plazo_str=plazo_txt,
        plazo_val=getattr(contrato, "plazo_ejecucion", None) or getattr(contrato, "plazo_meses", None),
        unidad_plazo=getattr(getattr(contrato, "unidad_plazo", None), "value", str(getattr(contrato, "unidad_plazo", "meses"))),
        tipo_persona=p_persona,
        obligaciones_contratista=oblig_minuta or oblig_ep,
        contexto_adicional=contrato.justificacion_necesidad or contrato.objeto or ""
    )

    if not oblig_empresa or len(oblig_empresa) <= 3:
        oblig_empresa = list(dinamic_oblig_empresa)
    else:
        # Si venían obligaciones legacy con "plataformas o sistemas" en mantenimiento o "honorarios" indebidos
        t_chk_emp = " ".join(oblig_empresa).lower()
        if "mantenimiento" in (contrato.objeto or "").lower() and "plataformas" in t_chk_emp:
            oblig_empresa = list(dinamic_oblig_empresa)
        elif "honorarios" in t_chk_emp and any(k in (contrato.objeto or "").lower() for k in ["mantenimiento", "todo costo", "obra", "suministro"]):
            oblig_empresa = list(dinamic_oblig_empresa)
        elif "informes mensuales" in t_chk_emp and ("día" in plazo_txt or "dia" in plazo_txt or "15" in plazo_txt or "20" in plazo_txt or "30" in plazo_txt):
            oblig_empresa = list(dinamic_oblig_empresa)
        elif is_gps_contract and any("herramientas a intervenir" in o.lower() for o in oblig_empresa):
            oblig_empresa = list(dinamic_oblig_empresa)

    # Persistir en el modelo contrato si fueron regeneradas o depuradas
    try:
        contrato.obligaciones_minuta = list(oblig_minuta)
        contrato.obligaciones_estudio_previo = list(oblig_ep)
        contrato.obligaciones_empresa = list(oblig_empresa)
    except Exception:
        pass

    # Marco Jurídico Especializado por tipología contractual (Ley 142/1994)
    tipo_upper = str(getattr(getattr(contrato, "tipologia", None), "value", str(getattr(contrato, "tipologia", "PRESTACION_SERVICIOS") or "PRESTACION_SERVICIOS"))).upper()
    mj = getattr(contrato, "marco_juridico", None)
    if mj and str(mj).strip():
        marco_jur = str(mj).strip()
    elif "OBRA" in tipo_upper:
        marco_jur = (
            "El presente Contrato de Obra se rige por las normas del Derecho Privado aplicables a las Empresas de Servicios Públicos (Art. 31, Ley 142 de 1994) "
            "y los principios constitucionales de la función administrativa y la gestión fiscal (Arts. 209 y 267 C.P.). En lo pertinente a la confección de obra material, "
            "se aplican los Artículos 2053 a 2062 del Código Civil Colombiano, la garantía legal de estabilidad decenal (Art. 2060 num. 3 C.C.), el Reglamento Técnico "
            "del Sector de Agua Potable y Saneamiento Básico RAS (Resolución 0330 de 2017 MVCT), las normas sismorresistentes NSR-10, el Sistema de Gestión de Seguridad "
            "y Salud en el Trabajo SG-SST (Decreto 1072 de 2015, Res. 0312/2019, Res. 4272/2021), la normatividad ambiental (Decreto 1076 de 2015, Res. 1257 de 2021 para RCD) "
            "y el régimen tributario de AIU (Arts. 462-1 y 468-3 del Estatuto Tributario)."
        )
    elif "SUMINISTRO" in tipo_upper:
        marco_jur = (
            "El presente Contrato de Suministro se rige por las normas del Derecho Privado y Comercial aplicables a las Empresas de Servicios Públicos (Art. 31, Ley 142 de 1994) "
            "y los principios constitucionales de la función administrativa y gestión fiscal (Arts. 209 y 267 C.P.). Su régimen especial mercantil corresponde a los Artículos 968 "
            "a 980 del Código de Comercio (contrato de suministro) y normas de la compraventa mercantil (Arts. 905 y ss. C.Co.), con obligación de saneamiento por vicios ocultos "
            "(Art. 934 C.Co.), control de calidad y especificaciones fisicoquímicas de insumos para agua potable (Decreto 1575 de 2007, Resolución 2115 de 2007), Sistema Globalmente "
            "Armonizado SGA (Decreto 1496 de 2018 para fichas de seguridad MSDS) y entrega DDP en el Almacén General de la entidad."
        )
    else:
        marco_jur = (
            "El presente Contrato de Prestación de Servicios se rige por las normas del Derecho Privado aplicables a las Empresas de Servicios Públicos (Art. 31, Ley 142 de 1994) "
            "y los principios constitucionales de la función administrativa y gestión fiscal (Arts. 209 y 267 C.P.). En lo sustancial, se fundamenta en el contrato civil de arrendamiento "
            "de servicios inmateriales (Arts. 2053 a 2069 del Código Civil), con estricta observancia del Artículo 23 del Código Sustantivo del Trabajo (CST) y la jurisprudencia de la "
            "Corte Constitucional (Sentencias C-614/09 y C-171/12) y del Consejo de Estado sobre autonomía técnica e inexistencia de subordinación laboral. El contratista asume la "
            "obligación legal de afiliación y cotización al Sistema de Seguridad Social Integral (Salud, Pensión y ARL) como independiente conforme a la Ley 100 de 1993, Decreto 1072 de 2015 "
            "y Decreto 1273 de 2018, sobre un IBC no inferior al 40% del valor mensualizado del contrato."
        )

    mod_str = getattr(getattr(contrato, "modalidad_seleccion", None), "value", str(getattr(contrato, "modalidad_seleccion", "CONTRATACION_DIRECTA") or "CONTRATACION_DIRECTA")).replace("_", " ").title()
    
    # Mapeo oficial y legal de Tipología Contractual (Ley 142 de 1994)
    tipo_denominacion_map = {
        "PRESTACION_SERVICIOS": "PRESTACIÓN DE SERVICIOS",
        "PRESTACION_DE_SERVICIOS": "PRESTACIÓN DE SERVICIOS",
        "PRESTACION_SERVICIO": "PRESTACIÓN DE SERVICIOS",
        "PRESTACION_DE_SERVICIO": "PRESTACIÓN DE SERVICIOS",
        "SERVICIOS": "PRESTACIÓN DE SERVICIOS",
        "OBRA": "OBRA",
        "CONTRATO_OBRA": "OBRA",
        "SUMINISTRO": "SUMINISTRO",
        "SUMINISTRO_BIENES": "SUMINISTRO",
        "ARRENDAMIENTO": "ARRENDAMIENTO",
        "ARRIENDO": "ARRENDAMIENTO",
        "CONSULTORIA": "CONSULTORÍA",
        "INTERVENTORIA": "INTERVENTORÍA",
    }

    meta_dict = getattr(contrato, "metadatos_agente", {}) or {}
    if not isinstance(meta_dict, dict):
        meta_dict = {}
    custom_tipo_contrato = str(meta_dict.get("tipo_contrato") or meta_dict.get("tipo_de_contrato") or "").strip()

    raw_tipologia = str(getattr(getattr(contrato, "tipologia", None), "value", getattr(contrato, "tipologia", "PRESTACION_SERVICIOS")) or "PRESTACION_SERVICIOS").upper()

    if custom_tipo_contrato:
        tipo_de_contrato_val = custom_tipo_contrato.upper()
    else:
        tipo_de_contrato_val = tipo_denominacion_map.get(raw_tipologia, raw_tipologia.replace("_", " ").upper())

    tipo_str_ctx = tipo_de_contrato_val
    est_str = getattr(getattr(contrato, "estado", None), "value", str(getattr(contrato, "estado", "ACTIVO") or "ACTIVO"))
    
    c_tipo_per = "JURIDICA" if is_juridica else "NATURAL"
    if is_juridica:
        raw_rep_nom = (getattr(c, "representante_legal_nombre", None) or meta_dict.get("representante_legal_nombre") or "").strip().upper()
        c_rep_nom = raw_rep_nom or contratista_nom
        raw_rep_doc = str(getattr(c, "representante_legal_documento", None) or meta_dict.get("representante_legal_documento") or "").strip()
        # Cédula del representante legal sin dígito de verificación
        clean_rep_doc = re.sub(r"-\d+$", "", raw_rep_doc).strip()
        if not clean_rep_doc or clean_rep_doc == raw_doc:
            clean_rep_doc = re.sub(r"[^\d\.]", "", raw_rep_doc)
        c_rep_doc = clean_rep_doc or clean_doc
        c_rep_doc_tipo_num = f"CC {c_rep_doc}" if c_rep_doc else doc_tipo_num
        el_la_rep = "la señora" if any(fn in c_rep_nom for fn in ["PAULA", "MARIA", "CAROLINA", "ANA", "CLAUDIA", "GLORIA", "LUZ", "ANDREA", "PATRICIA", "DIANA", "SANDRA", "MONICA", "ADRIANA", "MARTHA"]) else "el señor"
        contratista_presentacion = f"la {contratista_nom}, NIT {cedula_o_nit}, representada legalmente por {el_la_rep} {c_rep_nom}, identificado(a) con C.C. {c_rep_doc}"
    else:
        # Persona Natural: Obra en su propio nombre y la cédula va SIN DV
        c_rep_nom = contratista_nom
        c_rep_doc = clean_doc
        c_rep_doc_tipo_num = f"{doc_tipo} {clean_doc}"
        contratista_presentacion = f"el(la) señor(a) {contratista_nom}, identificado(a) con C.C. {clean_doc}"

    c_doc = clean_doc
    c_dir = getattr(c, "direccion", None) or "Jurisdicción de la ESP"
    c_mun = getattr(c, "municipio", None) or "Yolombó"
    c_dep = getattr(c, "departamento", None) or "Antioquia"
    c_correo = getattr(c, "correo_electronico", None) or "contacto@contratista.com"
    c_tel = getattr(c, "telefono", None) or "N/A"
    c_reg = getattr(getattr(c, "regimen_tributario", None), "value", str(getattr(c, "regimen_tributario", "No Responsable de IVA") or "No Responsable de IVA"))

    # -------------------------------------------------------------
    # Presupuesto oficial y Disponibilidad Presupuestal (CDP Ley 142/1994)
    # -------------------------------------------------------------
    cdp_num = getattr(contrato, "cdp_numero", None) or meta_dict.get("cdp_numero")
    cdp_fecha_raw = getattr(contrato, "cdp_fecha", None) or meta_dict.get("cdp_fecha")
    cdp_rubro = getattr(contrato, "cdp_rubro", None) or meta_dict.get("cdp_rubro") or ""
    cdp_rubro_nombre = meta_dict.get("cdp_rubro_nombre") or ""
    cdp_valor = meta_dict.get("cdp_valor")
    cdp_clasificadores = meta_dict.get("cdp_clasificadores") or []
    cdp_texto_completo = meta_dict.get("cdp_texto_completo") or ""

    # Si faltan datos pero el contrato tiene documentos asociados, buscar en ellos
    if (not cdp_clasificadores or not cdp_rubro_nombre or not cdp_num) and hasattr(contrato, "documentos") and contrato.documentos:
        for doc_item in contrato.documentos:
            d_extra = getattr(doc_item, "datos_extraidos_json", {}) or {}
            if isinstance(d_extra, dict):
                if not cdp_num and d_extra.get("cdp_numero"):
                    cdp_num = d_extra.get("cdp_numero")
                if not cdp_fecha_raw and d_extra.get("cdp_fecha"):
                    cdp_fecha_raw = d_extra.get("cdp_fecha")
                if not cdp_rubro and d_extra.get("cdp_rubro"):
                    cdp_rubro = d_extra.get("cdp_rubro")
                if not cdp_rubro_nombre and d_extra.get("cdp_rubro_nombre"):
                    cdp_rubro_nombre = d_extra.get("cdp_rubro_nombre")
                if not cdp_valor and d_extra.get("cdp_valor"):
                    cdp_valor = d_extra.get("cdp_valor")
                if not cdp_clasificadores and d_extra.get("cdp_clasificadores"):
                    cdp_clasificadores = d_extra.get("cdp_clasificadores")
                if not cdp_texto_completo and d_extra.get("cdp_texto_completo"):
                    cdp_texto_completo = d_extra.get("cdp_texto_completo")

    cdp_fecha_texto = format_date_spanish(cdp_fecha_raw) if cdp_fecha_raw else ""

    effective_cdp_val = cdp_valor if cdp_valor else valor_tot
    val_cdp_fmt = format_cop_currency(effective_cdp_val)

    clasif_fmt = ""
    if cdp_clasificadores:
        if isinstance(cdp_clasificadores, list):
            clasif_fmt = "; ".join(str(c).strip() for c in cdp_clasificadores if str(c).strip())
        else:
            clasif_fmt = str(cdp_clasificadores).strip()

    from app.utils.cdp_cleaner import limpiar_texto_cdp, construir_texto_cdp

    if cdp_num and str(cdp_num).strip() and str(cdp_num).strip().lower() not in ("por asignar", "sin asignar", "none"):
        if cdp_texto_completo and len(cdp_texto_completo.strip()) > 15:
            cdp_full_description = limpiar_texto_cdp(cdp_texto_completo.strip())
        else:
            rubros_list = []
            if cdp_rubro or cdp_rubro_nombre:
                rubros_list.append({"codigo": cdp_rubro, "nombre": cdp_rubro_nombre})
            cdp_full_description = construir_texto_cdp(
                numero=cdp_num,
                fecha_texto=cdp_fecha_texto,
                valor_fmt=val_cdp_fmt,
                rubros=rubros_list
            )
        # Garantía servidor: aplicar siempre limpiar_texto_cdp antes de inyectar en plantilla
        cdp_full_description = limpiar_texto_cdp(cdp_full_description)
    else:
        cdp_num = "Por asignar"
        cdp_full_description = "Por asignar (Certificado de Disponibilidad Presupuestal en trámite)"


    # Fechas formateadas en español estándar (ej: '15 de octubre de 2026')
    f_susc_val = format_date_spanish(getattr(contrato, "fecha_suscripcion", None), default="Pendiente de firma")
    f_ep_val = format_date_spanish(getattr(contrato, "fecha_estudio_previo", None) or getattr(contrato, "fecha_suscripcion", None), default="15 de enero de 2026")
    f_acta_val = format_date_spanish(getattr(contrato, "fecha_acta_inicio", None), default="Por definir")
    f_term_val = format_date_spanish(getattr(contrato, "fecha_terminacion", None), default="Por definir")
    f_gen_val = format_date_spanish(getattr(contrato, "fecha_suscripcion", None) or getattr(contrato, "fecha_estudio_previo", None), default="15 de enero de 2026")

    # Auto-corrección de inconsistencia en justificación de la necesidad:
    # Si es SUMINISTRO y la justificación guardada menciona planta de personal o contratar servicios de apoyo, regenerar de inmediato
    saved_just = getattr(contrato, "justificacion_necesidad", "") or ""
    is_sum_contract = "SUMINISTRO" in tipo_str or any(k in tipo_str for k in ["COMPRAVENTA", "BIENES"])
    is_incoherent = is_sum_contract and any(
        p in saved_just.lower() for p in ["planta de personal", "recurso humano suficiente", "contratar servicios de apoyo"]
    )
    is_generic = "Garantizar la prestación eficiente y continua de los servicios públicos bajo Ley 142/1994" in saved_just

    if not saved_just or is_incoherent or is_generic:
        justificacion_efectiva = build_descripcion_necesidad(
            contrato.objeto or "",
            tipo_str,
            contexto_adicional=saved_just or cdp_ctx or None
        )
        try:
            contrato.justificacion_necesidad = justificacion_efectiva
        except Exception:
            pass
    else:
        justificacion_efectiva = saved_just

    context = {
        # Identificación del proceso contractual
        "NUMERO_CONTRATO": getattr(contrato, "numero_contrato", None) or "ESP-2026-XXX",
        "CONTRATO": getattr(contrato, "numero_contrato", None) or "ESP-2026-XXX",
        "NUMERO_DE_CONTRATO": getattr(contrato, "numero_contrato", None) or "ESP-2026-XXX",
        "VIGENCIA": str(getattr(contrato, "vigencia", None) or datetime.now().year),
        "MODALIDAD": mod_str,
        "TIPOLOGIA": tipo_de_contrato_val,
        "TIPO_DE_CONTRATO": tipo_de_contrato_val,
        "TIPO DE CONTRATO": tipo_de_contrato_val,
        "TIPO_DEL_CONTRATO": tipo_de_contrato_val,
        "TIPO DEL CONTRATO": tipo_de_contrato_val,
        "TIPO_CONTRATO": tipo_de_contrato_val,
        "TIPO CONTRATO": tipo_de_contrato_val,
        "TIPOLOGIA_CONTRACTUAL": tipo_de_contrato_val,
        "TIPOLOGIA CONTRACTUAL": tipo_de_contrato_val,
        "TIPO": tipo_de_contrato_val,
        "ESTADO": est_str,
        
        # Datos del Contratista (con sinónimos frecuentes en plantillas)
        "CONTRATISTA": contratista_nom,
        "CONTRATISTA_NOMBRE": contratista_nom,
        "NOMBRE_CONTRATISTA": contratista_nom,
        "NOMBRE": contratista_nom,
        "RAZON_SOCIAL": contratista_nom,
        "CONTRATISTA_DOCUMENTO": doc_tipo_num,
        "DOCUMENTO": doc_tipo_num,
        "NIT": cedula_o_nit,
        "CEDULA": c_doc,
        "CC": c_doc,
        "NUMERO_DOCUMENTO": c_doc,
        "CONTRATISTA_TIPO_PERSONA": c_tipo_per,
        "TIPO_PERSONA": c_tipo_per,
        "REPRESENTANTE_LEGAL": c_rep_nom,
        "REPRESENTANTE LEGAL": c_rep_nom,
        "NOMBRE_REPRESENTANTE_LEGAL": c_rep_nom,
        "NOMBRE REPRESENTANTE LEGAL": c_rep_nom,
        "REPRESENTANTE": c_rep_nom,
        "REPRESENTANTE_DOC": c_rep_doc,
        "DOCUMENTO_REPRESENTANTE": c_rep_doc,
        "DOCUMENTO REPRESENTANTE": c_rep_doc,
        "DOCUMENTO_REPRESENTANTE_LEGAL": c_rep_doc,
        "DOCUMENTO REPRESENTANTE LEGAL": c_rep_doc,
        "NUMERO_DOCUMENTO_REPRESENTANTE_LEGAL": c_rep_doc,
        "NUMERO DOCUMENTO REPRESENTANTE LEGAL": c_rep_doc,
        "NUMERO_DOCUMENTO_REPRESENTANTE": c_rep_doc,
        "NUMERO DOCUMENTO REPRESENTANTE": c_rep_doc,
        "CEDULA_REPRESENTANTE_LEGAL": c_rep_doc,
        "CEDULA REPRESENTANTE LEGAL": c_rep_doc,
        "CEDULA_REPRESENTANTE": c_rep_doc,
        "CEDULA REPRESENTANTE": c_rep_doc,
        "CC_REPRESENTANTE_LEGAL": c_rep_doc,
        "CC REPRESENTANTE LEGAL": c_rep_doc,
        "DOCUMENTO_REPRESENTANTE_LEGAL_COMPLETO": c_rep_doc_tipo_num,
        "DOCUMENTO REPRESENTANTE LEGAL COMPLETO": c_rep_doc_tipo_num,
        "REPRESENTANTE_LEGAL_DOCUMENTO": c_rep_doc,
        "REPRESENTANTE LEGAL DOCUMENTO": c_rep_doc,
        "REPRESENTANTE_LEGAL_COMPLETO": f"{c_rep_nom}, identificado(a) con C.C. No. {c_rep_doc}" if is_juridica and c_rep_doc else c_rep_nom,
        "REPRESENTANTE LEGAL COMPLETO": f"{c_rep_nom}, identificado(a) con C.C. No. {c_rep_doc}" if is_juridica and c_rep_doc else c_rep_nom,
        "CONTRATISTA_PRESENTACION": contratista_presentacion,
        "CONTRATISTA_Y_REPRESENTANTE": contratista_presentacion,
        "CONTRATISTA_DIRECCION": c_dir,
        "DIRECCION": c_dir,
        "DOMICILIO": c_dir,
        "CONTRATISTA_MUNICIPIO": f"{c_mun}, {c_dep}" if c_dep else c_mun,
        "MUNICIPIO": c_mun,
        "CIUDAD": c_mun,
        "DEPARTAMENTO": c_dep,
        "CONTRATISTA_CORREO": c_correo,
        "CORREO": c_correo,
        "EMAIL": c_correo,
        "CONTRATISTA_TELEFONO": c_tel,
        "TELEFONO": c_tel,
        "CELULAR": c_tel,
        "REGIMEN_TRIBUTARIO": c_reg,

        # Objeto y justificación normativa
        "OBJETO": (contrato.objeto or "").upper(),
        "OBJETO_CONTRACTUAL": (contrato.objeto or "").upper(),
        "OBJETO_DEL_CONTRATO": (contrato.objeto or "").upper(),
        "JUSTIFICACION": justificacion_efectiva,
        "JUSTIFICACION_NECESIDAD": justificacion_efectiva,
        "DESCRIPCION_DE_LA_NECESIDAD_A_SATISFACER": justificacion_efectiva,
        "DESCRIPCION_NECESIDAD_A_SATISFACER": justificacion_efectiva,
        "DESCRIPCION_DE_LA_NECESIDAD": justificacion_efectiva,
        "DESCRIPCION_NECESIDAD": justificacion_efectiva,
        "NECESIDAD_A_SATISFACER": justificacion_efectiva,
        "NECESIDAD": justificacion_efectiva,

        
        # Marco Jurídico Especializado por tipología (Servicios, Obra, Suministro)
        "MARCO_JURIDICO": marco_jur,
        "MARCO JURIDICO": marco_jur,
        "MARCO_JURÍDICO": marco_jur,
        "MARCO JURÍDICO": marco_jur,
        "FUNDAMENTO_JURIDICO": marco_jur,
        "FUNDAMENTO JURIDICO": marco_jur,
        "FUNDAMENTO_JURÍDICO": marco_jur,
        "FUNDAMENTO JURÍDICO": marco_jur,
        "REGIMEN_JURIDICO": marco_jur,
        "REGIMEN JURIDICO": marco_jur,
        "REGIMEN_JURÍDICO": marco_jur,
        "REGIMEN JURÍDICO": marco_jur,
        "MARCO_LEGAL": marco_jur,
        "MARCO LEGAL": marco_jur,
        
        # Objetivos del Contrato (Múltiples sinónimos con y sin espacios, tildes y singulares/plurales)
        "OBJETIVO_GENERAL": obj_general,
        "OBJETIVOS_GENERAL": obj_general,
        "OBJETIVO GENERAL": obj_general,
        "OBJETIVOS GENERAL": obj_general,
        "OBJETIVO_GENERAL_DEL_CONTRATO": obj_general,
        "OBJETIVO_GENERAL_CONTRATO": obj_general,
        "OBJETIVOS_ESPECIFICOS": obj_especificos,
        "OBJETIVOS ESPECIFICOS": obj_especificos,
        "OBJETIVOS_ESPECÍFICOS": obj_especificos,
        "OBJETIVOS ESPECÍFICOS": obj_especificos,
        "OBJETIVO_ESPECIFICO": obj_especificos,
        "OBJETIVO ESPECIFICO": obj_especificos,
        "OBJETIVO_ESPECÍFICO": obj_especificos,
        "OBJETIVO ESPECÍFICO": obj_especificos,
        "OBJETIVOS": obj_especificos,

        # Obligaciones del Contratista
        "OBLIGACIONES": oblig_minuta or oblig_ep,
        "OBLIGACIONES_DEL_CONTRATISTA": oblig_minuta or oblig_ep,
        "OBLIGACIONES DEL CONTRATISTA": oblig_minuta or oblig_ep,
        "OBLIGACIONES_CONTRATISTA": oblig_minuta or oblig_ep,
        "OBLIGACIONES CONTRATISTA": oblig_minuta or oblig_ep,
        "OBLIGACIONES_MINUTA": oblig_minuta,
        "OBLIGACIONES MINUTA": oblig_minuta,
        "OBLIGACIONES_ESTUDIO_PREVIO": oblig_ep,
        "OBLIGACIONES ESTUDIO PREVIO": oblig_ep,
        "OBLIGACIONES_ESPECIFICAS": oblig_minuta or oblig_ep,
        "OBLIGACIONES ESPECIFICAS": oblig_minuta or oblig_ep,
        "OBLIGACIONES_ESPECÍFICAS": oblig_minuta or oblig_ep,
        "OBLIGACIONES ESPECÍFICAS": oblig_minuta or oblig_ep,

        # Obligaciones de la Empresa (LA EMPRESA / ESPY S.A. E.S.P.) adaptadas a la tipología
        "OBLIGACIONES_EMPRESA": oblig_empresa,
        "OBLIGACIONES EMPRESA": oblig_empresa,
        "OBLIGACIONES_DE_LA_EMPRESA": oblig_empresa,
        "OBLIGACIONES DE LA EMPRESA": oblig_empresa,
        "OBLIGACIONES_ENTIDAD": oblig_empresa,
        "OBLIGACIONES ENTIDAD": oblig_empresa,
        "OBLIGACIONES_DE_LA_ENTIDAD": oblig_empresa,
        "OBLIGACIONES DE LA ENTIDAD": oblig_empresa,
        "OBLIGACIONES_ESP": oblig_empresa,
        "OBLIGACIONES ESP": oblig_empresa,
        "OBLIGACIONES_DE_LA_ESP": oblig_empresa,
        "OBLIGACIONES DE LA ESP": oblig_empresa,

        # Aspectos económicos y de plazo
        "VALOR": valor_cop,
        "VALOR_NUMEROS": valor_cop,
        "VALOR_COP": valor_cop,
        "VALOR_TOTAL": valor_cop,
        "VALOR_TOTAL_NUMEROS": valor_cop,
        "VALOR_INICIAL": valor_ini_cop,
        "VALOR_INICIAL_NUMEROS": valor_ini_cop,
        "PRESUPUESTO": valor_cop,
        "PRESUPUESTO_OFICIAL": valor_cop,
        "VALOR_LETRAS": valor_letras,
        "VALOR_EN_LETRAS": valor_letras,
        "PLAZO": f"{getattr(contrato, 'plazo_ejecucion', None) or getattr(contrato, 'plazo_meses', 1)} {getattr(getattr(contrato, 'unidad_plazo', None), 'value', str(getattr(contrato, 'unidad_plazo', 'meses') or 'meses')).lower()}",
        "PLAZO_EJECUCION": f"{getattr(contrato, 'plazo_ejecucion', None) or getattr(contrato, 'plazo_meses', 1)} {getattr(getattr(contrato, 'unidad_plazo', None), 'value', str(getattr(contrato, 'unidad_plazo', 'meses') or 'meses')).lower()}",
        "DURACION": f"{getattr(contrato, 'plazo_ejecucion', None) or getattr(contrato, 'plazo_meses', 1)} {getattr(getattr(contrato, 'unidad_plazo', None), 'value', str(getattr(contrato, 'unidad_plazo', 'meses') or 'meses')).lower()}",
        "LUGAR_EJECUCION": getattr(contrato, "lugar_ejecucion", None) or "Instalaciones de la ESP",
        "FORMA_PAGO": build_forma_pago_clausula(
            tipologia=tipo_str,
            objeto=contrato.objeto or "",
            plazo_str=plazo_txt,
            plazo_val=getattr(contrato, "plazo_ejecucion", None) or getattr(contrato, "plazo_meses", None),
            unidad_plazo=getattr(getattr(contrato, "unidad_plazo", None), "value", str(getattr(contrato, "unidad_plazo", "meses"))),
            tipo_persona=p_persona,
            forma_pago_custom=getattr(contrato, "forma_pago", None)
        ),
        "PAGO": build_forma_pago_clausula(
            tipologia=tipo_str,
            objeto=contrato.objeto or "",
            plazo_str=plazo_txt,
            plazo_val=getattr(contrato, "plazo_ejecucion", None) or getattr(contrato, "plazo_meses", None),
            unidad_plazo=getattr(getattr(contrato, "unidad_plazo", None), "value", str(getattr(contrato, "unidad_plazo", "meses"))),
            tipo_persona=p_persona,
            forma_pago_custom=getattr(contrato, "forma_pago", None)
        ),

        # Presupuesto oficial y Disponibilidad Presupuestal (CDP Ley 142/1994)
        "CDP": cdp_full_description,
        "CDP_COMPLETO": cdp_full_description,
        "CDP COMPLETO": cdp_full_description,
        "CDP_DETALLE": cdp_full_description,
        "CDP DETALLE": cdp_full_description,
        "INFORMACION_CDP": cdp_full_description,
        "INFORMACION CDP": cdp_full_description,
        "INFORMACIÓN_CDP": cdp_full_description,
        "INFORMACIÓN CDP": cdp_full_description,
        "CDP_NUMERO": str(cdp_num),
        "CDP NUMERO": str(cdp_num),
        "NUMERO_CDP": str(cdp_num),
        "NUMERO CDP": str(cdp_num),
        "CDP_FECHA": cdp_fecha_texto or "Pendiente de expedición",
        "CDP FECHA": cdp_fecha_texto or "Pendiente de expedición",
        "FECHA_CDP": cdp_fecha_texto or "Pendiente de expedición",
        "FECHA CDP": cdp_fecha_texto or "Pendiente de expedición",
        "CDP_VALOR": val_cdp_fmt,
        "CDP VALOR": val_cdp_fmt,
        "VALOR_CDP": val_cdp_fmt,
        "VALOR CDP": val_cdp_fmt,
        "VALOR_RESPALDO_CDP": val_cdp_fmt,
        "VALOR RESPALDO CDP": val_cdp_fmt,
        "CDP_RUBRO": cdp_rubro or "Rubro Operativo Institucional",
        "CDP RUBRO": cdp_rubro or "Rubro Operativo Institucional",
        "RUBRO_CDP": cdp_rubro or "Rubro Operativo Institucional",
        "RUBRO CDP": cdp_rubro or "Rubro Operativo Institucional",
        "CDP_RUBRO_NOMBRE": cdp_rubro_nombre or "",
        "CDP RUBRO NOMBRE": cdp_rubro_nombre or "",
        "RUBRO_NOMBRE_CDP": cdp_rubro_nombre or "",
        "CDP_CLASIFICADORES": clasif_fmt or "Conforme a clasificadores CCPET",
        "CDP CLASIFICADORES": clasif_fmt or "Conforme a clasificadores CCPET",
        "CLASIFICADORES_CDP": clasif_fmt or "Conforme a clasificadores CCPET",
        "CLASIFICADORES": clasif_fmt or "Conforme a clasificadores CCPET",
        "RP": getattr(contrato, "rp_numero", None) or "Por asignar",
        "RP_NUMERO": getattr(contrato, "rp_numero", None) or "Por asignar",
        "NUMERO_RP": getattr(contrato, "rp_numero", None) or "Por asignar",

        # Supervisor institucional
        "SUPERVISOR": supervisor_nom,
        "SUPERVISOR_NOMBRE": supervisor_nom,
        "NOMBRE_SUPERVISOR": supervisor_nom,
        "SUPERVISOR_CARGO": supervisor_car,
        "CARGO_SUPERVISOR": supervisor_car,
        "SUPERVISOR_DOC": supervisor_doc_full,
        "DOCUMENTO_SUPERVISOR": supervisor_doc_full,
        "SUPERVISOR_DOCUMENTO": supervisor_doc_full,
        "CEDULA_SUPERVISOR": supervisor_num,
        "SUPERVISOR_TIPO_DOC": supervisor_tipo,
        "SUPERVISOR_DEPENDENCIA": supervisor_dep,
        "DEPENDENCIA": supervisor_dep,

        # Información Bancaria del Contratista
        "BANCO": (getattr(c, "banco_nombre", None) or "Por definir") if c else "Por definir",
        "BANCO_NOMBRE": (getattr(c, "banco_nombre", None) or "Por definir") if c else "Por definir",
        "ENTIDAD_BANCARIA": (getattr(c, "banco_nombre", None) or "Por definir") if c else "Por definir",
        "BANCO_TIPO_CUENTA": (getattr(c, "banco_tipo_cuenta", None) or "Ahorros") if c else "Ahorros",
        "TIPO_CUENTA": (getattr(c, "banco_tipo_cuenta", None) or "Ahorros") if c else "Ahorros",
        "BANCO_NUMERO_CUENTA": (getattr(c, "banco_numero_cuenta", None) or "Por definir") if c else "Por definir",
        "NUMERO_CUENTA": (getattr(c, "banco_numero_cuenta", None) or "Por definir") if c else "Por definir",
        "CUENTA_BANCARIA": f"Cuenta de {getattr(c, 'banco_tipo_cuenta', 'Ahorros')} No. {getattr(c, 'banco_numero_cuenta', '')} de {getattr(c, 'banco_nombre', '')}" if (c and getattr(c, "banco_numero_cuenta", None)) else "Por definir",

        # Fechas formateadas en español estándar (ej: '15 de octubre de 2026')
        "FECHA": f_gen_val,
        "FECHA_ESTUDIO_PREVIO": f_ep_val,
        "FECHA_SUSCRIPCION": f_susc_val,
        "FECHA_ACTA_INICIO": f_acta_val,
        "FECHA_TERMINACION": f_term_val,
        
        # Sinónimos y variaciones de Fecha de Inicio
        "FECHA_INICIO": f_acta_val,
        "FECHA DE INICIO": f_acta_val,
        "FECHA_ACTA": f_acta_val,
        "FECHA ACTA": f_acta_val,
        "FECHA_DE_ACTA_DE_INICIO": f_acta_val,
        "FECHA DE ACTA DE INICIO": f_acta_val,

        # Sinónimos y variaciones de Fecha de Terminación
        "FECHA_TERMINACION_ESTIMADA": f_term_val,
        "FECHA TERMINACION ESTIMADA": f_term_val,
        "FECHA_TERMINACIÓN_ESTIMADA": f_term_val,
        "FECHA TERMINACIÓN ESTIMADA": f_term_val,
        "FECHA_TERMINACIÓN": f_term_val,
        "FECHA TERMINACIÓN": f_term_val,
        "FECHA TERMINACION": f_term_val,
        "FECHA_FINAL": f_term_val,
        "FECHA FINAL": f_term_val,
        "FECHA_FIN": f_term_val,
        "FECHA FIN": f_term_val,

        # Sinónimos y variaciones de Fecha de Suscripción / Firma
        "FECHA_FIRMA": f_susc_val,
        "FECHA FIRMA": f_susc_val,
        "FECHA_DE_FIRMA": f_susc_val,
        "FECHA DE FIRMA": f_susc_val,
        "FECHA_DE_SUSCRIPCION": f_susc_val,
        "FECHA DE SUSCRIPCION": f_susc_val,
        "FECHA_SUSCRIPCIÓN": f_susc_val,
        "FECHA SUSCRIPCIÓN": f_susc_val,
    }

    try:
        from app.services.agents.addition_agent import addition_agent
        f_susc = getattr(contrato, "fecha_suscripcion", None) or datetime.now().date()
        f_info = addition_agent.format_legal_date(f_susc)
        context.update({
            "DIA_LETRAS": f_info["dia_letras"],
            "DIA LETRAS": f_info["dia_letras"],
            "DIA_EN_LETRAS": f_info["dia_letras"],
            "DIA EN LETRAS": f_info["dia_letras"],
            "DIA_NUMEROS": f_info["dia_numeros"],
            "DIA NUMEROS": f_info["dia_numeros"],
            "DIA_EN_NUMEROS": f_info["dia_numeros"],
            "DIA EN NUMEROS": f_info["dia_numeros"],
            "DIA": f_info["dia_numeros"],
            "MES": f_info["mes"],
            "MES_NOMBRE": f_info["mes"],
            "MES NOMBRE": f_info["mes"],
            "MES_EN_LETRAS": f_info["mes"],
            "MES EN LETRAS": f_info["mes"],
            "AÑO": f_info["ano"],
            "ANO": f_info["ano"],
            "ANIO": f_info["ano"],
            "AÑO_NUMERO": f_info["ano"],
            "ANO_NUMERO": f_info["ano"],
            "FECHA_FIRMA": f_info["texto_completo"],
            "FECHA_CONSTANCIA": f_info["texto_completo"],
        })
    except Exception as e_f:
        logger.warning(f"Aviso formateando fecha en build_contract_context: {e_f}")

    return context

def create_default_templates_if_missing():
    """Genera las plantillas base de Word con membrete corporativo y diseño institucional para ESP si no existen."""
    settings.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    settings.CUSTOM_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    # Migrar automáticamente plantillas personalizadas legacy a la modalidad de servicios si aún no existen
    try:
        legacy_ep_custom = settings.CUSTOM_TEMPLATES_DIR / "custom_plantilla_estudio_previo.docx"
        target_ep_serv = settings.CUSTOM_TEMPLATES_DIR / "custom_plantilla_estudio_previo_servicios.docx"
        if legacy_ep_custom.exists() and not target_ep_serv.exists() and legacy_ep_custom.stat().st_size > 0:
            shutil.copy2(legacy_ep_custom, target_ep_serv)
            logger.info("Migrada plantilla personalizada legacy Estudio Previo -> custom_plantilla_estudio_previo_servicios.docx")

        legacy_min_custom = settings.CUSTOM_TEMPLATES_DIR / "custom_plantilla_minuta_contrato.docx"
        target_min_serv = settings.CUSTOM_TEMPLATES_DIR / "custom_plantilla_minuta_servicios.docx"
        if legacy_min_custom.exists() and not target_min_serv.exists() and legacy_min_custom.stat().st_size > 0:
            shutil.copy2(legacy_min_custom, target_min_serv)
            logger.info("Migrada plantilla personalizada legacy Minuta Contrato -> custom_plantilla_minuta_servicios.docx")
    except Exception as e_mig:
        logger.warning(f"Aviso en migración de plantillas personalizadas: {e_mig}")
    
    # 1. Plantilla Estudio Previo - Prestación de Servicios
    path_ep_serv = settings.TEMPLATES_DIR / "plantilla_estudio_previo_servicios.docx"
    if not path_ep_serv.exists():
        doc_ep = docx.Document()
        _style_corporate_doc(doc_ep, "ESTUDIO PREVIO DE CONVENIENCIA Y OPORTUNIDAD\nCONTRATO DE PRESTACIÓN DE SERVICIOS")
        
        table = doc_ep.add_table(rows=6, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        rows_data = [
            ("Número de Contrato / Proceso:", "{{NUMERO_CONTRATO}}"),
            ("Modalidad de Selección:", "{{MODALIDAD}}"),
            ("Tipología Contractual:", "Prestación de Servicios (Apoyo a la Gestión / Profesionales)"),
            ("Presupuesto Oficial Estimado:", "{{VALOR_NUMEROS}} ({{VALOR_LETRAS}})"),
            ("Plazo Estimado de Ejecución:", "{{PLAZO}}"),
            ("Dependencia Solicitante:", "{{SUPERVISOR_DEPENDENCIA}}")
        ]
        for i, (k, v) in enumerate(rows_data):
            cell_k = table.cell(i, 0)
            cell_v = table.cell(i, 1)
            cell_k.text = k
            cell_v.text = v
            cell_k.paragraphs[0].runs[0].bold = True
            cell_k.paragraphs[0].runs[0].font.size = Pt(9.5)
            cell_v.paragraphs[0].runs[0].font.size = Pt(9.5)
            _set_cell_background(cell_k, "F0F4F8")

        doc_ep.add_heading("1. DESCRIPCIÓN DE LA NECESIDAD A SATISFACER (LEY 142/1994 Y SERVICIOS PÚBLICOS)", level=1)
        doc_ep.add_paragraph("{{DESCRIPCION_DE_LA_NECESIDAD_A_SATISFACER}}")
        doc_ep.add_heading("1.1. MARCO JURÍDICO Y RÉGIMEN LEGAL APLICABLE", level=2)
        doc_ep.add_paragraph("{{MARCO_JURIDICO}}")

        doc_ep.add_heading("2. OBJETO CONTRACTUAL A CONTRATAR", level=1)
        doc_ep.add_paragraph("{{OBJETO}}")

        doc_ep.add_heading("3. OBJETIVOS DEL CONTRATO", level=1)
        p_obj_gen = doc_ep.add_paragraph()
        p_obj_gen.add_run("Objetivo General: ").bold = True
        p_obj_gen.add_run("{{OBJETIVO_GENERAL}}")
        doc_ep.add_paragraph("Objetivos Específicos:")
        doc_ep.add_paragraph("{{OBJETIVOS_ESPECIFICOS}}")

        doc_ep.add_heading("4. OBLIGACIONES TÉCNICAS Y OPERATIVAS EXIGIDAS AL CONTRATISTA", level=1)
        doc_ep.add_paragraph("{{OBLIGACIONES_ESTUDIO_PREVIO}}")

        doc_ep.add_heading("5. LUGAR DE EJECUCIÓN Y FORMA DE PAGO", level=1)
        doc_ep.add_paragraph("Lugar de Ejecución: {{LUGAR_EJECUCION}}")
        doc_ep.add_paragraph("Condiciones de Pago: {{FORMA_PAGO}} (Abonos periódicos contra informe de actividades aprobado y verificación de aportes a Seguridad Social Integral y ARL).")

        doc_ep.add_heading("6. DESIGNACIÓN DE SUPERVISIÓN TÉCNICA", level=1)
        doc_ep.add_paragraph("La supervisión del contrato será ejercida por: {{SUPERVISOR_NOMBRE}}, en calidad de {{SUPERVISOR_CARGO}} de la {{SUPERVISOR_DEPENDENCIA}}.")

        doc_ep.add_paragraph("\n\n_____________________________________\n{{SUPERVISOR_NOMBRE}}\n{{SUPERVISOR_CARGO}}\nResponsable Estudio Previo")
        doc_ep.save(str(path_ep_serv))
        logger.info(f"Plantilla base de Estudio Previo Servicios creada en: {path_ep_serv}")

    # 2. Plantilla Estudio Previo - Suministro
    path_ep_sum = settings.TEMPLATES_DIR / "plantilla_estudio_previo_suministro.docx"
    if not path_ep_sum.exists():
        doc_sum = docx.Document()
        _style_corporate_doc(doc_sum, "ESTUDIO PREVIO DE CONVENIENCIA Y OPORTUNIDAD\nCONTRATO DE SUMINISTRO")
        
        table = doc_sum.add_table(rows=6, cols=2)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        rows_data = [
            ("Número de Contrato / Proceso:", "{{NUMERO_CONTRATO}}"),
            ("Modalidad de Selección:", "{{MODALIDAD}}"),
            ("Tipología Contractual:", "Suministro de Bienes, Materiales e Insumos"),
            ("Presupuesto Oficial Estimado:", "{{VALOR_NUMEROS}} ({{VALOR_LETRAS}})"),
            ("Plazo de Entrega Pactado:", "{{PLAZO}}"),
            ("Dependencia Solicitante:", "{{SUPERVISOR_DEPENDENCIA}}")
        ]
        for i, (k, v) in enumerate(rows_data):
            cell_k = table.cell(i, 0)
            cell_v = table.cell(i, 1)
            cell_k.text = k
            cell_v.text = v
            cell_k.paragraphs[0].runs[0].bold = True
            cell_k.paragraphs[0].runs[0].font.size = Pt(9.5)
            cell_v.paragraphs[0].runs[0].font.size = Pt(9.5)
            _set_cell_background(cell_k, "F0F4F8")

        doc_sum.add_heading("1. DESCRIPCIÓN DE LA NECESIDAD DE SUMINISTRO DE INSUMOS Y BIENES", level=1)
        doc_sum.add_paragraph("{{DESCRIPCION_DE_LA_NECESIDAD_A_SATISFACER}}")
        doc_sum.add_heading("1.1. MARCO COMERCIAL Y RÉGIMEN ESPECIAL DE SUMINISTRO", level=2)
        doc_sum.add_paragraph("{{MARCO_JURIDICO}}")

        doc_sum.add_heading("2. OBJETO Y ESPECIFICACIONES TÉCNICAS DEL SUMINISTRO", level=1)
        doc_sum.add_paragraph("Objeto: {{OBJETO}}")

        doc_sum.add_heading("3. ESPECIFICACIONES DE CALIDAD Y CONDICIONES DE FABRICACIÓN", level=1)
        doc_sum.add_paragraph("Los bienes e insumos suministrados deberán cumplir estrictamente con las normas técnicas colombianas (NTC), certificaciones de calidad de fábrica y fichas técnicas correspondientes.")
        doc_sum.add_paragraph("Requerimientos Específicos:")
        doc_sum.add_paragraph("{{OBJETIVOS_ESPECIFICOS}}")

        doc_sum.add_heading("4. OBLIGACIONES DEL PROVEEDOR / SUMINISTRADOR", level=1)
        doc_sum.add_paragraph("{{OBLIGACIONES_ESTUDIO_PREVIO}}")

        doc_sum.add_heading("5. CONDICIONES DE ENTREGA, TRANSPORTE Y FORMA DE PAGO", level=1)
        doc_sum.add_paragraph("Lugar de Entrega: Almacén General de la ESP ({{LUGAR_EJECUCION}}). Los fletes, seguros y descargue corren por cuenta exclusiva del proveedor.")
        doc_sum.add_paragraph("Forma de Pago: {{FORMA_PAGO}} (Contra presentación de factura electrónica y Acta de Entrada y Recibo a Satisfacción suscrita por el Almacenista y el Supervisor).")

        doc_sum.add_heading("6. DESIGNACIÓN DE SUPERVISIÓN Y CONTROL DE CALIDAD", level=1)
        doc_sum.add_paragraph("La supervisión y verificación del suministro estará a cargo de: {{SUPERVISOR_NOMBRE}}, {{SUPERVISOR_CARGO}}.")

        doc_sum.add_paragraph("\n\n_____________________________________\n{{SUPERVISOR_NOMBRE}}\n{{SUPERVISOR_CARGO}}\nResponsable Estudio Previo Suministro")
        doc_sum.save(str(path_ep_sum))
        logger.info(f"Plantilla base de Estudio Previo Suministro creada en: {path_ep_sum}")

    # 3. Plantilla Minuta de Contrato - Prestación de Servicios
    path_min_serv = settings.TEMPLATES_DIR / "plantilla_minuta_servicios.docx"
    if not path_min_serv.exists():
        doc_m = docx.Document()
        _style_corporate_doc(doc_m, "CONTRATO DE PRESTACIÓN DE SERVICIOS\nNo. {{NUMERO_CONTRATO}}")

        doc_m.add_paragraph(
            "Entre los suscritos a saber, por una parte la EMPRESA DE SERVICIOS PÚBLICOS DOMICILIARIOS (ESP), "
            "empresa constituida bajo el régimen especial de la Ley 142 de 1994, debidamente representada por su Gerente General, "
            "quien en adelante se denominará LA EMPRESA, y por la otra parte {{CONTRATISTA_NOMBRE}}, "
            "identificado(a) con {{CONTRATISTA_DOCUMENTO}}, representado legalmente por {{REPRESENTANTE_LEGAL}}, "
            "quien en adelante se denominará EL CONTRATISTA, se ha convenido celebrar el presente CONTRATO DE PRESTACIÓN DE SERVICIOS "
            "previas las siguientes cláusulas:\n"
        )

        doc_m.add_heading("CLÁUSULA PRIMERA - OBJETO:", level=1)
        doc_m.add_paragraph("EL CONTRATISTA se obliga para con LA EMPRESA a ejecutar a satisfacción el siguiente objeto: {{OBJETO}}.")

        doc_m.add_heading("CLÁUSULA SEGUNDA - VALOR Y FORMA DE PAGO:", level=1)
        doc_m.add_paragraph(
            "El valor total del presente contrato se fija en la suma de {{VALOR_NUMEROS}} ({{VALOR_LETRAS}}). "
            "LA EMPRESA cancelará dicho valor de la siguiente manera: {{FORMA_PAGO}}"
        )

        doc_m.add_heading("CLÁUSULA TERCERA - PLAZO Y LUGAR DE EJECUCIÓN:", level=1)
        doc_m.add_paragraph("El plazo de ejecución será de {{PLAZO}}, contado a partir de la suscripción del Acta de Inicio. Lugar: {{LUGAR_EJECUCION}}.")

        doc_m.add_heading("CLÁUSULA CUARTA - OBLIGACIONES ESPECÍFICAS DEL CONTRATISTA:", level=1)
        doc_m.add_paragraph("En desarrollo del objeto contractual, EL CONTRATISTA asume las siguientes obligaciones específicas:")
        doc_m.add_paragraph("{{OBLIGACIONES_MINUTA}}")

        doc_m.add_heading("CLÁUSULA QUINTA - OBLIGACIONES DE LA EMPRESA:", level=1)
        doc_m.add_paragraph("En desarrollo del presente contrato, LA EMPRESA asume las siguientes obligaciones:")
        doc_m.add_paragraph("{{OBLIGACIONES_EMPRESA}}")

        doc_m.add_heading("CLÁUSULA SEXTA - INEXISTENCIA DE SUBORDINACIÓN Y AUTONOMÍA TÉCNICA:", level=1)
        doc_m.add_paragraph(
            "El presente contrato de prestación de servicios se rige por las normas civiles y comerciales bajo el régimen de la Ley 142 de 1994. "
            "Por su naturaleza no genera vínculo laboral alguno ni prestaciones sociales entre LA EMPRESA y EL CONTRATISTA o sus dependientes. "
            "EL CONTRATISTA ejecutará sus obligaciones con total autonomía técnica, directiva y financiera."
        )

        doc_m.add_heading("CLÁUSULA SÉPTIMA - SUPERVISIÓN:", level=1)
        doc_m.add_paragraph("La supervisión del cumplimiento técnico y administrativo del presente contrato estará a cargo de {{SUPERVISOR_NOMBRE}} ({{SUPERVISOR_CARGO}}).")

        doc_m.add_heading("CLÁUSULA OCTAVA - RÉGIMEN Y MARCO JURÍDICO APLICABLE:", level=1)
        doc_m.add_paragraph("{{MARCO_JURIDICO}}")

        doc_m.add_paragraph(
            "\nPara constancia se firma por las partes el {{FECHA_SUSCRIPCION}}.\n\n"
            "LA EMPRESA:                                          EL CONTRATISTA:\n\n\n"
            "____________________________                 ____________________________\n"
            "GERENTE GENERAL                              {{CONTRATISTA_NOMBRE}}\n"
            "EMPRESA DE SERVICIOS PÚBLICOS (ESP)          {{CONTRATISTA_DOCUMENTO}}"
        )
        doc_m.save(str(path_min_serv))
        logger.info(f"Plantilla base de Minuta Servicios creada en: {path_min_serv}")

    # 4. Plantilla Minuta de Contrato - Suministro
    path_min_sum = settings.TEMPLATES_DIR / "plantilla_minuta_suministro.docx"
    if not path_min_sum.exists():
        doc_ms = docx.Document()
        _style_corporate_doc(doc_ms, "CONTRATO DE SUMINISTRO\nNo. {{NUMERO_CONTRATO}}")

        doc_ms.add_paragraph(
            "Entre los suscritos a saber, por una parte la EMPRESA DE SERVICIOS PÚBLICOS DOMICILIARIOS (ESP), "
            "empresa constituida bajo el régimen de la Ley 142 de 1994, debidamente representada por su Gerente General, "
            "quien en adelante se denominará LA EMPRESA, y por la otra parte {{CONTRATISTA_NOMBRE}}, "
            "identificado(a) con {{CONTRATISTA_DOCUMENTO}}, representado legalmente por {{REPRESENTANTE_LEGAL}}, "
            "quien en adelante se denominará EL PROVEEDOR / CONTRATISTA, se ha convenido celebrar el presente CONTRATO MERCANTIL DE SUMINISTRO "
            "previas las siguientes cláusulas:\n"
        )

        doc_ms.add_heading("CLÁUSULA PRIMERA - OBJETO DEL SUMINISTRO:", level=1)
        doc_ms.add_paragraph("EL PROVEEDOR se obliga para con LA EMPRESA a suministrar y entregar a satisfacción los siguientes bienes e insumos: {{OBJETO}}.")

        doc_ms.add_heading("CLÁUSULA SEGUNDA - VALOR TOTAL Y FORMA DE PAGO:", level=1)
        doc_ms.add_paragraph(
            "El valor total del presente contrato de suministro se fija en la suma de {{VALOR_NUMEROS}} ({{VALOR_LETRAS}}). "
            "LA EMPRESA cancelará dicho valor de la siguiente manera: {{FORMA_PAGO}}"
        )

        doc_ms.add_heading("CLÁUSULA TERCERA - LUGAR Y CONDICIONES DE ENTREGA:", level=1)
        doc_ms.add_paragraph("Los bienes objeto del contrato se entregarán en el Almacén General de LA EMPRESA en {{LUGAR_EJECUCION}}. El transporte, seguros, fletes y descargue son asumidos exclusivamente por EL PROVEEDOR.")

        doc_ms.add_heading("CLÁUSULA CUARTA - OBLIGACIONES ESPECÍFICAS DEL PROVEEDOR:", level=1)
        doc_ms.add_paragraph("{{OBLIGACIONES_MINUTA}}")

        doc_ms.add_heading("CLÁUSULA QUINTA - OBLIGACIONES DE LA EMPRESA:", level=1)
        doc_ms.add_paragraph("En desarrollo del contrato de suministro, LA EMPRESA asume las siguientes obligaciones:")
        doc_ms.add_paragraph("{{OBLIGACIONES_EMPRESA}}")

        doc_ms.add_heading("CLÁUSULA SEXTA - GARANTÍA DE CALIDAD Y RESPONSABILIDAD POR VICIOS OCULTOS:", level=1)
        doc_ms.add_paragraph(
            "EL PROVEEDOR garantiza que los bienes suministrados son nuevos, de óptima calidad y satisfacen plenamente las especificaciones técnicas exigidas. "
            "Conforme a los Artículos 934 y ss. del Código de Comercio, responderá por cualquier vicio oculto o defecto de fábrica debiendo reemplazar los elementos en un plazo no superior a 48 horas."
        )

        doc_ms.add_heading("CLÁUSULA SÉPTIMA - RECIBO A SATISFACCIÓN Y SUPERVISIÓN:", level=1)
        doc_ms.add_paragraph("La supervisión e inspección del suministro estará a cargo de {{SUPERVISOR_NOMBRE}} ({{SUPERVISOR_CARGO}}). El pago procederá una vez suscrita el Acta de Entrada al Almacén y Recibo a Satisfacción.")

        doc_ms.add_heading("CLÁUSULA OCTAVA - RÉGIMEN COMERCIAL APLICABLE:", level=1)
        doc_ms.add_paragraph("{{MARCO_JURIDICO}}")

        doc_ms.add_paragraph(
            "\nPara constancia se firma por las partes el {{FECHA_SUSCRIPCION}}.\n\n"
            "LA EMPRESA:                                          EL PROVEEDOR / CONTRATISTA:\n\n\n"
            "____________________________                 ____________________________\n"
            "GERENTE GENERAL                              {{CONTRATISTA_NOMBRE}}\n"
            "EMPRESA DE SERVICIOS PÚBLICOS (ESP)          {{CONTRATISTA_DOCUMENTO}}"
        )
        doc_ms.save(str(path_min_sum))
        logger.info(f"Plantilla base de Minuta Suministro creada en: {path_min_sum}")

    # 5. Plantilla Acta de Inicio (existente)
    path_acta = settings.TEMPLATES_DIR / "plantilla_acta_inicio.docx"
    if not path_acta.exists():
        doc_a = docx.Document()
        _style_corporate_doc(doc_a, "ACTA DE INICIO DE EJECUCIÓN CONTRACTUAL\nCONTRATO No. {{NUMERO_CONTRATO}}")

        doc_a.add_paragraph(
            "En las instalaciones de la Empresa de Servicios Públicos (ESP), el día {{FECHA_ACTA_INICIO}}, "
            "se reunieron el(la) señor(a) {{SUPERVISOR_NOMBRE}}, en su condición de {{SUPERVISOR_CARGO}}, "
            "y por la otra parte {{CONTRATISTA_NOMBRE}}, identificado(a) con {{CONTRATISTA_DOCUMENTO}}, "
            "con el objeto de suscribir la presente ACTA DE INICIO, previa verificación de los siguientes antecedentes:"
        )

        table_a = doc_a.add_table(rows=7, cols=2)
        table_a.alignment = WD_TABLE_ALIGNMENT.CENTER
        info_acta = [
            ("Contrato Número:", "{{NUMERO_CONTRATO}}"),
            ("Contratista:", "{{CONTRATISTA_NOMBRE}}"),
            ("Identificación:", "{{CONTRATISTA_DOCUMENTO}}"),
            ("Valor Total:", "{{VALOR_NUMEROS}}"),
            ("Plazo Pactado:", "{{PLAZO}}"),
            ("Fecha de Inicio:", "{{FECHA_ACTA_INICIO}}"),
            ("Fecha Terminación Estimada:", "{{FECHA_TERMINACION}}")
        ]
        for i, (k, v) in enumerate(info_acta):
            c_k = table_a.cell(i, 0)
            c_v = table_a.cell(i, 1)
            c_k.text = k
            c_v.text = v
            c_k.paragraphs[0].runs[0].bold = True
            c_k.paragraphs[0].runs[0].font.size = Pt(9.5)
            c_v.paragraphs[0].runs[0].font.size = Pt(9.5)
            _set_cell_background(c_k, "F0F4F8")

        doc_a.add_heading("CONSTANCIA DE REQUISITOS DE EJECUCIÓN:", level=1)
        doc_a.add_paragraph(
            "1. Se verificó la expedición y registro del Certificado de Disponibilidad Presupuestal No. {{CDP_NUMERO}}.\n"
            "2. Se acreditaron los pagos y afiliaciones al Sistema General de Seguridad Social y ARL según corresponda.\n"
            "3. Se aprobaron las pólizas de garantía pactadas en la minuta contractual.\n"
            "En mérito de lo anterior, las partes acuerdan dar inicio formal a la ejecución del objeto contractual:\n"
            "\"{{OBJETO}}\"."
        )

        doc_a.add_paragraph(
            "\nPara constancia se firma por los intervinientes:\n\n\n"
            "_________________________________         _________________________________\n"
            "{{SUPERVISOR_NOMBRE}}                     {{CONTRATISTA_NOMBRE}}\n"
            "{{SUPERVISOR_CARGO}}                      Contratista / Representante Legal\n"
            "Supervisor Designado ESP"
        )
        doc_a.save(str(path_acta))
        logger.info(f"Plantilla base de Acta de Inicio creada en: {path_acta}")

    # 6. Plantilla Minuta / Acta de Adición a Contrato
    path_adicion = settings.TEMPLATES_DIR / "plantilla_adicion_contrato.docx"
    if not path_adicion.exists():
        doc_adic = docx.Document()
        _style_corporate_doc(doc_adic, "MINUTA DE ADICIÓN CONTRACTUAL NRO. {{NUMERO_ADICION}}\nAL CONTRATO No. {{NUMERO_CONTRATO}}")

        doc_adic.add_paragraph(
            "Entre los suscritos a saber, por una parte la EMPRESA DE SERVICIOS PÚBLICOS DOMICILIARIOS (ESP), "
            "empresa constituida bajo el régimen de la Ley 142 de 1994, debidamente representada por su Gerente General, "
            "quien en adelante se denominará LA EMPRESA, y por la otra parte {{CONTRATISTA_NOMBRE}}, "
            "identificado(a) con {{CONTRATISTA_DOCUMENTO}}, representado legalmente por {{REPRESENTANTE_LEGAL}}, "
            "quien en adelante se denominará EL CONTRATISTA, han acordado suscribir la presente ADICIÓN CONTRACTUAL NRO. {{NUMERO_ADICION}} "
            "al Contrato No. {{NUMERO_CONTRATO}}, previas las siguientes consideraciones:\n"
        )

        table_ad = doc_adic.add_table(rows=5, cols=2)
        table_ad.alignment = WD_TABLE_ALIGNMENT.CENTER
        info_ad = [
            ("Contrato Principal:", "{{NUMERO_CONTRATO}}"),
            ("Contratista:", "{{CONTRATISTA_NOMBRE}}"),
            ("Valor Anterior del Contrato:", "{{VALOR_ANTERIOR}}"),
            ("Monto de la Presente Adición:", "{{VALOR_ADICION_NUMEROS}} ({{VALOR_ADICION_LETRAS}})"),
            ("Nuevo Valor Total Acumulado:", "{{VALOR_NUEVO_TOTAL}}")
        ]
        for i, (k, v) in enumerate(info_ad):
            c_k = table_ad.cell(i, 0)
            c_v = table_ad.cell(i, 1)
            c_k.text = k
            c_v.text = v
            c_k.paragraphs[0].runs[0].bold = True
            c_k.paragraphs[0].runs[0].font.size = Pt(9.5)
            c_v.paragraphs[0].runs[0].font.size = Pt(9.5)
            _set_cell_background(c_k, "F0F4F8")

        doc_adic.add_heading("CONSIDERACIONES JURÍDICAS Y PRESUPUESTALES:", level=1)
        doc_adic.add_paragraph(
            "1. Que las partes celebraron el Contrato No. {{NUMERO_CONTRATO}}, cuyo objeto contractual corresponde a: \"{{OBJETO}}\".\n"
            "2. Que durante la ejecución contractual se acreditó la necesidad técnica y operativa justificada para la continuidad del servicio: {{JUSTIFICACION}}.\n"
            "3. Que la presente adición presupuestal respeta el límite legal establecido y cuenta con respaldo financiero mediante el Certificado de Disponibilidad Presupuestal (CDP) No. {{CDP_NUMERO}}, expedido el {{CDP_FECHA}}, con cargo al rubro {{CDP_RUBRO}} {{CDP_RUBRO_NOMBRE}}."
        )

        doc_adic.add_heading("CLÁUSULA PRIMERA - ADICIÓN AL VALOR:", level=1)
        doc_adic.add_paragraph(
            "Adicionar al valor del Contrato No. {{NUMERO_CONTRATO}} la suma de {{VALOR_ADICION_NUMEROS}} ({{VALOR_ADICION_LETRAS}}), "
            "conforme a las disponibilidades presupuestales amparadas en el CDP No. {{CDP_NUMERO}}."
        )

        doc_adic.add_heading("CLÁUSULA SEGUNDA - NUEVO VALOR TOTAL CONTRACTUAL:", level=1)
        doc_adic.add_paragraph(
            "Como consecuencia de la adición estipulada en la cláusula anterior, el valor total acumulado del Contrato No. {{NUMERO_CONTRATO}} "
            "se fija en la suma de {{VALOR_NUEVO_TOTAL}}."
        )

        doc_adic.add_heading("CLÁUSULA TERCERA - VIGENCIA DE LAS DEMÁS ESTIPULACIONES:", level=1)
        doc_adic.add_paragraph(
            "Las demás cláusulas, plazos, obligaciones y condiciones estipuladas en el Contrato No. {{NUMERO_CONTRATO}} "
            "que no hayan sido objeto de modificación expresa mediante el presente documento, continúan con plena validez y fuerza vinculante."
        )

        doc_adic.add_paragraph(
            "\nPara constancia se firma por las partes en Yolombó, a los {{FECHA_ADICION}}.\n\n"
            "LA EMPRESA:                                          EL CONTRATISTA:\n\n\n"
            "____________________________                 ____________________________\n"
            "GERENTE GENERAL                              {{CONTRATISTA_NOMBRE}}\n"
            "EMPRESA DE SERVICIOS PÚBLICOS (ESP)          {{CONTRATISTA_DOCUMENTO}}"
        )
        doc_adic.save(str(path_adicion))
        logger.info(f"Plantilla base de Adición a Contrato creada en: {path_adicion}")

    # 7. Copias de compatibilidad legacy si faltan
    path_ep_legacy = settings.TEMPLATES_DIR / "plantilla_estudio_previo.docx"
    if not path_ep_legacy.exists() and path_ep_serv.exists():
        shutil.copy2(path_ep_serv, path_ep_legacy)

    path_min_legacy = settings.TEMPLATES_DIR / "plantilla_minuta_contrato.docx"
    if not path_min_legacy.exists() and path_min_serv.exists():
        shutil.copy2(path_min_serv, path_min_legacy)

def _style_corporate_doc(doc: docx.Document, title: str):
    """Aplica formato institucional para una ESP (márgenes, tipografía Arial tamaño 12, cabecera)."""
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)

    header = doc.sections[0].header
    p_head = header.paragraphs[0]
    p_head.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_h = p_head.add_run("EMPRESA DE SERVICIOS PÚBLICOS (ESP) | SISTEMA DE GESTIÓN CONTRACTUAL")
    run_h.font.name = "Arial"
    run_h.font.size = Pt(8.5)
    run_h.font.color.rgb = RGBColor(100, 116, 139)

    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = p_title.add_run(title)
    run_t.font.name = "Arial"
    run_t.font.size = Pt(13)
    run_t.font.bold = True
    run_t.font.color.rgb = RGBColor(0, 51, 102)  # Azul corporativo
    p_title.paragraph_format.space_after = Pt(14)

def _set_cell_background(cell, color_hex: str):
    """Aplica color de fondo a una celda de tabla en Word."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    tcPr.append(shd)

def _set_table_borders(table, color="CBD5E1", sz="4", val="single"):
    """Establece bordes sutiles y limpios en tablas de python-docx."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:insideV w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:left w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'<w:right w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def _set_cell_margins(cell, top=50, bottom=50, left=70, right=70):
    """Establece márgenes internos (padding dxa) en celda docx."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>'
    )
    tcPr.append(tcMar)

def inject_analisis_propuestas_mercado(doc: docx.Document, target_paragraph: Any, resumen_data: Dict[str, Any]):
    """
    Inserta en el Estudio Previo el resumen oficial y consolidado del ESTUDIO DE MERCADO
    (Elección de contratista + Análisis de Precios Unitarios APU), inmediatamente después
    de las obligaciones del contratista, encabezado obligatoriamente con el subtítulo:
    'ANALISIS DE LAS PROPUESTAS DE MERCADO:'
    """
    if not resumen_data or not isinstance(resumen_data, dict):
        return

    # Si target_paragraph es None, localizar el punto final de las obligaciones
    if target_paragraph is None:
        for idx, p_scan in enumerate(doc.paragraphs):
            t_scan = p_scan.text.upper()
            if "OBLIGACION" in t_scan or "SE OBLIGARÁ A" in t_scan:
                target_paragraph = p_scan
                for next_p in doc.paragraphs[idx+1:idx+35]:
                    if next_p.text.strip().startswith("•") or next_p.text.strip().startswith("-"):
                        target_paragraph = next_p
                    else:
                        break
                break

    if target_paragraph is None and doc.paragraphs:
        target_paragraph = doc.paragraphs[-1]

    if target_paragraph is None:
        return

    curr_elem = target_paragraph._element

    def add_p(text="", bold=False, size_pt=12, color=None, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=0, space_after=4, line_spacing=1.15):
        nonlocal curr_elem
        new_p_elm = OxmlElement("w:p")
        curr_elem.addnext(new_p_elm)
        curr_elem = new_p_elm
        new_p = docx.text.paragraph.Paragraph(new_p_elm, target_paragraph._parent)
        new_p.alignment = align
        new_p.paragraph_format.space_before = Pt(space_before)
        new_p.paragraph_format.space_after = Pt(space_after)
        new_p.paragraph_format.line_spacing = line_spacing
        if text:
            r = new_p.add_run(text)
            r.bold = bold
            r.font.name = "Arial"
            r.font.size = Pt(size_pt)
            if color:
                r.font.color.rgb = color
        return new_p

    def add_tbl(rows_cnt, cols_cnt, col_widths=None):
        nonlocal curr_elem
        tbl = doc.add_table(rows=rows_cnt, cols=cols_cnt)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        curr_elem.addnext(tbl._tbl)
        curr_elem = tbl._tbl
        _set_table_borders(tbl, color="CBD5E1", sz="4", val="single")
        if col_widths:
            for row in tbl.rows:
                for c_idx, w in enumerate(col_widths):
                    if c_idx < len(row.cells):
                        row.cells[c_idx].width = w
        return tbl

    textos = resumen_data.get("textos") or {}
    tabla_ofertas = resumen_data.get("tabla_ofertas") or []
    tabla_items = resumen_data.get("tabla_items") or []
    ganador_info = resumen_data.get("proponente_ganador") or {}

    # 1. Párrafo de separación y SUBTÍTULO OBLIGATORIO EXACTO
    add_p("", space_before=4, space_after=2)
    add_p(
        "ANALISIS DE LAS PROPUESTAS DE MERCADO:", 
        bold=True, 
        size_pt=10.5, 
        color=RGBColor(3, 0, 143), 
        align=WD_ALIGN_PARAGRAPH.LEFT, 
        space_before=10, 
        space_after=4
    )

    # 2. Introducción técnica-jurídica (Ley 142 de 1994 & Manual PR-ESPY-002)
    if textos.get("introduccion"):
        add_p(textos["introduccion"], size_pt=9.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=4)

    # 3. Sección 1: Elección de Contratista y Evaluación Comparativa
    add_p(
        "1. Análisis Comparativo de Ofertas y Elección de Contratista:",
        bold=True,
        size_pt=9.5,
        color=RGBColor(15, 23, 42),
        align=WD_ALIGN_PARAGRAPH.LEFT,
        space_before=5,
        space_after=2
    )
    if textos.get("eleccion_contratista"):
        add_p(textos["eleccion_contratista"], size_pt=9.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=4)

    # 4. Tabla de ofertas del mercado
    if tabla_ofertas:
        col_w = [Inches(2.2), Inches(1.1), Inches(1.1), Inches(1.2), Inches(1.1)]
        tbl_of = add_tbl(len(tabla_ofertas) + 1, 5, col_w)
        headers_of = ["Proponente / Oferente", "NIT / C.C.", "Valor Cotizado", "Control Aritmético", "Resultado / Selección"]
        
        # Encabezado
        for i_h, h_text in enumerate(headers_of):
            cell = tbl_of.rows[0].cells[i_h]
            cell.text = h_text
            _set_cell_background(cell, "0A3A60")
            _set_cell_margins(cell, top=60, bottom=60, left=80, right=80)
            if cell.paragraphs and cell.paragraphs[0].runs:
                r_h = cell.paragraphs[0].runs[0]
                r_h.bold = True
                r_h.font.name = "Calibri"
                r_h.font.size = Pt(8.5)
                r_h.font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i_h > 0 else WD_ALIGN_PARAGRAPH.LEFT

        # Filas de ofertas
        for r_idx, of_data in enumerate(tabla_ofertas, start=1):
            row = tbl_of.rows[r_idx]
            vals = [
                of_data.get("nombre", ""),
                of_data.get("nit", ""),
                of_data.get("valor_cotizado_fmt", ""),
                of_data.get("control_aritmetico", ""),
                of_data.get("estado_eleccion", "")
            ]
            is_win = of_data.get("es_ganador", False)
            bg_col = "ECFDF5" if is_win else ("FFFFFF" if r_idx % 2 != 0 else "F8FAFC")

            for c_idx, val_txt in enumerate(vals):
                cell = row.cells[c_idx]
                cell.text = str(val_txt)
                _set_cell_background(cell, bg_col)
                _set_cell_margins(cell, top=50, bottom=50, left=80, right=80)
                if cell.paragraphs and cell.paragraphs[0].runs:
                    r_c = cell.paragraphs[0].runs[0]
                    r_c.font.name = "Calibri"
                    r_c.font.size = Pt(8.0)
                    if is_win:
                        r_c.bold = True
                        if c_idx == 4:
                            r_c.font.color.rgb = RGBColor(22, 101, 52)
                if c_idx in (1, 3, 4):
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif c_idx == 2:
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 5. Sección 2: Análisis de Precios Unitarios (APU) y Presupuesto Oficial Precontractual
    add_p(
        "2. Análisis de Precios Unitarios (APU) y Presupuesto Oficial Precontractual:",
        bold=True,
        size_pt=9.5,
        color=RGBColor(15, 23, 42),
        align=WD_ALIGN_PARAGRAPH.LEFT,
        space_before=6,
        space_after=2
    )
    if textos.get("analisis_apu"):
        add_p(textos["analisis_apu"], size_pt=9.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=2, space_after=4)

    # 6. Tabla de ítems presupuestados y precios unitarios
    if tabla_items:
        col_w_items = [Inches(0.4), Inches(3.2), Inches(0.5), Inches(0.5), Inches(1.0), Inches(1.1)]
        tbl_it = add_tbl(len(tabla_items) + 2, 6, col_w_items)
        headers_it = ["Ítem", "Descripción del Bien o Servicio", "Unidad", "Cant.", "Vr. Unitario", "Vr. Total"]
        
        # Encabezado
        for i_h, h_text in enumerate(headers_it):
            cell = tbl_it.rows[0].cells[i_h]
            cell.text = h_text
            _set_cell_background(cell, "0A3A60")
            _set_cell_margins(cell, top=60, bottom=60, left=70, right=70)
            if cell.paragraphs and cell.paragraphs[0].runs:
                r_h = cell.paragraphs[0].runs[0]
                r_h.bold = True
                r_h.font.name = "Calibri"
                r_h.font.size = Pt(8.5)
                r_h.font.color.rgb = RGBColor(255, 255, 255)
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER if i_h not in (1, 4, 5) else (WD_ALIGN_PARAGRAPH.RIGHT if i_h >= 4 else WD_ALIGN_PARAGRAPH.LEFT)

        # Filas de ítems
        for r_idx, it_data in enumerate(tabla_items, start=1):
            row = tbl_it.rows[r_idx]
            vals_it = [
                str(it_data.get("item_numero", r_idx)),
                str(it_data.get("descripcion", "")),
                str(it_data.get("unidad", "UND")),
                f"{float(it_data.get('cantidad', 1)):g}",
                str(it_data.get("valor_unitario_fmt", "$0")),
                str(it_data.get("valor_total_fmt", "$0"))
            ]
            bg_col = "FFFFFF" if r_idx % 2 != 0 else "F8FAFC"
            for c_idx, val_txt in enumerate(vals_it):
                cell = row.cells[c_idx]
                cell.text = val_txt
                _set_cell_background(cell, bg_col)
                _set_cell_margins(cell, top=45, bottom=45, left=60, right=60)
                if cell.paragraphs and cell.paragraphs[0].runs:
                    r_c = cell.paragraphs[0].runs[0]
                    r_c.font.name = "Calibri"
                    r_c.font.size = Pt(8.0)
                if c_idx in (0, 2, 3):
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif c_idx >= 4:
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Fila Total
        tot_row = tbl_it.rows[-1]
        c_tot_label = tot_row.cells[0]
        c_tot_val = tot_row.cells[5]
        # Merge c0..c4
        for c_merge_idx in range(1, 5):
            c_tot_label.merge(tot_row.cells[c_merge_idx])
        c_tot_label.text = "VALOR TOTAL PRESUPUESTO OFICIAL (A TODO COSTO):"
        c_tot_val.text = ganador_info.get("valor_total_fmt", "") or "$0"
        
        for c in (c_tot_label, c_tot_val):
            _set_cell_background(c, "E0F2FE")
            _set_cell_margins(c, top=60, bottom=60, left=80, right=80)
            if c.paragraphs and c.paragraphs[0].runs:
                r_tot = c.paragraphs[0].runs[0]
                r_tot.bold = True
                r_tot.font.name = "Calibri"
                r_tot.font.size = Pt(8.5)
                r_tot.font.color.rgb = RGBColor(3, 0, 143)
        c_tot_label.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        c_tot_val.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # 7. Conclusión del estudio de mercado
    if textos.get("conclusion"):
        add_p(textos["conclusion"], size_pt=9.5, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_before=4, space_after=8)

    # 8. Espacio final antes del siguiente acápite
    add_p("", space_before=2, space_after=4)

def generate_docx_for_contract(
    contrato: Contrato, 
    template_type: str, 
    db_session = None
) -> Path:
    """
    Genera un documento Word final reemplazando placeholders conservando el formato.
    Utiliza la plantilla personalizada de la ESP si el usuario la cargó, o la plantilla oficial por defecto.
    template_type: 'ESTUDIO_PREVIO', 'MINUTA', 'ACTA_INICIO', o modalidades específicas
    ('ESTUDIO_PREVIO_SERVICIOS', 'ESTUDIO_PREVIO_SUMINISTRO', 'MINUTA_SERVICIOS', 'MINUTA_SUMINISTRO').
    """
    create_default_templates_if_missing()

    norm_type = template_type.upper().strip()
    tipo_str = str(contrato.tipologia.value if hasattr(contrato.tipologia, 'value') else contrato.tipologia).upper()
    is_suministro = "SUMINISTRO" in tipo_str

    # Resolución inteligente por tipología si se envía clave genérica
    if norm_type == "ESTUDIO_PREVIO":
        norm_type = "ESTUDIO_PREVIO_SUMINISTRO" if is_suministro else "ESTUDIO_PREVIO_SERVICIOS"
    elif norm_type == "MINUTA":
        norm_type = "MINUTA_SUMINISTRO" if is_suministro else "MINUTA_SERVICIOS"

    template_mapping = {
        "ESTUDIO_PREVIO": (TipoDocumento.ESTUDIO_PREVIO_DOCX, "Estudio_Previo"),
        "MINUTA": (TipoDocumento.MINUTA_DOCX, "Minuta_Contrato"),
        "ACTA_INICIO": (TipoDocumento.ACTA_INICIO_DOCX, "Acta_Inicio"),
        "ESTUDIO_PREVIO_SERVICIOS": (TipoDocumento.ESTUDIO_PREVIO_DOCX, "Estudio_Previo_Servicios"),
        "ESTUDIO_PREVIO_SUMINISTRO": (TipoDocumento.ESTUDIO_PREVIO_DOCX, "Estudio_Previo_Suministro"),
        "MINUTA_SERVICIOS": (TipoDocumento.MINUTA_DOCX, "Minuta_Servicios"),
        "MINUTA_SUMINISTRO": (TipoDocumento.MINUTA_DOCX, "Minuta_Suministro"),
        "ADICION": (TipoDocumento.MINUTA_DOCX, "Minuta_Adicion")
    }

    if norm_type not in template_mapping:
        raise ValueError(f"Tipo de plantilla inválido: '{template_type}'. Opciones: {list(template_mapping.keys())}")

    tipo_doc, prefix = template_mapping[norm_type]
    template_path, is_custom = get_active_template_path(norm_type)

    if not template_path.exists():
        raise FileNotFoundError(f"Plantilla no encontrada: {template_path}")

    logger.info(f"Generando documento contractual con plantilla ({'PERSONALIZADA DE LA ESP' if is_custom else 'OFICIAL POR DEFECTO'}): {template_path.name}")

    # Abrir plantilla Word (personalizada o por defecto)
    doc = docx.Document(str(template_path))

    # Construir contexto de variables con sinónimos
    context = build_contract_context(contrato)

    # Tratamiento especializado y dinámico para ACTA DE INICIO
    if norm_type == "ACTA_INICIO":
        f_inicio = getattr(contrato, "fecha_acta_inicio", None)
        f_term = getattr(contrato, "fecha_terminacion", None)
        f_susc = getattr(contrato, "fecha_suscripcion", None)

        # En un Acta de Inicio, si la plantilla usa {{FECHA}}, se refiere a la fecha del acta de inicio
        f_acta_val = format_date_spanish(f_inicio or f_susc, default="Por definir")
        context["FECHA"] = f_acta_val
        context["FECHA_ACTA_INICIO"] = f_acta_val
        context["FECHA_INICIO"] = f_acta_val
        context["FECHA DE INICIO"] = f_acta_val
        context["FECHA_ACTA"] = f_acta_val
        context["FECHA ACTA"] = f_acta_val

        if f_term:
            f_term_val = format_date_spanish(f_term, default="Por definir")
            context["FECHA_TERMINACION"] = f_term_val
            context["FECHA_TERMINACION_ESTIMADA"] = f_term_val
            context["FECHA TERMINACION ESTIMADA"] = f_term_val
            context["FECHA_TERMINACIÓN_ESTIMADA"] = f_term_val
            context["FECHA TERMINACIÓN ESTIMADA"] = f_term_val
            context["FECHA_TERMINACIÓN"] = f_term_val
            context["FECHA TERMINACIÓN"] = f_term_val
            context["FECHA TERMINACION"] = f_term_val
            context["FECHA_FINAL"] = f_term_val
            context["FECHA FINAL"] = f_term_val
            context["FECHA_FIN"] = f_term_val
            context["FECHA FIN"] = f_term_val

    if "ESTUDIO_PREVIO" in norm_type:
        f_ep = getattr(contrato, "fecha_estudio_previo", None) or getattr(contrato, "fecha_suscripcion", None)
        f_ep_val = format_date_spanish(f_ep, default="15 de enero de 2026")
        context["FECHA"] = f_ep_val
        context["FECHA_ESTUDIO_PREVIO"] = f_ep_val

    if "MINUTA" in norm_type:
        f_susc = getattr(contrato, "fecha_suscripcion", None)
        f_susc_val = format_date_spanish(f_susc, default="Pendiente de firma")
        context["FECHA"] = f_susc_val
        context["FECHA_SUSCRIPCION"] = f_susc_val
        context["FECHA_FIRMA"] = f_susc_val
        context["FECHA FIRMA"] = f_susc_val
        context["FECHA_DE_FIRMA"] = f_susc_val
        context["FECHA DE FIRMA"] = f_susc_val
        context["FECHA_DE_SUSCRIPCION"] = f_susc_val
        context["FECHA DE SUSCRIPCION"] = f_susc_val
        context["FECHA_SUSCRIPCIÓN"] = f_susc_val
        context["FECHA SUSCRIPCIÓN"] = f_susc_val

        # Validar y adaptar dinámicamente tablas en el documento
        for tbl in doc.tables:
            has_inicio_row = False
            term_row_idx = None
            for idx, r in enumerate(tbl.rows):
                if len(r.cells) >= 2:
                    label_txt = r.cells[0].text.strip().lower()
                    if "inicio" in label_txt:
                        has_inicio_row = True
                        if "{{FECHA}}" in r.cells[1].text:
                            r.cells[1].text = r.cells[1].text.replace("{{FECHA}}", "{{FECHA_ACTA_INICIO}}")
                    elif "terminaci" in label_txt or "final" in label_txt:
                        term_row_idx = idx
                        if "{{FECHA}}" in r.cells[1].text:
                            r.cells[1].text = r.cells[1].text.replace("{{FECHA}}", "{{FECHA_TERMINACION}}")

            # Si la tabla tiene fila de terminación pero no de inicio, insertar la fila de Fecha de Inicio antes
            if not has_inicio_row and term_row_idx is not None:
                new_row = tbl.add_row()
                target_term_row = tbl.rows[term_row_idx]
                target_term_row._tr.addprevious(new_row._tr)
                
                c0 = new_row.cells[0]
                c1 = new_row.cells[1]
                c0.text = "Fecha de Inicio:"
                c1.text = "{{FECHA_ACTA_INICIO}}"
                
                if c0.paragraphs and c0.paragraphs[0].runs:
                    c0.paragraphs[0].runs[0].bold = True
                    c0.paragraphs[0].runs[0].font.size = Pt(9.5)
                if c1.paragraphs and c1.paragraphs[0].runs:
                    c1.paragraphs[0].runs[0].font.size = Pt(9.5)
                _set_cell_background(c0, "F0F4F8")

    # Reemplazar placeholders conservando formato
    replace_info = replace_placeholders_in_document(doc, context)
    last_oblig_p = (replace_info or {}).get("last_obligations_paragraph") if isinstance(replace_info, dict) else None

    # Garantizar que en las minutas y estudios previos exista la sección de obligaciones de la empresa si la plantilla no la incluía
    if "MINUTA" in norm_type or "ESTUDIO_PREVIO" in norm_type:
        has_empresa_clause = False
        for p_check in doc.paragraphs:
            t_chk = p_check.text.upper()
            if "OBLIGACIONES DE LA EMPRESA" in t_chk or "OBLIGACIONES DE LA ESP" in t_chk or "OBLIGACIONES DE LA ENTIDAD" in t_chk:
                has_empresa_clause = True
                break
        if not has_empresa_clause:
            emp_list = context.get("OBLIGACIONES_EMPRESA") or []
            if emp_list:
                target_p = last_oblig_p
                if target_p is None:
                    for idx, p_scan in enumerate(doc.paragraphs):
                        if "OBLIGACION" in p_scan.text.upper():
                            target_p = p_scan
                            for next_p in doc.paragraphs[idx+1:idx+35]:
                                if next_p.text.strip().startswith("•") or next_p.text.strip().startswith("-"):
                                    target_p = next_p
                                else:
                                    break
                            break
                if target_p is not None:
                    if "MINUTA" in norm_type:
                        hdr_text = "\nCLÁUSULA - OBLIGACIONES DE LA EMPRESA:\nEn desarrollo del presente contrato, LA EMPRESA asume las siguientes obligaciones específicas:"
                    else:
                        hdr_text = "\nOBLIGACIONES DE LA EMPRESA (ESPY S.A. E.S.P.):\nAsimismo, para garantizar el adecuado desarrollo y cumplimiento del objeto contractual, la ESP YOLOMBO asume las siguientes obligaciones institucionales:"
                    new_h = insert_paragraph_after(target_p, hdr_text)
                    new_h.paragraph_format.left_indent = Inches(0)
                    new_h.paragraph_format.space_before = Pt(8)
                    new_h.paragraph_format.space_after = Pt(4)
                    for r in new_h.runs:
                        r.bold = True
                    cur_emp = new_h
                    for item in emp_list:
                        cur_emp = insert_paragraph_after(cur_emp, f"• {str(item).strip()}")

    # Inyección condicionada del ESTUDIO DE MERCADO al ESTUDIO PREVIO
    if "ESTUDIO_PREVIO" in norm_type:
        estudio_data = getattr(contrato, "estudio_mercado", None)
        if not estudio_data:
            meta = getattr(contrato, "metadatos_agente", {}) or {}
            if isinstance(meta, dict):
                estudio_data = meta.get("estudio_mercado")

        tiene_estudio = bool(
            estudio_data and isinstance(estudio_data, dict) and
            (estudio_data.get("ofertas") or estudio_data.get("proponente_ganador") or estudio_data.get("valor_total_adjudicado") or estudio_data.get("items_apu"))
        )

        if tiene_estudio:
            from app.services.agents.apu_agent import apu_agent
            resumen_data = apu_agent.build_resumen_estudio_mercado(estudio_data)
            inject_analisis_propuestas_mercado(doc, last_oblig_p, resumen_data)

    # -------------------------------------------------------------------------
    # AJUSTES POST-PROCESAMIENTO: COMPARECENCIA, TABLA RESUMEN Y FIRMAS
    # (Diferenciación estricta entre Persona Jurídica y Persona Natural)
    # -------------------------------------------------------------------------
    is_jur = context.get("CONTRATISTA_TIPO_PERSONA") == "JURIDICA"
    rep_nom_val = str(context.get("REPRESENTANTE_LEGAL") or "").strip()
    rep_doc_val = str(context.get("REPRESENTANTE_LEGAL_DOCUMENTO") or "").strip()
    c_nom_val = str(context.get("CONTRATISTA") or context.get("CONTRATISTA_NOMBRE") or "").strip()
    c_doc_val = str(context.get("DOCUMENTO") or context.get("CONTRATISTA_DOCUMENTO") or "").strip()

    # 1. PÁRRAFO DE COMPARECENCIA (Encabezado del Contrato y Acta de Inicio)
    if "MINUTA" in norm_type or norm_type == "ACTA_INICIO":
        for p in doc.paragraphs:
            p_text = p.text
            if "por la otra" in p_text.lower():
                if is_jur:
                    # SI ES PERSONA JURÍDICA:
                    el_la_rep = "la señora" if any(fn in rep_nom_val for fn in ["PAULA", "MARIA", "CAROLINA", "ANA", "CLAUDIA", "GLORIA", "LUZ", "ANDREA", "PATRICIA", "DIANA", "SANDRA", "MONICA", "ADRIANA", "MARTHA"]) else "el señor"
                    clean_nit_num = re.sub(r"^NIT\s*", "", c_doc_val, flags=re.IGNORECASE).strip()
                    # Evitar poner 'la ' antes de una razón social que no empiece por SOCIEDAD o EMPRESA
                    art_empresa = "la " if any(c_nom_val.upper().startswith(p) for p in ["SOCIEDAD", "EMPRESA"]) else ""
                    comparecencia_juridica = (
                        f"por la otra {art_empresa}{c_nom_val}, NIT {clean_nit_num}, "
                        f"representada legalmente por {el_la_rep} {rep_nom_val}, identificado(a) con C.C. {rep_doc_val}"
                    )
                    # Reemplazar variantes de comparecencia legacy
                    new_txt = re.sub(
                        r"por\s+la\s+otra\s+(?:el\s+se[ñ\ufffd]or|la\s+se[ñ\ufffd]ora|la\s+parte|parte|la)?\s*" + re.escape(c_nom_val) + r"\s*,\s*(?:C\.C\.|NIT|identificado\(a\)\s+con)?\s*(?:NIT\s*)?" + re.escape(clean_nit_num),
                        comparecencia_juridica,
                        p_text,
                        flags=re.IGNORECASE
                    )
                    if new_txt == p_text:
                        # Fallback con regex genérica sobre el bloque de comparecencia del contratista
                        new_txt = re.sub(
                            r"por\s+la\s+otra\s+(?:el\s+se[ñ\ufffd]or|la\s+se[ñ\ufffd]ora|la\s+parte|parte|la\s+)?[\s\S]*?(?:,\s*debidamente\s+acreditada|,\s*con\s+el\s+objeto\s+de\s+suscribir)",
                            comparecencia_juridica + (", debidamente acreditada" if "debidamente acreditada" in p_text else ", con el objeto de suscribir"),
                            p_text,
                            count=1,
                            flags=re.IGNORECASE
                        )
                    if new_txt != p_text:
                        p.text = new_txt
                else:
                    # SI ES PERSONA NATURAL:
                    # "...y por la otra el(la) señor(a) [NOMBRE DEL CONTRATISTA], identificado(a) con C.C. [NÚMERO DE CÉDULA]..."
                    clean_cc_num = re.sub(r"^(?:CC|C\.C\.)\s*", "", c_doc_val, flags=re.IGNORECASE).strip()
                    comparecencia_natural = f"por la otra el(la) señor(a) {c_nom_val}, identificado(a) con C.C. {clean_cc_num}"
                    new_txt = re.sub(
                        r"por\s+la\s+otra\s+(?:el\s+se[ñ\ufffd]or|la\s+se[ñ\ufffd]ora|parte)?\s*" + re.escape(c_nom_val) + r"\s*,\s*(?:C\.C\.|NIT|identificado\(a\)\s+con)?\s*(?:CC|C\.C\.)?\s*" + re.escape(clean_cc_num),
                        comparecencia_natural,
                        p_text,
                        flags=re.IGNORECASE
                    )
                    if new_txt == p_text:
                        new_txt = re.sub(
                            r"por\s+la\s+otra\s+(?:el\s+se[ñ\ufffd]or|la\s+se[ñ\ufffd]ora|parte\s+)?[\s\S]*?(?:,\s*debidamente\s+acreditada|,\s*con\s+el\s+objeto\s+de\s+suscribir)",
                            comparecencia_natural + (", debidamente acreditada" if "debidamente acreditada" in p_text else ", con el objeto de suscribir"),
                            p_text,
                            count=1,
                            flags=re.IGNORECASE
                        )
                    if new_txt != p_text:
                        p.text = new_txt

    # 2. TABLA DE RESUMEN INICIAL (Minuta y Acta de Inicio):
    # Cuando sea Persona Jurídica, incluir fila de Representante Legal DEBAJO de CONTRATISTA y Cédula - NIT
    if is_jur and rep_nom_val and doc.tables:
        t0 = doc.tables[0]
        has_rep_row = any("representante" in c.text.lower() for r in t0.rows for c in r.cells)
        if not has_rep_row:
            target_idx = None
            # Buscar la fila de 'Cédula - NIT' o 'Identificación' del contratista (que va después de CONTRATISTA)
            for idx, r in enumerate(t0.rows):
                row_txt = " ".join(c.text.lower() for c in r.cells)
                if any(k in row_txt for k in ["cédula", "cedula", "identificación", "identificacion"]) and idx > 1:
                    target_idx = idx
                    break
                elif "contratista" in row_txt and idx > 1:
                    target_idx = idx

            # Si no encontró cédula, buscar última mención de NIT después de la fila 1 (la fila 1 es NIT del contratante)
            if target_idx is None:
                for idx in range(2, len(t0.rows)):
                    row_txt = " ".join(c.text.lower() for c in t0.rows[idx].cells)
                    if "nit" in row_txt or "contratista" in row_txt:
                        target_idx = idx

            if target_idx is not None and target_idx < len(t0.rows):
                new_row = t0.add_row()
                target_r = t0.rows[target_idx]
                target_r._tr.addnext(new_row._tr)
                c0 = new_row.cells[0]
                c1 = new_row.cells[1] if len(new_row.cells) > 1 else new_row.cells[0]
                c0.text = "Representante Legal Contratista:"
                c1.text = f"{rep_nom_val} - C.C. {rep_doc_val}"
                if c0.paragraphs and c0.paragraphs[0].runs:
                    c0.paragraphs[0].runs[0].bold = True
                    c0.paragraphs[0].runs[0].font.size = Pt(9.5)
                if c1.paragraphs and c1.paragraphs[0].runs:
                    c1.paragraphs[0].runs[0].font.size = Pt(9.5)
                _set_cell_background(c0, "F0F4F8")

    # 3. ESTRUCTURA OBLIGATORIA DEL BLOQUE DE FIRMAS (Contrato y Acta de Inicio)
    if is_jur and rep_nom_val:
        for idx_p, p in enumerate(doc.paragraphs):
            t_p = p.text
            # Ignorar encabezados o preámbulos iniciales
            if idx_p < 4:
                continue

            # Minuta custom: P52-P54 (tiene líneas '____' y 'CAROLINA GIRALDO' en el mismo párrafo)
            if "MINUTA" in norm_type and "CAROLINA GIRALDO" in t_p and (c_nom_val in t_p or "{{CONTRATISTA}}" in t_p):
                # Línea superior de firmas y nombres
                p.text = f"___________________________\t\t\t_______________________\nCAROLINA GIRALDO GÓMEZ\t\t\t\t{c_nom_val}"
                if idx_p + 1 < len(doc.paragraphs):
                    p_next = doc.paragraphs[idx_p + 1]
                    p_next.text = f"Gerente General\t\t\t\t\tR.L. {rep_nom_val}"
                if idx_p + 2 < len(doc.paragraphs):
                    p_after = doc.paragraphs[idx_p + 2]
                    p_after.text = "Contratante\t\t\t\t\t\tContratista"
                break
            elif norm_type == "ACTA_INICIO" and "CAROLINA GIRALDO" in t_p and (c_nom_val in t_p or "{{CONTRATISTA}}" in t_p):
                # En Acta de Inicio custom: P8 tiene las líneas '____', P9 tiene los nombres, P10 los cargos
                p.text = f"CAROLINA GIRALDO GÓMEZ\t\t\t\t{c_nom_val}"
                if idx_p + 1 < len(doc.paragraphs):
                    p_next = doc.paragraphs[idx_p + 1]
                    p_next.text = f"Gerente General\t\t\t\t\tR.L. {rep_nom_val}"
                if idx_p + 2 < len(doc.paragraphs):
                    p_after = doc.paragraphs[idx_p + 2]
                    p_after.text = "ESP Yolombó\t\t\t\t\tContratista"
                break
            elif "GERENTE GENERAL" in t_p and c_nom_val in t_p:
                # Plantilla base institucional
                p.text = re.sub(
                    re.escape(c_nom_val) + r"\s*\n\s*(?:NIT|CC|C\.C\.)?[^\n]*",
                    f"{c_nom_val}\nR.L. {rep_nom_val}\nContratista",
                    t_p
                )
                break

    # 4. Correcciones gramaticales y de puntuación finales en Minuta / Acta
    for p in doc.paragraphs:
        if ".. Este contrato" in p.text:
            p.text = p.text.replace(".. Este contrato", ". Este contrato")
        if "por la otra la MONITOREO" in p.text:
            p.text = p.text.replace("por la otra la MONITOREO", "por la otra MONITOREO")
        if "RL. CARLOS IVAN" in p.text and "GONZALEZ" not in p.text:
            p.text = p.text.replace("RL. CARLOS IVAN ESCOBAR", "R.L. CARLOS IVAN ESCOBAR GONZALEZ")

    # Estandarización tipográfica obligatoria final: Letra tipo 'Arial' tamaño 12 en todo el contenido escrito
    enforce_arial_12_typography(doc)

    # Guardar en directorio de generados
    safe_num = contrato.numero_contrato.replace("/", "-").replace(" ", "_")
    output_filename = f"{prefix}_{safe_num}_{contrato.vigencia}.docx"
    output_path = settings.GENERATED_DIR / output_filename
    doc.save(str(output_path))
    logger.info(f"Documento Word generado exitosamente: {output_path}")

    # Registrar en base de datos si se proporcionó sesión
    if db_session:
        try:
            relative_path = str(output_path.relative_to(settings.BASE_DIR))
        except ValueError:
            relative_path = str(output_path.relative_to(settings.STORAGE_DIR.parent))
        db_doc = Documento(

            contrato_id=contrato.id,
            contratista_id=contrato.contratista_id,
            tipo_documento=tipo_doc,
            categoria=CategoriaDocumento.GENERADO_SISTEMA,
            nombre_archivo_original=output_filename,
            nombre_archivo_almacenado=output_filename,
            ruta_relativa=relative_path,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            tamano_bytes=output_path.stat().st_size,
            datos_extraidos_json={"template_type": template_type}
        )
        db_session.add(db_doc)
        db_session.commit()
        db_session.refresh(db_doc)

    return output_path


def generate_adicion_docx(
    contrato: Contrato,
    adicion_data: Dict[str, Any],
    db_session: Any = None
) -> Path:
    """
    Genera la Minuta Oficial de Adición Contractual en formato .docx.
    Utiliza prioritariamente la plantilla personalizada o base oficial 'ADICION'
    inyectando los marcadores correspondientes. En caso de ausencia o fallo,
    utiliza el generador procedimental institucional de respaldo.
    """
    from app.services.agents.addition_agent import addition_agent, MESES

    # Normalizar contrato si viene como diccionario o le faltan atributos
    if isinstance(contrato, dict):
        class ContractDictWrapper:
            def __init__(self, d):
                for k, v in d.items():
                    setattr(self, k, v)
            def __getattr__(self, name):
                return None
        contrato = ContractDictWrapper(contrato)

    if not hasattr(contrato, "contratista"):
        contrato.contratista = None
    if not hasattr(contrato, "id"):
        contrato.id = 1
    if not hasattr(contrato, "contratista_id"):
        contrato.contratista_id = 1
    if not hasattr(contrato, "valor_inicial"):
        contrato.valor_inicial = getattr(contrato, "valor_total", 0.0)
    if not hasattr(contrato, "tipologia"):
        contrato.tipologia = "PRESTACION_SERVICIOS"
    if not hasattr(contrato, "obligaciones_minuta"):
        contrato.obligaciones_minuta = []
    if not hasattr(contrato, "obligaciones_estudio_previo"):
        contrato.obligaciones_estudio_previo = []
    if not hasattr(contrato, "objetivos_especificos"):
        contrato.objetivos_especificos = []
    if not hasattr(contrato, "objetivo_general"):
        contrato.objetivo_general = getattr(contrato, "objeto", "")

    # 1. Intentar generar usando la plantilla de Adición (custom o default)
    try:
        tpl_path, is_custom = get_active_template_path("ADICION")
        if tpl_path.exists() and tpl_path.stat().st_size > 0:
            doc = docx.Document(str(tpl_path))
            
            num_adicion = adicion_data.get("numero_adicion", 1)
            val_adicion = float(adicion_data.get("valor_adicion", 0.0))
            val_num_str, val_letras_str, _ = addition_agent.format_currency_legal(val_adicion)
            val_anterior = float(adicion_data.get("valor_anterior") or getattr(contrato, "valor_total", 0.0) or 0.0)
            val_nuevo_total = float(adicion_data.get("valor_nuevo_total") or (val_anterior + val_adicion))
            val_ant_str, _, _ = addition_agent.format_currency_legal(val_anterior)
            val_nuevo_str, val_nuevo_letras, _ = addition_agent.format_currency_legal(val_nuevo_total)
            porcentaje_calc = round((val_adicion / (getattr(contrato, "valor_inicial", None) or val_anterior or 1.0)) * 100, 2)

            cdp_fecha_raw = adicion_data.get("cdp_fecha") or ""
            cdp_fecha_texto = str(cdp_fecha_raw)
            if cdp_fecha_raw:
                try:
                    d_obj = datetime.strptime(str(cdp_fecha_raw)[:10], "%Y-%m-%d").date()
                    cdp_fecha_texto = f"{d_obj.day} de {MESES.get(d_obj.month, '')} de {d_obj.year}"
                except Exception:
                    pass

            fecha_adic_raw = adicion_data.get("fecha_adicion") or datetime.now().strftime("%Y-%m-%d")
            fecha_adicion_texto = str(fecha_adic_raw)
            try:
                d_fa = datetime.strptime(str(fecha_adic_raw)[:10], "%Y-%m-%d").date()
                fecha_adicion_texto = f"{d_fa.day} de {MESES.get(d_fa.month, '')} de {d_fa.year}"
            except Exception:
                pass

            c = contrato.contratista
            contratista_nom = adicion_data.get("contratista_nombre") or (c.nombre_o_razon_social if c else "CONTRATISTA")
            raw_contratista_doc = adicion_data.get("contratista_documento") or (c.numero_documento if c else "")
            clean_contratista_doc = re.sub(r"^(?:NIT\.?|C\.?C\.?)\s*", "", str(raw_contratista_doc), flags=re.IGNORECASE).strip()
            tipo_doc_contr = "NIT." if (c and c.tipo_persona and c.tipo_persona.value == "JURIDICA") else "C.C. No."

            rep_nom = adicion_data.get("representante_legal_nombre") or (c.representante_legal_nombre if c else None)
            rep_doc = adicion_data.get("representante_legal_documento") or (c.representante_legal_documento if c else None)
            clean_rep_doc = re.sub(r"^(?:C\.?C\.?|NIT\.?)\s*", "", str(rep_doc or ""), flags=re.IGNORECASE).strip() if rep_doc else ""
            clean_rep_nom = rep_nom or (contratista_nom if (c and c.tipo_persona and c.tipo_persona.value != "JURIDICA") else (contratista_nom if not rep_nom else ""))
            
            just_adic = adicion_data.get("justificacion") or "Garantizar la culminación satisfactoria del objeto contractual."

            fecha_dict = addition_agent.format_legal_date(fecha_adic_raw)
            dia_letras = fecha_dict["dia_letras"]
            dia_numeros = fecha_dict["dia_numeros"]
            mes_nombre = fecha_dict["mes"]
            ano_num = fecha_dict["ano"]

            tipologia_raw = str(getattr(getattr(contrato, "tipologia", None), "value", getattr(contrato, "tipologia", "suministro"))).lower()
            if "obra" in tipologia_raw:
                tipo_desc = "obra"
            elif "arrendamiento" in tipologia_raw:
                tipo_desc = "arrendamiento"
            elif "servicio" in tipologia_raw or "prestacion" in tipologia_raw:
                tipo_desc = "prestación de servicios"
            else:
                tipo_desc = "suministro"

            context = build_contract_context(contrato)
            context.update({
                "NUMERO_ADICION": str(num_adicion),
                "ADICION_NUMERO": str(num_adicion),
                "NUMERO DE ADICION": str(num_adicion),
                
                # EL VALOR DE LA ADICIÓN SE OBTIENE ESTRICTAMENTE DEL CDP
                "VALOR_ADICION": val_num_str,
                "VALOR ADICION": val_num_str,
                "VALOR_ADICION_NUMEROS": val_num_str,
                "VALOR ADICION NUMEROS": val_num_str,
                "VALOR_ADICION_NUMERO": val_num_str,
                "VALOR ADICION NUMERO": val_num_str,
                "VALOR_ADICION_LETRAS": val_letras_str,
                "VALOR ADICION LETRAS": val_letras_str,
                "VALOR_ADICION_LETRA": val_letras_str,
                "VALOR ADICION LETRA": val_letras_str,
                "VALOR_ADICION_EN_LETRAS": val_letras_str,
                "VALOR ADICION EN LETRAS": val_letras_str,
                "VALOR_ADICION_COP": val_num_str,
                "VALOR_CDP": val_num_str,
                "VALOR CDP": val_num_str,
                "VALOR_RESPALDO_CDP": val_num_str,
                "VALOR RESPALDO CDP": val_num_str,

                # En minuta de adición, VALOR se refiere al valor adicionado por el CDP (no al total del contrato)
                "VALOR": val_num_str,
                "VALOR_NUMEROS": val_num_str,
                "VALOR_COP": val_num_str,
                "VALOR_LETRAS": val_letras_str,
                "VALOR_EN_LETRAS": val_letras_str,

                # Valores acumulados consolidados
                "VALOR_ANTERIOR": val_ant_str,
                "VALOR ANTERIOR": val_ant_str,
                "VALOR_NUEVO_TOTAL": val_nuevo_str,
                "VALOR NUEVO TOTAL": val_nuevo_str,
                "NUEVO_VALOR_TOTAL": val_nuevo_str,
                "VALOR_TOTAL_CONTRATO": val_nuevo_str,
                "VALOR_TOTAL": val_nuevo_str,
                "NUEVO_VALOR_TOTAL_LETRAS": val_nuevo_letras,
                "PORCENTAJE_ADICION": f"{porcentaje_calc}%",

                # Justificación técnica
                "JUSTIFICACION": just_adic,
                "JUSTIFICACION_ADICION": just_adic,
                "JUSTIFICACION ADICION": just_adic,
                "JUSTIFICACION_DE_LA_ADICION": just_adic,
                "JUSTIFICACION DE LA ADICION": just_adic,
                "JUSTIFICACION_TECNICA": just_adic,
                "JUSTIFICACION TECNICA": just_adic,

                # CDP
                "CDP_NUMERO": str(adicion_data.get("cdp_numero") or "000"),
                "CDP NUMERO": str(adicion_data.get("cdp_numero") or "000"),
                "NUMERO_CDP": str(adicion_data.get("cdp_numero") or "000"),
                "NUMERO CDP": str(adicion_data.get("cdp_numero") or "000"),
                "CDP": str(adicion_data.get("cdp_numero") or "000"),
                "CDP_FECHA": cdp_fecha_texto,
                "CDP FECHA": cdp_fecha_texto,
                "FECHA_CDP": cdp_fecha_texto,
                "FECHA CDP": cdp_fecha_texto,
                "CDP_RUBRO": str(adicion_data.get("cdp_rubro") or ""),
                "CDP RUBRO": str(adicion_data.get("cdp_rubro") or ""),
                "RUBRO_CDP": str(adicion_data.get("cdp_rubro") or ""),
                "CDP_RUBRO_NOMBRE": str(adicion_data.get("cdp_rubro_nombre") or ""),

                # Fechas
                "FECHA_ADICION": fecha_adicion_texto,
                "FECHA": fecha_adicion_texto,

                # Partes contractuales con documentos limpios
                "CONTRATISTA": contratista_nom,
                "CONTRATISTA_NOMBRE": contratista_nom,
                "DOCUMENTO": clean_contratista_doc or raw_contratista_doc,
                "NIT": clean_contratista_doc or raw_contratista_doc,
                "CONTRATISTA_DOCUMENTO": clean_contratista_doc or raw_contratista_doc,
                "REPRESENTANTE_LEGAL": clean_rep_nom,
                "REPRESENTANTE LEGAL": clean_rep_nom,
                "NOMBRE_REPRESENTANTE_LEGAL": clean_rep_nom,
                "NOMBRE REPRESENTANTE LEGAL": clean_rep_nom,
                "REPRESENTANTE": clean_rep_nom,
                "DOCUMENTO_REPRESENTANTE": clean_rep_doc or clean_contratista_doc,
                "DOCUMENTO REPRESENTANTE": clean_rep_doc or clean_contratista_doc,
                "DOCUMENTO_REPRESENTANTE_LEGAL": clean_rep_doc or clean_contratista_doc,
                "DOCUMENTO REPRESENTANTE LEGAL": clean_rep_doc or clean_contratista_doc,
                "NUMERO_DOCUMENTO_REPRESENTANTE_LEGAL": clean_rep_doc or clean_contratista_doc,
                "NUMERO DOCUMENTO REPRESENTANTE LEGAL": clean_rep_doc or clean_contratista_doc,
                "NUMERO_DOCUMENTO_REPRESENTANTE": clean_rep_doc or clean_contratista_doc,
                "NUMERO DOCUMENTO REPRESENTANTE": clean_rep_doc or clean_contratista_doc,
                "CEDULA_REPRESENTANTE_LEGAL": clean_rep_doc or clean_contratista_doc,
                "CEDULA REPRESENTANTE LEGAL": clean_rep_doc or clean_contratista_doc,
                "CEDULA_REPRESENTANTE": clean_rep_doc or clean_contratista_doc,
                "CEDULA REPRESENTANTE": clean_rep_doc or clean_contratista_doc,
                "CC_REPRESENTANTE_LEGAL": clean_rep_doc or clean_contratista_doc,
                "CC REPRESENTANTE LEGAL": clean_rep_doc or clean_contratista_doc,
                "DIA_LETRAS": dia_letras,
                "DIA LETRAS": dia_letras,
                "DIA_EN_LETRAS": dia_letras,
                "DIA EN LETRAS": dia_letras,
                "DIA_NUMEROS": dia_numeros,
                "DIA NUMEROS": dia_numeros,
                "DIA_EN_NUMEROS": dia_numeros,
                "DIA EN NUMEROS": dia_numeros,
                "DIA": dia_numeros,
                "MES": mes_nombre,
                "MES_NOMBRE": mes_nombre,
                "MES NOMBRE": mes_nombre,
                "MES_EN_LETRAS": mes_nombre,
                "MES EN LETRAS": mes_nombre,
                "AÑO": ano_num,
                "ANO": ano_num,
                "ANIO": ano_num,
                "AÑO_NUMERO": ano_num,
                "ANO_NUMERO": ano_num,
                "FECHA_FIRMA": fecha_dict["texto_completo"],
                "FECHA_CONSTANCIA": fecha_dict["texto_completo"],
            })

            replace_placeholders_in_document(doc, context)

            # Ajuste dinámico de encabezado y tipología si la plantilla los tiene semi-fijos
            for p in doc.paragraphs:
                p_text = p.text
                if "ADICIÓN NRO." in p_text.upper() or "ADICION NRO." in p_text.upper():
                    new_t = re.sub(r"ADICI[OÓ]N\s+NRO\.?\s*\d*", f"ADICIÓN NRO. {num_adicion}", p_text, flags=re.IGNORECASE)
                    if new_t != p_text:
                        p.text = new_t
                if "CONTRATO DE SUMINISTRO ESTÁN PRÓXIMOS A AGOTARSE" in p_text.upper() and tipo_desc != "suministro":
                    p.text = p_text.replace("contrato de suministro", f"contrato de {tipo_desc}").replace("CONTRATO DE SUMINISTRO", f"CONTRATO DE {tipo_desc.upper()}")

            # Estandarización tipográfica obligatoria: Letra tipo Arial tamaño 12 en todo el contenido escrito
            enforce_arial_12_typography(doc)

            safe_num = (contrato.numero_contrato or "ESP").replace("/", "-").replace(" ", "_")
            output_filename = f"Minuta_Adicion_{safe_num}_Adic{num_adicion}.docx"
            output_path = settings.GENERATED_DIR / output_filename
            doc.save(str(output_path))
            logger.info(f"Minuta de adición generada exitosamente con plantilla ({'PERSONALIZADA' if is_custom else 'OFICIAL'}): {output_path}")


            if db_session:
                relative_path = str(output_path.relative_to(settings.BASE_DIR))
                db_doc = Documento(
                    contrato_id=contrato.id,
                    contratista_id=contrato.contratista_id,
                    tipo_documento=TipoDocumento.MINUTA_DOCX,
                    categoria=CategoriaDocumento.GENERADO_SISTEMA,
                    nombre_archivo_original=output_filename,
                    nombre_archivo_almacenado=output_filename,
                    ruta_relativa=relative_path,
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    tamano_bytes=output_path.stat().st_size,
                    datos_extraidos_json={"template_type": "ADICION", "adicion_data": adicion_data}
                )
                db_session.add(db_doc)
                db_session.commit()
                db_session.refresh(db_doc)

            return output_path
    except Exception as e_tpl:
        logger.warning(f"Aviso al generar adición desde plantilla: {e_tpl}. Usando generador estándar.")

    # 2. Respaldo: Generador procedimental existente
    from app.services.agents.addition_agent import addition_agent, MESES

    doc = docx.Document()
    
    # Configuración de página: Carta y márgenes estándar
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    section.header_distance = Inches(0.4)
    section.footer_distance = Inches(0.4)

    # Configuración de estilo Normal (Arial 11pt)
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Arial'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(15, 23, 42)

    # 1. ENCABEZADO CON LOGO DE ESPY
    header = section.header
    header_p = header.paragraphs[0]
    header_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    header_p.paragraph_format.space_after = Pt(2)

    # Buscar logo oficial
    logo_candidates = [
        settings.BASE_DIR / "frontend" / "assets" / "logo.png",
        settings.BASE_DIR / "backend" / "templates" / "assets" / "logo.png",
        Path("c:/Users/Usuario/Documents/ESPY_Contratacion_Automatizada/frontend/assets/logo.png")
    ]
    logo_found = None
    for cand in logo_candidates:
        if cand.exists():
            logo_found = cand
            break

    if logo_found:
        try:
            run_logo = header_p.add_run()
            run_logo.add_picture(str(logo_found), height=Inches(0.65))
        except Exception as e_logo:
            logger.warning(f"Aviso agregando logo a minuta de adición: {e_logo}")
            run_txt = header_p.add_run("ESPY - Empresa de Servicios Públicos de Yolombó E.S.P.")
            run_txt.bold = True

    # Barra decorativa de color corporativo bajo el encabezado
    p_line = header.add_paragraph()
    p_line.paragraph_format.space_before = Pt(2)
    p_line.paragraph_format.space_after = Pt(0)
    # Borde inferior verde / azul corporativo en XML
    pPr = p_line._p.get_or_add_pPr()
    pBdr = parse_xml(
        r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        r'<w:bottom w:val="single" w:sz="16" w:space="1" w:color="0ea5e9"/>'
        r'</w:pBdr>'
    )
    pPr.append(pBdr)

    # 2. PIE DE PÁGINA INSTITUCIONAL OFICIAL
    footer = section.footer
    footer_p = footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_p.paragraph_format.space_before = Pt(4)
    footer_p.paragraph_format.line_spacing = 1.05

    # Línea divisoria en pie de página
    f_pPr = footer_p._p.get_or_add_pPr()
    f_pBdr = parse_xml(
        r'<w:pBdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        r'<w:top w:val="single" w:sz="12" w:space="2" w:color="10b981"/>'
        r'</w:pBdr>'
    )
    f_pPr.append(f_pBdr)

    r_f1 = footer_p.add_run("EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBÓ – NIT. 811015112-4\n")
    r_f1.bold = True
    r_f1.font.size = Pt(8.5)
    r_f1.font.color.rgb = RGBColor(30, 41, 59)

    r_f2 = footer_p.add_run("TELÉFONO: 3206976172\nserviciospublicosyol@hotmail.com\nCalle Colombia 20 #20 - 128 Yolombó – Antioquia")
    r_f2.font.size = Pt(8.0)
    r_f2.font.color.rgb = RGBColor(71, 85, 105)

    # -------------------------------------------------------------
    # CUERPO DEL DOCUMENTO
    # -------------------------------------------------------------
    num_adicion = adicion_data.get("numero_adicion", 1)
    num_contrato = contrato.numero_contrato or "CPS-000-2026"
    objeto_contrato = (contrato.objeto or "").upper()
    
    # Datos económicos
    val_adicion = float(adicion_data.get("valor_adicion", 0.0))
    val_num_str, val_letras_str, _ = addition_agent.format_currency_legal(val_adicion)
    
    # Datos CDP
    cdp_num = adicion_data.get("cdp_numero") or "000"
    cdp_fecha_raw = adicion_data.get("cdp_fecha") or ""
    if cdp_fecha_raw:
        try:
            d_obj = datetime.strptime(str(cdp_fecha_raw)[:10], "%Y-%m-%d").date()
            cdp_fecha_texto = f"{d_obj.day} de {MESES.get(d_obj.month, '')} de {d_obj.year}"
        except Exception:
            cdp_fecha_texto = str(cdp_fecha_raw)
    else:
        cdp_fecha_texto = "la vigencia"

    # Datos Contratista
    c = contrato.contratista
    contratista_nom = adicion_data.get("contratista_nombre") or (c.nombre_o_razon_social if c else "CONTRATISTA")
    contratista_doc = adicion_data.get("contratista_documento") or (c.numero_documento if c else "")
    tipo_doc_contr = "NIT." if (c and c.tipo_persona and c.tipo_persona.value == "JURIDICA") else "C.C. No."
    
    # Representante Legal
    rep_nom = adicion_data.get("representante_legal_nombre") or (c.representante_legal_nombre if c else None)
    rep_doc = adicion_data.get("representante_legal_documento") or (c.representante_legal_documento if c else None)

    # 3. TÍTULO PRINCIPAL
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(8)
    p_title.paragraph_format.space_after = Pt(2)
    p_title.paragraph_format.line_spacing = 1.15
    
    r_tit1 = p_title.add_run(f"ADICIÓN NRO. {num_adicion}\n")
    r_tit1.bold = True
    r_tit1.font.size = Pt(12)
    
    r_tit2 = p_title.add_run(f"{num_contrato}\n")
    r_tit2.bold = True
    r_tit2.font.size = Pt(11.5)
    
    r_tit3 = p_title.add_run(f'"{objeto_contrato}"')
    r_tit3.bold = True
    r_tit3.font.size = Pt(10.5)

    # 4. PREÁMBULO / COMPARECENCIA
    p_preambulo = doc.add_paragraph()
    p_preambulo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_preambulo.paragraph_format.space_before = Pt(12)
    p_preambulo.paragraph_format.space_after = Pt(10)
    p_preambulo.paragraph_format.line_spacing = 1.15

    r_pre = p_preambulo.add_run("Entre los suscritos: ")
    
    r_ger = p_preambulo.add_run("CAROLINA GIRALDO GÓMEZ")
    r_ger.bold = True
    
    r_pre2 = p_preambulo.add_run(
        ", mayor de edad, identificado con la cédula de ciudadanía número CC. No.1.152.451.796 de Medellín (Antioquia), "
        "en su calidad de Gerente General de la Empresa, y debidamente autorizado para contratar de acuerdo al Numeral 8 del "
        "artículo 3 del manual de contratación aprobado por la Junta Directiva de fecha diciembre 19 de 2011, obrando en "
        "calidad de Representante Legal de "
    )
    
    r_esp = p_preambulo.add_run(
        "LA EMPRESA MUNICIPAL DE ACUEDUCTO, ALCANTARILLADO Y ASEO DEL MUNICIPIO DE YOLOMBO E.S.P EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO"
    )
    r_esp.bold = True
    
    r_pre3 = p_preambulo.add_run(", con el NIT. 811.015.112-4 y que en el texto de este contrato se denominará ")
    
    r_contratante = p_preambulo.add_run("CONTRATANTE")
    r_contratante.bold = True
    
    r_pre4 = p_preambulo.add_run(f", por una parte, y por ")
    
    r_contratista = p_preambulo.add_run(contratista_nom)
    r_contratista.bold = True
    
    r_pre5 = p_preambulo.add_run(f", {tipo_doc_contr} {contratista_doc}")
    
    if rep_nom and rep_nom.strip():
        r_rep1 = p_preambulo.add_run(", representada legalmente por el señor(a) ")
        r_rep2 = p_preambulo.add_run(rep_nom.strip())
        r_rep2.bold = True
        r_rep3 = p_preambulo.add_run(f", C.C. {rep_doc or 'N/A'}")
    
    r_pre6 = p_preambulo.add_run(
        ", y quien para efectos de este contrato se denominará "
    )
    r_contratista_tag = p_preambulo.add_run("EL CONTRATISTA")
    r_contratista_tag.bold = True
    
    p_preambulo.add_run(
        ", hemos convenido en celebrar la presente adición contractual, con base en las siguientes:"
    )

    # 5. CONSIDERACIONES
    p_cons_tit = doc.add_paragraph()
    p_cons_tit.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cons_tit.paragraph_format.space_before = Pt(8)
    p_cons_tit.paragraph_format.space_after = Pt(8)
    r_c_tit = p_cons_tit.add_run("CONSIDERACIONES")
    r_c_tit.bold = True
    r_c_tit.font.size = Pt(11)

    # Tipología para consideraciones
    tipologia_raw = str(contrato.tipologia.value if hasattr(contrato.tipologia, 'value') else contrato.tipologia).lower()
    if "suministro" in tipologia_raw:
        tipo_desc = "suministro"
    elif "obra" in tipologia_raw:
        tipo_desc = "obra"
    elif "arrendamiento" in tipologia_raw:
        tipo_desc = "arrendamiento"
    else:
        tipo_desc = "prestación de servicios"

    val_inicial_contrato = getattr(contrato, "valor_inicial", None) or (contrato.valor_total - (contrato.adicion_1 or 0.0))
    justificacion_adicion = adicion_data.get("justificacion") or addition_agent.generate_justification(
        numero_contrato=num_contrato,
        objeto_contrato=objeto_contrato,
        tipologia=tipologia_raw,
        valor_adicion=val_adicion,
        valor_inicial=val_inicial_contrato,
        contratista_nombre=contratista_nom
    )

    # Dividir párrafos de la justificación técnica estructurada en apartados
    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", (justificacion_adicion or "").strip()) if b.strip()]
    consideraciones_items = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if re.match(r"^\d+\.\s+", lines[0]) and len(lines) > 1:
            header = re.sub(r"^\d+\.\s*", "", lines[0]).rstrip(":")
            body = " ".join(lines[1:])
            clean_p = f"Que en relación con {header.lower()}: {body}"
        else:
            clean_p = " ".join(lines)
            clean_p = re.sub(r"^\d+\.\s*", "", clean_p)
            if not clean_p.startswith("Que ") and not clean_p.startswith("Que:"):
                clean_p = f"Que {clean_p[0].lower() + clean_p[1:]}"
        consideraciones_items.append(clean_p.rstrip(".") + ".")

    consideraciones_items.extend([
        "Que el contrato, hasta la fecha, se ha venido ejecutando a cabalidad en los términos y especificaciones previstos.",
        "Que de conformidad con los artículos 31 y 32 de la Ley 142 de 1994, los actos y contratos de las Empresas de Servicios Públicos Domiciliarios se rigen por las normas del derecho privado, en concordancia con los principios de la función administrativa del artículo 209 de la Carta Política y la gestión fiscal eficiente.",
        f"Que se adicionará el valor del presente contrato en la suma de {val_num_str} ({val_letras_str}), amparando la suficiencia presupuestal indispensable para la culminación cabal y oportuna de su objeto en el plazo establecido.",
        f"Que tal adición está debidamente amparada en el Certificado de Disponibilidad Presupuestal Nro. {cdp_num} del {cdp_fecha_texto}.",
        "Que la supervisión designada por la entidad evaluó la pertinencia operativa y avaló íntegramente la presente adición presupuestal.",
        "Que el análisis de riesgos, la forma de pago y las cláusulas restantes del contrato principal permanecen inalteradas e incólumes."
    ])

    for item in consideraciones_items:
        p_item = doc.add_paragraph()
        p_item.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_item.paragraph_format.left_indent = Inches(0.25)
        p_item.paragraph_format.space_before = Pt(2)
        p_item.paragraph_format.space_after = Pt(4)
        p_item.paragraph_format.line_spacing = 1.15
        
        r_bullet = p_item.add_run("• ")
        r_bullet.bold = True
        p_item.add_run(item)

    # 6. ACUERDOS
    p_acuerdan_intro = doc.add_paragraph()
    p_acuerdan_intro.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_acuerdan_intro.paragraph_format.space_before = Pt(8)
    p_acuerdan_intro.paragraph_format.space_after = Pt(6)
    p_acuerdan_intro.add_run("Por lo anterior, las partes:")

    p_acuerdan = doc.add_paragraph()
    p_acuerdan.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_acuerdan.paragraph_format.space_before = Pt(4)
    p_acuerdan.paragraph_format.space_after = Pt(8)
    r_ac = p_acuerdan.add_run("ACUERDAN")
    r_ac.bold = True
    r_ac.font.size = Pt(11)

    # PRIMERO
    p_primero = doc.add_paragraph()
    p_primero.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_primero.paragraph_format.space_before = Pt(4)
    p_primero.paragraph_format.space_after = Pt(6)
    p_primero.paragraph_format.line_spacing = 1.15
    
    r_p1 = p_primero.add_run("PRIMERO: ADICIONAR ")
    r_p1.bold = True
    p_primero.add_run(f"el valor del presente contrato en la suma de ")
    r_val = p_primero.add_run(f"{val_num_str} ({val_letras_str})")
    r_val.bold = True
    p_primero.add_run(f", amparada en el certificado de disponibilidad presupuestal Nro. {cdp_num} del {cdp_fecha_texto}., de conformidad con los motivos expuestos.")

    # SEGUNDO
    p_segundo = doc.add_paragraph()
    p_segundo.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_segundo.paragraph_format.space_before = Pt(4)
    p_segundo.paragraph_format.space_after = Pt(12)
    p_segundo.paragraph_format.line_spacing = 1.15
    
    r_s1 = p_segundo.add_run("SEGUNDO: ")
    r_s1.bold = True
    p_segundo.add_run("Las cláusulas restantes del contrato no serán modificadas.")

    # 7. CONSTANCIA DE FIRMA Y FECHA
    fecha_adicion_raw = adicion_data.get("fecha_adicion")
    fecha_dict = addition_agent.format_legal_date(fecha_adicion_raw)
    
    p_constancia = doc.add_paragraph()
    p_constancia.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_constancia.paragraph_format.space_before = Pt(8)
    p_constancia.paragraph_format.space_after = Pt(28)
    p_constancia.paragraph_format.line_spacing = 1.15
    p_constancia.add_run(
        f"Para constancia se firma en el municipio de Yolombó el día {fecha_dict['dia_letras'].lower()} "
        f"({fecha_dict['dia_numeros']}) del mes de {fecha_dict['mes']} de {fecha_dict['ano']}."
    )

    # 8. FIRMAS
    table_firmas = doc.add_table(rows=1, cols=2)
    table_firmas.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_firmas.autofit = False

    cell_left = table_firmas.rows[0].cells[0]
    cell_right = table_firmas.rows[0].cells[1]
    cell_left.width = Inches(3.2)
    cell_right.width = Inches(3.2)

    # Contratante
    p_f_left = cell_left.paragraphs[0]
    p_f_left.paragraph_format.space_before = Pt(0)
    p_f_left.paragraph_format.space_after = Pt(2)
    p_f_left.paragraph_format.line_spacing = 1.05
    p_f_left.add_run("_________________________________________\n")
    r_cg = p_f_left.add_run("CAROLINA GIRALDO GÓMEZ\n")
    r_cg.bold = True
    p_f_left.add_run("Gerente General - Contratante\n")
    p_f_left.add_run("Empresa de Servicios Públicos de Yolombó E.S.P.")

    # Contratista
    p_f_right = cell_right.paragraphs[0]
    p_f_right.paragraph_format.space_before = Pt(0)
    p_f_right.paragraph_format.space_after = Pt(2)
    p_f_right.paragraph_format.line_spacing = 1.05
    p_f_right.add_run("_________________________________________\n")
    r_cn = p_f_right.add_run(f"{contratista_nom}\n")
    r_cn.bold = True
    if rep_nom and rep_nom.strip():
        p_f_right.add_run(f"{rep_nom.strip()}\n")
        p_f_right.add_run(f"Representante Legal - C.C. {rep_doc or ''}\n")
    p_f_right.add_run("Contratista")

    # Guardar archivo
    safe_num = contrato.numero_contrato.replace("/", "-").replace(" ", "_")
    output_filename = f"ADICION_{num_adicion}_{safe_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    output_path = settings.GENERATED_DIR / output_filename
    doc.save(str(output_path))
    logger.info(f"Minuta de adición Word generada exitosamente: {output_path}")

    # Registrar en base de datos si se proporcionó db_session
    if db_session:
        try:
            rel_path = str(output_path.relative_to(settings.BASE_DIR))
            db_doc = Documento(
                contrato_id=contrato.id,
                contratista_id=contrato.contratista_id,
                tipo_documento=TipoDocumento.ADICION_DOCX,
                categoria=CategoriaDocumento.GENERADO_SISTEMA,
                nombre_archivo_original=output_filename,
                nombre_archivo_almacenado=output_filename,
                ruta_relativa=rel_path,
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                tamano_bytes=output_path.stat().st_size,
                datos_extraidos_json={"numero_adicion": num_adicion, "valor_adicion": val_adicion, "cdp_numero": cdp_num}
            )
            db_session.add(db_doc)
            db_session.commit()
            db_session.refresh(db_doc)
        except Exception as e_db:
            logger.warning(f"Aviso registrando Documento de adición en DB: {e_db}")

    return output_path

