"""Reports Router: Endpoints to preview and download Word (.docx) and PowerPoint (.pptx) reports."""
from datetime import datetime
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.report_generator import (
    get_report_dataset,
    generate_word_report,
    generate_powerpoint_presentation,
    format_cop
)
from app.utils.logger import logger

reports_router = APIRouter(prefix="/reports", tags=["Centro de Reportes e Informes"])

@reports_router.get("/preview")
def get_reports_preview(
    vigencia: Optional[str] = Query("2026", description="Año de vigencia o 'ALL'"),
    periodo: Optional[str] = Query("ACUMULADO", description="Periodo de corte (Q1, Q2, Q3, Q4, S1, S2, ACUMULADO, ANUAL)"),
    db: Session = Depends(get_db)
):
    """Return aggregated metrics for the reports center UI live preview."""
    try:
        data = get_report_dataset(db, vigencia=vigencia, periodo=periodo)
        
        # Resumen formateado para el frontend
        return {
            "status": "success",
            "vigencia": data["vigencia"],
            "periodo_label": data["periodo_label"],
            "fecha_emision": data["fecha_emision"],
            "kpis": {
                "total_contratos": data["total_contratos"],
                "total_contratado": data["total_contratado"],
                "total_contratado_formatted": format_cop(data["total_contratado"]),
                "total_orden": data["total_orden"],
                "total_orden_formatted": format_cop(data["total_orden"]),
                "total_retencion": data["total_retencion"],
                "total_retencion_formatted": format_cop(data["total_retencion"]),
                "total_pagar": data["total_pagar"],
                "total_pagar_formatted": format_cop(data["total_pagar"]),
                "total_estampillas": data.get("ret_estampillas", 0.0),
                "total_estampillas_formatted": format_cop(data.get("ret_estampillas", 0.0)),
                "saldo_por_ejecutar": data["saldo_por_ejecutar"],
                "saldo_por_ejecutar_formatted": format_cop(data["saldo_por_ejecutar"]),
                "pct_ejecucion": data["pct_ejecucion"],
                "conteo_comprobantes": data["conteo_comprobantes"],
                "reserva_contingencia": data["reserva_contingencia"],
                "reserva_contingencia_formatted": format_cop(data["reserva_contingencia"]),
                "cupo_libre_operativo": data["cupo_libre_operativo"],
                "cupo_libre_operativo_formatted": format_cop(data["cupo_libre_operativo"])
            },
            "tipologias": {
                k: {
                    "valor": data["tipologias"][k],
                    "valor_formatted": format_cop(data["tipologias"][k]),
                    "conteo": data["tipologias_count"][k],
                    "pct": round((data["tipologias"][k] / data["total_contratado"] * 100), 1) if data["total_contratado"] > 0 else 0
                }
                for k in data["tipologias"]
            },
            "tipologias_summary": data.get("tipologias_summary", []),
            "retenciones": {
                "ret_fuente": format_cop(data["ret_fuente"]),
                "ret_ica": format_cop(data["ret_ica"]),
                "ret_garantia": format_cop(data["ret_garantia"]),
                "ret_estampillas": format_cop(data["ret_estampillas"])
            },
            "top_contracts": [
                {
                    "codigo": c.get("codigo") or c.get("numero_contrato", ""),
                    "valor": format_cop(c.get("valor_total", 0.0)),
                    "objeto": c.get("objeto", "")
                }
                for c in data["top_contracts"]
            ],
            "monthly_report": data.get("monthly_report", []),
            "secciones_oficiales": {
                "1_presupuesto_comprometido": {
                    "total_comprometido": data["total_comprometido"],
                    "total_comprometido_formatted": format_cop(data["total_comprometido"]),
                    "total_valor_inicial_formatted": format_cop(data.get("total_valor_inicial", 0.0)),
                    "total_adiciones_formatted": format_cop(data.get("total_adiciones", 0.0)),
                    "promedio_contrato_formatted": format_cop(data.get("promedio_por_contrato", 0.0))
                },
                "2_cantidad_contratos": {
                    "total_contratos": data["total_contratos"],
                    "modalidades": data.get("modalidades", {}),
                    "estados": data.get("estados", {})
                },
                "3_ejecucion_por_tipologia": [
                    {
                        "tipologia": tip["label"],
                        "comprometido_formatted": format_cop(tip["total_comprometido"]),
                        "ejecutado_formatted": format_cop(tip["total_ejecutado"]),
                        "saldo_formatted": format_cop(tip["saldo_por_girar"]),
                        "pct_ejecucion": tip["pct_ejecucion"]
                    }
                    for tip in data.get("tipologias_summary", [])
                ],
                "4_contratos_ejecutados_y_top": [
                    {
                        "tipologia": tip["label"],
                        "contratos_formalizados": tip["contratos_formalizados"],
                        "contratos_ejecutados": tip["contratos_ejecutados"],
                        "pct_ejecutados": tip["pct_contratos_ejecutados"],
                        "top_cuantias": tip["top_cuantias"]
                    }
                    for tip in data.get("tipologias_summary", [])
                ],
                "5_informe_financiero_mensual": {
                    "total_compromisos_formatted": format_cop(data["total_comprometido"]),
                    "total_ejecucion_bruta_formatted": format_cop(data["total_ejecucion_bruta"]),
                    "total_saldo_girar_formatted": format_cop(data["saldo_disponible_girar"]),
                    "total_retenciones_formatted": format_cop(data["total_retenciones"]),
                    "avance_global_pct": data["avance_presupuestal_global"],
                    "semaforo": data["estado_semaforo_global"],
                    "velocidad_giro_formatted": format_cop(data["velocidad_giro_promedio"])
                }
            }
        }
    except Exception as e:
        logger.error(f"Error generando preview de reportes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al compilar vista previa: {str(e)}")

@reports_router.get("/download/word")
def download_word_report(
    vigencia: Optional[str] = Query("2026", description="Año de vigencia o 'ALL'"),
    periodo: Optional[str] = Query("ACUMULADO", description="Periodo de corte"),
    include_annexes: bool = Query(True, description="Incluir anexos de liquidación y pólizas"),
    db: Session = Depends(get_db)
):
    """Compile and download official Word (.docx) report."""
    try:
        docx_path = generate_word_report(db, vigencia=vigencia, periodo=periodo, include_annexes=include_annexes)
        if not docx_path.exists():
            raise HTTPException(status_code=500, detail="No se pudo crear el archivo Word.")
        
        filename = f"Informe_Gerencial_ESPY_{vigencia}_{datetime.now().strftime('%Y%m%d')}.docx"
        return FileResponse(
            path=str(docx_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error descargando informe Word: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al generar informe Word: {str(e)}")

@reports_router.get("/download/powerpoint")
def download_powerpoint_report(
    vigencia: Optional[str] = Query("2026", description="Año de vigencia o 'ALL'"),
    periodo: Optional[str] = Query("ACUMULADO", description="Periodo de corte"),
    include_annexes: bool = Query(True, description="Incluir anexos y proyectos"),
    db: Session = Depends(get_db)
):
    """Compile and download executive PowerPoint (.pptx) presentation."""
    try:
        pptx_path = generate_powerpoint_presentation(db, vigencia=vigencia, periodo=periodo, include_annexes=include_annexes)
        if not pptx_path.exists():
            raise HTTPException(status_code=500, detail="No se pudo crear la presentación PowerPoint.")
        
        filename = f"Presentacion_Ejecutiva_ESPY_{vigencia}_{datetime.now().strftime('%Y%m%d')}.pptx"
        return FileResponse(
            path=str(pptx_path),
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error descargando presentación PowerPoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al generar presentación PowerPoint: {str(e)}")
