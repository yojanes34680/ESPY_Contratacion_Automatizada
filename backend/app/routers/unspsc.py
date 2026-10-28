"""Router API para el Agente Clasificador de Códigos UNSPSC.
Permite análisis integral de documentos, búsqueda en el catálogo oficial de 52.845 códigos,
vinculación directa a contratos del sistema y descarga de dictámenes en Word (.docx).
Soporta selección de motor ("clasico" por defecto o "nuevo") detrás de interruptor.
"""
import os
import re
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.contract import Contrato
from app.models.document import Documento
from app.models.audit_log import Auditoria
from app.models.user import Usuario
from app.routers.auth import get_current_user, require_editor
from app.schemas.unspsc import (
    UnspscAnalysisInput, 
    UnspscAnalysisResult, 
    UnspscCodeItem
)
from app.services.agents.unspsc_agent import unspsc_agent
from app.services.document_parser import parse_document_text
from app.utils.logger import logger

router = APIRouter(prefix="/unspsc", tags=["Agente Clasificador UNSPSC"])

# Creador perezoso (lazy) para el selector nuevo
_new_selector = None

def get_unspsc_selector():
    global _new_selector
    if _new_selector is None:
        from app.services.agents.unspsc.selector import unspsc_selector_agent
        _new_selector = unspsc_selector_agent
    return _new_selector


@router.get("/status")
def get_unspsc_status(current_user: Usuario = Depends(get_current_user)):
    """Retorna el estado del catálogo oficial UNSPSC y del motor configurado."""
    resources_dir = Path(__file__).resolve().parent.parent / "resources"
    bm25_path = resources_dir / "unspsc_bm25_index.pickle"
    emb_path = resources_dir / "unspsc_embeddings.npy"

    indice_bm25_cargado = bm25_path.exists()
    embeddings_cargados = emb_path.exists()

    if not indice_bm25_cargado:
        logger.error(f"[UNSPSC] Error crítico: El archivo de índice léxico BM25 no fue encontrado en {bm25_path}")

    return {
        "catalogo_cargado": unspsc_agent.get_catalog_size() > 0,
        "total_codigos_oficiales": unspsc_agent.get_catalog_size(),
        "archivo_fuente": "codigos unspsc_contratacion.xlsx",
        "motor_configurado": settings.UNSPSC_MOTOR,
        "indice_bm25_cargado": indice_bm25_cargado,
        "embeddings_cargados": embeddings_cargados
    }


@router.get("/search")
def search_unspsc_codes(
    query: str = Query("", description="Código o palabra clave a buscar"),
    limit: int = Query(50, ge=1, le=200),
    current_user: Usuario = Depends(get_current_user)
):
    """Busca en tiempo real dentro de los 52.845 códigos oficiales."""
    return unspsc_agent.search_catalog(query, limit)


@router.post("/analyze", response_model=UnspscAnalysisResult)
def analyze_unspsc_contract(
    payload: UnspscAnalysisInput,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ejecuta el análisis de contratación, estructuración y clasificación UNSPSC.
    Usa la clave del servidor (settings.GEMINI_API_KEY).
    Selecciona motor 'nuevo' o 'clasico' según settings.UNSPSC_MOTOR.
    """
    try:
        objeto = (payload.objeto or "").strip()
        estudio = (payload.estudio_previo or "").strip()
        propuesta = (payload.propuesta_economica or "").strip()

        if payload.contract_id:
            contrato = db.query(Contrato).filter(Contrato.id == payload.contract_id).first()
            if not contrato:
                raise HTTPException(status_code=404, detail="Contrato no encontrado.")
            
            if not objeto:
                objeto = contrato.objeto or ""
            if not estudio:
                estudio = contrato.justificacion_necesidad or ""
            
            docs = db.query(Documento).filter(Documento.contrato_id == payload.contract_id).all()
            if not estudio:
                for doc in docs:
                    nombre = (doc.nombre_archivo_original or "").lower()
                    tipo = str(doc.tipo_documento).lower()
                    if "estudio" in nombre or "necesidad" in nombre or "previo" in tipo:
                        file_p = Path(doc.ruta_archivo)
                        if file_p.exists():
                            try:
                                parsed = parse_document_text(file_p)
                                if parsed and len(parsed.strip()) > 30:
                                    clean_doc = unspsc_agent.clean_and_reconstruct_document_text(parsed)
                                    estudio = clean_doc[:30000] if len(clean_doc) > 30000 else clean_doc
                                    break
                            except Exception:
                                pass
            
            if not propuesta:
                for doc in docs:
                    nombre = (doc.nombre_archivo_original or "").lower()
                    tipo = str(doc.tipo_documento).lower()
                    if "propuesta" in nombre or "cotiz" in nombre or "oferta" in tipo:
                        file_p = Path(doc.ruta_archivo)
                        if file_p.exists():
                            try:
                                parsed = parse_document_text(file_p)
                                if parsed and len(parsed.strip()) > 30:
                                    clean_doc = unspsc_agent.clean_and_reconstruct_document_text(parsed)
                                    propuesta = clean_doc[:30000] if len(clean_doc) > 30000 else clean_doc
                                    break
                            except Exception:
                                pass

        input_data = UnspscAnalysisInput(
            objeto=objeto,
            estudio_previo=estudio,
            propuesta_economica=propuesta,
            contract_id=payload.contract_id
        )

        server_key = settings.GEMINI_API_KEY or None

        if settings.UNSPSC_MOTOR == "nuevo":
            selector = get_unspsc_selector()
            return selector.analyze_contract_unspsc(input_data, override_api_key=server_key)
        else:
            return unspsc_agent.analyze_contract_unspsc(input_data, override_api_key=server_key)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en análisis UNSPSC: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en el análisis UNSPSC. Revise el registro del servidor."
        )


@router.post("/analyze-files", response_model=UnspscAnalysisResult)
async def analyze_unspsc_files(
    estudio_file: Optional[UploadFile] = File(None, description="PDF o DOCX del Estudio Previo"),
    propuesta_file: Optional[UploadFile] = File(None, description="PDF o DOCX de la Propuesta Económica"),
    objeto_manual: Optional[str] = Form(None, description="Objeto contractual opcional ingresado por el usuario"),
    objeto: Optional[str] = Form(None, description="Objeto contractual opcional (alias de objeto_manual)"),
    estudio_previo_text: Optional[str] = Form(None, description="Texto pegado opcional del Estudio Previo"),
    propuesta_text: Optional[str] = Form(None, description="Texto pegado opcional de la Propuesta Económica"),
    contract_id: Optional[int] = Form(None, description="ID del contrato para autocompletar contexto"),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analiza directamente los archivos subidos y/o texto pegado (límite 20 MB por archivo).
    Usa la clave del servidor (settings.GEMINI_API_KEY).
    """
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

    temp_dir = settings.STORAGE_DIR / "temp_unspsc"
    temp_dir.mkdir(parents=True, exist_ok=True)
    files_to_clean = []

    estudio_final = ""
    propuesta_final = ""
    objeto_clean = (objeto_manual or objeto or "").strip()

    try:
        # Validación y lectura de estudio_file
        if estudio_file and estudio_file.filename:
            content = await estudio_file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo del estudio previo supera el límite permitido de 20 MB."
                )
            safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', estudio_file.filename)
            ts = int(datetime.now().timestamp() * 1000)
            save_path = temp_dir / f"estudio_{ts}_{safe_name}"
            with open(save_path, "wb") as f:
                f.write(content)
            files_to_clean.append(save_path)

            try:
                parsed_txt = parse_document_text(save_path)
                if parsed_txt:
                    clean_txt = unspsc_agent.clean_and_reconstruct_document_text(parsed_txt)
                    txt_sample = clean_txt[:30000] if len(clean_txt) > 30000 else clean_txt
                    estudio_final += f"\n{txt_sample}\n"
            except Exception as e_parse:
                logger.warning(f"Error parseando archivo de estudio previo: {e_parse}")

        # Validación y lectura de propuesta_file
        if propuesta_file and propuesta_file.filename:
            content_p = await propuesta_file.read()
            if len(content_p) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"El archivo de la propuesta supera el límite permitido de 20 MB."
                )
            safe_name_p = re.sub(r'[^a-zA-Z0-9_.-]', '_', propuesta_file.filename)
            ts_p = int(datetime.now().timestamp() * 1000)
            save_path_p = temp_dir / f"propuesta_{ts_p}_{safe_name_p}"
            with open(save_path_p, "wb") as f:
                f.write(content_p)
            files_to_clean.append(save_path_p)

            try:
                parsed_txt_p = parse_document_text(save_path_p)
                if parsed_txt_p:
                    clean_txt_p = unspsc_agent.clean_and_reconstruct_document_text(parsed_txt_p)
                    txt_sample_p = clean_txt_p[:30000] if len(clean_txt_p) > 30000 else clean_txt_p
                    propuesta_final += f"\n{txt_sample_p}\n"
            except Exception as e_parse_p:
                logger.warning(f"Error parseando archivo de propuesta económica: {e_parse_p}")

        # Incorporar texto pegado si fue provisto
        if estudio_previo_text and estudio_previo_text.strip():
            estudio_final = f"{estudio_previo_text.strip()}\n{estudio_final}".strip()
        if propuesta_text and propuesta_text.strip():
            propuesta_final = f"{propuesta_text.strip()}\n{propuesta_final}".strip()

        if not estudio_final.strip() and not objeto_clean and not contract_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Debe cargar el estudio previo (archivo o texto)"
            )

        input_data = UnspscAnalysisInput(
            objeto=objeto_clean,
            estudio_previo=estudio_final,
            propuesta_economica=propuesta_final,
            contract_id=contract_id
        )

        server_key = settings.GEMINI_API_KEY or None

        if settings.UNSPSC_MOTOR == "nuevo":
            selector = get_unspsc_selector()
            return selector.analyze_contract_unspsc(input_data, override_api_key=server_key)
        else:
            return unspsc_agent.analyze_contract_unspsc(input_data, override_api_key=server_key)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analizando archivos para clasificación UNSPSC: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en el análisis UNSPSC. Revise el registro del servidor."
        )
    finally:
        for f_path in files_to_clean:
            try:
                if f_path.exists():
                    f_path.unlink(missing_ok=True)
            except Exception as e_del:
                logger.debug(f"Aviso al limpiar temporal {f_path}: {e_del}")


@router.post("/contracts/{contract_id}/save")
def save_contract_unspsc(
    contract_id: int,
    payload: UnspscAnalysisResult,
    current_user: Usuario = Depends(require_editor),
    db: Session = Depends(get_db)
):
    """Guarda y vincula la clasificación UNSPSC en el contrato seleccionado (requiere rol EDITOR o ADMIN)."""
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    data_dict = payload.model_dump()
    contrato.codigos_unspsc = data_dict

    # Si el contrato no tiene objeto asignado, guardar también el objeto detectado
    if not (contrato.objeto and len(contrato.objeto.strip()) > 5):
        if payload.objeto_detectado and len(payload.objeto_detectado.strip()) > 5:
            contrato.objeto = payload.objeto_detectado.strip()

    # Paso 6: Guardar en UnspscHistoricalFeedback EXCLUSIVAMENTE los códigos con estado 'aprobado' y cita verificada
    feedback_saved = 0
    try:
        from app.models.unspsc import UnspscHistoricalFeedback
        import uuid
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item_cod in payload.codigos_seleccionados:
            # Solo códigos formalmente aprobados con cita verificada
            if item_cod.estado != "aprobado" or not item_cod.cita_verificada:
                continue

            desc_item = item_cod.justificacion_eleccion or contrato.objeto or ""
            m_cita = re.search(r'Cita:\s*"(.*?)"', desc_item)
            clean_item_desc = m_cita.group(1) if m_cita else item_cod.descripcion_codigo

            feedback_entry = UnspscHistoricalFeedback(
                id=str(uuid.uuid4()),
                item_descripcion=clean_item_desc[:500],
                codigo_unspsc=item_cod.codigo_unspsc,
                objeto_contrato=contrato.objeto[:1000] if contrato.objeto else None,
                contract_id=str(contract_id),
                creado_en=now_str
            )
            db.add(feedback_entry)
            feedback_saved += 1

        if feedback_saved > 0:
            # Si el motor nuevo está instanciado, invalidar/recargar su caché en memoria
            try:
                selector = get_unspsc_selector()
                selector.search_engine.reload_historical_feedback()
            except Exception:
                pass
    except Exception as e_hist:
        logger.warning(f"Error guardando feedback histórico UNSPSC: {e_hist}")

    # Registrar auditoría con el nombre de usuario real autenticado
    nombre_autor = current_user.nombre_completo if current_user else "Usuario Autenticado"
    detalle_dict = {
        "total_codigos": len(payload.codigos_seleccionados),
        "codigos": [c.codigo_unspsc for c in payload.codigos_seleccionados],
        "guardados_feedback_aprobados": feedback_saved,
        "autor_documento": current_user.documento if current_user else None
    }
    db.add(Auditoria(
        contrato_id=contract_id,
        usuario=nombre_autor,
        accion="CLASIFICACION_UNSPSC_GUARDADA",
        detalle=json.dumps(detalle_dict, ensure_ascii=False)
    ))
    db.commit()
    db.refresh(contrato)

    return {
        "success": True,
        "message": f"Clasificación UNSPSC guardada exitosamente en el contrato {contrato.numero_contrato}.",
        "total_codigos": len(payload.codigos_seleccionados),
        "feedback_aprobados_guardados": feedback_saved
    }


@router.get("/contracts/{contract_id}")
def get_contract_unspsc(
    contract_id: int,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene la clasificación de códigos UNSPSC asociada a un contrato."""
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    return {
        "contract_id": contract_id,
        "numero_contrato": contrato.numero_contrato,
        "tiene_clasificacion_unspsc": bool(contrato.codigos_unspsc),
        "codigos_unspsc": contrato.codigos_unspsc
    }


@router.post("/export-docx")
def export_unspsc_docx_report(
    payload: Dict[str, Any],
    current_user: Usuario = Depends(require_editor)
):
    """Genera y descarga el informe oficial en formato Word (.docx). Requiere rol EDITOR o ADMIN."""
    try:
        result_data = payload.get("result", {})
        objeto = payload.get("objeto", "")
        numero_contrato = payload.get("numero_contrato", "")

        analysis_result = UnspscAnalysisResult(**result_data)
        if not objeto or len(str(objeto).strip()) < 5:
            objeto = analysis_result.objeto_detectado or ""

        doc_path = unspsc_agent.generate_unspsc_report_docx(
            analysis_result,
            objeto=objeto,
            numero_contrato=numero_contrato
        )

        return FileResponse(
            path=str(doc_path),
            filename=doc_path.name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        logger.error(f"Error generando reporte Word UNSPSC: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error en la generación del informe Word UNSPSC. Revise el registro del servidor."
        )
