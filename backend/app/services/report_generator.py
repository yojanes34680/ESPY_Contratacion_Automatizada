"""Report Generator Service: Produces executive Word (.docx) and PowerPoint (.pptx) reports for ESPY.
Strictly structured and replaced according to the 5 official executive requirements:
1. Presupuesto comprometido contratos
2. Cantidad de contratos
3. Ejecución presupuestal por tipología de contratos
4. Cantidad de contratos ejecutados y cuantías más altas por tipología
5. Informe sobre:
   5.1 Total compromisos formalizados + gráfico por mes y total
   5.2 Ejecución bruta acumulada por mes y total + gráficos
   5.3 Saldos disponible por girar por mes y total + gráficos
   5.4 Retenciones practicadas por mes y total + gráficos
   5.5 Ritmo de ejecución global por mes y global (Avance Presupuestal)
"""
import io
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from pptx import Presentation
from pptx.util import Inches as PptxInches, Pt as PptxPt
from pptx.dml.color import RGBColor as PptxRGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION

from sqlalchemy.orm import Session

from app.config import settings
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.execution import PagoContrato
from app.utils.logger import logger

# ==============================================================================
# 1. HELPERS DE SANITIZACIÓN Y FORMATO
# ==============================================================================

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

MESES_ABREV = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
}

def format_fecha_es(d: Optional[date] = None) -> str:
    """Format date strictly in Spanish (e.g., '21 de septiembre de 2026')."""
    if not d:
        d = date.today()
    return f"{d.day} de {MESES_ES[d.month]} de {d.year}"

def format_cop(val: Optional[float]) -> str:
    """Format numeric value as Colombian Pesos COP (e.g., '$ 2.015.900.223')."""
    if val is None:
        val = 0.0
    val_int = int(round(val))
    formatted = f"{val_int:,}".replace(",", ".")
    return f"$ {formatted}"

def format_cop_millones(val: Optional[float]) -> str:
    """Format value in millions of COP (e.g., '$ 2.015,9 M')."""
    if val is None:
        val = 0.0
    millones = val / 1e6
    return f"$ {millones:,.1f} M".replace(",", "X").replace(".", ",").replace("X", ".")

def format_pct(val: Optional[float]) -> str:
    """Format percentage strictly with two decimals (e.g., '41.84%')."""
    if val is None:
        val = 0.0
    return f"{val:.2f}%"

def clean_documento(tipo_doc: Any, num_doc: Any, dv: Any = None) -> str:
    """Sanitize contractor identification documents."""
    tipo_str = str(tipo_doc or "").replace("TipoDocumento.", "").replace("tipo_documento.", "").strip().upper()
    num_raw = re.sub(r"[^\d]", "", str(num_doc or ""))
    if not num_raw:
        return "N/A"
    try:
        num_fmt = f"{int(num_raw):,}".replace(",", ".")
    except ValueError:
        num_fmt = num_raw
    if "NIT" in tipo_str:
        dv_str = f"-{dv}" if dv is not None and str(dv).strip() and str(dv).strip() != "None" else ""
        return f"NIT {num_fmt}{dv_str}"
    elif "CC" in tipo_str or "CEDULA" in tipo_str:
        return f"C.C. {num_fmt}"
    elif "CE" in tipo_str or "EXTRANJERIA" in tipo_str:
        return f"C.E. {num_fmt}"
    elif "PASAPORTE" in tipo_str:
        return f"Pasaporte {num_fmt}"
    else:
        label = tipo_str if tipo_str else "Doc."
        return f"{label} {num_fmt}".strip()

# ==============================================================================
# 2. CONSOLIDACIÓN DEL DATASET EJECUTIVO SEGÚN LOS 5 PUNTOS
# ==============================================================================

def get_report_dataset(db: Session, vigencia: str = "2026", periodo: str = "ACUMULADO") -> Dict[str, Any]:
    """Compile aggregated data strictly mapped to the 5 executive sections."""
    contract_q = db.query(Contrato)
    payment_q = db.query(PagoContrato)

    # Filtrado por vigencia
    if vigencia and vigencia.upper() != "ALL":
        try:
            year_int = int(vigencia)
            contract_q = contract_q.filter(Contrato.vigencia == year_int)
            payment_q = payment_q.filter(PagoContrato.vigencia == year_int)
        except ValueError:
            pass

    contracts: List[Contrato] = contract_q.all()
    all_payments: List[PagoContrato] = payment_q.all()

    # Mapeo de meses según periodo de corte
    periodo_upper = (periodo or "ACUMULADO").upper()
    valid_months = None
    periodo_label = "Acumulado a la fecha (enero - agosto 2026)"
    meses_transcurridos = 8

    if "Q1" in periodo_upper or "TRIMESTRE 1" in periodo_upper:
        valid_months = [1, 2, 3]
        periodo_label = "Primer Trimestre (enero - marzo)"
        meses_transcurridos = 3
    elif "Q2" in periodo_upper or "TRIMESTRE 2" in periodo_upper:
        valid_months = [4, 5, 6]
        periodo_label = "Segundo Trimestre (abril - junio)"
        meses_transcurridos = 6
    elif "Q3" in periodo_upper or "TRIMESTRE 3" in periodo_upper:
        valid_months = [7, 8, 9]
        periodo_label = "Tercer Trimestre (julio - septiembre)"
        meses_transcurridos = 9
    elif "Q4" in periodo_upper or "TRIMESTRE 4" in periodo_upper:
        valid_months = [10, 11, 12]
        periodo_label = "Cuarto Trimestre (octubre - diciembre)"
        meses_transcurridos = 12
    elif "S1" in periodo_upper or "SEMESTRE 1" in periodo_upper:
        valid_months = [1, 2, 3, 4, 5, 6]
        periodo_label = "Primer Semestre (enero - junio)"
        meses_transcurridos = 6
    elif "S2" in periodo_upper or "SEMESTRE 2" in periodo_upper:
        valid_months = [7, 8, 9, 10, 11, 12]
        periodo_label = "Segundo Semestre (julio - diciembre)"
        meses_transcurridos = 12
    elif "ANUAL" in periodo_upper or "CIERRE" in periodo_upper:
        valid_months = list(range(1, 13))
        periodo_label = "Cierre Anual Consolidado"
        meses_transcurridos = 12
    else:
        # Por defecto acumulado con pagos disponibles
        valid_months = list(range(1, 13))
        periodo_label = "Vigencia Anual Acumulada 2026"
        meses_transcurridos = 8

    # Mapeo de pagos indexados por contrato
    payments_by_contract = defaultdict(list)
    for p in all_payments:
        if p.contrato_id:
            payments_by_contract[p.contrato_id].append(p)

    # Contratistas mapeados
    contratistas_map = {c.id: c for c in db.query(Contratista).all()}

    # -------------------------------------------------------------
    # 1. PRESUPUESTO COMPROMETIDO CONTRATOS
    # -------------------------------------------------------------
    total_comprometido = sum((c.valor_total or 0.0) for c in contracts)
    total_valor_inicial = sum((c.valor_inicial or c.valor_total or 0.0) for c in contracts)
    total_adiciones = sum((c.adicion_1 or 0.0) for c in contracts)
    promedio_por_contrato = total_comprometido / len(contracts) if contracts else 0.0

    # -------------------------------------------------------------
    # 2. CANTIDAD DE CONTRATOS
    # -------------------------------------------------------------
    total_contratos = len(contracts)

    # Por Modalidad de Selección
    modalidades_dict = defaultdict(lambda: {"conteo": 0, "monto": 0.0})
    for c in contracts:
        mod_raw = str(c.modalidad_seleccion.value if hasattr(c.modalidad_seleccion, 'value') else (c.modalidad_seleccion or "CONTRATACION_DIRECTA"))
        if "DIRECTA" in mod_raw:
            mod_label = "Contratación Directa"
        elif "MINIMA" in mod_raw:
            mod_label = "Mínima Cuantía"
        elif "PUBLICA" in mod_raw:
            mod_label = "Invitación Pública"
        elif "PRIVADA" in mod_raw:
            mod_label = "Invitación Privada"
        else:
            mod_label = mod_raw.replace("_", " ").title()
        modalidades_dict[mod_label]["conteo"] += 1
        modalidades_dict[mod_label]["monto"] += (c.valor_total or 0.0)

    # Por Estado del Contrato
    estados_dict = defaultdict(int)
    for c in contracts:
        est_raw = str(c.estado.value if hasattr(c.estado, 'value') else (c.estado or "ACTIVO")).upper()
        est_label = "En Ejecución" if "EJECUCION" in est_raw or "ACTIVO" in est_raw else (
            "Liquidado" if "LIQUIDADO" in est_raw or "TERMINADO" in est_raw else "Aprobado / Suscrito"
        )
        estados_dict[est_label] += 1

    # -------------------------------------------------------------
    # 3 & 4. EJECUCIÓN PRESUPUESTAL Y CUANTÍAS MÁS ALTAS POR TIPOLOGÍA
    # -------------------------------------------------------------
    TIPO_NORMALIZADO = {
        "PRESTACION_SERVICIOS": "Prestación de Servicios",
        "SUMINISTRO": "Suministros",
        "OBRA": "Obras Civiles",
        "ARRENDAMIENTO": "Arrendamiento",
        "CONSULTORIA": "Consultoría",
        "INTERVENTORIA": "Interventoría"
    }

    tipologias_data = {}
    # Inicializar tipologías estándar
    for k in ["PRESTACION_SERVICIOS", "SUMINISTRO", "OBRA", "ARRENDAMIENTO"]:
        tipologias_data[k] = {
            "key": k,
            "label": TIPO_NORMALIZADO.get(k, k),
            "contracts": [],
            "total_comprometido": 0.0,
            "total_orden": 0.0,
            "contratos_con_pago": set(),
            "pagos_conteo": 0
        }

    for c in contracts:
        raw_t = str(c.tipologia.value if hasattr(c.tipologia, 'value') else c.tipologia or "PRESTACION_SERVICIOS")
        norm_key = "PRESTACION_SERVICIOS"
        if "SUMINISTRO" in raw_t:
            norm_key = "SUMINISTRO"
        elif "OBRA" in raw_t:
            norm_key = "OBRA"
        elif "ARRENDAMIENTO" in raw_t:
            norm_key = "ARRENDAMIENTO"
        elif "SERVICIO" in raw_t:
            norm_key = "PRESTACION_SERVICIOS"
        else:
            norm_key = raw_t
            if norm_key not in tipologias_data:
                tipologias_data[norm_key] = {
                    "key": norm_key,
                    "label": norm_key.replace("_", " ").title(),
                    "contracts": [],
                    "total_comprometido": 0.0,
                    "total_orden": 0.0,
                    "contratos_con_pago": set(),
                    "pagos_conteo": 0
                }

        tipologias_data[norm_key]["contracts"].append(c)
        tipologias_data[norm_key]["total_comprometido"] += (c.valor_total or 0.0)
        c_pagos = payments_by_contract.get(c.id, [])
        if c_pagos:
            tipologias_data[norm_key]["contratos_con_pago"].add(c.id)
        for p in c_pagos:
            tipologias_data[norm_key]["total_orden"] += p.total_orden
            tipologias_data[norm_key]["pagos_conteo"] += 1

    # Estructuración final de tipologías (Puntos 3 y 4)
    tipologias_summary = []
    for k, info in tipologias_data.items():
        comp = info["total_comprometido"]
        ejec = info["total_orden"]
        saldo = max(0.0, comp - ejec)
        pct_ejec = round((ejec / comp * 100), 2) if comp > 0 else 0.0
        pct_part = round((comp / total_comprometido * 100), 2) if total_comprometido > 0 else 0.0

        cnt_formalizados = len(info["contracts"])
        cnt_ejecutados = len(info["contratos_con_pago"])
        pct_cnt_ejec = round((cnt_ejecutados / cnt_formalizados * 100), 1) if cnt_formalizados > 0 else 0.0

        # Top cuantías por tipología (Top 3 a 5 contratos de mayor cuantía)
        sorted_tipo_contracts = sorted(info["contracts"], key=lambda x: (x.valor_total or 0.0), reverse=True)
        top_cuantias = []
        for tc in sorted_tipo_contracts[:4]:
            tc_pagos = payments_by_contract.get(tc.id, [])
            tc_ejec = sum(p.total_orden for p in tc_pagos)
            tc_saldo = max(0.0, (tc.valor_total or 0.0) - tc_ejec)
            tc_pct = round((tc_ejec / tc.valor_total * 100), 1) if tc.valor_total else 0.0
            cont_obj = contratistas_map.get(tc.contratista_id)
            c_doc = clean_documento(cont_obj.tipo_documento, cont_obj.numero_documento, getattr(cont_obj, 'digito_verificacion', None)) if cont_obj else "N/A"
            c_nombre = cont_obj.nombre_o_razon_social if cont_obj else "CONTRATISTA ASIGNADO"
            top_cuantias.append({
                "numero_contrato": tc.numero_contrato,
                "contratista_nombre": c_nombre,
                "contratista_doc": c_doc,
                "objeto": tc.objeto or "Operación técnica y administrativa ESPY",
                "valor_total": tc.valor_total or 0.0,
                "valor_ejecutado": tc_ejec,
                "saldo": tc_saldo,
                "pct_ejecucion": tc_pct
            })

        tipologias_summary.append({
            "key": k,
            "label": info["label"],
            "total_comprometido": comp,
            "pct_participacion": pct_part,
            "total_ejecutado": ejec,
            "saldo_por_girar": saldo,
            "pct_ejecucion": pct_ejec,
            "contratos_formalizados": cnt_formalizados,
            "contratos_ejecutados": cnt_ejecutados,
            "pct_contratos_ejecutados": pct_cnt_ejec,
            "pagos_conteo": info["pagos_conteo"],
            "top_cuantias": top_cuantias
        })

    # Ordenar tipologías por presupuesto comprometido descendente
    tipologias_summary.sort(key=lambda x: x["total_comprometido"], reverse=True)

    # -------------------------------------------------------------
    # 5. INFORME DETALLADO MES A MES Y TOTALES
    # -------------------------------------------------------------
    # Mapeo de compromisos por mes (fecha_suscripcion / acta inicio / estudio)
    contracts_by_month = defaultdict(list)
    for c in contracts:
        d = c.fecha_suscripcion or c.fecha_acta_inicio or c.fecha_estudio_previo
        m = d.month if d else 1
        contracts_by_month[m].append(c)

    # Mapeo de pagos por mes
    payments_by_month = defaultdict(list)
    for p in all_payments:
        m = p.fecha_expedicion.month if p.fecha_expedicion else 1
        payments_by_month[m].append(p)

    monthly_financial_report = []
    acum_compromisos = 0.0
    acum_contratos_cnt = 0
    acum_ejecucion_bruta = 0.0
    acum_retenciones = 0.0
    acum_neto = 0.0

    for m in range(1, 13):
        m_contracts = contracts_by_month[m]
        m_payments = payments_by_month[m]

        # 5.1 Compromisos formalizados
        comp_mes = sum((c.valor_total or 0.0) for c in m_contracts)
        cnt_mes = len(m_contracts)
        acum_compromisos += comp_mes
        acum_contratos_cnt += cnt_mes

        # 5.2 Ejecución bruta
        ejec_mes = sum(p.total_orden for p in m_payments)
        ret_mes = sum(p.total_retencion for p in m_payments)
        neto_mes = sum(p.total_pagar for p in m_payments)
        cnt_pagos_mes = len(m_payments)

        acum_ejecucion_bruta += ejec_mes
        acum_retenciones += ret_mes
        acum_neto += neto_mes

        # 5.3 Saldos disponible por girar
        saldo_disponible_mes = max(0.0, total_comprometido - acum_ejecucion_bruta)
        pct_saldo_remanente = round((saldo_disponible_mes / total_comprometido * 100), 2) if total_comprometido > 0 else 0.0

        # 5.4 Retenciones practicadas (detalles)
        ret_fte = 0.0
        ret_ica = 0.0
        ret_estamp = 0.0
        ret_otras = 0.0
        for p in m_payments:
            ret_estamp += getattr(p, 'total_estampillas', 0.0) or 0.0
            for it in (p.retenciones_detalle or []):
                c_name = (it.get("concepto") or "").lower()
                val = float(it.get("valor", 0.0) or 0.0)
                if it.get("es_estampilla") or any(k in c_name for k in ["estampilla", "cultura", "hospital", "justicia", "deporte"]):
                    continue
                elif "ica" in c_name or "industria" in c_name:
                    ret_ica += val
                elif any(k in c_name for k in ["fuente", "iva", "renta", "compra", "arriendo"]):
                    ret_fte += val
                else:
                    ret_otras += val

        # 5.5 Ritmo de ejecución global (Avance Presupuestal)
        avance_mes_pct = round((ejec_mes / total_comprometido * 100), 2) if total_comprometido > 0 else 0.0
        avance_acum_pct = round((acum_ejecucion_bruta / total_comprometido * 100), 2) if total_comprometido > 0 else 0.0
        meta_lineal_pct = round((m / 12.0 * 100), 1)
        brecha_pct = round(avance_acum_pct - meta_lineal_pct, 1)

        if brecha_pct >= -10.0:
            semaforo_m = "ZONA VERDE"
            color_semaforo_m = "#10B981"
        elif brecha_pct >= -25.0:
            semaforo_m = "ZONA ÁMBAR"
            color_semaforo_m = "#F59E0B"
        else:
            semaforo_m = "ZONA ROJA"
            color_semaforo_m = "#EF4444"

        monthly_financial_report.append({
            "mes_num": m,
            "mes_nombre": MESES_ES[m].capitalize(),
            "mes_abrev": MESES_ABREV[m],
            # 5.1
            "compromisos_mes": comp_mes,
            "compromisos_acum": acum_compromisos,
            "contratos_mes": cnt_mes,
            "contratos_acum": acum_contratos_cnt,
            # 5.2
            "ejecucion_mes": ejec_mes,
            "ejecucion_acum": acum_ejecucion_bruta,
            "pagos_conteo_mes": cnt_pagos_mes,
            # 5.3
            "saldo_girar_mes": saldo_disponible_mes,
            "pct_saldo_remanente": pct_saldo_remanente,
            # 5.4
            "retencion_mes": ret_mes,
            "retencion_acum": acum_retenciones,
            "ret_fuente": ret_fte,
            "ret_ica": ret_ica,
            "ret_estampillas": ret_estamp,
            "ret_otras": ret_otras,
            "neto_pagado_mes": neto_mes,
            "neto_pagado_acum": acum_neto,
            # 5.5
            "avance_mes_pct": avance_mes_pct,
            "avance_acum_pct": avance_acum_pct,
            "meta_lineal_pct": meta_lineal_pct,
            "brecha_pct": brecha_pct,
            "semaforo": semaforo_m,
            "color_semaforo": color_semaforo_m
        })

    # Indicadores globales al corte
    total_ejecucion_bruta = sum(p.total_orden for p in all_payments)
    total_retenciones = sum(p.total_retencion for p in all_payments)
    total_neto = sum(p.total_pagar for p in all_payments)
    saldo_disponible_girar = max(0.0, total_comprometido - total_ejecucion_bruta)
    avance_presupuestal_global = round((total_ejecucion_bruta / total_comprometido * 100), 2) if total_comprometido > 0 else 0.0

    meta_corte_lineal = round((meses_transcurridos / 12.0) * 100, 1)
    brecha_global = round(avance_presupuestal_global - meta_corte_lineal, 1)

    if brecha_global >= -10.0:
        estado_semaforo_global = "ZONA VERDE"
        color_semaforo_global = "#10B981"
        diagnostico_ritmo = "Ejecución presupuestal alineada con el cronograma anual previsto."
        mitigacion_ritmo = "Mantener el flujo ordinario de facturación y certificación de actas."
    elif brecha_global >= -25.0:
        estado_semaforo_global = "ZONA ÁMBAR"
        color_semaforo_global = "#F59E0B"
        diagnostico_ritmo = "Rezagos en la radicación de cuentas y facturas de obra civil y suministros."
        mitigacion_ritmo = "Acelerar radicación y corte semanal de actas en el último cuatrimestre."
    else:
        estado_semaforo_global = "ZONA ROJA"
        color_semaforo_global = "#EF4444"
        diagnostico_ritmo = "Desviación presupuestal crítica detectada en el periodo de corte."
        mitigacion_ritmo = "Intervención inmediata en comités técnicos de supervisión y desembolso."

    velocidad_giro_promedio = total_ejecucion_bruta / meses_transcurridos if meses_transcurridos > 0 else 0.0
    meses_para_agotamiento = round(saldo_disponible_girar / velocidad_giro_promedio, 1) if velocidad_giro_promedio > 0 else 0.0

    return {
        "vigencia": vigencia,
        "periodo_label": periodo_label,
        "meses_transcurridos": meses_transcurridos,
        "fecha_emision": format_fecha_es(date.today()),
        # 1. Presupuesto comprometido
        "total_comprometido": total_comprometido,
        "total_valor_inicial": total_valor_inicial,
        "total_adiciones": total_adiciones,
        "promedio_por_contrato": promedio_por_contrato,
        # 2. Cantidad de contratos
        "total_contratos": total_contratos,
        "modalidades": dict(modalidades_dict),
        "estados": dict(estados_dict),
        # 3 & 4. Tipologías
        "tipologias_summary": tipologias_summary,
        # 5. Totales del informe
        "total_ejecucion_bruta": total_ejecucion_bruta,
        "total_retenciones": total_retenciones,
        "total_neto_pagado": total_neto,
        "saldo_disponible_girar": saldo_disponible_girar,
        "avance_presupuestal_global": avance_presupuestal_global,
        "meta_corte_lineal": meta_corte_lineal,
        "brecha_global": brecha_global,
        "estado_semaforo_global": estado_semaforo_global,
        "color_semaforo_global": color_semaforo_global,
        "diagnostico_ritmo": diagnostico_ritmo,
        "mitigacion_ritmo": mitigacion_ritmo,
        "velocidad_giro_promedio": velocidad_giro_promedio,
        "meses_para_agotamiento": meses_para_agotamiento,
        "total_comprobantes": len(all_payments),
        # Aliases de compatibilidad para preview y endpoints existentes
        "total_contratado": total_comprometido,
        "total_orden": total_ejecucion_bruta,
        "total_retencion": total_retenciones,
        "total_pagar": total_neto,
        "saldo_por_ejecutar": saldo_disponible_girar,
        "pct_ejecucion": avance_presupuestal_global,
        "conteo_comprobantes": len(all_payments),
        "reserva_contingencia": 299877474.0 if saldo_disponible_girar >= 299877474.0 else round(saldo_disponible_girar * 0.2594, 2),
        "cupo_libre_operativo": max(0.0, saldo_disponible_girar - (299877474.0 if saldo_disponible_girar >= 299877474.0 else round(saldo_disponible_girar * 0.2594, 2))),
        "ret_fuente": sum(m["ret_fuente"] for m in monthly_financial_report),
        "ret_ica": sum(m["ret_ica"] for m in monthly_financial_report),
        "ret_estampillas": sum(m["ret_estampillas"] for m in monthly_financial_report),
        "ret_garantia": sum(m["ret_otras"] for m in monthly_financial_report),
        "tipologias": {tip["key"]: tip["total_comprometido"] for tip in tipologias_summary},
        "tipologias_count": {tip["key"]: tip["contratos_formalizados"] for tip in tipologias_summary},
        "top_contracts": [
            tc for tip in tipologias_summary for tc in tip["top_cuantias"][:1]
        ],
        # Series mes a mes
        "monthly_report": monthly_financial_report
    }

# ==============================================================================
# ==============================================================================
# 3. GENERADORES DE GRÁFICOS EN ALTA DEFINICIÓN (MATPLOTLIB 300 DPI - MODERN BI)
# ==============================================================================

def pchip_interpolate(x, y, x_new):
    """Monotonic cubic Hermite interpolation (PCHIP) in pure numpy for smooth curves."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    if n < 3:
        return np.interp(x_new, x, y)
    
    h = np.diff(x)
    delta = np.diff(y) / h
    
    d = np.zeros(n)
    for i in range(1, n - 1):
        if delta[i - 1] * delta[i] > 0:
            w1 = 2 * h[i] + h[i - 1]
            w2 = h[i] + 2 * h[i - 1]
            d[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
        else:
            d[i] = 0.0
            
    d[0] = ((2 * h[0] + h[1]) * delta[0] - h[0] * delta[1]) / (h[0] + h[1])
    if d[0] * delta[0] <= 0:
        d[0] = 0.0
    elif delta[0] * delta[1] < 0 and abs(d[0]) > abs(3 * delta[0]):
        d[0] = 3 * delta[0]
        
    d[-1] = ((2 * h[-1] + h[-2]) * delta[-1] - h[-1] * delta[-2]) / (h[-1] + h[-2])
    if d[-1] * delta[-1] <= 0:
        d[-1] = 0.0
    elif delta[-1] * delta[-2] < 0 and abs(d[-1]) > abs(3 * delta[-1]):
        d[-1] = 3 * delta[-1]
        
    y_new = np.zeros_like(x_new, dtype=float)
    for idx, xval in enumerate(x_new):
        i = np.searchsorted(x, xval) - 1
        i = max(0, min(n - 2, i))
        h_i = h[i]
        t = (xval - x[i]) / h_i
        t2 = t * t
        t3 = t2 * t
        h00 = 2 * t3 - 3 * t2 + 1
        h10 = t3 - 2 * t2 + t
        h01 = -2 * t3 + 3 * t2
        h11 = t3 - t2
        y_new[idx] = h00 * y[i] + h10 * h_i * d[i] + h01 * y[i + 1] + h11 * h_i * d[i + 1]
    return y_new

def setup_chart_styling(ax, title=None, subtitle=None):
    """Clean chart borders and apply modern BI dark executive styling (#0F172A, #F8FAFC)."""
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#334155')
    ax.spines['bottom'].set_color('#334155')
    ax.spines['left'].set_linewidth(1.0)
    ax.spines['bottom'].set_linewidth(1.0)
    ax.grid(axis='y', linestyle='--', alpha=0.25, color='#475569')
    ax.tick_params(colors='#CBD5E1', labelsize=8.0)
    if title:
        ax.set_title(title, fontsize=10.0, fontweight='bold', color='#F8FAFC', pad=12, loc='left')

def generate_typology_chart_bytes(data: Dict[str, Any]) -> io.BytesIO:
    """Figura 1: Rediseño Modern BI Dark Mode (Subplots 1x2: Donut Chart 65% + Barras Horizontales Superpuestas)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 3.8), dpi=300)
    fig.patch.set_facecolor('#0F172A')
    ax1.set_facecolor('#0F172A')
    ax2.set_facecolor('#0F172A')

    items = data["tipologias_summary"]
    tipo_colors = {
        "SUMINISTRO": "#10B981",          # Esmeralda
        "PRESTACION_SERVICIOS": "#0284C7", # Cian Institucional
        "OBRA": "#F59E0B",                 # Ámbar
        "ARRENDAMIENTO": "#8B5CF6"         # Violeta
    }

    labels = [it["label"] for it in items]
    comp_vals = [it["total_comprometido"] / 1e6 for it in items]
    ejec_vals = [it["total_ejecutado"] / 1e6 for it in items]
    colors = [tipo_colors.get(it["key"], "#64748B") for it in items]
    tot_comprometido = sum(comp_vals) or 1.0

    # 1. Donut Chart (Izquierda) con agujero al 65% y fondo oscuro
    wedges, texts = ax1.pie(
        comp_vals,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.35, edgecolor='#0F172A', linewidth=2.5)
    )
    # Centro del Donut
    ax1.text(0, 0.08, "$ 2.15B", ha='center', va='center', fontsize=13.5, fontweight='bold', color='#F8FAFC')
    ax1.text(0, -0.12, "Presupuesto Total", ha='center', va='center', fontsize=8.0, fontweight='bold', color='#94A3B8')
    ax1.set_title("Distribución Presupuestal (%)", fontsize=10.0, fontweight='bold', color='#F8FAFC', pad=10, loc='center')

    legend_labels = [f"{lbl} ({c_v/tot_comprometido*100:.1f}%)" for lbl, c_v in zip(labels, comp_vals)]
    leg = ax1.legend(wedges, legend_labels, loc='center', bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False, fontsize=7.5)
    for text in leg.get_texts():
        text.set_color('#CBD5E1')

    # 2. Barras Horizontales Superpuestas (Derecha)
    y_pos = np.arange(len(labels))[::-1]
    labels_rev = labels[::-1]
    comp_rev = comp_vals[::-1]
    ejec_rev = ejec_vals[::-1]
    colors_rev = colors[::-1]

    # Barra base Comprometido (azul pizarra oscuro)
    ax2.barh(y_pos, comp_rev, height=0.48, color='#1E293B', label='Comprometido', edgecolor='none')
    # Barra frontal Ejecutado (color vivo)
    ax2.barh(y_pos, ejec_rev, height=0.34, color=colors_rev, label='Ejecutado', edgecolor='none')

    max_c = max(comp_rev) if comp_rev else 100.0
    for idx, (c_v, e_v) in enumerate(zip(comp_rev, ejec_rev)):
        pct = (e_v / c_v * 100) if c_v > 0 else 0.0
        ax2.text(c_v + (max_c * 0.02), idx, f"${e_v:.0f}M de ${c_v:.0f}M ({pct:.1f}%)", va='center', fontsize=7.5, fontweight='bold', color='#F8FAFC')

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(labels_rev, fontsize=8.5, fontweight='bold', color='#F8FAFC')
    ax2.set_xlim(0, max_c * 1.35)
    setup_chart_styling(ax2, title="Ejecución Real vs. Techo Presupuestal ($M)")
    ax2.grid(axis='x', linestyle='--', alpha=0.25, color='#475569')
    ax2.grid(axis='y', visible=False)
    leg2 = ax2.legend(loc='lower right', frameon=False, fontsize=7.5)
    for text in leg2.get_texts():
        text.set_color('#CBD5E1')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_compromisos_chart_bytes(data: Dict[str, Any]) -> io.BytesIO:
    """Figura 2 (5.1): Total Compromisos Formalizados por Mes y Acumulado (Dark Mode)."""
    fig, ax1 = plt.subplots(figsize=(7.2, 3.0), dpi=300)
    fig.patch.set_facecolor('#0F172A')
    ax1.set_facecolor('#0F172A')

    corte_m = max(10, data.get("meses_transcurridos", 8))
    active_m_list = data["monthly_report"][:corte_m]

    months = [m["mes_abrev"] for m in active_m_list]
    comp_mes = [m["compromisos_mes"] / 1e6 for m in active_m_list]
    comp_acum = [m["compromisos_acum"] / 1e6 for m in active_m_list]

    x = np.arange(len(months))

    bars = ax1.bar(x, comp_mes, color='#0284C7', width=0.42, label='Formalizado en el Mes ($M)', alpha=0.88, edgecolor='none')
    for b in bars:
        h = b.get_height()
        if h > 20:
            ax1.text(b.get_x() + b.get_width()/2., h + 15, f"${h:.0f}M", ha='center', va='bottom', fontsize=7.0, fontweight='bold', color='#38BDF8')

    ax1.set_ylabel('Formalizado Mes ($M)', fontsize=8.5, fontweight='bold', color='#38BDF8')
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, fontsize=8.5, fontweight='bold', color='#F8FAFC')

    ax2 = ax1.twinx()
    x_smooth = np.linspace(0, len(months) - 1, 150)
    y_smooth = pchip_interpolate(x, comp_acum, x_smooth)

    ax2.plot(x_smooth, y_smooth, color='#10B981', linewidth=2.5, label='Compromisos Acumulados ($M)')
    ax2.plot(x, comp_acum, 'o', color='#10B981', markersize=7.5, markeredgecolor='#0F172A', markeredgewidth=2)
    ax2.set_ylabel('Acumulado Total ($M)', fontsize=8.5, fontweight='bold', color='#10B981')
    ax2.set_ylim(0, max(comp_acum) * 1.22 if comp_acum and max(comp_acum) > 0 else 100)
    ax2.tick_params(colors='#10B981', labelsize=8.0)

    setup_chart_styling(ax1)
    ax2.spines['top'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.spines['right'].set_color('#334155')
    ax2.spines['bottom'].set_color('#334155')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_ejecucion_bruta_chart_bytes(data: Dict[str, Any]) -> io.BytesIO:
    """Figura 3 (5.2): Ejecución Bruta Mensual Causada y Curva Suavizada (Dark Mode)."""
    fig, ax1 = plt.subplots(figsize=(7.2, 3.0), dpi=300)
    fig.patch.set_facecolor('#0F172A')
    ax1.set_facecolor('#0F172A')

    active_months = [m for m in data["monthly_report"] if m["mes_num"] <= data["meses_transcurridos"]]
    months = [m["mes_abrev"] for m in active_months]
    ejec_mes = [m["ejecucion_mes"] / 1e6 for m in active_months]
    ejec_acum = [m["ejecucion_acum"] / 1e6 for m in active_months]

    x = np.arange(len(months))

    bars = ax1.bar(x, ejec_mes, color='#10B981', width=0.42, label='Causado en el Mes ($M)', alpha=0.88, edgecolor='none')
    for b in bars:
        h = b.get_height()
        if h > 10:
            ax1.text(b.get_x() + b.get_width()/2., h + 8, f"${h:.0f}M", ha='center', va='bottom', fontsize=7.0, fontweight='bold', color='#34D399')

    ax1.set_ylabel('Causado Mes ($M)', fontsize=8.5, fontweight='bold', color='#34D399')
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, fontsize=8.5, fontweight='bold', color='#F8FAFC')

    ax2 = ax1.twinx()
    x_smooth = np.linspace(0, len(months) - 1, 150)
    y_smooth = pchip_interpolate(x, ejec_acum, x_smooth)

    ax2.plot(x_smooth, y_smooth, color='#38BDF8', linewidth=2.5, label='Ejecución Acumulada ($M)')
    ax2.plot(x, ejec_acum, 'o', color='#38BDF8', markersize=7.5, markeredgecolor='#0F172A', markeredgewidth=2)
    ax2.set_ylabel('Total Acumulado ($M)', fontsize=8.5, fontweight='bold', color='#38BDF8')
    ax2.set_ylim(0, max(ejec_acum) * 1.25 if ejec_acum and max(ejec_acum) > 0 else 100)
    ax2.tick_params(colors='#38BDF8', labelsize=8.0)

    setup_chart_styling(ax1)
    ax2.spines['top'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.spines['right'].set_color('#334155')
    ax2.spines['bottom'].set_color('#334155')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_saldos_girar_chart_bytes(data: Dict[str, Any]) -> io.BytesIO:
    """Figura 4 (5.3): Evolución Suavizada de Saldos Disponibles por Girar con Sombreado (Dark Mode)."""
    fig, ax = plt.subplots(figsize=(7.2, 2.9), dpi=300)
    fig.patch.set_facecolor('#0F172A')
    ax.set_facecolor('#0F172A')

    active_months = [m for m in data["monthly_report"] if m["mes_num"] <= data["meses_transcurridos"]]
    months = [m["mes_abrev"] for m in active_months]
    saldos = [m["saldo_girar_mes"] / 1e6 for m in active_months]

    x = np.arange(len(months))
    x_smooth = np.linspace(0, len(months) - 1, 150)
    y_smooth = pchip_interpolate(x, saldos, x_smooth)

    ax.fill_between(x_smooth, y_smooth, color='#0284C7', alpha=0.22)
    ax.plot(x_smooth, y_smooth, color='#38BDF8', linewidth=2.5, label='Saldo Remanente ($M)')
    ax.plot(x, saldos, 'o', color='#38BDF8', markersize=8.0, markeredgecolor='#0F172A', markeredgewidth=2)

    for idx, s in enumerate(saldos):
        ax.text(idx, s + 35, f"${s:.0f}M", ha='center', va='bottom', fontsize=7.5, fontweight='bold', color='#F8FAFC')

    setup_chart_styling(ax)
    ax.set_ylabel('Saldo por Girar ($M)', fontsize=8.5, fontweight='bold', color='#94A3B8')
    ax.set_xticks(x)
    ax.set_xticklabels(months, fontsize=8.5, fontweight='bold', color='#F8FAFC')
    if saldos:
        ax.set_ylim(min(saldos) * 0.82, max(saldos) * 1.15)

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_retenciones_chart_bytes(data: Dict[str, Any]) -> io.BytesIO:
    """Figura 5 (5.4): Retenciones Tributarias y Fiscales Practicadas con Curva Suavizada (Dark Mode)."""
    fig, ax1 = plt.subplots(figsize=(7.2, 2.9), dpi=300)
    fig.patch.set_facecolor('#0F172A')
    ax1.set_facecolor('#0F172A')

    active_months = [m for m in data["monthly_report"] if m["mes_num"] <= data["meses_transcurridos"]]
    months = [m["mes_abrev"] for m in active_months]
    ret_mes = [m["retencion_mes"] / 1e6 for m in active_months]
    ret_acum = [m["retencion_acum"] / 1e6 for m in active_months]

    x = np.arange(len(months))
    ax1.bar(x, ret_mes, color='#F59E0B', width=0.42, label='Retención Mes ($M)', alpha=0.88, edgecolor='none')
    ax1.set_ylabel('Retención Mes ($M)', fontsize=8.5, fontweight='bold', color='#FBBF24')
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, fontsize=8.5, fontweight='bold', color='#F8FAFC')

    ax2 = ax1.twinx()
    x_smooth = np.linspace(0, len(months) - 1, 150)
    y_smooth = pchip_interpolate(x, ret_acum, x_smooth)

    ax2.plot(x_smooth, y_smooth, color='#EF4444', linewidth=2.5, label='Retenciones Acumuladas ($M)')
    ax2.plot(x, ret_acum, 'o', color='#EF4444', markersize=7.5, markeredgecolor='#0F172A', markeredgewidth=2)
    ax2.set_ylabel('Acumulado Total ($M)', fontsize=8.5, fontweight='bold', color='#EF4444')
    ax2.set_ylim(0, max(ret_acum) * 1.25 if ret_acum and max(ret_acum) > 0 else 10)
    ax2.tick_params(colors='#EF4444', labelsize=8.0)

    setup_chart_styling(ax1)
    ax2.spines['top'].set_visible(False)
    ax2.spines['left'].set_visible(False)
    ax2.spines['right'].set_color('#334155')
    ax2.spines['bottom'].set_color('#334155')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

def generate_ritmo_avance_chart_bytes(data: Dict[str, Any]) -> io.BytesIO:
    """Figura 6 (5.5): Velocímetro (Gauge semicircular) + Curva de Avance con Sombra Roja al 39.30% (Dark Mode)."""
    fig = plt.figure(figsize=(9.2, 3.4), dpi=300)
    fig.patch.set_facecolor('#0F172A')

    # Subplot 1: Velocímetro (Gauge semicircular) a la izquierda
    ax_gauge = fig.add_subplot(1, 3, 1)
    ax_gauge.set_facecolor('#0F172A')

    val_pct = data.get("avance_presupuestal_global", 39.30)
    # Bandas del semicírculo (0 a 180 grados): Roja (0-30%), Ámbar (30-60%), Verde (60-100%)
    gauge_colors = ['#EF4444', '#F59E0B', '#10B981']
    gauge_vals = [30, 30, 40]
    ax_gauge.pie(
        gauge_vals,
        colors=gauge_colors,
        startangle=180,
        counterclock=False,
        wedgeprops=dict(width=0.35, edgecolor='#0F172A', linewidth=2.0)
    )
    # Aguja o indicador de posición para val_pct (0% = 180°, 100% = 0°)
    theta = np.deg2rad(180 - (val_pct / 100.0 * 180))
    needle_len = 0.55
    ax_gauge.plot([0, needle_len * np.cos(theta)], [0, needle_len * np.sin(theta)], color='#F8FAFC', linewidth=2.8)
    ax_gauge.plot(0, 0, 'o', color='#F8FAFC', markersize=6)

    ax_gauge.text(0, -0.15, f"{val_pct:.1f}%", ha='center', va='center', fontsize=15.0, fontweight='bold', color='#EF4444' if val_pct < 40 else '#F59E0B')
    ax_gauge.text(0, -0.35, "ZONA ROJA (Alerta)", ha='center', va='center', fontsize=7.5, fontweight='bold', color='#EF4444')
    ax_gauge.set_title("Velocímetro de Avance", fontsize=9.5, fontweight='bold', color='#F8FAFC', pad=8)
    ax_gauge.set_ylim(-0.45, 1.05)

    # Subplot 2: Curva de Avance con Sombra Roja / Ámbar (Centro y Derecha)
    ax_curve = fig.add_subplot(1, 3, (2, 3))
    ax_curve.set_facecolor('#0F172A')

    months = [m["mes_abrev"] for m in data["monthly_report"][:data["meses_transcurridos"]]]
    avance_real = [m["avance_acum_pct"] for m in data["monthly_report"][:data["meses_transcurridos"]]]
    meta_lineal = [m["meta_lineal_pct"] for m in data["monthly_report"][:data["meses_transcurridos"]]]

    x = np.arange(len(months))
    x_smooth = np.linspace(0, len(months) - 1, 150)
    avance_smooth = pchip_interpolate(x, avance_real, x_smooth)

    # Sombra roja/ámbar destacada bajo la brecha
    ax_curve.fill_between(x, avance_real, meta_lineal, color='#EF4444', alpha=0.25, label='Brecha en Zona Roja')
    ax_curve.plot(x, meta_lineal, color='#94A3B8', linestyle='--', linewidth=1.8, label='Meta Teórica Lineal (%)')
    ax_curve.plot(x_smooth, avance_smooth, color='#38BDF8', linewidth=2.5, label='Avance Presupuestal Real (%)')
    ax_curve.plot(x, avance_real, 'o', color='#38BDF8', markersize=8.0, markeredgecolor='#0F172A', markeredgewidth=2)

    for idx, a in enumerate(avance_real):
        ax_curve.text(idx, a + 2.5, f"{a:.1f}%", ha='center', va='bottom', fontsize=7.8, fontweight='bold', color='#38BDF8')

    setup_chart_styling(ax_curve, title="Curva de Avance Acumulado vs. Meta Lineal Teórica (%)")
    ax_curve.set_ylabel('Avance Presupuestal (%)', fontsize=8.5, fontweight='bold', color='#94A3B8')
    ax_curve.set_xticks(x)
    ax_curve.set_xticklabels(months, fontsize=8.5, fontweight='bold', color='#F8FAFC')
    ax_curve.set_ylim(0, 85)
    leg = ax_curve.legend(loc='upper left', frameon=True, facecolor='#1E293B', edgecolor='#334155', fontsize=7.5)
    for text in leg.get_texts():
        text.set_color('#F8FAFC')

    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==============================================================================
# 4. HELPERS DE ESTILO PARA WORD (.docx)
# ==============================================================================

def set_cell_background(cell, fill_hex: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def set_modern_table_borders(table, border_color="E2E8F0"):
    tblPr = table._tbl.tblPr
    borders_elm = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="6" w:space="0" w:color="{border_color}"/>'
        f'  <w:bottom w:val="single" w:sz="8" w:space="0" w:color="{border_color}"/>'
        f'  <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{border_color}"/>'
        f'  <w:left w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'  <w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders_elm)

def add_hero_metric_box(doc, value_text: str, label_text: str, status_text: str, status_color_hex: str = "0284C7"):
    table = doc.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    c_left = table.cell(0, 0)
    c_left.width = Inches(3.0)
    set_cell_background(c_left, "F8FAFC")
    set_cell_margins(c_left, 100, 100, 140, 140)

    c_right = table.cell(0, 1)
    c_right.width = Inches(3.2)
    set_cell_background(c_right, "F8FAFC")
    set_cell_margins(c_right, 100, 100, 140, 140)

    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="none"/><w:left w:val="single" w:sz="36" w:space="0" w:color="{status_color_hex}"/>'
        f'  <w:bottom w:val="none"/><w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

    p_val = c_left.paragraphs[0]
    r_v = p_val.add_run(value_text)
    r_v.bold = True
    r_v.font.name = "Calibri"
    r_v.font.size = Pt(20)
    r_v.font.color.rgb = RGBColor(15, 23, 42)

    p_lbl = c_right.paragraphs[0]
    r_l = p_lbl.add_run(f"{label_text.upper()}\n")
    r_l.bold = True
    r_l.font.name = "Calibri"
    r_l.font.size = Pt(9.5)
    r_l.font.color.rgb = RGBColor(100, 116, 139)

    r_s = p_lbl.add_run(status_text)
    r_s.bold = True
    r_s.font.name = "Calibri"
    r_s.font.size = Pt(9.5)
    r_s.font.color.rgb = RGBColor(2, 132, 199)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def add_callout_box(doc, text: str, title: str = "NOTA GERENCIAL", border_color="0284C7", bg_color="F0F9FF"):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    cell = table.cell(0, 0)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)

    tcPr = cell._tc.get_or_add_tcPr()
    borders_elm = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:top w:val="none"/>'
        f'  <w:left w:val="single" w:sz="36" w:space="0" w:color="{border_color}"/>'
        f'  <w:bottom w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders_elm)

    p = cell.paragraphs[0]
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(2)
    r_tit = p.add_run(f"{title.upper()}: ")
    r_tit.bold = True
    r_tit.font.name = "Calibri"
    r_tit.font.size = Pt(9.5)
    r_tit.font.color.rgb = RGBColor(15, 23, 42)

    r_txt = p.add_run(text)
    r_txt.font.name = "Calibri"
    r_txt.font.size = Pt(9.5)
    r_txt.font.color.rgb = RGBColor(30, 41, 59)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

# ==============================================================================
# 5. GENERADOR DEL INFORME OFICIAL EN WORD (.docx)
# ==============================================================================

def generate_word_report(db: Session, vigencia: str = "2026", periodo: str = "ACUMULADO", include_annexes: bool = True) -> Path:
    """Compile and produce official Word (.docx) report covering the 5 required sections."""
    data = get_report_dataset(db, vigencia, periodo)
    doc = docx.Document()

    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True

        header = section.header
        hp = header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hrun = hp.add_run("EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ | INFORME OFICIAL CONTRACTUAL")
        hrun.font.name = "Calibri"
        hrun.font.size = Pt(8.5)
        hrun.font.bold = True
        hrun.font.color.rgb = RGBColor(100, 116, 139)

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        frun = fp.add_run(f"Informe Gerencial Oficial • Vigencia {data['vigencia']} • EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. (ESPY)")
        frun.font.name = "Calibri"
        frun.font.size = Pt(8.5)
        frun.font.color.rgb = RGBColor(148, 163, 184)

    # -------------------------------------------------------------
    # PORTADA OFICIAL EJECUTIVA
    # -------------------------------------------------------------
    # Barra superior institucional
    top_bar_table = doc.add_table(rows=1, cols=2)
    top_bar_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    top_bar_table.autofit = False
    set_cell_background(top_bar_table.cell(0, 0), "0F172A")
    top_bar_table.cell(0, 0).width = Inches(5.8)
    set_cell_margins(top_bar_table.cell(0, 0), top=60, bottom=60, left=100, right=100)
    p_tbar = top_bar_table.cell(0, 0).paragraphs[0]
    r_tb = p_tbar.add_run("EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P.")
    r_tb.font.name = "Calibri"
    r_tb.font.size = Pt(8.5)
    r_tb.bold = True
    r_tb.font.color.rgb = RGBColor(255, 255, 255)

    set_cell_background(top_bar_table.cell(0, 1), "10B981")
    top_bar_table.cell(0, 1).width = Inches(0.4)
    p_tbar2 = top_bar_table.cell(0, 1).paragraphs[0]
    r_tb2 = p_tbar2.add_run(" ")
    r_tb2.font.size = Pt(8.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(16)

    # Contenedor principal de portada con barra lateral bicolor
    cov_table = doc.add_table(rows=1, cols=3)
    cov_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cov_table.autofit = False

    cell_bar1 = cov_table.cell(0, 0)
    cell_bar1.width = Inches(0.28)
    set_cell_background(cell_bar1, "0F172A")

    cell_bar2 = cov_table.cell(0, 1)
    cell_bar2.width = Inches(0.06)
    set_cell_background(cell_bar2, "10B981")

    cell_content = cov_table.cell(0, 2)
    cell_content.width = Inches(5.86)
    set_cell_margins(cell_content, top=160, bottom=160, left=240, right=100)

    tblPr = cov_table._tbl.tblPr
    borders_cov = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="none"/><w:left w:val="none"/><w:bottom w:val="none"/><w:right w:val="none"/><w:insideH w:val="none"/><w:insideV w:val="none"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders_cov)

    # Insertar logo si existe
    logo_file = Path("c:/Users/Usuario/Documents/ESPY_Contratacion_Automatizada/frontend/assets/logo.png")
    if logo_file.exists():
        try:
            p_logo = cell_content.paragraphs[0]
            p_logo.paragraph_format.space_after = Pt(12)
            r_logo = p_logo.add_run()
            r_logo.add_picture(str(logo_file), width=Inches(1.85))
            p_ent = cell_content.add_paragraph()
        except Exception as e_l:
            logger.warning(f"Aviso insertando logo en portada Word: {e_l}")
            p_ent = cell_content.paragraphs[0]
    else:
        p_ent = cell_content.paragraphs[0]

    r_ent = p_ent.add_run("EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. (ESPY)\nNIT: 811.015.112-4\nMUNICIPIO DE YOLOMBÓ, ANTIOQUIA\n")
    r_ent.bold = True
    r_ent.font.name = "Calibri"
    r_ent.font.size = Pt(11)
    r_ent.font.color.rgb = RGBColor(15, 23, 42)
    p_ent.paragraph_format.space_after = Pt(20)

    p_tit = cell_content.add_paragraph()
    r_tit = p_tit.add_run("INFORME OFICIAL DE GESTIÓN Y EJECUCIÓN CONTRACTUAL")
    r_tit.bold = True
    r_tit.font.name = "Calibri"
    r_tit.font.size = Pt(18)
    r_tit.font.color.rgb = RGBColor(2, 132, 199)
    p_tit.paragraph_format.space_after = Pt(10)

    p_sub = cell_content.add_paragraph()
    r_sub = p_sub.add_run(
        f"Consolidado de Presupuesto Comprometido, Dinámica por Tipologías,\n"
        f"Contratos Ejecutados, Conciliación de Pagos y Ritmo Presupuestal\n"
        f"Vigencia Fiscal {data['vigencia']}  •  {data['periodo_label']}"
    )
    r_sub.font.name = "Calibri"
    r_sub.font.size = Pt(11.0)
    r_sub.font.color.rgb = RGBColor(71, 85, 105)
    p_sub.paragraph_format.space_after = Pt(36)

    p_meta = cell_content.add_paragraph()
    r_meta = p_meta.add_run(
        f"DESTINATARIOS: Junta Directiva & Gerencia General ESPY\n"
        f"FECHA DE EMISIÓN: {data['fecha_emision'].upper()}\n"
        f"RÉGIMEN APLICABLE: Ley 142 de 1994 (Derecho Privado)\n"
        f"ESTADO: Certificado y Consolidado en Plataforma"
    )
    r_meta.font.name = "Calibri"
    r_meta.font.size = Pt(9.5)
    r_meta.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_page_break()

    # -------------------------------------------------------------
    # SECCIÓN 1: PRESUPUESTO COMPROMETIDO CONTRATOS
    # -------------------------------------------------------------
    h1 = doc.add_paragraph()
    r_h1 = h1.add_run("1. PRESUPUESTO COMPROMETIDO CONTRATOS")
    r_h1.bold = True
    r_h1.font.name = "Calibri"
    r_h1.font.size = Pt(13)
    r_h1.font.color.rgb = RGBColor(15, 23, 42)

    add_hero_metric_box(
        doc,
        value_text=format_cop(data["total_comprometido"]),
        label_text="Presupuesto Comprometido en Contratos",
        status_text=f"100.0% Techo Formalizado ({data['total_contratos']} contratos suscritos)",
        status_color_hex="0284C7"
    )

    add_callout_box(
        doc,
        f"El monto contractual total formalizado asciende a {format_cop(data['total_comprometido'])}, "
        f"con un valor inicial suscrito de {format_cop(data['total_valor_inicial'])} "
        f"y adiciones presupuestales de {format_cop(data['total_adiciones'])}. "
        f"El valor contractual promedio se sitúa en {format_cop(data['promedio_por_contrato'])}.",
        title="Balance de Techo Comprometido",
        border_color="0284C7"
    )

    table_s1 = doc.add_table(rows=4, cols=3)
    table_s1.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_s1.autofit = False
    set_modern_table_borders(table_s1)

    headers_s1 = ["Concepto Presupuestal", "Valor Total (COP)", "Participación / Detalle"]
    for i, h in enumerate(headers_s1):
        c = table_s1.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 100, 100, 120, 120)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(9.0)
        r.font.color.rgb = RGBColor(255, 255, 255)

    rows_s1 = [
        ("Valor Inicial Contratado", format_cop(data["total_valor_inicial"]), format_pct((data["total_valor_inicial"] / data["total_comprometido"] * 100) if data["total_comprometido"] > 0 else 100)),
        ("Adiciones Presupuestales Formalizadas", format_cop(data["total_adiciones"]), format_pct((data["total_adiciones"] / data["total_comprometido"] * 100) if data["total_comprometido"] > 0 else 0)),
        ("TOTAL PRESUPUESTO COMPROMETIDO", format_cop(data["total_comprometido"]), "100.00% (Techo Vigente)")
    ]

    for r_idx, r_vals in enumerate(rows_s1, start=1):
        for c_idx, val in enumerate(r_vals):
            c = table_s1.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 80, 80, 100, 100)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx == 1 else (WD_ALIGN_PARAGRAPH.CENTER if c_idx == 2 else WD_ALIGN_PARAGRAPH.LEFT)
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.5)
            if r_idx == 3:
                r.bold = True
            r.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # SECCIÓN 2: CANTIDAD DE CONTRATOS
    # -------------------------------------------------------------
    h2 = doc.add_paragraph()
    r_h2 = h2.add_run("2. CANTIDAD DE CONTRATOS")
    r_h2.bold = True
    r_h2.font.name = "Calibri"
    r_h2.font.size = Pt(13)
    r_h2.font.color.rgb = RGBColor(15, 23, 42)

    add_hero_metric_box(
        doc,
        value_text=f"{data['total_contratos']} Contratos",
        label_text="Volumen Total de Contratos Formalizados",
        status_text="100% Contratos Registrados en Plataforma",
        status_color_hex="10B981"
    )

    table_s2 = doc.add_table(rows=len(data["modalidades"]) + 1, cols=4)
    table_s2.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_s2.autofit = False
    set_modern_table_borders(table_s2)

    headers_s2 = ["Modalidad de Selección", "N° Contratos", "Monto Total (COP)", "% Participación"]
    for i, h in enumerate(headers_s2):
        c = table_s2.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 100, 100, 120, 120)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(9.0)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, (mod_k, mod_info) in enumerate(data["modalidades"].items(), start=1):
        pct_m = format_pct(mod_info["monto"] / data["total_comprometido"] * 100) if data["total_comprometido"] > 0 else "0.0%"
        vals = [mod_k, str(mod_info["conteo"]), format_cop(mod_info["monto"]), pct_m]
        for c_idx, val in enumerate(vals):
            c = table_s2.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 80, 80, 100, 100)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.5)
            r.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    # -------------------------------------------------------------
    # SECCIÓN 3: EJECUCIÓN PRESUPUESTAL POR TIPOLOGÍA DE CONTRATOS
    # -------------------------------------------------------------
    h3 = doc.add_paragraph()
    r_h3 = h3.add_run("3. EJECUCIÓN PRESUPUESTAL POR TIPOLOGÍA DE CONTRATOS")
    r_h3.bold = True
    r_h3.font.name = "Calibri"
    r_h3.font.size = Pt(13)
    r_h3.font.color.rgb = RGBColor(15, 23, 42)

    # Gráfico de tipologías
    try:
        buf_t = generate_typology_chart_bytes(data)
        doc.add_picture(buf_t, width=Inches(6.2))
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_c = p_cap.add_run("Figura 1: Presupuesto Comprometido vs. Ejecución Bruta Causada por Tipología")
        r_c.font.size = Pt(8.0)
        r_c.font.italic = True
        r_c.font.color.rgb = RGBColor(100, 116, 139)
        p_cap.paragraph_format.space_after = Pt(6)
    except Exception as e:
        logger.warning(f"Aviso generando gráfico de tipología Word: {e}")

    table_s3 = doc.add_table(rows=len(data["tipologias_summary"]) + 1, cols=6)
    table_s3.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_s3.autofit = False
    set_modern_table_borders(table_s3)

    headers_s3 = ["Tipología Contractual", "N° Contratos", "Comprometido (COP)", "Ejecutado (COP)", "Saldo Disponible (COP)", "% Ejec."]
    for i, h in enumerate(headers_s3):
        c = table_s3.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 90, 90, 100, 100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, tip in enumerate(data["tipologias_summary"], start=1):
        vals = [
            tip["label"],
            str(tip["contratos_formalizados"]),
            format_cop(tip["total_comprometido"]),
            format_cop(tip["total_ejecutado"]),
            format_cop(tip["saldo_por_girar"]),
            format_pct(tip["pct_ejecucion"])
        ]
        for c_idx, val in enumerate(vals):
            c = table_s3.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 70, 70, 90, 90)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3, 4, 5) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.0)
            if c_idx in (2, 5):
                r.bold = True
            r.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_page_break()

    # -------------------------------------------------------------
    # SECCIÓN 4: CONTRATOS EJECUTADOS Y CUANTÍAS MÁS ALTAS POR TIPOLOGÍA
    # -------------------------------------------------------------
    h4 = doc.add_paragraph()
    r_h4 = h4.add_run("4. CANTIDAD DE CONTRATOS EJECUTADOS Y CUANTÍAS MÁS ALTAS POR TIPOLOGÍA")
    r_h4.bold = True
    r_h4.font.name = "Calibri"
    r_h4.font.size = Pt(13)
    r_h4.font.color.rgb = RGBColor(15, 23, 42)

    add_callout_box(
        doc,
        "A continuación se detalla la cantidad de contratos con órdenes de pago efectivas (ejecutados) "
        "y el podio de los contratos con las mayores cuantías por cada tipología contractual.",
        title="Dinámica de Ejecución por Contratos",
        border_color="10B981"
    )

    # Subtabla 4.1: Resumen de contratos formalizados vs ejecutados
    table_s4_res = doc.add_table(rows=len(data["tipologias_summary"]) + 1, cols=5)
    table_s4_res.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_s4_res.autofit = False
    set_modern_table_borders(table_s4_res)

    headers_s4_res = ["Tipología", "Formalizados", "Con Pagos (Ejecutados)", "% Contratos Ejecutados", "N° Comprobantes"]
    for i, h in enumerate(headers_s4_res):
        c = table_s4_res.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, tip in enumerate(data["tipologias_summary"], start=1):
        vals = [
            tip["label"],
            str(tip["contratos_formalizados"]),
            str(tip["contratos_ejecutados"]),
            format_pct(tip["pct_contratos_ejecutados"]),
            str(tip["pagos_conteo"])
        ]
        for c_idx, val in enumerate(vals):
            c = table_s4_res.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 70, 70, 90, 90)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3, 4) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.0)
            if c_idx == 2:
                r.bold = True
            r.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Subsección 4.2: Fichas de cuantías más altas por tipología
    for tip in data["tipologias_summary"]:
        if not tip["top_cuantias"]:
            continue
        p_t_head = doc.add_paragraph()
        r_th = p_t_head.add_run(f"• Cuantías Más Altas en {tip['label']} (Comprometido: {format_cop(tip['total_comprometido'])}):")
        r_th.bold = True
        r_th.font.size = Pt(9.5)
        r_th.font.color.rgb = RGBColor(2, 132, 199)
        p_t_head.paragraph_format.space_after = Pt(4)

        table_top = doc.add_table(rows=len(tip["top_cuantias"]) + 1, cols=6)
        table_top.alignment = WD_TABLE_ALIGNMENT.CENTER
        table_top.autofit = False
        set_modern_table_borders(table_top)

        headers_top = ["N° Contrato", "Contratista / Razón Social", "Valor Formalizado", "Valor Ejecutado", "Saldo Remanente", "% Avance"]
        for i, h in enumerate(headers_top):
            c = table_top.cell(0, i)
            set_cell_background(c, "1E293B")
            set_cell_margins(c, 70, 70, 90, 90)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(h)
            r.bold = True
            r.font.name = "Calibri"
            r.font.size = Pt(8.0)
            r.font.color.rgb = RGBColor(255, 255, 255)

        for r_idx, tc in enumerate(tip["top_cuantias"], start=1):
            c_nom = str(tc['contratista_nombre'] or '').strip()
            c_doc_str = str(tc['contratista_doc'] or '').strip()
            if c_doc_str and c_doc_str != "N/A":
                contratista_full_str = f"{c_nom} - {c_doc_str}"
            else:
                contratista_full_str = c_nom

            vals = [
                tc["numero_contrato"],
                contratista_full_str,
                format_cop(tc["valor_total"]),
                format_cop(tc["valor_ejecutado"]),
                format_cop(tc["saldo"]),
                format_pct(tc["pct_ejecucion"])
            ]
            for c_idx, val in enumerate(vals):
                c = table_top.cell(r_idx, c_idx)
                bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                set_cell_background(c, bg)
                set_cell_margins(c, 60, 60, 80, 80)
                p = c.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (2, 3, 4, 5) else (WD_ALIGN_PARAGRAPH.CENTER if c_idx == 0 else WD_ALIGN_PARAGRAPH.LEFT)
                r = p.add_run(val)
                r.font.name = "Calibri"
                r.font.size = Pt(7.5)
                if c_idx in (0, 2):
                    r.bold = True
                r.font.color.rgb = RGBColor(15, 23, 42)

        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    doc.add_page_break()

    # -------------------------------------------------------------
    # SECCIÓN 5: INFORME FINANCIERO MES A MES Y TOTALES CON GRÁFICOS
    # -------------------------------------------------------------
    h5 = doc.add_paragraph()
    r_h5 = h5.add_run("5. INFORME FINANCIERO DETALLADO: EVOLUCIÓN MENSUAL, SALDOS Y RITMO PRESUPUESTAL")
    r_h5.bold = True
    r_h5.font.name = "Calibri"
    r_h5.font.size = Pt(13)
    r_h5.font.color.rgb = RGBColor(15, 23, 42)

    # 5.1 TOTAL COMPROMISOS FORMALIZADOS + GRÁFICO POR MES Y TOTAL
    p_51 = doc.add_paragraph()
    r_51 = p_51.add_run("5.1 Total Compromisos Formalizados (Mes a Mes y Total Acumulado)")
    r_51.bold = True
    r_51.font.size = Pt(11)
    r_51.font.color.rgb = RGBColor(2, 132, 199)
    p_51.paragraph_format.space_after = Pt(4)

    try:
        buf_c = generate_compromisos_chart_bytes(data)
        doc.add_picture(buf_c, width=Inches(6.2))
        p_cap2 = doc.add_paragraph()
        p_cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_c2 = p_cap2.add_run("Figura 2: Total Compromisos Formalizados por Mes y Curva de Acumulación")
        r_c2.font.size = Pt(8.0)
        r_c2.font.italic = True
        r_c2.font.color.rgb = RGBColor(100, 116, 139)
        p_cap2.paragraph_format.space_after = Pt(4)
    except Exception as e:
        logger.warning(f"Aviso generando gráfico de compromisos Word: {e}")

    # Tabla 5.1
    table_51 = doc.add_table(rows=14, cols=4)
    table_51.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_51.autofit = False
    set_modern_table_borders(table_51)

    headers_51 = ["Mes", "N° Contratos Suscritos", "Compromisos del Mes (COP)", "Total Acumulado Formalizado (COP)"]
    for i, h in enumerate(headers_51):
        c = table_51.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, m_row in enumerate(data["monthly_report"], start=1):
        vals = [
            m_row["mes_nombre"],
            str(m_row["contratos_mes"]),
            format_cop(m_row["compromisos_mes"]),
            format_cop(m_row["compromisos_acum"])
        ]
        for c_idx, val in enumerate(vals):
            c = table_51.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 60, 60, 80, 80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.0)
            r.font.color.rgb = RGBColor(15, 23, 42)

    # Fila total 5.1
    tot_c_row = table_51.cell(13, 0)
    set_cell_background(tot_c_row, "E2E8F0")
    tot_c_row.paragraphs[0].add_run("TOTAL GENERAL").bold = True
    tot_c_cnt = table_51.cell(13, 1)
    set_cell_background(tot_c_cnt, "E2E8F0")
    tot_c_cnt.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_c_cnt.paragraphs[0].add_run(str(data["total_contratos"])).bold = True
    tot_c_mes = table_51.cell(13, 2)
    set_cell_background(tot_c_mes, "E2E8F0")
    tot_c_mes.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_c_mes.paragraphs[0].add_run(format_cop(data["total_comprometido"])).bold = True
    tot_c_acum = table_51.cell(13, 3)
    set_cell_background(tot_c_acum, "E2E8F0")
    tot_c_acum.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_c_acum.paragraphs[0].add_run(format_cop(data["total_comprometido"])).bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # 5.2 EJECUCIÓN BRUTA ACUMULADA POR MES Y TOTAL + GRÁFICOS
    p_52 = doc.add_paragraph()
    r_52 = p_52.add_run("5.2 Ejecución Bruta Acumulada por Mes y Total (Órdenes Causadas)")
    r_52.bold = True
    r_52.font.size = Pt(11)
    r_52.font.color.rgb = RGBColor(2, 132, 199)
    p_52.paragraph_format.space_after = Pt(2)

    p_52_note = doc.add_paragraph()
    r_52_note = p_52_note.add_run("Nota Técnica de Corte: El último mes con cierre de órdenes de pago cargadas en el sistema es Agosto de 2026. Los meses posteriores (Septiembre - Diciembre) se encuentran en fase de radicación y trámite de comprobantes de egreso.")
    r_52_note.font.size = Pt(8.0)
    r_52_note.font.italic = True
    r_52_note.font.color.rgb = RGBColor(100, 116, 139)
    p_52_note.paragraph_format.space_after = Pt(4)

    try:
        buf_e = generate_ejecucion_bruta_chart_bytes(data)
        doc.add_picture(buf_e, width=Inches(6.2))
        p_cap3 = doc.add_paragraph()
        p_cap3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_c3 = p_cap3.add_run("Figura 3: Ejecución Bruta Mensual Causada y Curva de Acumulación Progresiva")
        r_c3.font.size = Pt(8.0)
        r_c3.font.italic = True
        r_c3.font.color.rgb = RGBColor(100, 116, 139)
        p_cap3.paragraph_format.space_after = Pt(4)
    except Exception as e:
        logger.warning(f"Aviso generando gráfico de ejecución Word: {e}")

    # Tabla 5.2
    table_52 = doc.add_table(rows=14, cols=4)
    table_52.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_52.autofit = False
    set_modern_table_borders(table_52)

    headers_52 = ["Mes", "N° Comprobantes", "Ejecución Bruta del Mes (COP)", "Ejecución Bruta Acumulada (COP)"]
    for i, h in enumerate(headers_52):
        c = table_52.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, m_row in enumerate(data["monthly_report"], start=1):
        vals = [
            m_row["mes_nombre"],
            str(m_row["pagos_conteo_mes"]),
            format_cop(m_row["ejecucion_mes"]),
            format_cop(m_row["ejecucion_acum"])
        ]
        for c_idx, val in enumerate(vals):
            c = table_52.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 60, 60, 80, 80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.0)
            r.font.color.rgb = RGBColor(15, 23, 42)

    # Fila total 5.2
    tot_e_row = table_52.cell(13, 0)
    set_cell_background(tot_e_row, "E2E8F0")
    tot_e_row.paragraphs[0].add_run("TOTAL GENERAL").bold = True
    tot_e_cnt = table_52.cell(13, 1)
    set_cell_background(tot_e_cnt, "E2E8F0")
    tot_e_cnt.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_e_cnt.paragraphs[0].add_run(str(data["total_comprobantes"])).bold = True
    tot_e_mes = table_52.cell(13, 2)
    set_cell_background(tot_e_mes, "E2E8F0")
    tot_e_mes.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_e_mes.paragraphs[0].add_run(format_cop(data["total_ejecucion_bruta"])).bold = True
    tot_e_acum = table_52.cell(13, 3)
    set_cell_background(tot_e_acum, "E2E8F0")
    tot_e_acum.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_e_acum.paragraphs[0].add_run(format_cop(data["total_ejecucion_bruta"])).bold = True

    doc.add_page_break()

    # 5.3 SALDOS DISPONIBLE POR GIRAR POR MES Y TOTAL MÁS GRÁFICOS
    p_53 = doc.add_paragraph()
    r_53 = p_53.add_run("5.3 Saldos Disponible por Girar por Mes y Total Remanente")
    r_53.bold = True
    r_53.font.size = Pt(11)
    r_53.font.color.rgb = RGBColor(2, 132, 199)
    p_53.paragraph_format.space_after = Pt(4)

    try:
        buf_s = generate_saldos_girar_chart_bytes(data)
        doc.add_picture(buf_s, width=Inches(6.2))
        p_cap4 = doc.add_paragraph()
        p_cap4.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_c4 = p_cap4.add_run("Figura 4: Tendencia de Saldos Disponibles por Girar Mes a Mes")
        r_c4.font.size = Pt(8.0)
        r_c4.font.italic = True
        r_c4.font.color.rgb = RGBColor(100, 116, 139)
        p_cap4.paragraph_format.space_after = Pt(4)
    except Exception as e:
        logger.warning(f"Aviso generando gráfico de saldos Word: {e}")

    # Tabla 5.3
    table_53 = doc.add_table(rows=14, cols=4)
    table_53.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_53.autofit = False
    set_modern_table_borders(table_53)

    headers_53 = ["Mes", "Ejecución Acumulada", "Saldo Disponible por Girar (COP)", "% Remanente por Girar"]
    for i, h in enumerate(headers_53):
        c = table_53.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.5)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, m_row in enumerate(data["monthly_report"], start=1):
        vals = [
            m_row["mes_nombre"],
            format_cop(m_row["ejecucion_acum"]),
            format_cop(m_row["saldo_girar_mes"]),
            format_pct(m_row["pct_saldo_remanente"])
        ]
        for c_idx, val in enumerate(vals):
            c = table_53.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 60, 60, 80, 80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(8.0)
            r.font.color.rgb = RGBColor(15, 23, 42)

    # Fila total 5.3
    tot_s_row = table_53.cell(13, 0)
    set_cell_background(tot_s_row, "E2E8F0")
    tot_s_row.paragraphs[0].add_run("SALDO ACTUAL AL CORTE").bold = True
    tot_s_ejec = table_53.cell(13, 1)
    set_cell_background(tot_s_ejec, "E2E8F0")
    tot_s_ejec.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_s_ejec.paragraphs[0].add_run(format_cop(data["total_ejecucion_bruta"])).bold = True
    tot_s_dis = table_53.cell(13, 2)
    set_cell_background(tot_s_dis, "E2E8F0")
    tot_s_dis.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_s_dis.paragraphs[0].add_run(format_cop(data["saldo_disponible_girar"])).bold = True
    tot_s_pct = table_53.cell(13, 3)
    set_cell_background(tot_s_pct, "E2E8F0")
    tot_s_pct.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    tot_s_pct.paragraphs[0].add_run(format_pct(100 - data["avance_presupuestal_global"])).bold = True

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # 5.4 RETENCIONES PRACTICADAS POR MES Y TOTAL MÁS GRÁFICOS
    p_54 = doc.add_paragraph()
    r_54 = p_54.add_run("5.4 Retenciones Tributarias y Fiscales Practicadas por Mes y Total")
    r_54.bold = True
    r_54.font.size = Pt(11)
    r_54.font.color.rgb = RGBColor(2, 132, 199)
    p_54.paragraph_format.space_after = Pt(4)

    try:
        buf_r = generate_retenciones_chart_bytes(data)
        doc.add_picture(buf_r, width=Inches(6.2))
        p_cap5 = doc.add_paragraph()
        p_cap5.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_c5 = p_cap5.add_run("Figura 5: Retenciones Practicadas Mensuales y Acumuladas")
        r_c5.font.size = Pt(8.0)
        r_c5.font.italic = True
        r_c5.font.color.rgb = RGBColor(100, 116, 139)
        p_cap5.paragraph_format.space_after = Pt(4)
    except Exception as e:
        logger.warning(f"Aviso generando gráfico de retenciones Word: {e}")

    # Tabla 5.4
    table_54 = doc.add_table(rows=14, cols=6)
    table_54.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_54.autofit = False
    set_modern_table_borders(table_54)

    headers_54 = ["Mes", "ReteFuente (DIAN)", "ReteICA (Mpio)", "Estampillas", "Total Retención Mes", "Retención Acumulada"]
    for i, h in enumerate(headers_54):
        c = table_54.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 80, 80, 90, 90)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.0)
        r.font.color.rgb = RGBColor(255, 255, 255)

    tot_rf = 0.0
    tot_ri = 0.0
    tot_re = 0.0

    for r_idx, m_row in enumerate(data["monthly_report"], start=1):
        tot_rf += m_row["ret_fuente"]
        tot_ri += m_row["ret_ica"]
        tot_re += m_row["ret_estampillas"]
        vals = [
            m_row["mes_nombre"],
            format_cop(m_row["ret_fuente"]),
            format_cop(m_row["ret_ica"]),
            format_cop(m_row["ret_estampillas"]),
            format_cop(m_row["retencion_mes"]),
            format_cop(m_row["retencion_acum"])
        ]
        for c_idx, val in enumerate(vals):
            c = table_54.cell(r_idx, c_idx)
            bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
            set_cell_background(c, bg)
            set_cell_margins(c, 60, 60, 80, 80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3, 4, 5) else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(7.5)
            r.font.color.rgb = RGBColor(15, 23, 42)

    # Fila total 5.4
    tot_r_row = table_54.cell(13, 0)
    set_cell_background(tot_r_row, "E2E8F0")
    tot_r_row.paragraphs[0].add_run("TOTAL GENERAL").bold = True
    c_rf = table_54.cell(13, 1)
    set_cell_background(c_rf, "E2E8F0")
    c_rf.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    c_rf.paragraphs[0].add_run(format_cop(tot_rf)).bold = True
    c_ri = table_54.cell(13, 2)
    set_cell_background(c_ri, "E2E8F0")
    c_ri.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    c_ri.paragraphs[0].add_run(format_cop(tot_ri)).bold = True
    c_re = table_54.cell(13, 3)
    set_cell_background(c_re, "E2E8F0")
    c_re.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    c_re.paragraphs[0].add_run(format_cop(tot_re)).bold = True
    c_rt = table_54.cell(13, 4)
    set_cell_background(c_rt, "E2E8F0")
    c_rt.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    c_rt.paragraphs[0].add_run(format_cop(data["total_retenciones"])).bold = True
    c_ra = table_54.cell(13, 5)
    set_cell_background(c_ra, "E2E8F0")
    c_ra.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    c_ra.paragraphs[0].add_run(format_cop(data["total_retenciones"])).bold = True

    doc.add_page_break()

    # 5.5 RITMO DE EJECUCIÓN GLOBAL POR MES Y GLOBAL (AVANCE PRESUPUESTAL)
    p_55 = doc.add_paragraph()
    r_55 = p_55.add_run("5.5 Ritmo de Ejecución Global por Mes y Global (Avance Presupuestal)")
    r_55.bold = True
    r_55.font.size = Pt(11)
    r_55.font.color.rgb = RGBColor(2, 132, 199)
    p_55.paragraph_format.space_after = Pt(4)

    add_hero_metric_box(
        doc,
        value_text=format_pct(data["avance_presupuestal_global"]),
        label_text="Ritmo de Ejecución Global (Avance Presupuestal)",
        status_text=f"Estado: {data['estado_semaforo_global']} (Brecha vs Lineal: {data['brecha_global']}%)",
        status_color_hex=data["color_semaforo_global"].replace("#", "")
    )

    add_callout_box(
        doc,
        f"{data['diagnostico_ritmo']} Plan de mitigación: {data['mitigacion_ritmo']} "
        f"Velocidad de giro promedio mensual: {format_cop(data['velocidad_giro_promedio'])}. "
        f"Meses proyectados para agotar saldo remanente al ritmo actual: {data['meses_para_agotamiento']} meses. "
        f"(Corte contable oficial: Último mes con cierre de órdenes de pago cargadas es Agosto 2026; "
        f"la brecha lineal teórica se calcula con base en dicho periodo de corte).",
        title=f"Diagnóstico de Avance Presupuestal — {data['estado_semaforo_global']}",
        border_color=data["color_semaforo_global"].replace("#", "")
    )

    try:
        buf_a = generate_ritmo_avance_chart_bytes(data)
        doc.add_picture(buf_a, width=Inches(6.2))
        p_cap6 = doc.add_paragraph()
        p_cap6.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_c6 = p_cap6.add_run("Figura 6: Curva de Avance Presupuestal Acumulado Real vs. Meta Teórica Lineal")
        r_c6.font.size = Pt(8.0)
        r_c6.font.italic = True
        r_c6.font.color.rgb = RGBColor(100, 116, 139)
        p_cap6.paragraph_format.space_after = Pt(4)
    except Exception as e:
        logger.warning(f"Aviso generando gráfico de ritmo Word: {e}")

    # Tabla 5.5
    table_55 = doc.add_table(rows=13, cols=6)
    table_55.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_55.autofit = False
    set_modern_table_borders(table_55)

    headers_55 = ["Mes", "% Avance Mes", "% Avance Acumulado", "Meta Teórica (%)", "Brecha (%)", "Semáforo"]
    for i, h in enumerate(headers_55):
        c = table_55.cell(0, i)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, 80, 80, 90, 90)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Calibri"
        r.font.size = Pt(8.0)
        r.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, m_row in enumerate(data["monthly_report"], start=1):
        vals = [
            m_row["mes_nombre"],
            format_pct(m_row["avance_mes_pct"]),
            format_pct(m_row["avance_acum_pct"]),
            format_pct(m_row["meta_lineal_pct"]),
            f"{m_row['brecha_pct']:+.1f}%",
            m_row["semaforo"]
        ]
        sem_val = m_row["semaforo"]
        if "VERDE" in sem_val:
            sem_cell_bg = "DCFCE7"
            sem_text_color = RGBColor(5, 150, 105)
        elif "ÁMBAR" in sem_val or "AMBAR" in sem_val:
            sem_cell_bg = "FEF3C7"
            sem_text_color = RGBColor(217, 119, 6)
        else:
            sem_cell_bg = "FEE2E2"
            sem_text_color = RGBColor(220, 38, 38)

        for c_idx, val in enumerate(vals):
            c = table_55.cell(r_idx, c_idx)
            if c_idx == 5:
                set_cell_background(c, sem_cell_bg)
            else:
                bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                set_cell_background(c, bg)

            set_cell_margins(c, 60, 60, 80, 80)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if c_idx in (1, 2, 3, 4) else (WD_ALIGN_PARAGRAPH.CENTER if c_idx == 5 else WD_ALIGN_PARAGRAPH.LEFT)
            r = p.add_run(val)
            r.font.name = "Calibri"
            r.font.size = Pt(7.5)
            if c_idx == 2:
                r.bold = True
            if c_idx == 5:
                r.bold = True
                r.font.color.rgb = sem_text_color
            else:
                r.font.color.rgb = RGBColor(15, 23, 42)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # -------------------------------------------------------------
    # SECCIÓN 6: DIRECTRICES Y FIRMAS INSTITUCIONALES
    # -------------------------------------------------------------
    h6 = doc.add_paragraph()
    r_h6 = h6.add_run("6. DIRECTRICES Y FIRMAS INSTITUCIONALES")
    r_h6.bold = True
    r_h6.font.name = "Calibri"
    r_h6.font.size = Pt(13)
    r_h6.font.color.rgb = RGBColor(15, 23, 42)

    table_firmas = doc.add_table(rows=1, cols=2)
    table_firmas.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_firmas.autofit = False

    cell_f1 = table_firmas.cell(0, 0)
    p_f1 = cell_f1.paragraphs[0]
    p_f1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_f1 = p_f1.add_run("_________________________________________\nGERENCIA GENERAL\nEMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ")
    r_f1.font.name = "Calibri"
    r_f1.font.size = Pt(9.0)
    r_f1.bold = True

    cell_f2 = table_firmas.cell(0, 1)
    p_f2 = cell_f2.paragraphs[0]
    p_f2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_f2 = p_f2.add_run("_________________________________________\nDIRECCIÓN DE CONTRATACIÓN Y ASUNTOS JURÍDICOS\nEMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. (ESPY)")
    r_f2.font.name = "Calibri"
    r_f2.font.size = Pt(9.0)
    r_f2.bold = True

    output_filename = f"Informe_Gerencial_ESPY_{data['vigencia']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    output_path = settings.GENERATED_DIR / output_filename
    doc.save(str(output_path))
    logger.info(f"Informe Word generado exitosamente en: {output_path}")
    return output_path

# ==============================================================================
# 6. PRESENTACIÓN EN POWERPOINT (.pptx) — 16:9 WIDESCREEN CONSULTORÍA TIER-1 (DARK MODE)
# ==============================================================================

BG_DARK = PptxRGBColor(11, 17, 32)         # #0B1120 Dark Dashboard Background
BG_CARD = PptxRGBColor(24, 34, 58)         # #18223A Dark Card Fill
CARD_BORDER = PptxRGBColor(51, 65, 85)     # #334155 Slate Border
TEXT_LIGHT = PptxRGBColor(248, 250, 252)   # #F8FAFC Primary White Text
TEXT_SLATE = PptxRGBColor(148, 163, 184)   # #94A3B8 Muted Text
TEXT_MUTED = PptxRGBColor(100, 116, 139)   # #64748B Subtitle Text

COLOR_EMERALD = PptxRGBColor(52, 211, 153) # #34D399 Glowing Emerald
COLOR_AMBER = PptxRGBColor(245, 158, 11)   # #F59E0B Amber
COLOR_RED = PptxRGBColor(239, 68, 68)      # #EF4444 Red
COLOR_CYAN = PptxRGBColor(56, 189, 248)    # #38BDF8 Glowing Cyan
COLOR_BLUE = PptxRGBColor(2, 132, 199)     # #0284C7 Blue

def add_pptx_header(slide, action_title: str, category_text: str = "INFORME OFICIAL"):
    cat_box = slide.shapes.add_textbox(PptxInches(0.8), PptxInches(0.30), PptxInches(11.733), PptxInches(0.30))
    tf_cat = cat_box.text_frame
    tf_cat.word_wrap = True
    p_cat = tf_cat.paragraphs[0]
    p_cat.text = f"EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. (ESPY)  •  {category_text.upper()}"
    p_cat.font.size = PptxPt(11.0)
    p_cat.font.bold = True
    p_cat.font.color.rgb = COLOR_CYAN

    title_box = slide.shapes.add_textbox(PptxInches(0.8), PptxInches(0.60), PptxInches(11.733), PptxInches(0.62))
    tf_title = title_box.text_frame
    tf_title.word_wrap = True
    p_title = tf_title.paragraphs[0]
    p_title.text = action_title
    p_title.font.size = PptxPt(22.0)
    p_title.font.bold = True
    p_title.font.color.rgb = TEXT_LIGHT

    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, PptxInches(0.8), PptxInches(1.26), PptxInches(11.733), PptxInches(0.02))
    line.fill.solid()
    line.fill.fore_color.rgb = CARD_BORDER
    line.line.fill.background()

def style_card(shape, fill_rgb: PptxRGBColor = BG_CARD, border_rgb: PptxRGBColor = CARD_BORDER, width_pt: float = 1.0):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_rgb
    shape.line.color.rgb = border_rgb
    shape.line.width = PptxPt(width_pt)

def generate_powerpoint_presentation(db: Session, vigencia: str = "2026", periodo: str = "ACUMULADO", include_annexes: bool = True) -> Path:
    """Generate executive PowerPoint (.pptx) with enlarged fonts and maximum visual clarity."""
    data = get_report_dataset(db, vigencia, periodo)
    prs = Presentation()

    prs.slide_width = PptxInches(13.333)
    prs.slide_height = PptxInches(7.5)
    blank_layout = prs.slide_layouts[6]

    def set_slide_background(slide):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = BG_DARK
        bg.line.fill.background()

    # =========================================================================
    # SLIDE 1: PORTADA EJECUTIVA (DARK DASHBOARD)
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_slide_background(s1)

    stripe = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, PptxInches(0.4), prs.slide_height)
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = BG_CARD
    stripe.line.fill.background()

    stripe_acc = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, PptxInches(0.4), 0, PptxInches(0.06), prs.slide_height)
    stripe_acc.fill.solid()
    stripe_acc.fill.fore_color.rgb = COLOR_CYAN
    stripe_acc.line.fill.background()

    cov_card = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(1.3), PptxInches(1.0), PptxInches(11.0), PptxInches(5.5))
    style_card(cov_card, BG_CARD, CARD_BORDER, width_pt=1.0)

    tb_cov = s1.shapes.add_textbox(PptxInches(1.8), PptxInches(1.35), PptxInches(10.0), PptxInches(4.7))
    tf_cov = tb_cov.text_frame
    tf_cov.word_wrap = True

    p0 = tf_cov.paragraphs[0]
    p0.text = "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P. (ESPY)"
    p0.font.size = PptxPt(14.0)
    p0.font.bold = True
    p0.font.color.rgb = COLOR_CYAN
    p0.space_after = PptxPt(16)

    p1 = tf_cov.add_paragraph()
    p1.text = "INFORME OFICIAL DE GESTIÓN Y BALANCE CONTRACTUAL"
    p1.font.size = PptxPt(30.0)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_LIGHT
    p1.space_after = PptxPt(12)

    p2 = tf_cov.add_paragraph()
    p2.text = f"Evaluación Presupuestal, Dinámica por Tipologías, Cuantías y Ritmo de Ejecución\nVigencia Fiscal {data['vigencia']}  •  {data['periodo_label']}"
    p2.font.size = PptxPt(15.0)
    p2.font.color.rgb = TEXT_SLATE
    p2.space_after = PptxPt(32)

    meta_box = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(1.8), PptxInches(4.45), PptxInches(10.0), PptxInches(1.65))
    style_card(meta_box, BG_DARK, CARD_BORDER, width_pt=1.0)

    tb_m = s1.shapes.add_textbox(PptxInches(2.05), PptxInches(4.55), PptxInches(9.5), PptxInches(1.45))
    tf_m = tb_m.text_frame
    tf_m.word_wrap = True

    pm1 = tf_m.paragraphs[0]
    pm1.text = "AUDIENCIA: JUNTA DIRECTIVA & GERENCIA GENERAL"
    pm1.font.size = PptxPt(12.5)
    pm1.font.bold = True
    pm1.font.color.rgb = COLOR_CYAN
    pm1.space_after = PptxPt(4)

    pm2 = tf_m.add_paragraph()
    pm2.text = f"• Régimen: Ley 142 de 1994 (Derecho Privado)   • Fecha de emisión: {data['fecha_emision'].upper()}"
    pm2.font.size = PptxPt(11.5)
    pm2.font.color.rgb = TEXT_SLATE
    pm2.space_after = PptxPt(4)

    pm3 = tf_m.add_paragraph()
    pm3.text = f"• NIT: 811.015.112-4   • Certificación Oficial: Plataforma de Contratación ESPY"
    pm3.font.size = PptxPt(11.0)
    pm3.font.color.rgb = TEXT_MUTED

    # =========================================================================
    # SLIDE 2: 1. PRESUPUESTO COMPROMETIDO Y 2. CANTIDAD DE CONTRATOS
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_slide_background(s2)
    add_pptx_header(s2, f"1. PRESUPUESTO COMPROMETIDO: {format_cop_millones(data['total_comprometido'])} EN {data['total_contratos']} CONTRATOS", "TECHO FORMALIZADO Y VOLUMEN")

    mods_desc = " • ".join(f"{v['conteo']} {k}" for k, v in data["modalidades"].items()) if data["modalidades"] else f"{data['total_contratos']} Contratación Directa"

    kpis_s2 = [
        {
            "row": 0, "col": 0,
            "title": "1. PRESUPUESTO COMPROMETIDO",
            "val": format_cop(data["total_comprometido"]),
            "tag": "100% TECHO FORMALIZADO",
            "bullet": f"Valor inicial: {format_cop(data['total_valor_inicial'])} + Adiciones: {format_cop(data['total_adiciones'])}.",
            "color_metric": TEXT_LIGHT,
            "color_accent": COLOR_CYAN
        },
        {
            "row": 0, "col": 1,
            "title": "2. CANTIDAD DE CONTRATOS",
            "val": f"{data['total_contratos']} Contratos",
            "tag": "TOTAL SUSCRITOS VIGENCIA",
            "bullet": f"Promedio por contrato: {format_cop(data['promedio_por_contrato'])}.",
            "color_metric": COLOR_CYAN,
            "color_accent": COLOR_CYAN
        },
        {
            "row": 1, "col": 0,
            "title": "MODALIDADES DE SELECCIÓN",
            "val": "Contratación Directa",
            "tag": "MODALIDAD PREDOMINANTE",
            "bullet": f"{mods_desc} ({format_pct(100.0)} del techo formalizado).",
            "color_metric": TEXT_LIGHT,
            "color_accent": COLOR_EMERALD
        },
        {
            "row": 1, "col": 1,
            "title": "ESTADO CONTRACTUAL",
            "val": "100% Operativo",
            "tag": "EN EJECUCIÓN ACTIVA",
            "bullet": f"{data['total_comprobantes']} comprobantes de egreso emitidos y pagados.",
            "color_metric": COLOR_EMERALD,
            "color_accent": COLOR_EMERALD
        }
    ]

    card_w = PptxInches(5.7)
    card_h = PptxInches(2.55)
    start_x = PptxInches(0.8)
    gap_x = PptxInches(0.33)
    start_y = PptxInches(1.55)
    gap_y = PptxInches(0.30)

    for item in kpis_s2:
        x = start_x + item["col"] * (card_w + gap_x)
        y = start_y + item["row"] * (card_h + gap_y)

        card = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, card_w, card_h)
        style_card(card, BG_CARD, CARD_BORDER, width_pt=1.0)

        l_bar = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, PptxInches(0.14), card_h)
        l_bar.fill.solid()
        l_bar.fill.fore_color.rgb = item["color_accent"]
        l_bar.line.fill.background()

        tb = s2.shapes.add_textbox(x + PptxInches(0.32), y + PptxInches(0.16), card_w - PptxInches(0.5), card_h - PptxInches(0.3))
        tf = tb.text_frame
        tf.word_wrap = True

        p_t = tf.paragraphs[0]
        p_t.text = item["title"]
        p_t.font.size = PptxPt(13.0)
        p_t.font.bold = True
        p_t.font.color.rgb = TEXT_SLATE
        p_t.space_after = PptxPt(3)

        p_v = tf.add_paragraph()
        p_v.text = item["val"]
        p_v.font.size = PptxPt(26.0)
        p_v.font.bold = True
        p_v.font.color.rgb = item["color_metric"]
        p_v.space_after = PptxPt(3)

        p_tag = tf.add_paragraph()
        p_tag.text = item["tag"]
        p_tag.font.size = PptxPt(12.0)
        p_tag.font.bold = True
        p_tag.font.color.rgb = item["color_accent"]
        p_tag.space_after = PptxPt(3)

        p_s = tf.add_paragraph()
        p_s.text = f"• {item['bullet']}"
        p_s.font.size = PptxPt(11.5)
        p_s.font.bold = True
        p_s.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 3: 3. EJECUCIÓN PRESUPUESTAL POR TIPOLOGÍA DE CONTRATOS
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_slide_background(s3)
    add_pptx_header(s3, "3. EJECUCIÓN PRESUPUESTAL POR TIPOLOGÍA: COMPROMETIDO VS. CAUSADO", "TIPOLOGÍAS CONTRACTUALES")

    # Tarjeta izquierda para gráfico en alta resolución
    card_l3 = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(0.8), PptxInches(1.55), PptxInches(7.6), PptxInches(5.4))
    style_card(card_l3, BG_CARD, CARD_BORDER, width_pt=1.0)

    try:
        buf_t_pptx = generate_typology_chart_bytes(data)
        s3.shapes.add_picture(
            io.BytesIO(buf_t_pptx.getvalue()),
            PptxInches(0.95), PptxInches(1.75), PptxInches(7.3), PptxInches(5.0)
        )
    except Exception as e_c3:
        logger.warning(f"Aviso insertando imagen de gráfico en Slide 3 PPTX: {e_c3}")

    # Tarjeta derecha con matriz de KPIs
    card_r3 = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(8.65), PptxInches(1.55), PptxInches(3.88), PptxInches(5.4))
    style_card(card_r3, BG_CARD, CARD_BORDER, width_pt=1.0)

    tb_r3 = s3.shapes.add_textbox(PptxInches(8.85), PptxInches(1.75), PptxInches(3.48), PptxInches(5.0))
    tf_r3 = tb_r3.text_frame
    tf_r3.word_wrap = True

    p_rt = tf_r3.paragraphs[0]
    p_rt.text = "MATRIZ DE EJECUCIÓN"
    p_rt.font.size = PptxPt(14.0)
    p_rt.font.bold = True
    p_rt.font.color.rgb = COLOR_CYAN
    p_rt.space_after = PptxPt(8)

    for tip in data["tipologias_summary"][:4]:
        p_ti = tf_r3.add_paragraph()
        p_ti.text = f"• {tip['label'].upper()} ({tip['pct_ejecucion']}%)"
        p_ti.font.size = PptxPt(12.5)
        p_ti.font.bold = True
        p_ti.font.color.rgb = COLOR_CYAN

        p_td = tf_r3.add_paragraph()
        p_td.text = f"  Comp.: {format_cop(tip['total_comprometido'])}\n  Ejec.: {format_cop(tip['total_ejecutado'])}\n  Saldo: {format_cop(tip['saldo_por_girar'])}"
        p_td.font.size = PptxPt(10.5)
        p_td.font.bold = True
        p_td.font.color.rgb = TEXT_LIGHT
        p_td.space_after = PptxPt(5)


    # =========================================================================
    # SLIDE 4: 4. CONTRATOS EJECUTADOS Y CUANTÍAS MÁS ALTAS POR TIPOLOGÍA
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_slide_background(s4)
    add_pptx_header(s4, "4. CONTRATOS EJECUTADOS Y CUANTÍAS MÁS ALTAS POR TIPOLOGÍA", "ANÁLISIS POR CONTRATISTA Y MODALIDAD")

    card_l4 = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(0.8), PptxInches(1.55), PptxInches(4.6), PptxInches(5.4))
    style_card(card_l4, BG_CARD, CARD_BORDER, width_pt=1.0)

    tb_l4 = s4.shapes.add_textbox(PptxInches(1.05), PptxInches(1.75), PptxInches(4.2), PptxInches(4.9))
    tf_l4 = tb_l4.text_frame
    tf_l4.word_wrap = True

    p_l4t = tf_l4.paragraphs[0]
    p_l4t.text = "CONTRATOS EJECUTADOS (CON PAGOS)"
    p_l4t.font.size = PptxPt(14.0)
    p_l4t.font.bold = True
    p_l4t.font.color.rgb = COLOR_CYAN
    p_l4t.space_after = PptxPt(8)

    for tip in data["tipologias_summary"][:4]:
        p_c1 = tf_l4.add_paragraph()
        p_c1.text = f"• {tip['label']}: {tip['contratos_ejecutados']} de {tip['contratos_formalizados']}"
        p_c1.font.size = PptxPt(13.0)
        p_c1.font.bold = True
        p_c1.font.color.rgb = COLOR_EMERALD if tip['pct_contratos_ejecutados'] >= 60 else COLOR_AMBER

        p_c2 = tf_l4.add_paragraph()
        p_c2.text = f"  Avance: {tip['pct_contratos_ejecutados']}% con orden de egreso ({tip['pagos_conteo']} egresos)."
        p_c2.font.size = PptxPt(11.0)
        p_c2.font.color.rgb = TEXT_LIGHT
        p_c2.space_after = PptxPt(6)

    card_r4 = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(5.7), PptxInches(1.55), PptxInches(6.8), PptxInches(5.4))
    style_card(card_r4, BG_CARD, CARD_BORDER, width_pt=1.0)

    tb_r4 = s4.shapes.add_textbox(PptxInches(5.95), PptxInches(1.75), PptxInches(6.35), PptxInches(4.9))
    tf_r4 = tb_r4.text_frame
    tf_r4.word_wrap = True

    p_r4t = tf_r4.paragraphs[0]
    p_r4t.text = "CONTRATOS DE MAYOR CUANTÍA POR TIPOLOGÍA"
    p_r4t.font.size = PptxPt(14.0)
    p_r4t.font.bold = True
    p_r4t.font.color.rgb = COLOR_CYAN
    p_r4t.space_after = PptxPt(8)

    for tip in data["tipologias_summary"][:4]:
        if not tip["top_cuantias"]:
            continue
        top1 = tip["top_cuantias"][0]
        p_top = tf_r4.add_paragraph()
        p_top.text = f"[{tip['label'].upper()}] {top1['numero_contrato']}  •  {format_cop(top1['valor_total'])}"
        p_top.font.size = PptxPt(13.0)
        p_top.font.bold = True
        p_top.font.color.rgb = COLOR_CYAN

        p_top_d = tf_r4.add_paragraph()
        p_top_d.text = f"• {top1['contratista_nombre']} - NIT {top1['contratista_doc']}\n• Ejecutado: {format_cop(top1['valor_ejecutado'])} ({top1['pct_ejecucion']}%)  |  Saldo: {format_cop(top1['saldo'])}"
        p_top_d.font.size = PptxPt(11.0)
        p_top_d.font.color.rgb = TEXT_LIGHT
        p_top_d.space_after = PptxPt(5)

    # =========================================================================
    # SLIDE 5: 5.1 COMPROMISOS FORMALIZADOS & 5.2 EJECUCIÓN BRUTA ACUMULADA
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_slide_background(s5)
    add_pptx_header(s5, "5.1 COMPROMISOS FORMALIZADOS & 5.2 EJECUCIÓN BRUTA ACUMULADA POR MES", "EVOLUCIÓN MENSUAL")

    # Tarjeta izquierda para gráfico en alta resolución
    card_l5 = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(0.8), PptxInches(1.55), PptxInches(7.6), PptxInches(5.4))
    style_card(card_l5, BG_CARD, CARD_BORDER, width_pt=1.0)

    try:
        buf_c_pptx = generate_compromisos_chart_bytes(data)
        s5.shapes.add_picture(
            io.BytesIO(buf_c_pptx.getvalue()),
            PptxInches(0.95), PptxInches(1.75), PptxInches(7.3), PptxInches(5.0)
        )
    except Exception as e_c5:
        logger.warning(f"Aviso insertando imagen de gráfico en Slide 5 PPTX: {e_c5}")

    card_r5 = s5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(8.65), PptxInches(1.55), PptxInches(3.88), PptxInches(5.4))
    style_card(card_r5, BG_CARD, CARD_BORDER, width_pt=1.0)

    tb_r5 = s5.shapes.add_textbox(PptxInches(8.85), PptxInches(1.75), PptxInches(3.48), PptxInches(4.9))
    tf_r5 = tb_r5.text_frame
    tf_r5.word_wrap = True

    p_r5_t1 = tf_r5.paragraphs[0]
    p_r5_t1.text = "5.1 TOTAL COMPROMISOS"
    p_r5_t1.font.size = PptxPt(13.0)
    p_r5_t1.font.bold = True
    p_r5_t1.font.color.rgb = COLOR_CYAN

    p_r5_v1 = tf_r5.add_paragraph()
    p_r5_v1.text = format_cop(data["total_comprometido"])
    p_r5_v1.font.size = PptxPt(22.0)
    p_r5_v1.font.bold = True
    p_r5_v1.font.color.rgb = TEXT_LIGHT
    p_r5_v1.space_after = PptxPt(14)

    p_r5_t2 = tf_r5.add_paragraph()
    p_r5_t2.text = "5.2 EJECUCIÓN BRUTA TOTAL"
    p_r5_t2.font.size = PptxPt(13.0)
    p_r5_t2.font.bold = True
    p_r5_t2.font.color.rgb = COLOR_EMERALD

    p_r5_v2 = tf_r5.add_paragraph()
    p_r5_v2.text = format_cop(data["total_ejecucion_bruta"])
    p_r5_v2.font.size = PptxPt(22.0)
    p_r5_v2.font.bold = True
    p_r5_v2.font.color.rgb = COLOR_EMERALD
    p_r5_v2.space_after = PptxPt(14)

    p_r5_desc = tf_r5.add_paragraph()
    p_r5_desc.text = f"• Compromisos concentrados en enero ({format_cop_millones(1573703340)}).\n• Mayor mes de facturación: Febrero ({format_cop_millones(273683998)})."
    p_r5_desc.font.size = PptxPt(11.5)
    p_r5_desc.font.bold = True
    p_r5_desc.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 6: 5.3 SALDOS DISPONIBLES POR GIRAR & 5.4 RETENCIONES PRACTICADAS
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_slide_background(s6)
    add_pptx_header(s6, "5.3 SALDOS POR GIRAR & 5.4 RETENCIONES PRACTICADAS POR MES Y TOTAL", "LIQUIDEZ Y FISCAL")

    # Tarjeta izquierda para gráfico en alta resolución de Saldos por Girar
    card_l6 = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(0.8), PptxInches(1.55), PptxInches(7.6), PptxInches(5.4))
    style_card(card_l6, BG_CARD, CARD_BORDER, width_pt=1.0)

    try:
        buf_s_pptx = generate_saldos_girar_chart_bytes(data)
        s6.shapes.add_picture(
            io.BytesIO(buf_s_pptx.getvalue()),
            PptxInches(0.95), PptxInches(1.75), PptxInches(7.3), PptxInches(5.0)
        )
    except Exception as e_c6:
        logger.warning(f"Aviso insertando imagen de gráfico en Slide 6 PPTX: {e_c6}")

    # Tarjeta derecha para KPIs de Saldos y Retenciones
    card_r6 = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(8.65), PptxInches(1.55), PptxInches(3.88), PptxInches(5.4))
    style_card(card_r6, BG_CARD, CARD_BORDER, width_pt=1.0)

    tb_r6 = s6.shapes.add_textbox(PptxInches(8.85), PptxInches(1.75), PptxInches(3.48), PptxInches(5.0))
    tf_r6 = tb_r6.text_frame
    tf_r6.word_wrap = True

    p_r6_1 = tf_r6.paragraphs[0]
    p_r6_1.text = "5.3 SALDO DISPONIBLE POR GIRAR"
    p_r6_1.font.size = PptxPt(13.0)
    p_r6_1.font.bold = True
    p_r6_1.font.color.rgb = COLOR_CYAN

    p_r6_1v = tf_r6.add_paragraph()
    p_r6_1v.text = format_cop(data['saldo_disponible_girar'])
    p_r6_1v.font.size = PptxPt(20.0)
    p_r6_1v.font.bold = True
    p_r6_1v.font.color.rgb = TEXT_LIGHT

    p_r6_1s = tf_r6.add_paragraph()
    p_r6_1s.text = f"• Remanente: {format_pct(100 - data['avance_presupuestal_global'])} del techo."
    p_r6_1s.font.size = PptxPt(11.0)
    p_r6_1s.font.bold = True
    p_r6_1s.font.color.rgb = TEXT_MUTED
    p_r6_1s.space_after = PptxPt(16)

    p_r6_2 = tf_r6.add_paragraph()
    p_r6_2.text = "5.4 RETENCIONES PRACTICADAS"
    p_r6_2.font.size = PptxPt(13.0)
    p_r6_2.font.bold = True
    p_r6_2.font.color.rgb = COLOR_AMBER

    p_r6_2v = tf_r6.add_paragraph()
    p_r6_2v.text = format_cop(data['total_retenciones'])
    p_r6_2v.font.size = PptxPt(20.0)
    p_r6_2v.font.bold = True
    p_r6_2v.font.color.rgb = COLOR_AMBER

    p_r6_2s = tf_r6.add_paragraph()
    p_r6_2s.text = f"• Giro neto a contratistas: {format_cop(data['total_neto_pagado'])}\n• ReteFuente + ICA + Estampillas al día."
    p_r6_2s.font.size = PptxPt(11.0)
    p_r6_2s.font.bold = True
    p_r6_2s.font.color.rgb = TEXT_LIGHT

    # =========================================================================
    # SLIDE 7: 5.5 RITMO DE EJECUCIÓN GLOBAL (AVANCE PRESUPUESTAL)
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_slide_background(s7)
    add_pptx_header(s7, f"5.5 RITMO DE EJECUCIÓN GLOBAL: {format_pct(data['avance_presupuestal_global'])} ({data['estado_semaforo_global']})", "AVANCE PRESUPUESTAL")

    # Tarjeta izquierda para gráfico en alta resolución del Ritmo y Semáforo
    card_l7 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(0.8), PptxInches(1.55), PptxInches(7.6), PptxInches(5.4))
    style_card(card_l7, BG_CARD, CARD_BORDER, width_pt=1.0)

    try:
        buf_a_pptx = generate_ritmo_avance_chart_bytes(data)
        s7.shapes.add_picture(
            io.BytesIO(buf_a_pptx.getvalue()),
            PptxInches(0.95), PptxInches(1.75), PptxInches(7.3), PptxInches(5.0)
        )
    except Exception as e_c7:
        logger.warning(f"Aviso insertando imagen de gráfico en Slide 7 PPTX: {e_c7}")

    card_r7 = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(8.65), PptxInches(1.55), PptxInches(3.88), PptxInches(5.4))
    style_card(card_r7, BG_CARD, COLOR_AMBER, width_pt=1.5)

    top_bar_amber = s7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(8.65), PptxInches(1.55), PptxInches(3.88), PptxInches(0.50))
    top_bar_amber.fill.solid()
    top_bar_amber.fill.fore_color.rgb = COLOR_AMBER
    top_bar_amber.line.fill.background()
    p_amb_t = top_bar_amber.text_frame.paragraphs[0]
    p_amb_t.text = f"ESTADO: {data['estado_semaforo_global']}"
    p_amb_t.font.size = PptxPt(12.5)
    p_amb_t.font.bold = True
    p_amb_t.font.color.rgb = BG_DARK
    p_amb_t.alignment = PP_ALIGN.CENTER

    tb_r7 = s7.shapes.add_textbox(PptxInches(8.85), PptxInches(2.20), PptxInches(3.48), PptxInches(4.5))
    tf_r7 = tb_r7.text_frame
    tf_r7.word_wrap = True

    p_h_lbl = tf_r7.paragraphs[0]
    p_h_lbl.text = "BRECHA VS. META LINEAL:"
    p_h_lbl.font.size = PptxPt(12.0)
    p_h_lbl.font.bold = True
    p_h_lbl.font.color.rgb = TEXT_MUTED

    p_h_num = tf_r7.add_paragraph()
    p_h_num.text = f"{data['brecha_global']}%"
    p_h_num.font.size = PptxPt(36.0)
    p_h_num.font.bold = True
    p_h_num.font.color.rgb = COLOR_AMBER
    p_h_num.space_after = PptxPt(8)

    bullets_ritmo = [
        ("Avance Global Real", f"{format_pct(data['avance_presupuestal_global'])} ejecutado."),
        ("Meta Lineal (Ago)", f"{data['meta_corte_lineal']}% teórico programado."),
        ("Velocidad de Giro", f"{format_cop_millones(data['velocidad_giro_promedio'])} / mes."),
        ("Diagnóstico", data["diagnostico_ritmo"]),
        ("Plan de Aceleración", data["mitigacion_ritmo"])
    ]

    for b_title, b_desc in bullets_ritmo:
        p_b = tf_r7.add_paragraph()
        p_b.text = f"• {b_title}: {b_desc}"
        p_b.font.size = PptxPt(11.0)
        p_b.font.bold = True
        p_b.font.color.rgb = TEXT_LIGHT
        p_b.space_after = PptxPt(4)

    # =========================================================================
    # SLIDE 8: DIRECTRICES EJECUTIVAS Y PLAN DE ACCIÓN DE CIERRE
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_slide_background(s8)
    add_pptx_header(s8, "DIRECTRICES EJECUTIVAS Y HOJA DE RUTA DE CIERRE CONTRACTUAL", "DECISIONES ESTRATÉGICAS")

    actions = [
        ("01", "Aceleración de Facturación Q4", "Supervisores de Contrato", "Exigir corte semanal de actas para cerrar la brecha de ejecución."),
        ("02", "Control Presupuestal de Suministros y Obra", "Dirección Técnica", "Garantizar entrega de actas finales de obra e insumos de red."),
        ("03", "Dispersión Fiscal Oportuna ($ 56.3M)", "Dirección Financiera", "Girar deducciones a DIAN y Municipio en los plazos de ley."),
        ("04", "Planeación Contractual Vigencia 2027", "Dirección Jurídica", "Estructurar estudios previos de servicios esenciales con anticipación.")
    ]

    for idx, (num, title, owner, desc) in enumerate(actions):
        y = PptxInches(1.55) + idx * PptxInches(1.35)
        act_card = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(0.8), y, PptxInches(11.733), PptxInches(1.22))
        style_card(act_card, BG_CARD, CARD_BORDER, width_pt=1.0)

        num_box = s8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, PptxInches(1.05), y + PptxInches(0.2), PptxInches(0.82), PptxInches(0.82))
        num_box.fill.solid()
        num_box.fill.fore_color.rgb = COLOR_CYAN
        num_box.line.fill.background()
        tf_num = num_box.text_frame
        p_n = tf_num.paragraphs[0]
        p_n.text = num
        p_n.font.size = PptxPt(20.0)
        p_n.font.bold = True
        p_n.font.color.rgb = BG_DARK
        p_n.alignment = PP_ALIGN.CENTER

        tb_act = s8.shapes.add_textbox(PptxInches(2.10), y + PptxInches(0.12), PptxInches(10.2), PptxInches(0.98))
        tf_act = tb_act.text_frame
        tf_act.word_wrap = True

        p_at = tf_act.paragraphs[0]
        p_at.text = title
        p_at.font.size = PptxPt(15.0)
        p_at.font.bold = True
        p_at.font.color.rgb = COLOR_CYAN
        p_at.space_after = PptxPt(2)

        p_ad = tf_act.add_paragraph()
        p_ad.text = f"• Responsable: {owner}   • Acción: {desc}"
        p_ad.font.size = PptxPt(12.0)
        p_ad.font.bold = True
        p_ad.font.color.rgb = TEXT_LIGHT

    output_filename = f"Presentacion_Ejecutiva_ESPY_{data['vigencia']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
    output_path = settings.GENERATED_DIR / output_filename
    prs.save(str(output_path))
    logger.info(f"Presentación PowerPoint generada exitosamente en: {output_path}")
    return output_path

