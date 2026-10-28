"""
Servicio para analizar y procesar paquetes de pago en PDF de la ESPY.
Un paquete de pago típico incluye:
1. Comprobante de Egreso (CE Nº ...)
2. Orden de Pago (OP Nº ...)
3. Factura Electrónica de Venta o Cuenta de Cobro
4. Certificación de Cumplimiento y Supervisión Contractual
"""
import io
import re
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

import json
from pydantic import BaseModel, Field

from app.models.contractor import Contratista
from app.models.contract import Contrato
from app.services.document_parser import extract_text_from_pdf
from app.config import settings
from app.utils.logger import logger


class RetencionExtraida(BaseModel):
    descripcion: str = Field(description="Nombre o concepto de la retención o estampilla tal como aparece en la tabla")
    porcentaje: float = Field(default=0.0, description="Porcentaje de la deducción (ej. 0.6, 2.0, 15.0)")
    valor: float = Field(description="Valor monetario retenido en COP")


class PaymentPacketExtractionSchema(BaseModel):
    codigo_egreso: Optional[str] = Field(default=None, description="Número de Comprobante de Egreso (ej. 00245 o CE N° 00245)")
    codigo_orden_pago: Optional[str] = Field(default=None, description="Número de Orden de Pago (ej. 00204 u OP N° 00204)")
    fecha_expedicion: Optional[str] = Field(default=None, description="Fecha de expedición en formato DD/MM/YYYY o YYYY-MM-DD")
    nit_beneficiario: Optional[str] = Field(default=None, description="NIT o Cédula del beneficiario")
    nombre_beneficiario: Optional[str] = Field(default=None, description="Nombre o Razón Social del beneficiario")
    rubro_presupuestal: Optional[str] = Field(default=None, description="Código de rubro presupuestal (ej. 2.1.2.02.02.007)")
    concepto: Optional[str] = Field(default=None, description="Concepto del egreso")
    
    # Montos leídos estrictamente de los recuadros del Comprobante de Egreso y/o Orden de Pago
    valor_bruto_orden: float = Field(default=0.0, description="Monto del recuadro 'Total de la Presente Orden'")
    total_retenciones: float = Field(default=0.0, description="Monto del recuadro 'Total Retenciones'")
    valor_neto_pagar: float = Field(default=0.0, description="Monto del recuadro 'Total a Pagar'")
    
    # Textos de respaldo
    valor_en_letras_egreso: Optional[str] = Field(default=None, description="Texto de 'Valor en letras' del Comprobante de Egreso")
    valor_en_letras_op: Optional[str] = Field(default=None, description="Texto de 'Valor en letras' de la Orden de Pago")
    valor_movimiento_bancos: Optional[float] = Field(default=None, description="Valor numérico en la tabla Detalle de Movimiento de Bancos y Caja")
    
    # Tabla detallada de Retenciones (Páginas 2 y 3)
    retenciones_tabla: List[RetencionExtraida] = Field(default_factory=list, description="Filas individuales de la tabla RETENCIONES (DESCRIPCIÓN, %, VALOR)")
    
    # Datos de supervisión contractual / contrato
    numero_contrato: Optional[str] = Field(default=None, description="Código del contrato oficial (ej. CA-013-2026, CPS-004-2026)")
    factura_numero: Optional[str] = Field(default=None, description="Número de factura electrónica de venta o cuenta de cobro")


def parse_colombian_currency(val: Any) -> float:
    """
    Sanitización y conversión de valores monetarios colombianos a float:
    Resuelve sin fallos el formato de Sistemas Aries (8.330.000,00 o 199.500,00)
    y el formato estándar estadounidense (8,330,000.00 o 8330000):
    - Si termina en ,00 o ,\\d{2}, elimina puntos de miles y cambia coma decimal por punto.
    - Si termina en .00 o .\\d{2} y tiene comas de miles, elimina comas.
    - Si tiene puntos de miles sin decimales, elimina puntos.
    - Nunca multiplica por 100 los centavos.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    s = str(val).replace('$', '').strip()
    if not s:
        return 0.0
        
    # Eliminar espacios internos
    s = s.replace(' ', '')
    
    # Caso 1: Formato colombiano con coma decimal (ej. '8.330.000,00', '199.500,00', '5.617.500,50')
    if ',' in s:
        # Si tiene coma y punto, el punto es de miles y la coma es decimal
        parts = s.split(',')
        int_part = parts[0].replace('.', '')
        dec_part = parts[1] if len(parts) > 1 else '0'
        clean = f"{int_part}.{dec_part}"
    elif '.' in s:
        # Caso 2: Puntos únicamente. Puede ser '8,330,000.00' (si trajo comas) o '8.330.000' (miles) o '8330000.00' (decimal)
        parts = s.split('.')
        if len(parts) > 2:
            # Varios puntos (ej. '8.330.000') -> todos son separadores de miles
            clean = s.replace('.', '')
        elif len(parts) == 2:
            if len(parts[1]) == 3:
                # Ej. '8.330' -> miles
                clean = s.replace('.', '')
            else:
                # Ej. '8330000.00' o '7000000.5' -> punto decimal
                clean = s
        else:
            clean = s
    else:
        clean = s

    try:
        return float(clean)
    except (ValueError, TypeError):
        return 0.0


def parse_currency(val_str: Optional[str]) -> float:
    """Alias retrocompatible con parse_colombian_currency."""
    return parse_colombian_currency(val_str)


def classify_deductions_breakdown(
    retenciones_items: List[Dict[str, Any]], 
    total_retenciones_box: float = 0.0
) -> Dict[str, Any]:
    """
    Clasificación determinista de estampillas y retenciones tributarias colombianas.
    Recorre las filas de la tabla RETENCIONES y las clasifica con precisión sin perder un solo peso:
    1. retefuente: honorarios, servicios generales, compras, arrendamiento, declarante, no declarante, contratos construccion (sin iva/ica/estampilla).
    2. reteiva: iva, servicios gravados, reteiva, retencion de iva.
    3. reteica: ica, industria y comercio, reteica, avisos y tableros.
    4. estampillas: procultura, adulto mayor, bienestar anciano, prohospital, prodesarrollo, universidad, justicia familiar, pro-deporte, tasa pro, contribucion, obra publica, seguridad.
    5. otras_retenciones: embargos, deducciones o amortizaciones adicionales.
    """
    retefuente_val = 0.0
    reteiva_val = 0.0
    reteica_val = 0.0
    estampillas_val = 0.0
    otras_val = 0.0
    
    desglose_clasificado = []
    
    for item in retenciones_items or []:
        concepto_orig = item.get("concepto") or item.get("descripcion") or ""
        c_lower = concepto_orig.lower().strip()
        pct = float(item.get("porcentaje", 0.0) or 0.0)
        val = parse_colombian_currency(item.get("valor", 0.0))
        
        if val <= 0:
            continue
            
        categoria = "OTRAS"
        es_estampilla = False
        
        # 1. Chequeo de Estampillas y Tasas Territoriales
        estampilla_keywords = [
            "estampilla", "pro-cultura", "procultura", "adulto mayor", "bienestar del anciano",
            "pro-hospital", "prohospital", "pro-desarrollo", "prodesarrollo", "universidad",
            "justicia familiar", "pro-deporte", "prodeporte", "tasa pro", "contribucion", "obra publica",
            "obra pública", "seguridad", "fondo seguridad", "juaticia"
        ]
        
        # 2. Chequeo de ReteIVA
        reteiva_keywords = ["iva", "servicios gravados", "reteiva", "retencion de iva", "retención de iva"]
        
        # 3. Chequeo de ReteICA
        reteica_keywords = ["ica", "industria y comercio", "reteica", "avisos y tableros"]
        
        # 4. Chequeo de ReteFuente
        retefuente_keywords = [
            "retencion en la fuente", "retención en la fuente", "retefuente", "honorarios",
            "servicios generales", "compras", "arrendamiento", "arriendo", "declarante",
            "no declarante", "contratos de construccion", "contratos de construcción", "personas juridicas",
            "personas jurídicas", "software", "combustible"
        ]
        
        if any(kw in c_lower for kw in estampilla_keywords):
            categoria = "ESTAMPILLAS"
            es_estampilla = True
            estampillas_val += val
        elif any(kw in c_lower for kw in reteiva_keywords) and not any(kw in c_lower for kw in reteica_keywords):
            categoria = "RETEIVA"
            reteiva_val += val
        elif any(kw in c_lower for kw in reteica_keywords):
            categoria = "RETEICA"
            reteica_val += val
        elif any(kw in c_lower for kw in retefuente_keywords):
            categoria = "RETEFUENTE"
            retefuente_val += val
        else:
            categoria = "OTRAS"
            otras_val += val
            
        desglose_clasificado.append({
            "concepto": concepto_orig,
            "porcentaje": pct,
            "valor": val,
            "categoria": categoria,
            "es_estampilla": es_estampilla
        })

    suma_calculada = round(retefuente_val + reteiva_val + reteica_val + estampillas_val + otras_val, 2)
    
    return {
        "retefuente": round(retefuente_val, 2),
        "reteiva": round(reteiva_val, 2),
        "reteica": round(reteica_val, 2),
        "estampillas": round(estampillas_val, 2),
        "otras_retenciones": round(otras_val, 2),
        "total_retenciones_suma": suma_calculada,
        "desglose_retenciones": desglose_clasificado
    }


def parse_words_to_number_cop(words_str: Optional[str]) -> Optional[float]:
    """
    Interpreta un texto de 'Valor en letras' en pesos colombianos y lo convierte a número flotante.
    Ejemplo: 'OCHO MILLONES CIENTO TREINTA MIL QUINIENTOS PESOS M/L' -> 8130500.0
    """
    if not words_str:
        return None
        
    w = words_str.upper().strip()
    # Limpiar sufijos bancarios colombianos
    w = re.sub(r'\b(?:PESOS|MONEDA|CORRIENTE|LEGAL|M/L|M/CTE|COLOMBIANOS|CON|\d{2}/100|CERO|CENTAVOS)\b', ' ', w)
    w = re.sub(r'[\.,;]', ' ', w)
    
    tokens = [t.strip() for t in w.split() if t.strip()]
    if not tokens:
        return None
        
    num_map = {
        'UN': 1, 'UNO': 1, 'UNA': 1, 'DOS': 2, 'TRES': 3, 'CUATRO': 4, 'CINCO': 5,
        'SEIS': 6, 'SIETE': 7, 'OCHO': 8, 'NUEVE': 9, 'DIEZ': 10, 'ONCE': 11,
        'DOCE': 12, 'TRECE': 13, 'CATORCE': 14, 'QUINCE': 15, 'DIECISEIS': 16,
        'DIECISÉIS': 16, 'DIECISIETE': 17, 'DIECIOCHO': 18, 'DIECINUEVE': 19,
        'VEINTE': 20, 'VEINTIUN': 21, 'VEINTIUNO': 21, 'VEINTIÚN': 21, 'VEINTIDOS': 22,
        'VEINTIDÓS': 22, 'VEINTITRES': 23, 'VEINTITRÉS': 23, 'VEINTICUATRO': 24,
        'VEINTICINCO': 25, 'VEINTISEIS': 26, 'VEINTISÉIS': 26, 'VEINTISIETE': 27,
        'VEINTIOCHO': 28, 'VEINTINUEVE': 29, 'TREINTA': 30, 'CUARENTA': 40,
        'CINCUENTA': 50, 'SESENTA': 60, 'SETENTA': 70, 'OCHENTA': 80, 'NOVENTA': 90,
        'CIEN': 100, 'CIENTO': 100, 'DOSCIENTOS': 200, 'TRESCIENTOS': 300,
        'CUATROCIENTOS': 400, 'QUINIENTOS': 500, 'SEISCIENTOS': 600, 'SETECIENTOS': 700,
        'OCHOCIENTOS': 800, 'NOVECIENTOS': 900
    }
    
    total = 0.0
    current = 0.0
    
    for t in tokens:
        if t in num_map:
            current += num_map[t]
        elif t == 'Y':
            continue
        elif t in ('MIL', 'MILES'):
            if current == 0:
                current = 1
            current *= 1000
            total += current
            current = 0
        elif t in ('MILLON', 'MILLÓN', 'MILLONES'):
            if current == 0:
                current = 1
            current *= 1000000
            total += current
            current = 0
        elif t in ('BILLON', 'BILLÓN', 'BILLONES'):
            if current == 0:
                current = 1
            current *= 1000000000000
            total += current
            current = 0
            
    total += current
    return float(total) if total > 0 else None


def reconcile_payment_amounts(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Motor de reconciliación matemática y verificación contable con 'Valor en Letras':
    1. Regla de la Ecuación Fundamental del Egreso: Total Orden (Bruto) - Total Retenciones = Total a Pagar (Neto)
    2. Cruce con 'Valor en letras' del Egreso (Neto) y de la Orden de Pago (Bruto).
    3. Reconciliación con la tabla de Retenciones y Estampillas.
    """
    raw_bruto = parse_colombian_currency(data.get("valor_bruto_orden") or data.get("total_orden"))
    raw_ret = parse_colombian_currency(data.get("total_retenciones") or data.get("total_retencion"))
    raw_neto = parse_colombian_currency(data.get("valor_neto_pagar") or data.get("total_pagar"))
    raw_bancos = parse_colombian_currency(data.get("valor_movimiento_bancos"))
    
    letras_egreso = parse_words_to_number_cop(data.get("valor_en_letras_egreso"))
    letras_op = parse_words_to_number_cop(data.get("valor_en_letras_op"))
    
    # Clasificar retenciones
    ret_items = data.get("retenciones_tabla") or data.get("retenciones_detalle") or []
    deductions = classify_deductions_breakdown(ret_items, raw_ret)
    
    ret_suma = deductions["total_retenciones_suma"]
    if raw_ret == 0.0 and ret_suma > 0.0:
        raw_ret = ret_suma
    elif ret_suma > 0.0 and abs(raw_ret - ret_suma) > 1.0:
        # Si la suma de las filas coincide con la resta de orden - pagar, actualizar raw_ret
        if raw_bruto > 0 and raw_neto > 0 and abs((raw_bruto - ret_suma) - raw_neto) <= 1.0:
            raw_ret = ret_suma
            
    # Validar valor neto con bancos o valor en letras del Comprobante de Egreso
    if letras_egreso and abs(raw_neto - letras_egreso) > 1.0:
        if raw_bancos and abs(raw_bancos - letras_egreso) <= 1.0:
            raw_neto = letras_egreso
        elif raw_bruto > 0 and raw_ret > 0 and abs((raw_bruto - raw_ret) - letras_egreso) <= 1.0:
            raw_neto = letras_egreso
            
    if raw_bancos and raw_neto == 0.0:
        raw_neto = raw_bancos

    # Si hubo confusión con el subtotal de la factura (ej. tomó 7.000.000 en vez de 8.330.000)
    # pero tiene neto=8.130.500 y retenciones=199.500 -> bruto = neto + ret = 8.330.000
    if raw_neto > 0 and raw_ret >= 0:
        calc_bruto = round(raw_neto + raw_ret, 2)
        if letras_op and abs(calc_bruto - letras_op) <= 1.0:
            raw_bruto = calc_bruto
        elif abs(raw_bruto - calc_bruto) > 1.0:
            # Si el bruto leído no cuadra pero calc_bruto coincide con letras_op o con orden de pago
            if letras_op and abs(raw_bruto - letras_op) > 1.0:
                raw_bruto = calc_bruto
            elif raw_bruto == 0.0:
                raw_bruto = calc_bruto

    # Corrección de valor neto si el bruto y retención son válidos pero neto no cuadra
    if raw_bruto > 0 and raw_ret >= 0:
        calc_neto = round(raw_bruto - raw_ret, 2)
        if abs(raw_neto - calc_neto) > 1.0:
            raw_neto = calc_neto

    data["valor_bruto_orden"] = raw_bruto
    data["total_orden"] = raw_bruto
    data["total_retenciones"] = raw_ret
    data["total_retencion"] = raw_ret
    data["valor_neto_pagar"] = raw_neto
    data["total_pagar"] = raw_neto
    data["total_estampillas"] = deductions["estampillas"]
    data["retefuente"] = deductions["retefuente"]
    data["reteiva"] = deductions["reteiva"]
    data["reteica"] = deductions["reteica"]
    data["otras_retenciones"] = deductions["otras_retenciones"]
    data["desglose_retenciones"] = deductions["desglose_retenciones"]
    data["retenciones_detalle"] = deductions["desglose_retenciones"]
    
    return data


def parse_retencion_token(token: str) -> Optional[Dict[str, Any]]:
    """Convierte una cadena de retención (ej. 'Estampilla Pro Cultura (2.00%: 134286.00)') a diccionario estructurado."""
    if not token or not str(token).strip() or str(token).strip().lower() == 'sin retenciones':
        return None
    token_str = str(token).strip()
    m = re.match(r'^(.*?)\s*\(([\d\.]+)%\s*:\s*([\d\.]+)\)$', token_str)
    if not m:
        return None
    concepto = m.group(1).strip()
    try:
        pct = float(m.group(2))
    except ValueError:
        pct = 0.0
    try:
        val = float(m.group(3))
    except ValueError:
        val = 0.0
    c_lower = concepto.lower()
    es_estampilla = any(kw in c_lower for kw in [
        'estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte', 'adulto mayor', 'seguridad', 'obra p'
    ])
    return {
        "concepto": concepto,
        "porcentaje": pct,
        "valor": val,
        "es_estampilla": es_estampilla
    }


def normalize_retencion_name(name: str) -> str:
    """Estandariza el nombre comercial/tributario del concepto de deducción."""
    if not name:
        return "Otras Retenciones"
    n = str(name).strip()
    nl = n.lower()
    if 'justicia' in nl or 'juaticia' in nl:
        return 'Estampilla Pro-Justicia Familiar'
    elif 'cultura' in nl:
        return 'Estampilla Pro Cultura'
    elif 'hospital' in nl:
        return 'Estampilla Pro-Hospital'
    elif 'deporte' in nl:
        return 'Tasa Pro Deporte y Recreación'
    elif 'ica' in nl or 'industria' in nl:
        return 'Industria y Comercio ICA'
    elif 'iva' in nl:
        return 'Retención en la Fuente IVA'
    elif 'seguridad' in nl or 'obra p' in nl:
        return 'Contribución Especial Obra Pública (5% Fondo Seguridad)'
    elif 'jur' in nl:
        return 'Retención en la Fuente Personas Jurídicas'
    elif 'arriendo' in nl:
        return 'Retención Arriendo de Bienes'
    elif 'software' in nl:
        return 'Retención Software y Licencias'
    elif 'combustible' in nl:
        return 'Retención Combustible'
    elif 'compras' in nl and 'no declarante' in nl:
        return 'Compras No declarantes'
    elif 'compras 2.5' in nl:
        return 'Retención en la Fuente Compras (2.5%)'
    elif 'compras' in nl:
        return 'Retención en la Fuente Compras'
    return n


def extract_payment_packet_with_gemini(pdf_bytes: bytes, filename: str) -> Optional[PaymentPacketExtractionSchema]:
    """
    Extracción Multimodal de paquetes de pago mediante Google Gemini (gemini-2.5-flash).
    Envía el PDF íntegro o sus páginas renderizadas para que la IA lea de la Página 1 a la última
    aplicando las reglas contables oficiales de Sistemas Aries / ESPY.
    """
    if not settings.GEMINI_API_KEY:
        return None
        
    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        
        system_instruction = (
            "Eres un Contador Público Colombiano y Auditor Senior experto en Contabilidad Pública, Tesorería de Empresas "
            "de Servicios Públicos Domiciliarios (Ley 142 de 1994) y en el sistema contable 'Sistemas Aries / AriesNet' "
            "usado por la Empresa de Servicios Públicos de Yolombó (ESPY).\n\n"
            "Tu misión es auditar y extraer con 100% de exactitud matemática y tributaria la información del PAQUETE DE PAGO.\n"
            "Cada paquete típico contiene:\n"
            "- Páginas 1 y 2: COMPROBANTE DE EGRESO (formato 19_ce_espyolombo_CCPET.rdlc). En la Pág. 1 están: CE N°, Fecha de Expedición, "
            "  Documentos Asignados (Num Doc apunta a la OP), Nit o Cédula, Beneficiario, Concepto de este Egreso, Rubro Presupuestal, "
            "  los tres recuadros inferiores: 'Total de la Presente Orden', 'Total Retenciones', 'Total a Pagar', el 'Valor en letras' "
            "  (que en el CE corresponde al Total a Pagar neto) y el 'Detalle de Movimiento de Bancos y Caja'.\n"
            "  ⚠️ TRAMPA CRÍTICA: En el cuerpo aparece 'Valor Rubro' y luego repetido 6 veces el mismo monto bajo 'Valor Clasificador' "
            "  (CCPET01, CCPET02, CCPET05, CCPET70, CCPET83, CCPET84). ¡JAMÁS sumes los 'Valor Clasificador'! Son el mismo presupuesto.\n"
            "  ⚠️ PÁGINA 2: La tabla detallada 'RETENCIONES' (columnas DESCRIPCIÓN, %, VALOR) donde se imprimen las estampillas, ReteIVA, "
            "  ReteFuente y ReteICA suele quedar en la Página 2 del Comprobante de Egreso.\n"
            "- Páginas 3 y 4: ORDEN DE PAGO (OP N°, formato 19_op_espyolombo_CCPET.rdlc). Muestra también la tabla 'RETENCIONES' y los 3 recuadros "
            "  inferiores ('Total de la Presente Orden', 'Total Retenciones', 'Total a Pagar'). Su 'Valor en letras' equivale al Total de la Orden (bruto).\n"
            "- Página 5: FACTURA ELECTRÓNICA DE VENTA o Cuenta de Cobro. ⚠️ TRAMPA CRÍTICA: La factura muestra el subtotal antes de IVA "
            "  y suele mostrar RETE/FUENTE: $0, RETE/IVA: $0, RETE/ICA: $0 porque quien practica las deducciones es la ESPY en el Egreso. "
            "  ¡PROHIBIDO tomar los totales o retenciones de la Factura Electrónica si existen Comprobante de Egreso u Orden de Pago!\n"
            "- Página 6: CERTIFICACIÓN DE CUMPLIMIENTO Y SUPERVISIÓN CONTRACTUAL. Aquí aparece explícitamente el código oficial del contrato "
            "  (ej. 'en cumplimiento del contrato número CA-013-2026', 'CPS-004-2026', 'CS-014-2026', 'CO-033-2026').\n\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. valor_bruto_orden = Recuadro 'Total de la Presente Orden' del Comprobante de Egreso / Orden de Pago.\n"
            "2. total_retenciones = Recuadro 'Total Retenciones'.\n"
            "3. valor_neto_pagar = Recuadro 'Total a Pagar'.\n"
            "4. Cumplir estrictamente la ecuación: valor_bruto_orden - total_retenciones = valor_neto_pagar.\n"
            "5. retenciones_tabla: Extrae el 100% de las filas de la tabla RETENCIONES con su descripcion, porcentaje y valor numérico."
        )
        
        pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        
        logger.info(f"Invocando Gemini Multimodal (gemini-2.5-flash) para auditar paquete de pago: {filename}...")
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL or "gemini-2.5-flash",
            contents=[
                pdf_part,
                "Extrae todos los datos estructurados del comprobante de egreso, retenciones y orden de pago siguiendo el esquema JSON."
            ],
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "response_schema": PaymentPacketExtractionSchema,
                "temperature": 0.0,
            }
        )
        
        if response and response.text:
            parsed_json = json.loads(response.text)
            return PaymentPacketExtractionSchema(**parsed_json)
            
    except Exception as gem_err:
        logger.warning(f"Extracción multimodal con Gemini no pudo completarse para {filename}: {gem_err}. Continuando con extracción heurística y OCR...")
        return None


def extract_payment_packet_data(file_bytes: bytes, filename: str, db: Session, vigencia_default: int = 2026) -> Dict[str, Any]:
    """
    Extrae los datos estructurados equivalentes a las 8 columnas del TXT desde un paquete de pago PDF.
    Integra primero extracción multimodal con Gemini si hay API Key disponible, y cuenta con motor
    heurístico/OCR espacial de alta precisión con reconciliación contable y 'Valor en Letras'.
    """
    # 0. Intentar extracción multimodal directa con Gemini si el archivo es un PDF real
    gemini_data = None
    if file_bytes.startswith(b"%PDF"):
        gemini_res = extract_payment_packet_with_gemini(file_bytes, filename)
        if gemini_res:
            gemini_data = gemini_res.model_dump()

    # 1. Guardar temporalmente para pasar al extractor de documentos / OCR (necesario también para cruce textual)
    suffix = Path(filename).suffix or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        text = extract_text_from_pdf(tmp_path)
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass

    if not text or len(text.strip()) < 10:
        try:
            decoded_candidate = file_bytes.decode("utf-8", errors="ignore")
            if "COMPROBANTE" in decoded_candidate.upper() or "CONTRATO" in decoded_candidate.upper() or "EGRESO" in decoded_candidate.upper():
                text = decoded_candidate
        except Exception:
            pass

    if not text:
        text = ""

    if (not text or len(text.strip()) < 10) and not gemini_data:
        raise ValueError(f"No se pudo extraer texto ni datos del archivo '{filename}'. Verifique que no esté dañado.")

    # -------------------------------------------------------------
    # 1. Delimitar la extracción exclusivamente al COMPROBANTE DE EGRESO (Páginas 1 y 2)
    # Formato 19_ce_espyolombo_CCPET.rdlc / AriesNet
    # PROHIBIDO desbordarse a la Orden de Pago (OP), Cuentas de Cobro o Actas
    # -------------------------------------------------------------
    ce_start = 0
    m_ce_start = re.search(r'\bCOMPROBANTE\s+DE\s+EGRESO\b', text, re.IGNORECASE)
    if m_ce_start:
        ce_start = m_ce_start.start()

    # El Comprobante de Egreso finaliza donde inicia la Orden de Pago, Cuenta de Cobro, Acta o certificación
    m_ce_end = re.search(
        r'\b(?:ORDEN\s+DE\s+PAGO|ORDENDEPAGO|OP\s*N[°ºo\.]|CUENTA\s+DE\s+COBRO|FACTURA\s+ELECTRONICA|ACTA\s+DE\s+AVANCE|CERTIFICACI[OÓ]N\s+DE\s+CUMPLIMIENTO)\b',
        text[ce_start:],
        re.IGNORECASE
    )
    if m_ce_end:
        egreso_text = text[ce_start : ce_start + m_ce_end.start()]
    else:
        egreso_text = text[ce_start:]

    # Dividir el Comprobante de Egreso en Página 1 y Página 2 si están marcadas
    egreso_p1 = egreso_text
    egreso_p2 = egreso_text
    if "=== PÁGINA" in egreso_text:
        pages = egreso_text.split("=== PÁGINA")
        if len(pages) >= 2:
            egreso_p1 = "=== PÁGINA" + pages[1]
        if len(pages) >= 3:
            egreso_p2 = "=== PÁGINA" + pages[2]
        else:
            egreso_p2 = egreso_p1
    elif "Página 2 de" in egreso_text or "Página 2" in egreso_text:
        p2_idx = egreso_text.find("Página 2")
        egreso_p1 = egreso_text[:p2_idx]
        egreso_p2 = egreso_text[p2_idx:]

    # -------------------------------------------------------------
    # 2. Extracción precisa por etiquetas ancla en la Página 1 del CE
    # -------------------------------------------------------------
    # 2.1 Código de Egreso: Extrae el texto que sigue a "CE N°" (ej. "CE N° 00211")
    codigo_egreso = None
    m_ce = re.search(r'CE\s*(?:N[°ºo\.]?|N[^\w\s]?)\s*0*(\d+)', egreso_p1, re.IGNORECASE) or re.search(r'CE\s*(?:N[°ºo\.]?|N[^\w\s]?)\s*0*(\d+)', egreso_text, re.IGNORECASE)
    if m_ce:
        codigo_egreso = f"CE N° {m_ce.group(1).zfill(5)}"
    else:
        m_ce_alt = re.search(r'COMPROBANTE\s+DE\s+EGRESO[\s\S]{0,80}?(?:N[°ºo\.]?|N[^\w\s]?)\s*0*(\d+)', egreso_text, re.IGNORECASE)
        if m_ce_alt:
            codigo_egreso = f"CE N° {m_ce_alt.group(1).zfill(5)}"

    # 2.2 Orden de Pago vinculada (referencia contable)
    orden_pago = None
    m_op = re.search(r'OP\s*(?:N[°ºo\.]?|N[^\w\s]?)\s*0*(\d+)', text, re.IGNORECASE)
    if m_op:
        orden_pago = f"OP N° {m_op.group(1).zfill(5)}"
    else:
        m_doc = re.search(r'Num\s+Doc\.?\s*[:\s]*0*(\d+)', egreso_p1, re.IGNORECASE)
        if m_doc:
            orden_pago = f"OP N° {m_doc.group(1).zfill(5)}"

    # 2.3 Fecha de Expedición: Extrae ÚNICAMENTE la fecha que acompaña la etiqueta "Fecha de Expedición:"
    # ESTÁ PROHIBIDO usar datetime.now() o la fecha del sistema.
    fecha_expedicion = None
    fecha_str = None

    # Prioridad 1: Etiqueta formal "Fecha de Expedición:"
    m_fexp = re.search(r'Fecha\s+de\s+Expedici[oó]n:?\s*[:\s]*(\d{2}/\d{2}/\d{4})', egreso_p1, re.IGNORECASE) or re.search(r'Fecha\s+de\s+Expedici[oó]n:?\s*[:\s]*(\d{2}/\d{2}/\d{4})', egreso_text, re.IGNORECASE)
    if m_fexp:
        fecha_str = m_fexp.group(1)
    else:
        # Prioridad 2: "Fecha Doc." dentro de la tabla Documentos Asignados de la página 1
        m_fdoc = re.search(r'Fecha\s+Doc\.?\s*[:\s]*(\d{2}/\d{2}/\d{4})', egreso_p1, re.IGNORECASE)
        if m_fdoc:
            fecha_str = m_fdoc.group(1)
        else:
            # Prioridad 3: Fecha en pie de imprenta de AriesNet (ej. "el día: jueves, 30 de abril de 2026")
            m_meses = {
                'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
            }
            m_pie = re.search(r'el\s+d[ií]a:?\s*\w*,\s*(\d{1,2})\s+de\s+([a-zA-Z]+)\s+de\s+(20\d{2})', egreso_text, re.IGNORECASE)
            if m_pie:
                d_day = m_pie.group(1).zfill(2)
                d_m_str = m_pie.group(2).lower()
                d_year = m_pie.group(3)
                if d_m_str in m_meses:
                    fecha_str = f"{d_day}/{m_meses[d_m_str]}/{d_year}"
            else:
                # Prioridad 4: Cualquier fecha válida DD/MM/YYYY en la cabecera de la página 1
                m_any_date = re.search(r'\b(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/(20\d{2})\b', egreso_p1[:1500])
                if m_any_date:
                    fecha_str = m_any_date.group(0)

    if fecha_str:
        try:
            fecha_expedicion = datetime.strptime(fecha_str, "%d/%m/%Y").date()
        except ValueError:
            pass

    # 2.4 Beneficiario y NIT
    nombre_beneficiario = None
    m_ben = re.search(r'Benefici[aá]rio:?\s*([^\n\r]+)', egreso_p1, re.IGNORECASE) or re.search(r'Benefici[aá]rio:?\s*([^\n\r]+)', egreso_text, re.IGNORECASE)
    if m_ben:
        nombre_beneficiario = m_ben.group(1).strip()
        nombre_beneficiario = re.sub(r'[\.\-]+$', '', nombre_beneficiario).strip()

    nit_beneficiario = None
    m_nit = re.search(r'Nit\s*(?:o\s*C[eé]dula)?:?\s*([\d\.\-]+)', egreso_p1, re.IGNORECASE) or re.search(r'Nit\s*(?:o\s*C[eé]dula)?:?\s*([\d\.\-]+)', egreso_text, re.IGNORECASE)
    if m_nit:
        nit_raw = m_nit.group(1).strip()
        nit_clean = re.sub(r'[^\d]', '', nit_raw)
        if nit_clean and "811015112" not in nit_clean:
            nit_beneficiario = nit_raw

    # 2.5 Rubro de Egreso (Presupuestal)
    rubro_egreso = None
    m_rubros = re.findall(r'\b(2\.\d\.\d\.\d{2}\.\d{2}\.\d{3}(?:\.\d{2})*)\b', egreso_p1) or re.findall(r'\b(2\.\d\.\d\.\d{2}\.\d{2}\.\d{3}(?:\.\d{2})*)\b', egreso_text)
    if m_rubros:
        rubro_egreso = m_rubros[0]

    # -------------------------------------------------------------
    # 2.6 Extracción precisa de Totales Financieros en Página 1
    # Ubica las etiquetas exactas:
    # - "Total de la Presente Orden"
    # - "Total Retenciones"
    # - "Total a Pagar"
    # -------------------------------------------------------------
    def extract_totals_from_source(src_text: str) -> Tuple[float, float, float]:
        t_ord = 0.0
        t_ret = 0.0
        t_pag = 0.0

        # -------------------------------------------------------------------------
        # REGLA DE LECTURA ESPACIAL (CRÍTICA):
        # 3 cajas horizontales contiguas en la parte inferior de la Página 1:
        # 1. Caja Izquierda (Debajo de "Total de la Presente Orden") -> total_orden
        # 2. Caja Central (Debajo de "Total Retenciones")           -> total_retenciones
        # 3. Caja Derecha (Debajo de "Total a Pagar")               -> total_a_pagar
        # -------------------------------------------------------------------------
        
        # Método 1: Búsqueda tabular secuencial estricta de izquierda a derecha (AriesNet)
        re_ord_lbl = r'Total\s+(?:de\s+la\s+)?Presente\s+Orden'
        re_ret_lbl = r'Total\s+Retenciones'
        re_pag_lbl = r'Total\s+(?:a\s+)?Pagar'

        m_tbl = re.search(
            rf'{re_ord_lbl}[\s\S]{{0,60}}?{re_ret_lbl}[\s\S]{{0,60}}?{re_pag_lbl}[\s\S]{{0,100}}?([\d\.\s]+,\d{{2}})[\s\S]{{0,60}}?([\d\.\s]+,\d{{2}})[\s\S]{{0,60}}?([\d\.\s]+,\d{{2}})',
            src_text,
            re.IGNORECASE
        )
        if m_tbl:
            c_ord = parse_currency(m_tbl.group(1))
            c_ret = parse_currency(m_tbl.group(2))
            c_pag = parse_currency(m_tbl.group(3))
            # Validación espacial matemática inmediata: total_orden - total_retenciones == total_a_pagar
            if c_ord > 0 and abs(round(c_ord - c_ret, 2) - round(c_pag, 2)) < 0.1:
                return c_ord, c_ret, c_pag
            elif c_ord > 0:
                t_ord, t_ret, t_pag = c_ord, c_ret, c_pag

        # Método 2: Directo clave-valor por etiquetas exactas
        m_o = re.search(r'Total\s+(?:de\s+la\s+)?Presente\s+Orden\s*[:\s]\s*([\d\.\s]+,\d{2})', src_text, re.IGNORECASE)
        m_r = re.search(r'Total\s+Retenciones\s*[:\s]\s*([\d\.\s]+,\d{2})', src_text, re.IGNORECASE)
        m_p = re.search(r'Total\s+(?:a\s+)?Pagar\s*[:\s]\s*([\d\.\s]+,\d{2})', src_text, re.IGNORECASE)

        if m_o and m_r and m_p:
            c_ord = parse_currency(m_o.group(1))
            c_ret = parse_currency(m_r.group(1))
            c_pag = parse_currency(m_p.group(1))
            if c_ord > 0 and abs(round(c_ord - c_ret, 2) - round(c_pag, 2)) < 0.1:
                return c_ord, c_ret, c_pag
            elif c_ord > 0:
                t_ord, t_ret, t_pag = c_ord, c_ret, c_pag

        # Método 3: Búsqueda individual de celdas
        if t_ord == 0.0 and m_o: t_ord = parse_currency(m_o.group(1))
        if t_ret == 0.0 and m_r: t_ret = parse_currency(m_r.group(1))
        if t_pag == 0.0 and m_p: t_pag = parse_currency(m_p.group(1))

        # Método 4: Respaldo por 'Valor Rubro' y 'Movimiento de Bancos y Caja'
        if t_ord == 0.0:
            m_vr = re.search(r'Valor\s+Rubro[\s\S]{0,40}?([\d\.\s]+,\d{2})', src_text, re.IGNORECASE)
            if m_vr:
                t_ord = parse_currency(m_vr.group(1))

        if t_pag == 0.0:
            m_ban = re.search(r'(?:Detalle\s+de\s+Movimiento\s+de\s+Bancos|Bancos\s+y\s+Caja)[\s\S]{0,180}?([\d\.\s]+,\d{2})', src_text, re.IGNORECASE)
            if m_ban:
                t_pag = parse_currency(m_ban.group(1))

        # Validación lógica de auto-corrección: total_orden - total_retenciones == total_a_pagar
        if t_ord > 0 and t_ret > 0 and t_pag > 0:
            if abs(round(t_ord - t_ret, 2) - round(t_pag, 2)) >= 0.1:
                # Si no coincide la resta, verificar si hubo cruce de posición o re-evaluar la resta
                calc_pag = round(t_ord - t_ret, 2)
                if abs(calc_pag - t_pag) < 1.0:
                    t_pag = calc_pag

        return t_ord, t_ret, t_pag

    # Intentar primero exclusivamente sobre Página 1 del Comprobante de Egreso
    total_orden, total_retencion, total_pagar = extract_totals_from_source(egreso_p1)
    if total_orden == 0.0:
        total_orden, total_retencion, total_pagar = extract_totals_from_source(egreso_text)

    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # 3. Extracción completa de Retenciones en la Página 2 del CE
    # En la página inmediatamente siguiente del Comprobante de Egreso
    # (donde está la tabla "RETENCIONES" con columnas DESCRIPCIÓN, % y VALOR)
    # Formato 19_ce_espyolombo_CCPET.rdlc
    # -------------------------------------------------------------
    def parse_retenciones_section(src_text: str, flexible: bool = False) -> List[Dict[str, Any]]:
        items = []
        if not src_text:
            return items

        # Localizar el bloque de la tabla RETENCIONES (entre RETENCIONES y Gerente/Auxiliar/firmas/OP)
        m_sec = re.search(
            r'(?<!Total\s)\bRETENCIONES\b\s*(?:DESCRIPCI[OÓ]N[\s\S]{0,40}?VALOR)?\s*([\s\S]+?)(?:Gerente|Auxiliar|Firma|=== PÁGINA [3-9]|\bORDENDEPAGO\b|\bORDEN\s+DE\s+PAGO\b|$)',
            src_text,
            re.IGNORECASE
        )
        
        target_chunk = m_sec.group(1) if m_sec else src_text

        raw_lines = [l.replace('|', ' ').strip() for l in target_chunk.splitlines() if l.strip()]
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]
            if line.upper().startswith("DESCRIPCI") or "VALOR" in line.upper() or "===" in line:
                i += 1
                continue

            # Caso 1: En una sola línea con 3 columnas (ej. "Industria y comercio ICA   0,60   19.800,00" o "Tasa Pro Deporte ... 2.00 66000.00")
            m_single = re.match(r'^(.*?)\s+([\-−–]?\d+(?:[\.,]\d+)?%?)\s+([\d\.]+,\d{2}|\d{4,}(?:\.\d{2})?)$', line)
            if m_single:
                c_name = m_single.group(1).strip()
                pct_str = m_single.group(2).replace('%', '').replace(',', '.').replace('−', '-').replace('–', '-').strip()
                try:
                    pct = abs(float(pct_str))
                except ValueError:
                    pct = 0.0
                val = parse_colombian_currency(m_single.group(3))
                c_lower = c_name.lower()
                es_est = any(kw in c_lower for kw in ['estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte'])
                if val > 0:
                    items.append({
                        "concepto": c_name,
                        "porcentaje": pct,
                        "valor": val,
                        "es_estampilla": es_est
                    })
                i += 1
            # Caso 2: En 3 líneas consecutivas producto del OCR (Concepto, %, Valor)
            elif (i + 2 < len(raw_lines) 
                  and re.match(r'^[\-−–]?\d+(?:[\.,]\d+)?%?$', raw_lines[i + 1]) 
                  and re.match(r'^([\d\.]+,\d{2}|\d{4,}(?:\.\d{2})?)$', raw_lines[i + 2])):
                c_name = raw_lines[i].strip()
                pct_str = raw_lines[i + 1].replace('%', '').replace(',', '.').replace('−', '-').replace('–', '-').strip()
                try:
                    pct = abs(float(pct_str))
                except ValueError:
                    pct = 0.0
                val = parse_colombian_currency(raw_lines[i + 2])
                c_lower = c_name.lower()
                es_est = any(kw in c_lower for kw in ['estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte'])
                if val > 0:
                    items.append({
                        "concepto": c_name,
                        "porcentaje": pct,
                        "valor": val,
                        "es_estampilla": es_est
                    })
                i += 3
            # Caso 3: En 2 líneas (Línea 1: Concepto, Línea 2: % y Valor juntos)
            elif (i + 1 < len(raw_lines)
                  and re.match(r'^([\-−–]?\d+(?:[\.,]\d+)?%?)\s+([\d\.]+,\d{2}|\d{4,}(?:\.\d{2})?)$', raw_lines[i + 1])):
                c_name = raw_lines[i].strip()
                m_sub = re.match(r'^([\-−–]?\d+(?:[\.,]\d+)?%?)\s+([\d\.]+,\d{2}|\d{4,}(?:\.\d{2})?)$', raw_lines[i + 1])
                pct_str = m_sub.group(1).replace('%', '').replace(',', '.').replace('−', '-').replace('–', '-').strip()
                try:
                    pct = abs(float(pct_str))
                except ValueError:
                    pct = 0.0
                val = parse_colombian_currency(m_sub.group(2))
                c_lower = c_name.lower()
                es_est = any(kw in c_lower for kw in ['estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte'])
                if val > 0:
                    items.append({
                        "concepto": c_name,
                        "porcentaje": pct,
                        "valor": val,
                        "es_estampilla": es_est
                    })
                i += 2
            # Caso 4 (Modo flexible): Captura de líneas con ruidos numéricos o códigos contables (ej: "303 Tasa Pro Deporte ... 3208333 2.00% 66.000,00")
            elif flexible:
                m_flex = re.search(r'([A-Za-zÁÉÍÓÚáéíóúñÑ\s\.\-]{3,45}?)\s*.*?([\-−–]?\d+(?:[\.,]\d+)?)\s*%\s*.*?([\d\.]+,\d{2})', line)
                if not m_flex:
                    m_flex = re.search(r'([A-Za-zÁÉÍÓÚáéíóúñÑ\s\.\-]{3,45}?)\s+([\-−–]?\d+(?:[\.,]\d+)?)\s+([\d\.]+,\d{2})', line)
                if m_flex:
                    c_name = m_flex.group(1).strip()
                    c_name = re.sub(r'^\d+\s*', '', c_name).strip() # Limpiar código contable prefijo si vino (ej "303 ")
                    pct_str = m_flex.group(2).replace(',', '.').replace('−', '-').replace('–', '-').strip()
                    try:
                        pct = abs(float(pct_str))
                    except ValueError:
                        pct = 0.0
                    val = parse_colombian_currency(m_flex.group(3))
                    c_lower = c_name.lower()
                    es_est = any(kw in c_lower for kw in ['estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte'])
                    if val > 0:
                        items.append({
                            "concepto": c_name,
                            "porcentaje": pct,
                            "valor": val,
                            "es_estampilla": es_est
                        })
                i += 1
            else:
                i += 1

        return items

    # Buscar prioritariamente en Página 2 del Comprobante de Egreso
    retenciones_items = parse_retenciones_section(egreso_p2)
    if not retenciones_items and egreso_p2 != egreso_text:
        retenciones_items = parse_retenciones_section(egreso_text)

    # -------------------------------------------------------------
    # 3.1 Validación de consistencia matemática del desglose de retenciones:
    # Si suma_desglose < total_retencion, reescanear la página 2 con patrones más flexibles
    # para capturar líneas con saltos, ruidos de OCR o columnas fusionadas (ICA, Hospital, Deporte, etc.)
    # -------------------------------------------------------------
    def sum_items(its: List[Dict[str, Any]]) -> float:
        return round(sum(it["valor"] for it in its), 2)

    suma_desglose = sum_items(retenciones_items)
    if total_retencion > 0 and (not retenciones_items or suma_desglose < (total_retencion - 1.0)):
        logger.warning(
            f"Desglose de retenciones incompleto en {filename} ({suma_desglose} vs Total {total_retencion}). "
            f"Activando reescaneo flexible en Página 2 y texto completo del egreso..."
        )
        flexible_items = parse_retenciones_section(egreso_p2, flexible=True)
        if sum_items(flexible_items) > suma_desglose:
            retenciones_items = flexible_items
            suma_desglose = sum_items(retenciones_items)

        if suma_desglose < (total_retencion - 1.0) and egreso_p2 != egreso_text:
            flexible_items_full = parse_retenciones_section(egreso_text, flexible=True)
            if sum_items(flexible_items_full) > suma_desglose:
                retenciones_items = flexible_items_full
                suma_desglose = sum_items(retenciones_items)

        # Si aún no cuadra o faltan retenciones tributarias estándar (ICA, Estampillas),
        # ejecutar búsqueda focalizada por conceptos tributarios conocidos en la Página 2
        if suma_desglose < (total_retencion - 1.0):
            target_text_for_scan = egreso_p2 if len(egreso_p2.strip()) > 50 else egreso_text
            # Patrones específicos para conceptos comunes en ESPY:
            # 1. ICA / Industria y Comercio (0.60%)
            # 2. Estampilla Pro Cultura (2.00%)
            # 3. Estampilla Pro-Hospital (1.00%)
            # 4. Tasa Pro Deporte (2.00%)
            # 5. Estampilla Pro-Justicia Familiar (2.00%)
            # 6. Retención en la fuente (Servicios/Compras/Personas Jurídicas)
            known_tax_patterns = [
                (r'(?:Industria\s+y\s+[cC]omercio|ICA)', 0.60, 'Industria y comercio ICA'),
                (r'(?:Estampilla\s+)?Pro[\s\-]*Cultura', 2.00, 'Estampilla Pro Cultura'),
                (r'(?:Estampilla\s+)?Pro[\s\-]*Hospital', 1.00, 'Estampilla Pro-Hospital'),
                (r'(?:Tasa\s+)?Pro[\s\-]*Deporte(?:\s+y\s+Recreaci[oó]n)?', 2.00, 'Tasa Pro Deporte y Recreacion'),
                (r'(?:Estampilla\s+)?Pro[\s\-]*Justicia(?:\s+Familiar)?', 2.00, 'Estampilla Pro-Justicia Familiar'),
                (r'Compras\s+(?:No\s+declarantes|no\s+declarante)', 3.50, 'Compras No declarantes'),
            ]

            existing_concepts = {it["concepto"].lower() for it in retenciones_items}
            for pattern, def_pct, std_name in known_tax_patterns:
                if any(kw in existing_concepts for kw in std_name.lower().split() if len(kw) > 4):
                    continue  # Ya capturado
                
                # Buscar mención del concepto acompañado de % y valor en cualquier parte de la página 2
                m_tax = re.search(
                    rf'\b{pattern}\b[\s\S]{{0,50}}?([\d]+(?:[,\.][\d]{{1,2}})?%?)[\s\S]{{0,30}}?([\d\.]+,\d{{2}})',
                    target_text_for_scan,
                    re.IGNORECASE
                )
                if m_tax:
                    pct_val = parse_colombian_currency(m_tax.group(1).replace('%', '')) or def_pct
                    val_val = parse_colombian_currency(m_tax.group(2))
                    if val_val > 0:
                        c_lower = std_name.lower()
                        es_est = any(kw in c_lower for kw in ['estampilla', 'cultura', 'hospital', 'justicia', 'juaticia', 'deporte'])
                        retenciones_items.append({
                            "concepto": std_name,
                            "porcentaje": pct_val,
                            "valor": val_val,
                            "es_estampilla": es_est
                        })
                        existing_concepts.add(std_name.lower())

            suma_desglose = sum_items(retenciones_items)

    # -------------------------------------------------------------
    # 4. Validación de consistencia matemática previa al guardado:
    # Regla Estricta: total_orden - total_retencion == total_pagar
    # -------------------------------------------------------------
    def is_consistent(o: float, r: float, p: float) -> bool:
        return o > 0 and r >= 0 and p > 0 and r < o and abs(round(o - r, 2) - round(p, 2)) < 0.1

    # Regla Preventiva: Si retención > pagar o retención > orden, los valores fueron leídos de forma invertida
    if total_retencion > total_pagar and total_pagar > 0:
        # Ejemplo CE N° 00245: Se mapeó total_pagar como retención y viceversa
        if abs(round(total_orden - total_pagar, 2) - round(total_retencion, 2)) < 0.1 or total_pagar < 1000000:
            logger.warning(f"Inversión espacial detectada en {filename}: Retención ({total_retencion}) > Pagar ({total_pagar}). Invirtiendo valores...")
            total_retencion, total_pagar = total_pagar, total_retencion

    if not is_consistent(total_orden, total_retencion, total_pagar):
        logger.warning(f"Inconsistencia matemática en {filename}: Orden={total_orden}, Ret={total_retencion}, Pagar={total_pagar}. Ejecutando re-análisis espacial estricto...")
        
        # Reintento por anclas aisladas de valores en Página 1
        m_o_strict = re.search(r'Total\s+(?:de\s+la\s+)?Presente\s+Orden[\s\S]{0,35}?([\d\.\s]+,\d{2})', egreso_p1, re.IGNORECASE)
        m_r_strict = re.search(r'Total\s+Retenciones[\s\S]{0,35}?([\d\.\s]+,\d{2})', egreso_p1, re.IGNORECASE)
        m_p_strict = re.search(r'Total\s+(?:a\s+)?Pagar[\s\S]{0,35}?([\d\.\s]+,\d{2})', egreso_p1, re.IGNORECASE)

        c_ord = parse_currency(m_o_strict.group(1)) if m_o_strict else 0.0
        c_ret = parse_currency(m_r_strict.group(1)) if m_r_strict else 0.0
        c_pag = parse_currency(m_p_strict.group(1)) if m_p_strict else 0.0

        if is_consistent(c_ord, c_ret, c_pag):
            total_orden, total_retencion, total_pagar = c_ord, c_ret, c_pag
        else:
            # Si existen retenciones leídas de la tabla en página 2, usarlas como ancla
            sum_ret = sum(it["valor"] for it in retenciones_items)
            if sum_ret > 0:
                total_retencion = sum_ret
                if total_orden > 0:
                    total_pagar = round(total_orden - total_retencion, 2)
            elif total_orden > 0 and total_pagar > 0 and total_orden > total_pagar:
                diff = round(total_orden - total_pagar, 2)
                # Solo aceptar si la diferencia es razonable como porcentaje de retención (< 30% del valor total)
                if diff < (total_orden * 0.35):
                    total_retencion = diff

    # Si total_retencion > 0 pero no se detectaron retenciones en la tabla de la página 2,
    # registrar advertencia estricta
    total_estampillas = sum(it["valor"] for it in retenciones_items if it.get("es_estampilla"))
    if retenciones_items:
        retenciones_raw = ", ".join(f"{it['concepto']} ({it['porcentaje']:.2f}%: {it['valor']:.2f})" for it in retenciones_items)
    elif total_retencion == 0.0:
        retenciones_raw = "Sin retenciones"
    else:
        # Si total_retencion > 0, ESTÁ PROHIBIDO arrojar 'Sin retenciones'
        retenciones_raw = f"Retenciones pendientes de desglose ({total_retencion:.2f})"

    # -------------------------------------------------------------
    # 8. Concepto y Metadatos de Factura
    # -------------------------------------------------------------
    concepto = None
    m_conc = re.search(r'Concepto\s+de\s+este\s+Egreso[\s\S]{0,20}?[\n\r]([^\n\r]+(?:[\n\r][^\n\r]+)?)', text, re.IGNORECASE)
    if m_conc:
        concepto = m_conc.group(1).strip()
        concepto = re.sub(r'\s+', ' ', concepto)

    factura_numero = None
    m_fac = re.search(r'(?:FACTURA\s+ELECTRONICA|FACTURA|CUENTA\s+DE\s+COBRO)[\s\S]{0,40}?(?:DE\s+VENTA\s+No\.?|No\.?|N[°ºo]?\.?)\s*([A-Z0-9\-_]+)', text, re.IGNORECASE)
    if m_fac:
        factura_numero = m_fac.group(1).strip()

    # -------------------------------------------------------------
    # 9. Vinculación Inteligente al Contratista y Contrato
    # -------------------------------------------------------------
    codigo_contrato = None
    contratista_match = None
    contrato_match = None
    requiere_seleccion_contrato = False
    contratos_candidatos = []

    # -------------------------------------------------------------
    # 9.0 Escaneo Prioritario de 'CERTIFICACIÓN DE CUMPLIMIENTO Y SUPERVISIÓN CONTRACTUAL'
    # Para pagos nuevos o sin historial donde el egreso no contiene el código del contrato
    # -------------------------------------------------------------
    cert_contrato_codigo = None
    cert_contratista_nombre = None
    cert_contratista_nit = None

    # Recorrer páginas o secciones buscando el encabezado de Certificación de Supervisión
    m_cert_hdr = re.search(r'CERTIFICACI[OÓ]N\s+DE\s+CUMPLIMIENTO\s+Y\s+SUPERVISI[OÓ]N\s+(?:CONTRACTUAL)?', text, re.IGNORECASE)
    if m_cert_hdr:
        cert_chunk = text[m_cert_hdr.start():m_cert_hdr.start() + 2500]
        
        # 1. Código del Contrato: el patrón que sigue a "contrato número" -> r'(?:contrato\s+n[uú]mero\s+)([A-Z]{2,3}-\d{3}-\d{4})'
        m_cert_code = re.search(r'(?:contrato\s+n[uú]mero\s+)([A-Z]{2,3}-\d{3}-\d{4})', cert_chunk, re.IGNORECASE)
        if not m_cert_code:
            m_cert_code = re.search(r'(?:contrato\s+(?:n[uú]mero|n[°ºo]?\.?)\s*)([A-Z]{2,3}-\d{3}-\d{4})', cert_chunk, re.IGNORECASE)
        if m_cert_code:
            cert_contrato_codigo = m_cert_code.group(1).strip().upper()

        # 2. Nombre del Contratista: el texto que sigue a "constancia de que" y precede a ", identificado con"
        m_cert_nom = re.search(r'constancia\s+de\s+que\s+([\s\S]+?)(?:,\s*identificado\s+con|\s+identificado\s+con)', cert_chunk, re.IGNORECASE)
        if m_cert_nom:
            raw_nom = m_cert_nom.group(1).strip()
            raw_nom = re.sub(r'[\r\n\t]+', ' ', raw_nom)
            raw_nom = re.sub(r'\s{2,}', ' ', raw_nom)
            if len(raw_nom) > 3:
                cert_contratista_nombre = raw_nom

        # 3. Identificación: el número de cédula/NIT bajo "(CC/NIT)"
        m_cert_doc = re.search(r'\(CC/NIT\)\s*([\d\.\-]+)', cert_chunk, re.IGNORECASE)
        if not m_cert_doc:
            m_cert_doc = re.search(r'(?:identificado\s+con\s+(?:\(CC/NIT\)|CC/NIT|c[eé]dula|nit)?\s*[:\s]*)([\d\.\-]+)', cert_chunk, re.IGNORECASE)
        if m_cert_doc:
            raw_doc = m_cert_doc.group(1).strip()
            clean_cert_doc = re.sub(r'[^\d]', '', raw_doc)
            if clean_cert_doc and "811015112" not in clean_cert_doc:
                cert_contratista_nit = raw_doc

    if cert_contratista_nombre and (not nombre_beneficiario or len(nombre_beneficiario) < 3 or "BENEFICIARIO" in (nombre_beneficiario or "")):
        nombre_beneficiario = cert_contratista_nombre
    if cert_contratista_nit and not nit_beneficiario:
        nit_beneficiario = cert_contratista_nit

    # 9.1 Búsqueda y Extracción Prioritaria del Código del Contrato en el Paquete PDF
    # Reconoce los prefijos oficiales de la ESPY:
    # - CS- (Contrato de Suministro, ej. CS-023-2026)
    # - CPS- (Contrato de Prestación de Servicios)
    # - CO- (Contrato de Obra)
    # - CA- (Contrato de Arrendamiento)
    # Expresión regular universal: r'(?:contrato\s+(?:n[uú]mero|n[°o]\.?)\s*)?([A-Z]{2,3}-\d{3}-\d{4})'
    contract_patterns = [
        r'(?:contrato\s+(?:n[uú]mero|n[°oº\.]?)\s*)?([A-Z]{2,3}-\d{3}-\d{4})',
        r'\b((?:CPS|CS|CO|CA|CD)-\d{3,4}-\d{4})\b',
        r'(?:CONTRATO\s+(?:N[UÚ]MERO|N[°ºo]?\.?)\s*|CONTRATO\s+)([A-Z]{1,4}-\d{3,4}-\d{4})',
        r'\b(0\d{2}-\d{4})\b'
    ]
    
    # Recolectar todos los códigos de contratos válidos encontrados en el texto
    found_contract_codes = set()
    if cert_contrato_codigo:
        found_contract_codes.add(cert_contrato_codigo)

    for cp in contract_patterns:
        matches = re.findall(cp, text, re.IGNORECASE)
        for cand in matches:
            cand_norm = cand.strip().upper()
            c_db = db.query(Contrato).filter(Contrato.numero_contrato == cand_norm).first()
            if c_db:
                found_contract_codes.add(c_db.numero_contrato)

    if cert_contrato_codigo:
        # Prioridad 1: Código extraído de la Certificación de Supervisión
        c_db = db.query(Contrato).filter(Contrato.numero_contrato == cert_contrato_codigo).first()
        if c_db:
            contrato_match = c_db
            codigo_contrato = c_db.numero_contrato
            contratista_match = c_db.contratista
        else:
            # Contrato no existe aún en la base de datos
            codigo_contrato = cert_contrato_codigo
    elif len(found_contract_codes) == 1:
        # Encontrado exactamente un contrato unívoco en el PDF
        matched_num = list(found_contract_codes)[0]
        contrato_match = db.query(Contrato).filter(Contrato.numero_contrato == matched_num).first()
        if contrato_match:
            codigo_contrato = contrato_match.numero_contrato
            contratista_match = contrato_match.contratista
        else:
            codigo_contrato = matched_num
    elif len(found_contract_codes) > 1:
        # Múltiples códigos de contrato mencionados en el PDF: se requiere selección explícita
        logger.warning(f"Múltiples códigos de contrato detectados en '{filename}': {found_contract_codes}")

    # 9.2 Si el contratista no fue resuelto por contrato directo, identificar al Contratista por NIT
    if not contratista_match and nit_beneficiario:
        clean_doc = re.sub(r'[^\d]', '', nit_beneficiario)
        contratista_match = db.query(Contratista).filter(
            Contratista.numero_documento.like(f"%{clean_doc}%")
        ).first()

    # Si aún no hay match, buscar por Nombre o Razón Social (priorizando coincidencia exacta/completa)
    if not contratista_match and nombre_beneficiario:
        clean_ben = re.sub(r'[\r\n\t]+', ' ', nombre_beneficiario).strip().upper()
        # Coincidencia completa
        contratista_match = db.query(Contratista).filter(
            func.upper(Contratista.nombre_o_razon_social) == clean_ben
        ).first()
        if not contratista_match:
            # Coincidencia parcial con al menos 2 tokens representativos
            tokens = [t for t in re.split(r'[\s,\.]+', clean_ben) if len(t) > 2 and t not in ('SAS', 'S.A.S', 'LTDA', 'E.U', 'Y', 'DE', 'LA', 'EL')]
            if len(tokens) >= 2:
                phrase = f"%{tokens[0]}%{tokens[1]}%"
                contratista_match = db.query(Contratista).filter(
                    Contratista.nombre_o_razon_social.ilike(phrase)
                ).first()
            elif tokens:
                candidates = db.query(Contratista).filter(
                    Contratista.nombre_o_razon_social.ilike(f"%{tokens[0]}%")
                ).all()
                if len(candidates) == 1:
                    contratista_match = candidates[0]

    # 9.3 Con el Contratista identificado, resolver el Contrato correspondiente
    if contratista_match and not contrato_match:
        contratos_del_contratista = db.query(Contrato).filter(
            Contrato.contratista_id == contratista_match.id
        ).all()

        if len(contratos_del_contratista) == 1:
            contrato_match = contratos_del_contratista[0]
            codigo_contrato = contrato_match.numero_contrato
        elif len(contratos_del_contratista) > 1:
            # Si se encontraron códigos en el documento y alguno pertenece a este contratista:
            intersect = [c for c in contratos_del_contratista if c.numero_contrato in found_contract_codes]
            if len(intersect) == 1:
                contrato_match = intersect[0]
                codigo_contrato = contrato_match.numero_contrato
            else:
                # Regla Crítica: ESTÁ PROHIBIDO asignar el pago automáticamente al primer contrato que encuentre.
                # Se marca para selección por el usuario en modal interactivo.
                requiere_seleccion_contrato = True
                contratos_candidatos = [
                    {
                        "id": c.id,
                        "numero_contrato": c.numero_contrato,
                        "objeto": c.objeto or "Sin objeto registrado",
                        "valor_total": float(c.valor_total or 0.0),
                        "vigencia": c.vigencia
                    }
                    for c in contratos_del_contratista
                ]
                codigo_contrato = "PENDIENTE_SELECCION"

    # Si se obtuvo información de Gemini, enriquecer/priorizar sobre la extracción heurística
    if gemini_data:
        if gemini_data.get("codigo_egreso") and not codigo_egreso:
            raw_c = str(gemini_data["codigo_egreso"]).strip()
            digits = re.sub(r'[^\d]', '', raw_c)
            if digits:
                codigo_egreso = f"CE N° {digits.zfill(5)}"
        if gemini_data.get("codigo_orden_pago") and not orden_pago:
            raw_op = str(gemini_data["codigo_orden_pago"]).strip()
            digits_op = re.sub(r'[^\d]', '', raw_op)
            if digits_op:
                orden_pago = f"OP N° {digits_op.zfill(5)}"
        if gemini_data.get("fecha_expedicion") and not fecha_expedicion:
            f_gem = str(gemini_data["fecha_expedicion"]).strip()
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    fecha_expedicion = datetime.strptime(f_gem, fmt).date()
                    fecha_str = f_gem
                    break
                except ValueError:
                    pass
        if gemini_data.get("nombre_beneficiario") and (not nombre_beneficiario or len(nombre_beneficiario) < 3):
            nombre_beneficiario = gemini_data["nombre_beneficiario"].strip()
        if gemini_data.get("nit_beneficiario") and not nit_beneficiario:
            nit_beneficiario = gemini_data["nit_beneficiario"].strip()
        if gemini_data.get("rubro_presupuestal") and not rubro_egreso:
            rubro_egreso = gemini_data["rubro_presupuestal"].strip()
        if gemini_data.get("concepto") and not concepto:
            concepto = gemini_data["concepto"].strip()
        if gemini_data.get("numero_contrato") and not cert_contrato_codigo:
            c_gem = str(gemini_data["numero_contrato"]).strip().upper()
            m_cgem = re.search(r'\b(?:CPS|CS|CO|CA|CD)-\d{3,4}-\d{4}\b', c_gem)
            if m_cgem:
                cert_contrato_codigo = m_cgem.group(0)
        if gemini_data.get("factura_numero") and not factura_numero:
            factura_numero = gemini_data["factura_numero"].strip()
            
        # Tabla de retenciones de Gemini si vino más completa
        gem_ret_rows = gemini_data.get("retenciones_tabla") or []
        if gem_ret_rows and (len(gem_ret_rows) > len(retenciones_items) or not retenciones_items):
            retenciones_items = [
                {
                    "concepto": r.get("descripcion") or r.get("concepto"),
                    "porcentaje": float(r.get("porcentaje") or 0.0),
                    "valor": float(r.get("valor") or 0.0)
                }
                for r in gem_ret_rows
            ]

    # Resolver montos prioritarios
    bruto_in = gemini_data.get("valor_bruto_orden", 0.0) if gemini_data else total_orden
    ret_in = gemini_data.get("total_retenciones", 0.0) if gemini_data else total_retencion
    neto_in = gemini_data.get("valor_neto_pagar", 0.0) if gemini_data else total_pagar
    if total_orden > 0 and bruto_in == 0.0:
        bruto_in = total_orden
    if total_retencion > 0 and ret_in == 0.0:
        ret_in = total_retencion
    if total_pagar > 0 and neto_in == 0.0:
        neto_in = total_pagar

    # Ejecutar motor de reconciliación matemática y cruce con letras
    recon_payload = {
        "valor_bruto_orden": bruto_in,
        "total_retenciones": ret_in,
        "valor_neto_pagar": neto_in,
        "valor_en_letras_egreso": gemini_data.get("valor_en_letras_egreso") if gemini_data else None,
        "valor_en_letras_op": gemini_data.get("valor_en_letras_op") if gemini_data else None,
        "valor_movimiento_bancos": gemini_data.get("valor_movimiento_bancos") if gemini_data else None,
        "retenciones_detalle": retenciones_items
    }
    reconciled = reconcile_payment_amounts(recon_payload)

    total_orden = reconciled["total_orden"]
    total_retencion = reconciled["total_retencion"]
    total_pagar = reconciled["total_pagar"]
    total_estampillas = reconciled["total_estampillas"]
    retenciones_items = reconciled["retenciones_detalle"]

    if retenciones_items:
        retenciones_raw = ", ".join(f"{it['concepto']} ({it['porcentaje']:.2f}%: {it['valor']:.2f})" for it in retenciones_items)
    elif total_retencion == 0.0:
        retenciones_raw = "Sin retenciones"
    else:
        retenciones_raw = f"Retenciones pendientes de desglose ({total_retencion:.2f})"

    # Cruce inteligente por Contrato/Contratista si no se ha resuelto
    if not contrato_match and cert_contrato_codigo:
        c_db = db.query(Contrato).filter(Contrato.numero_contrato == cert_contrato_codigo).first()
        if c_db:
            contrato_match = c_db
            codigo_contrato = c_db.numero_contrato
            contratista_match = c_db.contratista

    if not contratista_match and nit_beneficiario:
        clean_doc = re.sub(r'[^\d]', '', nit_beneficiario)
        contratista_match = db.query(Contratista).filter(
            Contratista.numero_documento.like(f"%{clean_doc}%")
        ).first()

    if not contratista_match and nombre_beneficiario:
        clean_ben = re.sub(r'[\r\n\t]+', ' ', nombre_beneficiario).strip().upper()
        contratista_match = db.query(Contratista).filter(
            func.upper(Contratista.nombre_o_razon_social) == clean_ben
        ).first()
        if not contratista_match:
            tokens = [t for t in re.split(r'[\s,\.]+', clean_ben) if len(t) > 2 and t not in ('SAS', 'S.A.S', 'LTDA', 'E.U', 'Y', 'DE', 'LA', 'EL')]
            if len(tokens) >= 2:
                phrase = f"%{tokens[0]}%{tokens[1]}%"
                contratista_match = db.query(Contratista).filter(
                    Contratista.nombre_o_razon_social.ilike(phrase)
                ).first()
            elif tokens:
                candidates = db.query(Contratista).filter(
                    Contratista.nombre_o_razon_social.ilike(f"%{tokens[0]}%")
                ).all()
                if len(candidates) == 1:
                    contratista_match = candidates[0]

    if contratista_match and not contrato_match:
        contratos_del_contratista = db.query(Contrato).filter(
            Contrato.contratista_id == contratista_match.id
        ).all()

        if len(contratos_del_contratista) == 1:
            contrato_match = contratos_del_contratista[0]
            codigo_contrato = contrato_match.numero_contrato
        elif len(contratos_del_contratista) > 1:
            intersect = [c for c in contratos_del_contratista if c.numero_contrato in found_contract_codes]
            if len(intersect) == 1:
                contrato_match = intersect[0]
                codigo_contrato = contrato_match.numero_contrato
            else:
                requiere_seleccion_contrato = True
                contratos_candidatos = [
                    {
                        "id": c.id,
                        "numero_contrato": c.numero_contrato,
                        "objeto": c.objeto or "Sin objeto registrado",
                        "valor_total": float(c.valor_total or 0.0),
                        "vigencia": c.vigencia
                    }
                    for c in contratos_del_contratista
                ]
                codigo_contrato = "PENDIENTE_SELECCION"

    if contratista_match and (not nombre_beneficiario or len(nombre_beneficiario) < 3):
        nombre_beneficiario = contratista_match.nombre_o_razon_social

    return {
        "archivo": filename,
        "codigo_contrato": codigo_contrato or (contrato_match.numero_contrato if contrato_match else "SIN_ASIGNAR"),
        "codigo_egreso": codigo_egreso or "CE N° PENDIENTE",
        "fecha_expedicion": fecha_expedicion,
        "fecha_expedicion_str": fecha_str or (fecha_expedicion.strftime("%d/%m/%Y") if fecha_expedicion else datetime.now().strftime("%d/%m/%Y")),
        "nombre_beneficiario": nombre_beneficiario or (contratista_match.nombre_o_razon_social if contratista_match else "BENEFICIARIO DESCONOCIDO"),
        "nit_beneficiario": nit_beneficiario or (contratista_match.numero_documento if contratista_match else None),
        "rubro_egreso": rubro_egreso or (contrato_match.cdp_rubro if contrato_match else "2.1.2.02.02.008"),
        "total_orden": total_orden,
        "total_retencion": total_retencion,
        "total_pagar": total_pagar,
        "total_estampillas": total_estampillas,
        "retefuente": reconciled.get("retefuente", 0.0),
        "reteiva": reconciled.get("reteiva", 0.0),
        "reteica": reconciled.get("reteica", 0.0),
        "otras_retenciones": reconciled.get("otras_retenciones", 0.0),
        "desglose_retenciones": reconciled.get("desglose_retenciones", []),
        "retenciones_detalle": retenciones_items,
        "retenciones_raw": retenciones_raw,
        "orden_pago": orden_pago,
        "codigo_orden_pago": orden_pago,
        "numero_orden_pago": re.sub(r'[^\d]', '', orden_pago) if orden_pago else None,
        "factura_numero": factura_numero,
        "concepto": concepto,
        "contrato_id": contrato_match.id if contrato_match else None,
        "contratista_id": contratista_match.id if contratista_match else None,
        "contratista_nombre": contratista_match.nombre_o_razon_social if contratista_match else None,
        "contrato_numero": contrato_match.numero_contrato if contrato_match else None,
        "requiere_seleccion_contrato": requiere_seleccion_contrato,
        "contratos_candidatos": contratos_candidatos,
        "cert_contrato_codigo": cert_contrato_codigo,
        "cert_contratista_nombre": cert_contratista_nombre,
        "cert_contratista_nit": cert_contratista_nit
    }


def format_record_to_txt_line(record: Dict[str, Any]) -> str:
    """Genera la línea CSV/TXT con las 8 columnas requeridas y el desglose de retenciones/estampillas."""
    tot_orden_str = f"{record['total_orden']:.2f}".rstrip('0').rstrip('.') if '.' in f"{record['total_orden']:.2f}" else str(int(record['total_orden']))
    tot_ret_str = f"{record['total_retencion']:.2f}".rstrip('0').rstrip('.') if '.' in f"{record['total_retencion']:.2f}" else str(int(record['total_retencion']))
    tot_pag_str = f"{record['total_pagar']:.2f}".rstrip('0').rstrip('.') if '.' in f"{record['total_pagar']:.2f}" else str(int(record['total_pagar']))
    
    base_line = f"{record['codigo_contrato']},{record['codigo_egreso']},{record['fecha_expedicion_str']},{record['nombre_beneficiario']},{record['rubro_egreso']},{tot_orden_str},{tot_ret_str},{tot_pag_str}"
    
    ret_items = record.get('retenciones_detalle') or []
    if ret_items:
        items_str = ",".join(f"{it['concepto']} ({it['porcentaje']:.2f}%: {it['valor']:.2f})" for it in ret_items)
        return f"{base_line},{items_str}"
    elif record.get('total_retencion', 0.0) == 0.0:
        return f"{base_line},Sin retenciones"
    elif record.get('retenciones_raw') and record.get('retenciones_raw') != "Sin retenciones":
        return f"{base_line},{record['retenciones_raw']}"
    else:
        return base_line

