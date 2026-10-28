"""Word templates generation and download endpoints router."""
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.contract import Contrato
from app.models.document import Documento
from app.models.audit_log import Auditoria
from app.services.docx_engine import (
    generate_docx_for_contract, 
    create_default_templates_if_missing,
    get_all_templates_status,
    get_template_status,
    save_custom_template,
    reset_custom_template,
    get_active_template_path
)
from fastapi import UploadFile, File
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario

router = APIRouter(prefix="/templates", tags=["Plantillas y Generación Word"])

@router.get("/status")
def get_templates_status():
    """
    Retorna el estado de las 3 plantillas contractuales (Estudio Previo, Minuta y Acta de Inicio),
    indicando si son plantillas personalizadas cargadas por el usuario o las oficiales por defecto,
    así como los marcadores detectados en cada una.
    """
    create_default_templates_if_missing()
    return get_all_templates_status()

@router.get("/available")
def list_available_templates():
    """Devuelve las plantillas Word disponibles para generación contractual."""
    create_default_templates_if_missing()
    return get_all_templates_status()

@router.post("/upload/{template_type}")
async def upload_custom_template(
    template_type: str,
    file: UploadFile = File(...),
    current_user: Usuario = Depends(require_admin)
):
    """
    Permite a la ESP cargar sus propios modelos de Word (.docx) para:
    - ESTUDIO_PREVIO
    - MINUTA
    - ACTA_INICIO
    El sistema pasará a utilizar dicho modelo de forma inmediata en todas las generaciones.
    """
    norm_type = template_type.upper().strip()
    valid_exts = (".docx", ".doc", ".docm", ".dotx")
    if not file.filename or not any(file.filename.lower().endswith(ext) for ext in valid_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se admiten documentos de Microsoft Word en formato .docx o .doc."
        )

    try:
        content = await file.read()
        res = save_custom_template(norm_type, content, file.filename)
        return {
            "mensaje": f"Plantilla personalizada para '{norm_type}' cargada y activada exitosamente.",
            "detalle": res
        }
    except Exception as e:
        logger.error(f"Error cargando plantilla personalizada: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se pudo procesar la plantilla Word: {str(e)}"
        )
    finally:
        await file.close()

@router.post("/reset/{template_type}")
def reset_template(
    template_type: str,
    current_user: Usuario = Depends(require_admin)
):
    """Restablece la plantilla especificada al modelo oficial corporativo por defecto."""
    norm_type = template_type.upper().strip()
    try:
        reset_custom_template(norm_type)
        return {
            "mensaje": f"Plantilla '{norm_type}' restablecida al modelo oficial por defecto.",
            "detalle": get_template_status(norm_type)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/download-active/{template_type}")
def download_active_template(template_type: str):
    """Descarga el archivo de plantilla Word (.docx) que se encuentra activo actualmente."""
    norm_type = template_type.upper().strip()
    try:
        path, is_custom = get_active_template_path(norm_type)
        return FileResponse(
            path=str(path),
            filename=path.name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró la plantilla para {template_type}: {str(e)}"
        )

@router.post("/generate/{contract_id}/{template_type}")
def generate_document(
    contract_id: int, 
    template_type: str, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """
    Genera el documento Word (.docx) para el contrato especificado a partir de la plantilla modelo,
    preservando tipografía, tablas, márgenes y membretes oficiales de la ESP.
    template_type: 'ESTUDIO_PREVIO', 'MINUTA', 'ACTA_INICIO'.
    """
    norm_type = template_type.upper().strip()
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    try:
        output_path = generate_docx_for_contract(contrato, norm_type, db_session=db)
        
        # Registrar auditoría
        audit = Auditoria(
            contrato_id=contrato.id,
            accion="GENERACION_DOCX",
            usuario=current_user.nombre_completo or current_user.username,
            usuario_documento=current_user.documento,
            usuario_nombre=current_user.nombre_completo or current_user.username
        )
        db.add(audit)
        db.commit()

        return {
            "mensaje": f"Documento Word generado exitosamente para {norm_type}.",
            "archivo_nombre": output_path.name,
            "tamano_bytes": output_path.stat().st_size,
            "download_url": f"/api/templates/download/{contract_id}/{norm_type}"
        }
    except Exception as e:
        logger.error(f"Error generando documento Word: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando el documento Word: {str(e)}"
        )

@router.get("/download/{contract_id}/{template_type}")
def download_generated_document(
    contract_id: int, 
    template_type: str, 
    db: Session = Depends(get_db)
):
    """Descarga el documento Word (.docx) generado para el contrato."""
    norm_type = template_type.upper().strip()
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    # Generar o recuperar documento
    try:
        output_path = generate_docx_for_contract(contrato, norm_type, db_session=db)
        return FileResponse(
            path=str(output_path),
            filename=output_path.name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"No se pudo descargar el documento: {str(e)}"
        )
