from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.utils.logger import logger
from app.schemas.apu import (
    ItemCotizacion,
    ProponenteOferta,
    ProcesoConfig,
    ItemAPUConsolidado,
    EvaluacionComparativaPayload,
    EvaluacionComparativaResult,
    APUDescomposicion
)
from app.services.agents.apu_agent import apu_agent
from app.routers.auth import require_editor
from app.models.user import Usuario

router = APIRouter(prefix="/apu", tags=["Contratación Inteligente y APU"])

class DecomposeItemRequest(BaseModel):
    item: ItemCotizacion
    contexto_objeto: Optional[str] = ""

@router.get("/demo-case", response_model=EvaluacionComparativaPayload)
def get_apu_demo_case():
    """
    Retorna el caso real oficial del PGIRS de Yolombó (ASOCOMUNAL, TORREON, M360 COMPANY)
    con los 15 requerimientos ambientales y desglose de costos.
    """
    try:
        return apu_agent.get_demo_case()
    except Exception as e:
        logger.error(f"Error obteniendo caso demo APU: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error obteniendo caso demo: {str(e)}"
        )

class CalculateRulesRequest(BaseModel):
    valor_total: float
    smlmv: float = 1750905.0
    tipo_contrato: str = "Suministro"
    plazo_meses: int = 1
    anticipo_pct: float = 0.0
    modalidad_manual_codigo: str = "AUTO"
    causal_directa_numeral_19: Optional[str] = None

@router.post("/calculate-rules")
def calculate_rules_endpoint(req: CalculateRulesRequest):
    """
    Calcula la modalidad de selección y las garantías requeridas según el Manual de Contratación ESPY (PR-ESPY-002).
    """
    return apu_agent.calculate_manual_modalidad_and_guarantees(
        valor_total=req.valor_total,
        smlmv=req.smlmv,
        tipo_contrato=req.tipo_contrato,
        plazo_meses=req.plazo_meses,
        anticipo_pct=req.anticipo_pct,
        modalidad_manual_codigo=req.modalidad_manual_codigo,
        causal_directa_numeral_19=req.causal_directa_numeral_19
    )

@router.post("/extract-multiple-offers", response_model=List[ProponenteOferta])
async def extract_multiple_offers(
    files: List[UploadFile] = File(...),
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini")
):
    """
    Procesa múltiples archivos de cotización de forma simultánea (PDF, Excel, Word, CSV, JSON).
    Soporta archivos individuales y PDFs escaneados compuestos con múltiples propuestas integradas.
    """
    results: List[ProponenteOferta] = []
    for file in files:
        try:
            contents = await file.read()
            extracted_offers = apu_agent.extract_all_offers_from_file(
                file_bytes=contents,
                filename=file.filename or "cotizaciones.pdf",
                override_api_key=api_key
            )
            results.extend(extracted_offers)
        except Exception as e:
            logger.error(f"Error extrayendo cotización {file.filename}: {e}")
    return results

@router.post("/extract-offer", response_model=ProponenteOferta)
async def extract_offer_from_file(
    file: UploadFile = File(...),
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini")
):
    """
    Procesa un archivo de cotización individual (Excel, CSV, JSON, Word, PDF) o texto,
    extrayendo metadatos del proponente e ítems con auditoría aritmética automática.
    """
    try:
        contents = await file.read()
        extracted_offers = apu_agent.extract_all_offers_from_file(
            file_bytes=contents,
            filename=file.filename or "cotizacion.xlsx",
            override_api_key=api_key
        )
        if extracted_offers:
            return extracted_offers[0]
        return apu_agent.parse_and_extract_offer(
            file_bytes=contents,
            filename=file.filename or "cotizacion.xlsx",
            override_api_key=api_key
        )
    except Exception as e:
        logger.error(f"Error extrayendo cotización: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error extrayendo oferta de {file.filename}: {str(e)}"
        )

@router.post("/evaluate", response_model=EvaluacionComparativaResult)
def evaluate_proposals_endpoint(
    payload: EvaluacionComparativaPayload,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini")
):
    """
    Ejecuta el estudio comparativo de mercado, control aritmético, clasificación por menor precio,
    matriz comparativa ítem a ítem y auto-desglose de APU precontractual.
    """
    try:
        return apu_agent.evaluate_proposals(payload, override_api_key=api_key)
    except Exception as e:
        logger.error(f"Error evaluando propuestas: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en evaluación comparativa: {str(e)}"
        )

@router.post("/decompose-item", response_model=APUDescomposicion)
def decompose_item_endpoint(
    payload: DecomposeItemRequest,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini")
):
    """
    Desglosa un precio unitario en Componentes A (Materiales), B (Mano de obra) y C (Transporte/Equipos).
    """
    try:
        return apu_agent.decompose_item_apu(
            item=payload.item,
            contexto_objeto=payload.contexto_objeto or "",
            override_api_key=api_key
        )
    except Exception as e:
        logger.error(f"Error desglosando APU de ítem: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error desglosando APU: {str(e)}"
        )

@router.post("/generate-informe-docx")
def generate_informe_docx_endpoint(
    payload: EvaluacionComparativaResult
):
    """
    Genera y descarga el DOCUMENTO 1:
    'INFORME DE EVALUACIÓN COMPARATIVA DE PROPUESTAS Y RECOMENDACIÓN DE SELECCIÓN' en formato Word (.docx).
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"Informe_Evaluacion_Comparativa_ESPY_{timestamp}.docx"
        out_dir = settings.GENERATED_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / safe_name

        apu_agent.generate_docx_evaluacion(payload, output_path)

        return FileResponse(
            path=str(output_path),
            filename=safe_name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        logger.error(f"Error generando Documento 1 (.docx): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando Informe de Evaluación Word: {str(e)}"
        )

@router.post("/generate-presupuesto-apu-docx")
def generate_presupuesto_apu_docx_endpoint(
    payload: EvaluacionComparativaResult
):
    """
    Genera y descarga el DOCUMENTO 2:
    'ANÁLISIS DE PRECIOS UNITARIOS (APU) Y PRESUPUESTO OFICIAL PRECONTRACTUAL' en formato Word (.docx).
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"APU_Presupuesto_Precontractual_ESPY_{timestamp}.docx"
        out_dir = settings.GENERATED_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / safe_name

        apu_agent.generate_docx_apu(payload, output_path)

        return FileResponse(
            path=str(output_path),
            filename=safe_name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        logger.error(f"Error generando Documento 2 (.docx): {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando APU y Presupuesto Oficial Word: {str(e)}"
        )

@router.post("/incorporar-a-contrato/{contract_id}")
def incorporar_apu_a_contrato_endpoint(
    contract_id: int,
    payload: Dict[str, Any],
    _user: Usuario = Depends(require_editor)
):
    """
    Incorpora el resultado de la evaluación APU y estudio de mercado directamente a un contrato.
    """
    from app.database import SessionLocal
    from app.models.contract import Contrato
    from app.models.audit_log import Auditoria

    with SessionLocal() as db:
        contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contrato con ID {contract_id} no encontrado."
            )

        estudio_result = payload
        if "ofertas" in payload and "proponente_ganador" not in payload:
            try:
                from app.schemas.apu import EvaluacionComparativaPayload
                eval_payload = EvaluacionComparativaPayload(**payload)
                eval_res = apu_agent.evaluate_proposals(eval_payload)
                estudio_result = eval_res.model_dump()
            except Exception as e_ev:
                logger.warning(f"Aviso evaluando en apu router: {e_ev}")

        resumen = apu_agent.build_resumen_estudio_mercado(estudio_result)

        contract.estudio_mercado = estudio_result
        meta = dict(contract.metadatos_agente or {})
        meta["tiene_estudio_mercado"] = True
        meta["estudio_mercado"] = estudio_result
        contract.metadatos_agente = meta
        contract.updated_at = datetime.now()

        audit = Auditoria(
            contrato_id=contract.id,
            accion="INCORPORACION_ESTUDIO_MERCADO",
            detalle="Estudio de mercado y APU incorporado desde módulo APU para Estudio Previo.",
            usuario=_user.nombre_completo or _user.username,
            usuario_documento=_user.documento,
            usuario_nombre=_user.nombre_completo or _user.username
        )
        db.add(audit)
        db.commit()

        return {
            "status": "success",
            "mensaje": f"Estudio de mercado incorporado con éxito al contrato {contract.numero_contrato}.",
            "contrato_id": contract.id,
            "numero_contrato": contract.numero_contrato,
            "tiene_estudio_mercado": True,
            "resumen": resumen
        }

