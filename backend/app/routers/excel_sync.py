"""Master Excel synchronization and download router."""
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.contract import Contrato
from app.models.audit_log import Auditoria
from app.services.excel_engine import (
    sync_contract_to_master_excel, 
    sync_all_contracts_to_master_excel,
    delete_contract_from_master_excel,
    get_or_create_master_workbook,
    generate_filtered_excel
)
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario

router = APIRouter(prefix="/excel", tags=["Sincronización Matriz Excel"])

@router.post("/sync/{contract_id}")
def sync_contract(
    contract_id: int, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """Sincroniza un contrato específico en la Matriz Maestra de Excel."""
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    try:
        result = sync_contract_to_master_excel(contrato)

        # Registrar auditoría
        audit = Auditoria(
            contrato_id=contrato.id,
            accion="SYNC_EXCEL",
            detalle=f"Contrato {contrato.numero_contrato} sincronizado en Matriz Excel ({result['accion']} en Fila {result['fila_excel']}).",
            usuario=current_user.nombre_completo or current_user.username,
            usuario_documento=current_user.documento,
            usuario_nombre=current_user.nombre_completo or current_user.username
        )
        db.add(audit)
        db.commit()

        return {
            "mensaje": f"Contrato {contrato.numero_contrato} sincronizado exitosamente.",
            "resultado": result,
            "download_url": "/api/excel/download"
        }
    except Exception as e:
        logger.error(f"Error sincronizando contrato en Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la sincronización con Excel: {str(e)}"
        )

@router.delete("/contract/{contract_id}")
def delete_contract_from_excel_endpoint(
    contract_id: int, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """Elimina la fila de un contrato en la Matriz Maestra de Excel sin borrarlo de la base de datos."""
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    try:
        result = delete_contract_from_master_excel(contrato.numero_contrato)
        if not result.get("eliminado"):
            return {
                "mensaje": f"El contrato {contrato.numero_contrato} no estaba presente en la Matriz Excel.",
                "resultado": result
            }

        # Registrar auditoría
        audit = Auditoria(
            contrato_id=contrato.id,
            accion="DELETE_FROM_EXCEL",
            detalle=f"Contrato {contrato.numero_contrato} eliminado de la Matriz Excel (Fila anterior {result.get('fila_eliminada')}).",
            usuario=current_user.nombre_completo or current_user.username,
            usuario_documento=current_user.documento,
            usuario_nombre=current_user.nombre_completo or current_user.username
        )
        db.add(audit)
        db.commit()

        return {
            "mensaje": f"Contrato {contrato.numero_contrato} eliminado de la Matriz Excel exitosamente.",
            "resultado": result,
            "download_url": "/api/excel/download"
        }
    except Exception as e:
        logger.error(f"Error eliminando contrato de Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al eliminar contrato de Excel: {str(e)}"
        )

@router.post("/sync-all")
def sync_all_contracts(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """Sincroniza todos los contratos existentes hacia la Matriz Maestra de Excel."""
    try:
        summary = sync_all_contracts_to_master_excel(db)
        return {
            "mensaje": f"Se sincronizaron {summary['total_sincronizados']} contratos con el libro maestro.",
            "resumen": summary,
            "download_url": "/api/excel/download"
        }
    except Exception as e:
        logger.error(f"Error sincronizando todos los contratos en Excel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en sincronización masiva con Excel: {str(e)}"
        )

@router.get("/download")
def download_master_excel(
    vigencia: Optional[int] = Query(None, description="Filtrar por vigencia fiscal específica (ej: 2026, 2027)"),
    db: Session = Depends(get_db)
):
    """Descarga el archivo físico de la Matriz de Contratación en Excel (.xlsx), ya sea completo o por vigencia."""
    if vigencia:
        try:
            path = generate_filtered_excel(vigencia, db)
            return FileResponse(
                path=str(path),
                filename=f"Matriz_Contratacion_Vigencia_{vigencia}_ESP.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            logger.error(f"Error generando Excel para vigencia {vigencia}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generando archivo Excel para la vigencia {vigencia}: {str(e)}"
            )

    get_or_create_master_workbook()

    if not settings.MASTER_EXCEL_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo maestro de Excel no existe."
        )

    return FileResponse(
        path=str(settings.MASTER_EXCEL_PATH),
        filename="Matriz_Contratacion_Maestra_ESP.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
