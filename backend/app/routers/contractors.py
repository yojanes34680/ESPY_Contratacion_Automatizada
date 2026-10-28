import uuid
import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from app.database import get_db
from app.config import settings
from app.models.contractor import Contratista, TipoPersona, TipoDocumento, RegimenTributario
from app.models.document import Documento, TipoDocumento as ModelTipoDoc, CategoriaDocumento
from app.schemas.contractor import ContratistaCreate, ContratistaRead, ContratistaUpdate
from app.services.document_parser import parse_document_text
from app.services.rut_parser import parse_dian_rut, calculate_dian_dv
from app.services.gemini_client import gemini_service
from app.services.contractor_enrichment import (
    get_missing_contractor_fields,
    enrich_contractor,
    extract_and_enrich_from_docs
)
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario

router = APIRouter(prefix="/contractors", tags=["Contratistas"])

class ContractorEnrichmentRequest(BaseModel):
    document_ids: List[int] = []
    manual_data: Optional[Dict[str, Any]] = None


@router.post("/parse-rut")
async def parse_rut_endpoint(
    file: UploadFile = File(...),
    _user: Usuario = Depends(require_editor)
):
    """
    Analiza un archivo RUT DIAN (PDF, Word o imagen) y extrae sus datos tributarios,
    de identidad, ubicación, contacto y representación legal.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo inválido.")

    unique_prefix = uuid.uuid4().hex[:10]
    safe_name = f"temp_rut_{unique_prefix}_{Path(file.filename).name}"
    temp_path = settings.UPLOADS_DIR / safe_name
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        raw_text = parse_document_text(temp_path)
        if not raw_text or len(raw_text.strip()) < 10:
            raise HTTPException(status_code=400, detail="No se pudo extraer texto legible del archivo RUT.")

        # 1. Parseo determinista DIAN Formulario 001
        rut_data = parse_dian_rut(raw_text)

        # 2. Enriquecimiento con IA si está disponible
        try:
            ai_data = gemini_service.extract_contractor_data(raw_text)
            ai_dict = ai_data.model_dump()
            for k, v in ai_dict.items():
                if v and not rut_data.get(k):
                    rut_data[k] = v
        except Exception as e_ai:
            logger.debug(f"Aviso en análisis IA de RUT: {e_ai}")

        # Normalización estricta Persona Natural vs Empresa
        tipo_persona = rut_data.get("tipo_persona", "NATURAL")
        if tipo_persona == "NATURAL":
            if rut_data.get("numero_documento"):
                import re
                rut_data["numero_documento"] = re.sub(r"-\d+$", "", str(rut_data["numero_documento"])).strip()
            rut_data["digito_verificacion"] = None
            rut_data["representante_legal_nombre"] = None
            rut_data["representante_legal_documento"] = None
            rut_data["tipo_documento"] = "CC"
        else:
            rut_data["tipo_persona"] = "JURIDICA"
            rut_data["tipo_documento"] = "NIT"
            if rut_data.get("numero_documento") and not rut_data.get("digito_verificacion"):
                rut_data["digito_verificacion"] = calculate_dian_dv(rut_data["numero_documento"])
            if rut_data.get("representante_legal_documento"):
                import re
                rut_data["representante_legal_documento"] = re.sub(r"-\d+$", "", str(rut_data["representante_legal_documento"])).strip()

        return {
            "status": "success",
            "filename": file.filename,
            "data": rut_data
        }
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


@router.post("/{contractor_id}/update-from-rut")
async def update_contractor_from_rut_endpoint(
    contractor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """
    Actualiza la información de un contratista (especialmente si es empresa) directamente
    a partir del archivo RUT DIAN adjunto. Asocia el archivo al expediente del contratista.
    """
    contractor = db.query(Contratista).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(status_code=404, detail=f"Contratista con ID {contractor_id} no encontrado.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo inválido.")

    unique_prefix = uuid.uuid4().hex[:10]
    safe_name = f"rut_{unique_prefix}_{Path(file.filename).name}"
    target_path = settings.UPLOADS_DIR / safe_name
    settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(target_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando archivo: {e}")

    # Registrar documento en BD
    relative_path = str(target_path.relative_to(settings.BASE_DIR))
    db_doc = Documento(
        contratista_id=contractor_id,
        tipo_documento=ModelTipoDoc.RUT,
        categoria=CategoriaDocumento.SOPORTE_CONTRATISTA,
        nombre_archivo_original=file.filename,
        nombre_archivo_almacenado=safe_name,
        ruta_relativa=relative_path,
        mime_type=file.content_type,
        tamano_bytes=file_size,
        datos_extraidos_json={}
    )
    db.add(db_doc)
    db.flush()

    raw_text = parse_document_text(target_path)
    rut_data = parse_dian_rut(raw_text) if raw_text else {}

    try:
        if raw_text:
            ai_data = gemini_service.extract_contractor_data(raw_text)
            ai_dict = ai_data.model_dump()
            for k, v in ai_dict.items():
                if v and not rut_data.get(k):
                    rut_data[k] = v
    except Exception as e_ai:
        logger.debug(f"Aviso en análisis IA de RUT: {e_ai}")

    db_doc.datos_extraidos_json = rut_data

    # Enriquecer y actualizar el contratista
    enr_res = enrich_contractor(contractor, rut_data, db, source_desc=f"RUT Oficial '{file.filename}'")

    db.commit()
    refreshed = db.query(Contratista).options(
        joinedload(Contratista.contratos),
        joinedload(Contratista.documentos)
    ).filter(Contratista.id == contractor_id).first()

    return {
        "status": "success",
        "contractor": ContratistaRead.model_validate(refreshed),
        "document_id": db_doc.id,
        "campos_actualizados": enr_res.get("campos_actualizados", []),
        "extracted_data": rut_data
    }


@router.post("", response_model=ContratistaRead, status_code=status.HTTP_201_CREATED)
def create_contractor(
    contractor_in: ContratistaCreate, 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Registra un nuevo contratista en el sistema."""
    # Verificar unicidad de número de documento
    existing = db.query(Contratista).filter(
        Contratista.numero_documento == contractor_in.numero_documento
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un contratista registrado con el documento {contractor_in.numero_documento}."
        )

    db_obj = Contratista(**contractor_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    logger.info(f"Contratista creado: ID {db_obj.id} - {db_obj.nombre_o_razon_social}")
    return db_obj

@router.get("", response_model=List[ContratistaRead])
def list_contractors(
    query: Optional[str] = Query(None, description="Buscar por nombre, número de documento, representante o correo"),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """Lista contratistas registrados con paginación, búsqueda, contratos celebrados y documentos soporte."""
    q = db.query(Contratista).options(
        joinedload(Contratista.contratos),
        joinedload(Contratista.documentos)
    )
    if query:
        search = f"%{query.strip()}%"
        q = q.filter(
            or_(
                Contratista.nombre_o_razon_social.ilike(search),
                Contratista.nombre_comercial.ilike(search),
                Contratista.numero_documento.ilike(search),
                Contratista.representante_legal_nombre.ilike(search),
                Contratista.correo_electronico.ilike(search),
                Contratista.municipio.ilike(search),
                Contratista.departamento.ilike(search)
            )
        )
    return q.order_by(Contratista.nombre_o_razon_social.asc()).offset(skip).limit(limit).all()

@router.get("/{contractor_id}", response_model=ContratistaRead)
def get_contractor(contractor_id: int, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de un contratista por ID incluyendo contratos y documentos."""
    contractor = db.query(Contratista).options(
        joinedload(Contratista.contratos),
        joinedload(Contratista.documentos)
    ).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contratista con ID {contractor_id} no encontrado."
        )
    return contractor

@router.put("/{contractor_id}", response_model=ContratistaRead)
def update_contractor(
    contractor_id: int, 
    update_data: ContratistaUpdate, 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Actualiza la información de un contratista."""
    contractor = db.query(Contratista).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contratista con ID {contractor_id} no encontrado."
        )

    # Validar unicidad de documento si fue modificado
    if update_data.numero_documento and update_data.numero_documento != contractor.numero_documento:
        duplicate = db.query(Contratista).filter(
            Contratista.numero_documento == update_data.numero_documento
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El documento {update_data.numero_documento} ya pertenece a otro contratista."
            )

    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(contractor, key, value)

    db.commit()
    db.refresh(contractor)
    logger.info(f"Contratista ID {contractor_id} actualizado exitosamente.")
    return contractor

@router.get("/{contractor_id}/missing-fields")
def get_contractor_missing_fields_endpoint(contractor_id: int, db: Session = Depends(get_db)):
    """Evalúa y lista los campos esenciales faltantes o desactualizados del contratista."""
    contractor = db.query(Contratista).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contratista con ID {contractor_id} no encontrado."
        )
    missing = get_missing_contractor_fields(contractor)
    return {
        "contractor_id": contractor_id,
        "nombre_o_razon_social": contractor.nombre_o_razon_social,
        "numero_documento": contractor.numero_documento,
        "missing_fields": missing,
        "total_missing": len(missing),
        "is_complete": len(missing) == 0
    }

@router.post("/{contractor_id}/enrich-from-docs")
def enrich_contractor_from_docs_endpoint(
    contractor_id: int, 
    payload: ContractorEnrichmentRequest, 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """
    Enriquece y actualiza de manera no destructiva la información faltante del contratista
    a partir de documentos soporte (RUT, propuesta, certificados) o datos manuales verificados.
    """
    contractor = db.query(Contratista).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contratista con ID {contractor_id} no encontrado."
        )

    result = extract_and_enrich_from_docs(
        contractor=contractor,
        document_ids=payload.document_ids or [],
        db=db,
        manual_data=payload.manual_data
    )

    # Devolver contratista refrescado y el resumen de enriquecimiento
    refreshed_contractor = db.query(Contratista).options(
        joinedload(Contratista.contratos),
        joinedload(Contratista.documentos)
    ).filter(Contratista.id == contractor_id).first()

    return {
        "status": "success",
        "contractor": ContratistaRead.model_validate(refreshed_contractor),
        "enrichment_summary": result
    }

@router.patch("/{contractor_id}/deactivate")
def deactivate_contractor(
    contractor_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """Desactiva un contratista que posee contratos asociados en el sistema."""
    contractor = db.query(Contratista).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contratista con ID {contractor_id} no encontrado."
        )

    contractor.activo = False
    db.commit()
    db.refresh(contractor)
    logger.info(f"Contratista ID {contractor_id} ('{contractor.nombre_o_razon_social}') desactivado exitosamente.")
    return {
        "status": "success",
        "mensaje": f"Contratista '{contractor.nombre_o_razon_social}' desactivado exitosamente.",
        "contractor_id": contractor_id,
        "activo": contractor.activo
    }

@router.delete("/{contractor_id}")
def delete_contractor(
    contractor_id: int, 
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """
    Elimina físicamente un contratista ÚNICAMENTE si no tiene contratos asociados.
    Si tiene contratos celebrados o registrados, está prohibido borrarlo (debe desactivarse).
    """
    contractor = db.query(Contratista).options(
        joinedload(Contratista.contratos),
        joinedload(Contratista.documentos)
    ).filter(Contratista.id == contractor_id).first()

    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contratista con ID {contractor_id} no encontrado."
        )

    contractor_name = contractor.nombre_o_razon_social
    num_contratos = len(contractor.contratos or [])

    if num_contratos > 0:
        codigos = [c.numero_contrato for c in contractor.contratos if c.numero_contrato]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No se puede eliminar al contratista '{contractor_name}' porque tiene {num_contratos} "
                f"contrato(s) registrado(s): {', '.join(codigos)}. Para preservar la trazabilidad jurídica "
                f"e histórica de la contratación pública, debe usar la opción de Desactivar Contratista."
            )
        )

    from app.config import settings

    # Limpiar documentos huérfanos o directos del contratista
    for doc in (contractor.documentos or []):
        rel_path = getattr(doc, "ruta_relativa", None)
        if rel_path:
            full_path = settings.BASE_DIR / rel_path
            if full_path.exists():
                try:
                    full_path.unlink()
                except Exception:
                    pass
        db.delete(doc)

    db.delete(contractor)
    db.commit()
    logger.info(f"Contratista ID {contractor_id} ('{contractor_name}') eliminado exitosamente.")
    return {
        "status": "success",
        "mensaje": f"Contratista '{contractor_name}' eliminado exitosamente.",
        "contractor_id": contractor_id
    }
