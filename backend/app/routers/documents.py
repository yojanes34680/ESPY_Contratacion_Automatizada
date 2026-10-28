"""Document management and upload endpoints router."""
import uuid
import os
import shutil
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.document import Documento, TipoDocumento, CategoriaDocumento
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.audit_log import Auditoria
from app.schemas.document import DocumentoRead, DocumentoUploadResponse
from app.services.document_parser import parse_document_text
from app.services.rut_parser import parse_dian_rut
from app.services.contractor_enrichment import enrich_contractor
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario

router = APIRouter(prefix="/documents", tags=["Documentos"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".png", ".jpg", ".jpeg"}

@router.post("/upload", response_model=DocumentoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    contrato_id: Optional[int] = Form(None),
    contratista_id: Optional[int] = Form(None),
    tipo_documento: TipoDocumento = Form(TipoDocumento.OTRO),
    categoria: CategoriaDocumento = Form(CategoriaDocumento.SOPORTE_CONTRATISTA),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """
    Recibe y almacena un documento soporte (PDF, Word, etc.), asociándolo a un contrato o contratista.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo inválido."
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no permitido ({file_ext}). Formatos soportados: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Validar que si se indicó contrato_id o contratista_id, existan
    if contrato_id:
        contract = db.query(Contrato).filter(Contrato.id == contrato_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contrato con ID {contrato_id} no existe."
            )
        if not contratista_id and contract.contratista_id:
            contratista_id = contract.contratista_id

    if contratista_id:
        contractor = db.query(Contratista).filter(Contratista.id == contratista_id).first()
        if not contractor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contratista con ID {contratista_id} no existe."
            )

    # Generar nombre único y almacenar
    unique_prefix = uuid.uuid4().hex[:10]
    safe_filename = f"{unique_prefix}_{Path(file.filename).name}"
    target_path = settings.UPLOADS_DIR / safe_filename

    # Guardar en disco
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(target_path)
    except Exception as e:
        logger.error(f"Error al guardar archivo en disco: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando el archivo en disco: {str(e)}"
        )
    finally:
        await file.close()

    # Registro en base de datos
    try:
        relative_path = str(target_path.relative_to(settings.BASE_DIR))
    except ValueError:
        relative_path = str(target_path.relative_to(settings.STORAGE_DIR.parent))
    db_doc = Documento(

        contrato_id=contrato_id,
        contratista_id=contratista_id,
        tipo_documento=tipo_documento,
        categoria=categoria,
        nombre_archivo_original=file.filename,
        nombre_archivo_almacenado=safe_filename,
        ruta_relativa=relative_path,
        mime_type=file.content_type,
        tamano_bytes=file_size,
        datos_extraidos_json={}
    )
    db.add(db_doc)
    db.flush()

    # Auto-enriquecimiento no destructivo de contratista si está vinculado y es PDF/Word
    enriched_fields = []
    if contratista_id and file_ext in (".pdf", ".docx", ".doc"):
        try:
            raw_text = parse_document_text(target_path)
            if raw_text and len(raw_text.strip()) > 20:
                rut_data = parse_dian_rut(raw_text)
                contractor_obj = db.query(Contratista).filter(Contratista.id == contratista_id).first()
                if contractor_obj and rut_data:
                    enr_res = enrich_contractor(contractor_obj, rut_data, db, source_desc=f"Documento '{file.filename}'")
                    enriched_fields = enr_res.get("campos_actualizados", [])
                    db_doc.datos_extraidos_json = rut_data
        except Exception as e_enr:
            logger.warning(f"Aviso en enriquecimiento automático durante carga: {e_enr}")

    # Registro de auditoría
    if contrato_id:
        audit = Auditoria(
            contrato_id=contrato_id,
            accion="CARGA_DOCUMENTO",
            detalle=f"Archivo '{file.filename}' cargado como {tipo_documento.value} ({file_size} bytes).",
            usuario=_user.nombre_completo or _user.username,
            usuario_documento=_user.documento,
            usuario_nombre=_user.nombre_completo or _user.username
        )
        db.add(audit)

    db.commit()
    db.refresh(db_doc)
    logger.info(f"Documento subido con éxito: ID {db_doc.id} - {db_doc.nombre_archivo_original}")

    msg = "Archivo cargado y registrado satisfactoriamente."
    if enriched_fields:
        msg += f" Se actualizaron campos del contratista: {', '.join(enriched_fields)}."

    return DocumentoUploadResponse(
        id=db_doc.id,
        nombre_archivo_original=db_doc.nombre_archivo_original,
        tipo_documento=db_doc.tipo_documento,
        categoria=db_doc.categoria,
        tamano_bytes=db_doc.tamano_bytes,
        mensaje=msg,
        datos_extraidos_preliminares={"extension": file_ext, "storage_path": relative_path, "campos_enriquecidos": enriched_fields}
    )

@router.post("/upload-multiple", response_model=List[DocumentoUploadResponse], status_code=status.HTTP_201_CREATED)
async def upload_multiple_documents(
    files: List[UploadFile] = File(...),
    contrato_id: Optional[int] = Form(None),
    contratista_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """
    Recibe y almacena hasta 8 documentos soporte simultáneamente (Cédula, RUT, Cotización, Certificados, etc.).
    """
    if not files or len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se ha seleccionado ningún archivo."
        )

    if len(files) > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Se superó el límite máximo de 8 documentos simultáneos (se recibieron {len(files)} archivos)."
        )

    responses = []
    for file in files:
        if not file.filename:
            continue
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            continue

        unique_prefix = uuid.uuid4().hex[:10]
        safe_filename = f"{unique_prefix}_{Path(file.filename).name}"
        target_path = settings.UPLOADS_DIR / safe_filename

        try:
            with open(target_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_size = os.path.getsize(target_path)
        except Exception as e:
            logger.error(f"Error guardando {file.filename}: {e}")
            continue
        finally:
            await file.close()

        try:
            relative_path = str(target_path.relative_to(settings.BASE_DIR))
        except ValueError:
            relative_path = str(target_path.relative_to(settings.STORAGE_DIR.parent))
        
        # Detección inicial de tipo según nombre

        fn_upper = file.filename.upper()
        if "RUT" in fn_upper:
            detected_tipo = TipoDocumento.RUT
        elif "CEDULA" in fn_upper or "C.C" in fn_upper or "IDENTIFICACION" in fn_upper:
            detected_tipo = TipoDocumento.CEDULA
        elif "PROPUESTA" in fn_upper or "COTIZACION" in fn_upper or "OFERTA" in fn_upper:
            detected_tipo = TipoDocumento.PROPUESTA
        elif "ANTECEDENTE" in fn_upper:
            detected_tipo = TipoDocumento.ANTECEDENTES
        else:
            detected_tipo = TipoDocumento.OTRO

        db_doc = Documento(
            contrato_id=contrato_id,
            contratista_id=contratista_id,
            tipo_documento=detected_tipo,
            categoria=CategoriaDocumento.SOPORTE_CONTRATISTA,
            nombre_archivo_original=file.filename,
            nombre_archivo_almacenado=safe_filename,
            ruta_relativa=relative_path,
            mime_type=file.content_type,
            tamano_bytes=file_size,
            datos_extraidos_json={}
        )
        db.add(db_doc)
        db.flush()

        # Auto-enriquecimiento no destructivo si está asociado a contratista
        enriched_fields = []
        if contratista_id and file_ext in (".pdf", ".docx", ".doc"):
            try:
                raw_text = parse_document_text(target_path)
                if raw_text and len(raw_text.strip()) > 20:
                    rut_data = parse_dian_rut(raw_text)
                    contractor_obj = db.query(Contratista).filter(Contratista.id == contratista_id).first()
                    if contractor_obj and rut_data:
                        enr_res = enrich_contractor(contractor_obj, rut_data, db, source_desc=f"Documento lote '{file.filename}'")
                        enriched_fields = enr_res.get("campos_actualizados", [])
                        db_doc.datos_extraidos_json = rut_data
            except Exception as e_enr:
                logger.warning(f"Aviso en enriquecimiento automático en lote: {e_enr}")

        msg = "Archivo cargado y registrado satisfactoriamente."
        if enriched_fields:
            msg += f" Se actualizaron campos del contratista: {', '.join(enriched_fields)}."

        responses.append(DocumentoUploadResponse(
            id=db_doc.id,
            nombre_archivo_original=db_doc.nombre_archivo_original,
            tipo_documento=db_doc.tipo_documento,
            categoria=db_doc.categoria,
            tamano_bytes=db_doc.tamano_bytes,
            mensaje=msg,
            datos_extraidos_preliminares={"extension": file_ext, "storage_path": relative_path, "campos_enriquecidos": enriched_fields}
        ))

    db.commit()
    logger.info(f"Lote de {len(responses)} documentos procesado y almacenado.")
    return responses

@router.get("", response_model=List[DocumentoRead])
def list_documents(
    contrato_id: Optional[int] = None,
    contratista_id: Optional[int] = None,
    tipo_documento: Optional[TipoDocumento] = None,
    categoria: Optional[CategoriaDocumento] = None,
    db: Session = Depends(get_db)
):
    """Lista documentos filtrados por contrato, contratista o tipo."""
    q = db.query(Documento)
    if contrato_id:
        q = q.filter(Documento.contrato_id == contrato_id)
    if contratista_id:
        q = q.filter(Documento.contratista_id == contratista_id)
    if tipo_documento:
        q = q.filter(Documento.tipo_documento == tipo_documento)
    if categoria:
        q = q.filter(Documento.categoria == categoria)

    return q.order_by(Documento.id.desc()).all()

@router.get("/{document_id}", response_model=DocumentoRead)
def get_document(document_id: int, db: Session = Depends(get_db)):
    """Obtiene los metadatos de un documento por su ID."""
    doc = db.query(Documento).filter(Documento.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado."
        )
    return doc

@router.get("/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    """Descarga el archivo físico de un documento almacenado."""
    doc = db.query(Documento).filter(Documento.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado."
        )

    full_path = settings.BASE_DIR / doc.ruta_relativa
    if not full_path.exists():
        alt_path = settings.STORAGE_DIR.parent / doc.ruta_relativa
        if alt_path.exists():
            full_path = alt_path
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El archivo físico no se encuentra en la ruta esperada."
            )


    return FileResponse(
        path=str(full_path),
        filename=doc.nombre_archivo_original,
        media_type=doc.mime_type or "application/octet-stream"
    )

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int, 
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """Elimina el registro de un documento y su archivo físico asociado."""
    doc = db.query(Documento).filter(Documento.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado."
        )

    # Eliminar archivo físico si existe
    try:
        full_path = settings.BASE_DIR / doc.ruta_relativa
        if full_path.exists():
            os.remove(full_path)
    except Exception as e:
        logger.warning(f"No se pudo eliminar el archivo físico {doc.ruta_relativa}: {e}")

    db.delete(doc)
    db.commit()
    logger.info(f"Documento ID {document_id} eliminado.")
    return None
