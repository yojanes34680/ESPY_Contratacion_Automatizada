"""Document parser service for extracting text from PDF (digital & scanned OCR) and Word (.docx) files."""
from pathlib import Path
from typing import Optional, Union
import docx
import pypdf
import re
from app.utils.logger import logger

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import pypdfium2 as pdfium
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    HAS_OCR = True
    _ocr_engine = None

    def get_ocr_engine():
        global _ocr_engine
        if _ocr_engine is None:
            _ocr_engine = RapidOCR()
        return _ocr_engine
except ImportError:
    HAS_OCR = False

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
import gc

def extract_text_from_pdf_ocr(file_path: Path, max_pages: int = 25) -> str:
    """
    Ejecuta OCR sobre las páginas escaneadas del PDF utilizando pypdfium2 y RapidOCR.
    Soporta expedientes de hasta 25 páginas y aplica escaneo focalizado en formularios DIAN (RUT).
    """
    if not HAS_OCR:
        logger.warning("RapidOCR o pypdfium2 no están disponibles para OCR local.")
        return ""

    cache_file = file_path.with_suffix(".ocr.txt")
    if cache_file.exists():
        try:
            cached = cache_file.read_text(encoding="utf-8")
            if cached and len(cached.strip()) > 20:
                logger.info(f"Usando texto OCR en caché para {file_path.name}")
                return cached
        except Exception:
            pass

    try:
        engine = get_ocr_engine()
        doc = pdfium.PdfDocument(str(file_path))
        num_pages = len(doc)
        pages_to_process = min(num_pages, max_pages)

        logger.info(f"Ejecutando OCR sobre {pages_to_process} páginas de PDF escaneado: {file_path.name}...")
        extracted_pages = []

        for i in range(pages_to_process):
            try:
                page = doc[i]
                # Renderizar a scale=1.5 asegurando formato RGB (3 canales) para RapidOCR
                pil_image = page.render(scale=1.5).to_pil().convert("RGB")

                img_arr = np.array(pil_image)
                ocr_res, _ = engine(img_arr)
                del img_arr

                page_lines = []
                if ocr_res:
                    # Agrupar espacialmente por líneas visuales horizontales para evitar desfases o inversiones en tablas/columnas
                    det_items = []
                    for r in ocr_res:
                        if not r or len(r) < 2 or not str(r[1]).strip():
                            continue
                        pts = r[0]
                        txt = str(r[1]).strip()
                        min_x = min(p[0] for p in pts)
                        min_y = min(p[1] for p in pts)
                        max_y = max(p[1] for p in pts)
                        height = max(1.0, max_y - min_y)
                        center_y = (min_y + max_y) / 2.0
                        det_items.append({
                            "txt": txt,
                            "min_x": min_x,
                            "center_y": center_y,
                            "height": height
                        })

                    # Ordenar verticalmente por coordenada Y
                    det_items.sort(key=lambda it: it["center_y"])

                    # Agrupar en la misma línea visual horizontal con tolerancia estricta
                    curr_line = []
                    curr_y = None
                    for it in det_items:
                        y_tol = min(10.0, it["height"] * 0.45)
                        if curr_y is None:
                            curr_line = [it]
                            curr_y = it["center_y"]
                        elif abs(it["center_y"] - curr_y) <= y_tol:
                            curr_line.append(it)
                            curr_y = sum(x["center_y"] for x in curr_line) / len(curr_line)
                        else:
                            curr_line.sort(key=lambda x: x["min_x"])
                            page_lines.append(" | ".join(x["txt"] for x in curr_line))
                            curr_line = [it]
                            curr_y = it["center_y"]
                    if curr_line:
                        curr_line.sort(key=lambda x: x["min_x"])
                        page_lines.append(" | ".join(x["txt"] for x in curr_line))

                # Si es página de formulario DIAN (RUT), realizar recorte focalizado de casillas clave
                p_text_prelim = " ".join(page_lines).upper()
                is_rut_form = bool(re.search(r'\bDIAN\b', p_text_prelim)) and any(k in p_text_prelim for k in ["001", "REGISTRO UNICO", "REGISTRO ÚNICO", "TRIBUTARIO", "RUT", "FORMULARIO"])
                if is_rut_form or any(k in p_text_prelim for k in ["REGISTRO UNICO TRIBUTARIO", "REGISTRO ÚNICO TRIBUTARIO"]):
                    W, H = pil_image.size
                    from PIL import ImageOps

                    # 1. Recorte Casilla 5 (NIT) y 6 (DV) en RUT
                    try:
                        nit_crop = pil_image.crop((int(0.04 * W), int(0.20 * H), int(0.45 * W), int(0.27 * H)))
                        nit_crop_padded = ImageOps.expand(nit_crop, border=40, fill='white')
                        nit_arr = np.array(nit_crop_padded)
                        res_nit, _ = engine(nit_arr)
                        del nit_arr
                        if res_nit:
                            for r in res_nit:
                                txt = r[1].strip()
                                digits = re.sub(r"[^\d]", "", txt)
                                if len(digits) >= 4:
                                    page_lines.append(f"RUT_CASILLA_5_NIT_DETECTADO: {txt}")
                    except Exception as e_nit:
                        logger.debug(f"Aviso en crop NIT: {e_nit}")

                    # 2. Recorte Zona de Contacto y Teléfonos (Casillas 38 a 45)
                    try:
                        contact_crop = pil_image.crop((int(0.04 * W), int(0.40 * H), int(0.95 * W), int(0.55 * H)))
                        contact_crop_padded = ImageOps.expand(contact_crop, border=35, fill='white')
                        contact_arr = np.array(contact_crop_padded)
                        res_contact, _ = engine(contact_arr)
                        del contact_arr
                        if res_contact:
                            c_texts = [r[1].strip() for r in res_contact if len(r[1].strip()) >= 2]
                            if c_texts:
                                page_lines.append(f"RUT_CONTACTO_UBICACION_BLOQUE: {' | '.join(c_texts)}")
                    except Exception as e_c:
                        logger.debug(f"Aviso en crop contacto: {e_c}")

                    # 3. Recorte Casilla Representación Legal si es página 3
                    if "REPRESENTA" in p_text_prelim or i == 2:
                        try:
                            rep_crop = pil_image.crop((int(0.04 * W), int(0.26 * H), int(0.95 * W), int(0.42 * H)))
                            rep_crop_padded = ImageOps.expand(rep_crop, border=35, fill='white')
                            rep_arr = np.array(rep_crop_padded)
                            res_rep, _ = engine(rep_arr)
                            del rep_arr
                            if res_rep:
                                rep_texts = [r[1].strip() for r in res_rep if len(r[1].strip()) > 2]
                                if rep_texts:
                                    page_lines.append(f"RUT_REPRESENTACION_LEGAL_BLOQUE: {' | '.join(rep_texts)}")
                        except Exception as e_rep:
                            logger.debug(f"Aviso en crop rep legal: {e_rep}")

                del pil_image
                gc.collect()

                if page_lines:
                    extracted_pages.append(f"=== PÁGINA {i+1} ===\n" + "\n".join(page_lines))
            except Exception as e_p:
                logger.warning(f"Error procesando página {i+1} en OCR: {e_p}")
                gc.collect()

        full_result = "\n\n".join(extracted_pages)
        if full_result and len(full_result.strip()) > 50:
            try:
                cache_file.write_text(full_result, encoding="utf-8")
            except Exception:
                pass
        return full_result
    except Exception as e:
        logger.error(f"Error en OCR de PDF {file_path}: {e}")
        return ""

def extract_text_from_pdf(file_path: Union[Path, str]) -> str:
    """
    Extrae texto de un archivo PDF preservando delimitadores de página. Si no contiene
    capa de texto digital (escaneado), activa automáticamente el motor de OCR local.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo PDF no encontrado: {file_path}")

    text_parts = []

    # 1. Intentar primero con pdfplumber si está disponible
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text and len(page_text.strip()) > 5:
                        text_parts.append(f"=== PÁGINA {i+1} ===\n" + page_text.strip())
            if text_parts:
                digital_text = "\n\n".join(text_parts).strip()
                if len(digital_text) >= 50:
                    return digital_text
        except Exception as e:
            logger.warning(f"Fallo extracción digital con pdfplumber ({e}), probando pypdf...")

    # 2. Intentar con pypdf
    try:
        reader = pypdf.PdfReader(str(file_path))
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text and len(page_text.strip()) > 5:
                text_parts.append(f"=== PÁGINA {i+1} ===\n" + page_text.strip())
        digital_text = "\n\n".join(text_parts).strip()
        if len(digital_text) >= 50:
            return digital_text
    except Exception as e:
        logger.warning(f"Fallo extracción digital con pypdf ({e}).")

    # 3. Si el texto digital está vacío o es casi nulo (< 50 caracteres), es un PDF escaneado -> Ejecutar OCR
    logger.info(f"El PDF '{file_path.name}' no tiene texto digital incrustado. Activando OCR inteligente...")
    ocr_text = extract_text_from_pdf_ocr(file_path)

    # 4. Respaldo general con Gemini Vision si el OCR devolvió vacío o insuficiente (< 40 caracteres)
    # en PDFs escaneados (ej. Propuestas Económicas, Cotizaciones o tablas donde RapidOCR falla)
    if len(ocr_text.strip()) < 40 and HAS_OCR:
        try:
            from app.config import settings
            from app.services.gemini_client import gemini_service
            if settings.GEMINI_API_KEY:
                client = gemini_service._get_client()
                if client:
                    doc_pdf = pdfium.PdfDocument(str(file_path))
                    pages_to_read = min(len(doc_pdf), 4)
                    vision_pages = []
                    from google.genai import types
                    for p_idx in range(pages_to_read):
                        page = doc_pdf[p_idx]
                        pil_img = page.render(scale=2.0).to_pil().convert("RGB")
                        import io
                        buf = io.BytesIO()
                        pil_img.save(buf, format="PNG")
                        img_bytes = buf.getvalue()
                        prompt = (
                            "Transcribe fiel e íntegramente todo el texto y tablas visibles de esta página del documento o propuesta económica/cotización. "
                            "Preserva las columnas de tablas (ej. Ítem, Descripción del bien/servicio, Cantidad, Valor unitario, Valor total) "
                            "sin omitir especificaciones técnicas ni dimensiones."
                        )
                        models_to_try = [settings.GEMINI_MODEL]
                        if "gemini-3.5-flash" not in models_to_try:
                            models_to_try.append("gemini-3.5-flash")
                        for m in models_to_try:
                            try:
                                resp = client.models.generate_content(
                                    model=m,
                                    contents=[
                                        types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                                        prompt
                                    ]
                                )
                                if resp and resp.text:
                                    vision_pages.append(f"=== PÁGINA {p_idx+1} (GEMINI VISION) ===\n" + resp.text.strip())
                                    break
                            except Exception as em:
                                logger.warning(f"Error en visión modelo {m}: {em}")
                    if vision_pages:
                        ocr_text = "\n\n".join(vision_pages).strip()
                        logger.info(f"Gemini Vision transcribió exitosamente {len(ocr_text)} caracteres de {file_path.name}")
        except Exception as e_gen_vis:
            logger.warning(f"Aviso en respaldo general Gemini Vision para {file_path.name}: {e_gen_vis}")

    # 4.1 Respaldo automático con Gemini Vision para documentos de identidad (Cédulas) o fotocopias borrosas
    is_cedula_doc = any(k in file_path.name.lower() for k in ["cedula", "cédula", "cc", "identificacion", "identificación", "documento"])
    ced_check = extract_colombian_cedula_data(ocr_text) if ocr_text else {}
    needs_vision_fallback = (is_cedula_doc or (ocr_text and "CEDULA" in ocr_text.upper())) and (
        not ced_check.get("numero_documento") or not ced_check.get("nombre_completo")
    )

    if needs_vision_fallback and HAS_OCR:
        try:
            doc_pdf = pdfium.PdfDocument(str(file_path))
            if len(doc_pdf) > 0:
                import io
                first_page = doc_pdf[0]
                pil_img = first_page.render(scale=2.0).to_pil().convert("RGB")
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                img_bytes = buf.getvalue()

                from app.services.gemini_client import gemini_service
                vis_res = gemini_service.extract_cedula_with_vision(img_bytes)
                if vis_res and (vis_res.get("numero_documento") or vis_res.get("nombre_completo")):
                    logger.info(f"Gemini Vision rescató datos de Cédula: {vis_res}")
                    vision_summary = (
                        f"\n=== LECTURA GEMINI VISION CEDULA ===\n"
                        f"NUMERO: {vis_res.get('numero_documento') or ''}\n"
                        f"NOMBRES: {vis_res.get('nombres') or ''}\n"
                        f"APELLIDOS: {vis_res.get('apellidos') or ''}\n"
                        f"NOMBRE COMPLETO: {vis_res.get('nombre_completo') or ''}\n"
                        f"FECHA EXPEDICION: {vis_res.get('fecha_expedicion') or ''}\n"
                        f"LUGAR EXPEDICION: {vis_res.get('lugar_expedicion') or ''}\n"
                    )
                    ocr_text = f"{ocr_text}\n{vision_summary}".strip()
        except Exception as e_vis:
            logger.warning(f"Aviso en respaldo Gemini Vision para PDF {file_path.name}: {e_vis}")

    if ocr_text.strip():
        logger.info(f"OCR exitoso: {len(ocr_text)} caracteres extraídos del documento escaneado.")
        return ocr_text

    # Si todo falló, buscar si es texto sintético o pre-extraído
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            if ("%PDF" in content or "COMPROBANTE" in content or "=== PÁGINA" in content) and len(content.strip()) > 20:
                return content
    except Exception:
        pass

    return ""

def extract_text_from_docx(file_path: Union[Path, str]) -> str:
    """
    Extrae texto plano de un documento Word (.docx) leyendo párrafos y celdas de tablas.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo DOCX no encontrado: {file_path}")

    try:
        doc = docx.Document(str(file_path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        
        # Extraer también de tablas
        for table in doc.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    paragraphs.append(" | ".join(row_texts))

        return "\n".join(paragraphs)
    except Exception as e:
        logger.error(f"Error extrayendo texto de DOCX {file_path}: {e}")
        return ""

def extract_text_from_excel(file_path: Union[Path, str]) -> str:
    """
    Extrae texto de un archivo Excel (.xlsx / .xls) leyendo las celdas de las hojas.
    Útil para propuestas económicas estructuradas en hojas de cálculo.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Archivo Excel no encontrado: {file_path}")
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=True)
        lines = []
        for sheet_name in wb.sheetnames[:5]:
            ws = wb[sheet_name]
            lines.append(f"=== HOJA: {sheet_name} ===")
            row_count = 0
            for row in ws.iter_rows(values_only=True):
                if row_count > 300:
                    break
                row_vals = [str(cell).strip() for cell in row if cell is not None and str(cell).strip()]
                if row_vals:
                    lines.append(" | ".join(row_vals))
                    row_count += 1
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error extrayendo texto de Excel {file_path}: {e}")
        return ""

INVALID_PERSON_NAMES = {
    "CERTIFICADO", "DISPONIBILIDAD", "PRESUPUESTAL", "REPUBLICA", "COLOMBIA",
    "DEPARTAMENTO", "ANTIOQUIA", "MUNICIPIO", "YOLOMBO", "EMPRESA", "SERVICIOS",
    "PUBLICOS", "FORMULARIO", "REGISTRO", "UNICO", "TRIBUTARIO", "DIAN", "DIRECCION",
    "IMPUESTOS", "ADUANAS", "NACIONALES", "PERSONA", "JURIDICA", "NATURAL", "NIT",
    "CEDULA", "CIUDADANIA", "IDENTIFICACION", "PERSONAL", "PROPUESTA", "COTIZACION",
    "CONTRATO", "SUMINISTRO", "REPRESENTANTE", "LEGAL", "PRINCIPAL", "SUPLENTE", "FIRMA",
    "PAGINA", "PÁGINA", "HOJA", "CODDANA"
}

def is_valid_person_name(name: Optional[str]) -> bool:
    """
    Valida si un texto corresponde a un nombre de persona natural válido en Colombia.
    Retorna False si tiene menos de 2 palabras o si contiene palabras reservadas/documentales.
    """
    if not name or not isinstance(name, str):
        return False
    clean = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ\s]", " ", name).strip()
    words = [w.upper() for w in clean.split() if len(w) > 1]
    if len(words) < 2:
        return False
    for w in words:
        if w in INVALID_PERSON_NAMES:
            return False
    return True

def extract_colombian_cedula_data(text: str) -> dict:
    """
    Extrae con máxima precisión el número de documento y nombre completo (en orden NOMBRES APELLIDOS)
    de Cédulas de Ciudadanía colombianas en cualquiera de sus formatos:
    - Formato A: Cédula Digital / Policarbonato (MRZ reverso o etiquetas frente).
    - Formato B: Cédula Amarilla Tradicional de Hologramas (etiquetas debajo del valor o serial del código de barras).
    """
    result = {
        "tipo_documento": "CC",
        "numero_documento": None,
        "nombres": None,
        "apellidos": None,
        "nombre_completo": None,
        "fecha_expedicion": None,
        "lugar_expedicion": None
    }
    if not text:
        return result

    raw_text = text.strip()
    
    # -------------------------------------------------------------
    # A) EXTRACCIÓN DEL NÚMERO DE CÉDULA (numero_documento)
    # -------------------------------------------------------------
    cedula_num = None

    # Mecanismo 1 (MRZ Cédula Digital): Buscar r"C[0O]L\s*([0-9O]{6,11})<+"
    mrz_col = re.search(r"C[0O]L\s*([0-9O]{6,11})<+", raw_text, re.IGNORECASE)
    if mrz_col:
        c_cand = mrz_col.group(1).replace("O", "0").replace("o", "0")
        if 6 <= len(c_cand) <= 10:
            cedula_num = c_cand

    # Mecanismo 2 (Serial Código de Barras Cédula Amarilla): r"[A-Z0-9]+-\d+-\d+-[FMfm]-0*(\d{6,10})-\d{8}"
    if not cedula_num:
        barcode_serial = re.search(r"[A-Z0-9]+-\d+-\d+-[FMfm]-0*(\d{6,10})-\d{8}", raw_text)
        if barcode_serial:
            cedula_num = barcode_serial.group(1)

    # Mecanismo 3 (Etiquetas NUIP / NUMERO): r"(?:NUIP|N[UÚ]MERO|NRO)[\s:\.\-]*([0-9\.\s,]{6,14})"
    if not cedula_num:
        nuip_m = re.search(r"(?:NUIP|N[UÚ]MERO|NRO)[\s:\.\-]*([0-9\.\s,]{6,14})", raw_text, re.IGNORECASE)
        if nuip_m:
            clean_digits = re.sub(r"[^\d]", "", nuip_m.group(1))
            if 6 <= len(clean_digits) <= 10:
                cedula_num = clean_digits

    # Mecanismo 4 (Número con puntos de miles cerca al encabezado cuando el OCR no lee la palabra NUMERO)
    if not cedula_num:
        m4 = re.search(r"(?:CIUDADAN[IÍ]A|COLOMBIA)[\s\S]{1,150}?\b(\d{1,3}(?:\.\d{3}){1,3})\b", raw_text, re.IGNORECASE)
        if m4:
            clean_digits = re.sub(r"[^\d]", "", m4.group(1))
            if 6 <= len(clean_digits) <= 10:
                cedula_num = clean_digits

    # Fallback general para números de cédula aislados de 6 a 10 dígitos tras palabras clave de cédula
    if not cedula_num:
        m_gen = re.search(r"(?:CEDULA\s+DE\s+CIUDADANIA|C[EÉ]DULA)[\s\S]{1,100}?\b(\d{7,10})\b", raw_text, re.IGNORECASE)
        if m_gen:
            cedula_num = m_gen.group(1)

    if cedula_num:
        result["numero_documento"] = cedula_num

    # -------------------------------------------------------------
    # B) EXTRACCIÓN DEL NOMBRE COMPLETO (orden "NOMBRES APELLIDOS")
    # -------------------------------------------------------------
    # Mecanismo 1 (MRZ Cédula Digital):
    for l in raw_text.splitlines():
        if "<" in l and re.search(r"[A-Za-z]", l):
            cleaned_mrz = re.sub(r"[KkXx]<", "<<", l)
            m = re.search(r"([A-ZÑ]+(?:<[A-ZÑ]+)*)<<+([A-ZÑ]+(?:<[A-ZÑ]+)*)", cleaned_mrz)
            if m:
                ap_raw = m.group(1).replace("<", " ").strip()
                nom_raw = m.group(2).replace("<", " ").strip()
                apellidos = " ".join(ap_raw.split())
                nombres = " ".join(nom_raw.split())
                cand_full = f"{nombres} {apellidos}"
                if is_valid_person_name(cand_full):
                    result["apellidos"] = apellidos
                    result["nombres"] = nombres
                    result["nombre_completo"] = cand_full
                    break

    # Mecanismo 2 (Cédula Digital sin MRZ - Etiquetas ENCIMA del valor)
    if not result.get("nombre_completo"):
        ap_encima = re.search(r"Apellidos\s*[\n:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,40})", raw_text, re.IGNORECASE)
        nom_encima = re.search(r"Nombres\s*[\n:\s]+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{3,40})", raw_text, re.IGNORECASE)
        if ap_encima and nom_encima:
            ap_val = ap_encima.group(1).strip().split("\n")[0].strip()
            nom_val = nom_encima.group(1).strip().split("\n")[0].strip()
            cand_full = f"{nom_val.upper()} {ap_val.upper()}"
            if is_valid_person_name(cand_full):
                result["apellidos"] = ap_val.upper()
                result["nombres"] = nom_val.upper()
                result["nombre_completo"] = cand_full

    # Mecanismo 3 (Cédula Amarilla - Etiquetas DEBAJO del valor):
    if not result.get("nombre_completo"):
        cedula_ap = re.search(r"([A-ZÁÉÍÓÚÑ]{3,25}(?:\s+[A-ZÁÉÍÓÚÑ]{3,25})?)\s*[\n\r]+\s*APELLIDOS", raw_text, re.IGNORECASE)
        cedula_nom = re.search(r"([A-ZÁÉÍÓÚÑ]{3,25}(?:\s+[A-ZÁÉÍÓÚÑ]{3,25})?)\s*[\n\r]+\s*(?:NOMBRES?|JOMRES|JOMBRES)", raw_text, re.IGNORECASE)
        if cedula_ap and cedula_nom:
            ap_val = cedula_ap.group(1).strip()
            nom_val = cedula_nom.group(1).strip()
            cand_full = f"{nom_val.upper()} {ap_val.upper()}"
            if is_valid_person_name(cand_full):
                result["apellidos"] = ap_val.upper()
                result["nombres"] = nom_val.upper()
                result["nombre_completo"] = cand_full

    # Mecanismo 4 (Cédula Amarilla con ruido OCR):
    if not result.get("nombre_completo"):
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        cand_lines = []
        noise_words = {
            "REPUBLICA", "COLOMBIA", "REPUBLICADECOLOMBIA", "IDENTIFICACION", "PERSONAL",
            "CEDULA", "CIUDADANIA", "CEDULADECIUDADANIA", "NUMERO", "APELLIDOS", "NOMBRES",
            "FIRMA", "NACIMIENTO", "ESTATURA", "SEXO", "EXPEDICION", "FECHA", "LUGAR", "INDICE",
            "CODDANA", "PAGINA", "HOJA"
        }
        for l in lines:
            clean_l = re.sub(r"[^A-ZÁÉÍÓÚÑ\s]", "", l.upper()).strip()
            parts = clean_l.split()
            if not parts or any(p in noise_words for p in parts):
                continue
            if 4 <= len(clean_l) <= 40 and 1 <= len(parts) <= 4:
                cand_lines.append(clean_l)

        if len(cand_lines) >= 2:
            apellidos = cand_lines[0]
            nombres = cand_lines[1]
            cand_full = f"{nombres} {apellidos}"
            if is_valid_person_name(cand_full):
                result["apellidos"] = apellidos
                result["nombres"] = nombres
                result["nombre_completo"] = cand_full

    # -------------------------------------------------------------
    # C) FECHA Y LUGAR DE EXPEDICIÓN
    # -------------------------------------------------------------
    exp_m = re.search(r"(\d{1,2}[-\s]+[A-Z]{3}[-\s]+\d{4})\s+([A-Za-zÁÉÍÓÚáéíóú\s]+?)\s+(?:FECHA\s+Y\s+LUGAR\s+DE\s+EXPEDICI[OÓ]N|FECHA\s+EXPEDICION)", raw_text, re.IGNORECASE)
    if exp_m:
        result["fecha_expedicion"] = exp_m.group(1).strip()
        result["lugar_expedicion"] = exp_m.group(2).strip()

    return result


def parse_document_text(file_path: Union[Path, str]) -> str:
    """
    Despacha el archivo al extractor correspondiente según su extensión.
    Soporta PDF, Word (.docx, .doc), Excel (.xlsx, .xls), TXT, JSON, CSV.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        ocr_candidate = file_path.with_suffix(".ocr.txt")
        if ocr_candidate.exists():
            try:
                return ocr_candidate.read_text(encoding="utf-8")
            except Exception:
                pass
        logger.warning(f"Archivo no existe para parseo de texto: {file_path}")
        return ""

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    elif suffix in (".xlsx", ".xls"):
        return extract_text_from_excel(file_path)
    elif suffix in (".txt", ".json", ".csv"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        logger.warning(f"Formato no soportado directamente para extracción de texto: {suffix}")
        return ""



