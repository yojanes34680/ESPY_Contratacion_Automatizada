"""API Router for Contract Additions (Adiciones Contractuales)."""
import os
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.config import settings
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.contract_addition import AdicionContrato
from app.models.document import Documento, TipoDocumento, CategoriaDocumento
from app.services.document_parser import parse_document_text
from app.services.gemini_client import gemini_service
from app.services.agents.addition_agent import addition_agent
from app.services.docx_engine import generate_adicion_docx
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario

router = APIRouter(prefix="/additions", tags=["Adiciones a Contratos"])

# -------------------------------------------------------------
# Schemas
# -------------------------------------------------------------
class GenerateJustificationRequest(BaseModel):
    contrato_id: Optional[int] = None
    valor_adicion: Optional[float] = None
    necesidad_usuario: Optional[str] = None
    razon_tecnica: Optional[str] = None
    tipo_contrato: Optional[str] = None
    objeto_contrato: Optional[str] = None
    override_api_key: Optional[str] = None

class CreateAdditionRequest(BaseModel):
    contrato_id: int
    numero_adicion: Optional[int] = None
    valor_adicion: float = Field(..., gt=0, description="Monto a adicionar en pesos COP")
    justificacion: str = Field(..., description="Justificación técnica y operativa de la adición")
    cdp_numero: Optional[str] = None
    cdp_fecha: Optional[str] = None
    cdp_rubro: Optional[str] = None
    cdp_rubro_nombre: Optional[str] = None
    cdp_valor: Optional[float] = None
    cdp_documento_id: Optional[int] = None
    representante_legal_nombre: Optional[str] = None
    representante_legal_documento: Optional[str] = None
    guardar_en_contratista: bool = False
    fecha_adicion: Optional[str] = None

class UpdateAdditionRequest(BaseModel):
    valor_adicion: Optional[float] = Field(None, gt=0, description="Monto a adicionar en pesos COP")
    justificacion: Optional[str] = Field(None, description="Justificación técnica y operativa de la adición")
    cdp_numero: Optional[str] = None
    cdp_fecha: Optional[str] = None
    cdp_rubro: Optional[str] = None
    cdp_rubro_nombre: Optional[str] = None
    cdp_valor: Optional[float] = None
    cdp_documento_id: Optional[int] = None
    representante_legal_nombre: Optional[str] = None
    representante_legal_documento: Optional[str] = None
    guardar_en_contratista: bool = False
    fecha_adicion: Optional[str] = None

# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------

@router.get("/contracts-list")
def get_contracts_for_addition(db: Session = Depends(get_db)):
    """
    Retorna la lista de contratos activos de la empresa para selección en el modal de adiciones.
    """
    contracts = db.query(Contrato).options(joinedload(Contrato.contratista)).all()
    result = []
    for c in contracts:
        c_dict = {
            "id": c.id,
            "numero_contrato": c.numero_contrato,
            "tipologia": c.tipologia.value if hasattr(c.tipologia, 'value') else str(c.tipologia),
            "objeto": c.objeto,
            "valor_inicial": c.valor_inicial or c.valor_total,
            "adicion_1": c.adicion_1 or 0.0,
            "valor_total": c.valor_total,
            "contratista_id": c.contratista_id,
            "contratista_nombre": c.contratista.nombre_o_razon_social if c.contratista else "Sin asignar",
            "contratista_documento": c.contratista.numero_documento if c.contratista else "",
            "tipo_persona": c.contratista.tipo_persona.value if (c.contratista and hasattr(c.contratista.tipo_persona, 'value')) else "NATURAL",
            "representante_legal_nombre": c.contratista.representante_legal_nombre if c.contratista else None,
            "representante_legal_documento": c.contratista.representante_legal_documento if c.contratista else None,
        }
        result.append(c_dict)
    
    # Ordenar por consecutivo numérico si es posible
    def get_num(item):
        import re
        m = re.search(r"(\d+)", item["numero_contrato"])
        return int(m.group(1)) if m else 0
    
    result.sort(key=get_num, reverse=True)
    return result


@router.get("/contract-context/{contract_id}")
def get_contract_addition_context(contract_id: int, db: Session = Depends(get_db)):
    """
    Retorna el contexto exhaustivo de un contrato para estructurar su adición:
    valores vigentes, adiciones previas acumuladas, datos del contratista y representante legal.
    """
    contrato = db.query(Contrato).options(
        joinedload(Contrato.contratista),
        joinedload(Contrato.adiciones)
    ).filter(Contrato.id == contract_id).first()

    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    # Conteo de adiciones previas
    num_adiciones_previas = len(contrato.adiciones) if contrato.adiciones else (1 if (contrato.adicion_1 and contrato.adicion_1 > 0) else 0)
    siguiente_numero = num_adiciones_previas + 1

    c = contrato.contratista
    return {
        "contrato_id": contrato.id,
        "numero_contrato": contrato.numero_contrato,
        "tipologia": contrato.tipologia.value if hasattr(contrato.tipologia, 'value') else str(contrato.tipologia),
        "objeto": contrato.objeto,
        "valor_inicial": contrato.valor_inicial if contrato.valor_inicial is not None else (contrato.valor_total - (contrato.adicion_1 or 0.0)),
        "adiciones_acumuladas": contrato.adicion_1 or 0.0,
        "valor_total_actual": contrato.valor_total,
        "siguiente_numero_adicion": siguiente_numero,
        "contratista": {
            "id": c.id if c else None,
            "nombre_o_razon_social": c.nombre_o_razon_social if c else "",
            "tipo_persona": c.tipo_persona.value if (c and hasattr(c.tipo_persona, 'value')) else "NATURAL",
            "numero_documento": c.numero_documento if c else "",
            "digito_verificacion": c.digito_verificacion if c else None,
            "representante_legal_nombre": c.representante_legal_nombre if c else "",
            "representante_legal_documento": c.representante_legal_documento if c else "",
            "direccion": c.direccion if c else "",
            "municipio": c.municipio if c else "",
            "telefono": c.telefono if c else ""
        }
    }


@router.post("/upload-cdp")
async def upload_addition_cdp(
    file: UploadFile = File(...),
    contrato_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """
    Carga el Certificado de Disponibilidad Presupuestal (CDP) de la adición (PDF/Word/Imagen)
    y ejecuta extracción inteligente/OCR para devolver el número de CDP, fecha, rubro y valor.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo no válido.")

    ext = Path(file.filename).suffix.lower()
    if ext not in [".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg"]:
        raise HTTPException(status_code=400, detail="Formato no soportado. Cargue un PDF, Word o imagen.")

    # Guardar archivo en disco
    unique_id = uuid.uuid4().hex[:10]
    safe_name = f"cdp_adicion_{unique_id}_{file.filename.replace(' ', '_')}"
    dest_path = settings.UPLOADS_DIR / safe_name

    content = await file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    # Registrar en tabla Documentos
    rel_path = str(dest_path.relative_to(settings.BASE_DIR))
    db_doc = Documento(
        contrato_id=contrato_id,
        tipo_documento=TipoDocumento.CDP,
        categoria=CategoriaDocumento.SOPORTE_CONTRATISTA,
        nombre_archivo_original=file.filename,
        nombre_archivo_almacenado=safe_name,
        ruta_relativa=rel_path,
        mime_type=file.content_type or "application/pdf",
        tamano_bytes=len(content),
        datos_extraidos_json={}
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # Extraer texto (con OCR si es escaneado)
    try:
        raw_text = parse_document_text(dest_path)
        extracted = gemini_service.extract_contractor_data(raw_text)
        ext_dict = extracted.model_dump()
        db_doc.datos_extraidos_json = ext_dict
        db.commit()

        cdp_data = {
            "document_id": db_doc.id,
            "filename": file.filename,
            "cdp_numero": ext_dict.get("cdp_numero"),
            "cdp_fecha": ext_dict.get("cdp_fecha"),
            "cdp_rubro": ext_dict.get("cdp_rubro"),
            "cdp_rubro_nombre": ext_dict.get("cdp_rubro_nombre"),
            "cdp_valor": ext_dict.get("cdp_valor"),
            "cdp_objeto": ext_dict.get("cdp_objeto"),
            "status": "extracted"
        }
        return cdp_data
    except Exception as e:
        logger.error(f"Error extrayendo datos de CDP {file.filename}: {e}")
        return {
            "document_id": db_doc.id,
            "filename": file.filename,
            "cdp_numero": None,
            "cdp_fecha": None,
            "cdp_rubro": None,
            "cdp_rubro_nombre": None,
            "cdp_valor": None,
            "status": "partial"
        }


@router.post("/generate-justification")
def generate_addition_justification(
    payload: GenerateJustificationRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """
    Genera la redacción jurídica formal de la justificación técnica, legal y financiera
    de la adición contractual en 3 apartados obligatorios aplicando la Regla de Oro.
    """
    contrato = None
    if payload.contrato_id:
        contrato = db.query(Contrato).options(
            joinedload(Contrato.contratista)
        ).filter(Contrato.id == payload.contrato_id).first()
        if not contrato:
            raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    tipologia_str = payload.tipo_contrato or (
        (contrato.tipologia.value if hasattr(contrato.tipologia, 'value') else str(contrato.tipologia)) if contrato else ""
    )
    objeto_contrato = payload.objeto_contrato or (contrato.objeto if contrato else "")
    numero_contrato = contrato.numero_contrato if contrato else "Vigente"
    contratista_nom = (contrato.contratista.nombre_o_razon_social if contrato and contrato.contratista else None)
    val_inicial = (contrato.valor_inicial if contrato and contrato.valor_inicial is not None else (
        (contrato.valor_total - (contrato.adicion_1 or 0.0)) if contrato else None
    ))
    plazo_texto = contrato.plazo_texto if contrato else None

    valor_adicion = payload.valor_adicion or 0.0
    motivo = (payload.razon_tecnica or payload.necesidad_usuario or "").strip()

    # Validar requerimientos técnicos según la Regla de Oro
    val_res = addition_agent.validate_requirements(
        tipologia=tipologia_str,
        objeto_contrato=objeto_contrato,
        valor_adicion=valor_adicion,
        razon_tecnica=motivo
    )

    if not val_res["valid"]:
        return {
            "status": "requires_information",
            "ready": False,
            "missing_fields": val_res["missing_fields"],
            "message": "NUNCA se debe inventar la causa de la adición. Debe proporcionar la razón técnica específica.",
            "pregunta": (
                "¿Cuál es la razón técnica y específica por la que el presupuesto inicial se agotó o es insuficiente? "
                "(Ej: 'Aumentó la turbiedad del río y se necesitó más sulfato', 'Se encontraron cantidades de obra no previstas en la excavación', "
                "'Se requiere extender el servicio por 2 meses más debido a X motivo')"
            ),
            "preguntas_obligatorias": val_res["questions"],
            "inquiry_prompt": val_res["inquiry_prompt"],
            "justificacion": val_res["inquiry_prompt"]
        }

    justificacion = addition_agent.generate_justification(
        numero_contrato=numero_contrato,
        objeto_contrato=objeto_contrato,
        tipologia=tipologia_str,
        valor_adicion=valor_adicion,
        razon_tecnica=motivo,
        override_api_key=payload.override_api_key,
        valor_inicial=val_inicial,
        contratista_nombre=contratista_nom,
        plazo_texto=plazo_texto
    )
    return {
        "status": "success",
        "ready": True,
        "justificacion": justificacion
    }


@router.post("/create")
def create_contract_addition(
    payload: CreateAdditionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """
    Registra la adición contractual, actualiza el valor acumulado del contrato en la base de datos,
    actualiza el representante legal del contratista si se solicitó, y genera la minuta Word (.docx).
    """
    contrato = db.query(Contrato).options(
        joinedload(Contrato.contratista),
        joinedload(Contrato.adiciones)
    ).filter(Contrato.id == payload.contrato_id).first()

    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    val_adicion = payload.valor_adicion
    _, val_letras, _ = addition_agent.format_currency_legal(val_adicion)

    # Consecutivo de la adición
    num_adicion = payload.numero_adicion
    if not num_adicion:
        num_adicion = len(contrato.adiciones) + 1 if contrato.adiciones else 1

    # Fecha de la adición
    fecha_adicion_date = date.today()
    if payload.fecha_adicion:
        try:
            fecha_adicion_date = datetime.strptime(payload.fecha_adicion[:10], "%Y-%m-%d").date()
        except Exception:
            try:
                fecha_adicion_date = datetime.strptime(payload.fecha_adicion[:10], "%d/%m/%Y").date()
            except Exception:
                fecha_adicion_date = date.today()

    # Fecha de CDP si viene
    cdp_fecha_date = None
    if payload.cdp_fecha:
        try:
            cdp_fecha_date = datetime.strptime(payload.cdp_fecha[:10], "%Y-%m-%d").date()
        except Exception:
            try:
                cdp_fecha_date = datetime.strptime(payload.cdp_fecha[:10], "%d/%m/%Y").date()
            except Exception:
                pass

    # Datos contratista
    c = contrato.contratista
    contratista_nom = c.nombre_o_razon_social if c else "CONTRATISTA"
    contratista_doc = c.numero_documento if c else ""

    rep_nom = payload.representante_legal_nombre or (c.representante_legal_nombre if c else None)
    rep_doc = payload.representante_legal_documento or (c.representante_legal_documento if c else None)

    # Actualizar contratista si el usuario lo solicitó
    if payload.guardar_en_contratista and c:
        if payload.representante_legal_nombre:
            c.representante_legal_nombre = payload.representante_legal_nombre.strip()
        if payload.representante_legal_documento:
            c.representante_legal_documento = payload.representante_legal_documento.strip()
        db.commit()

    valor_anterior = contrato.valor_total
    valor_nuevo_total = valor_anterior + val_adicion

    # Actualizar valores en el contrato
    contrato.adicion_1 = (contrato.adicion_1 or 0.0) + val_adicion
    contrato.valor_total = valor_nuevo_total
    if not contrato.valor_inicial:
        contrato.valor_inicial = valor_anterior
    db.commit()

    # Crear registro de AdicionContrato
    nueva_adicion = AdicionContrato(
        contrato_id=contrato.id,
        numero_adicion=num_adicion,
        valor_adicion=val_adicion,
        valor_adicion_letras=val_letras,
        valor_anterior=valor_anterior,
        valor_nuevo_total=valor_nuevo_total,
        justificacion=payload.justificacion,
        cdp_numero=payload.cdp_numero,
        cdp_fecha=cdp_fecha_date,
        cdp_rubro=payload.cdp_rubro,
        cdp_rubro_nombre=payload.cdp_rubro_nombre,
        cdp_valor=payload.cdp_valor,
        contratista_nombre=contratista_nom,
        contratista_documento=contratista_doc,
        representante_legal_nombre=rep_nom,
        representante_legal_documento=rep_doc,
        fecha_adicion=fecha_adicion_date,
        documento_soporte_cdp_id=payload.cdp_documento_id
    )
    db.add(nueva_adicion)
    db.commit()
    db.refresh(nueva_adicion)

    # Generar Minuta Word (.docx) oficial idéntica a la muestra
    adicion_data = {
        "numero_adicion": num_adicion,
        "valor_adicion": val_adicion,
        "valor_anterior": valor_anterior,
        "valor_nuevo_total": valor_nuevo_total,
        "justificacion": payload.justificacion,
        "cdp_numero": payload.cdp_numero,
        "cdp_fecha": payload.cdp_fecha,
        "cdp_rubro": payload.cdp_rubro,
        "cdp_rubro_nombre": payload.cdp_rubro_nombre,
        "cdp_valor": payload.cdp_valor,
        "contratista_nombre": contratista_nom,
        "contratista_documento": contratista_doc,
        "representante_legal_nombre": rep_nom,
        "representante_legal_documento": rep_doc,
        "fecha_adicion": payload.fecha_adicion or fecha_adicion_date.isoformat()
    }

    docx_path = generate_adicion_docx(contrato, adicion_data, db_session=db)
    nueva_adicion.ruta_minuta_docx = str(docx_path.relative_to(settings.BASE_DIR))
    db.commit()

    return {
        "status": "success",
        "message": f"Adición Nro. {num_adicion} creada exitosamente.",
        "addition_id": nueva_adicion.id,
        "numero_adicion": num_adicion,
        "valor_adicion": val_adicion,
        "valor_nuevo_total": valor_nuevo_total,
        "download_url": f"/api/additions/{nueva_adicion.id}/download-docx",
        "contrato_numero": contrato.numero_contrato
    }


@router.get("/{addition_id}/download-docx")
def download_addition_docx(addition_id: int, db: Session = Depends(get_db)):
    """
    Descarga directamente el archivo Word (.docx) de la minuta de adición generada.
    """
    adicion = db.query(AdicionContrato).options(joinedload(AdicionContrato.contrato)).filter(AdicionContrato.id == addition_id).first()
    if not adicion:
        raise HTTPException(status_code=404, detail="Registro de adición no encontrado.")

    if not adicion.ruta_minuta_docx:
        # Regenerar si no existe
        contrato = adicion.contrato
        adicion_data = {
            "numero_adicion": adicion.numero_adicion,
            "valor_adicion": adicion.valor_adicion,
            "justificacion": adicion.justificacion,
            "cdp_numero": adicion.cdp_numero,
            "cdp_fecha": adicion.cdp_fecha.isoformat() if adicion.cdp_fecha else None,
            "contratista_nombre": adicion.contratista_nombre,
            "contratista_documento": adicion.contratista_documento,
            "representante_legal_nombre": adicion.representante_legal_nombre,
            "representante_legal_documento": adicion.representante_legal_documento,
            "fecha_adicion": adicion.fecha_adicion.isoformat() if adicion.fecha_adicion else None
        }
        docx_path = generate_adicion_docx(contrato, adicion_data, db_session=db)
        adicion.ruta_minuta_docx = str(docx_path.relative_to(settings.BASE_DIR))
        db.commit()
        full_path = docx_path
    else:
        full_path = settings.BASE_DIR / adicion.ruta_minuta_docx

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Archivo .docx no encontrado en el servidor.")

    download_filename = f"Minuta_Adicion_{adicion.numero_adicion}_{adicion.contrato.numero_contrato.replace('/', '-')}.docx"
    return FileResponse(
        path=full_path,
        filename=download_filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/contract/{contract_id}/list")
def list_additions_for_contract(contract_id: int, db: Session = Depends(get_db)):
    """
    Lista el histórico de todas las adiciones celebradas para un contrato específico.
    """
    additions = db.query(AdicionContrato).filter(AdicionContrato.contrato_id == contract_id).order_by(AdicionContrato.numero_adicion.asc()).all()
    res = []
    for a in additions:
        res.append({
            "id": a.id,
            "contrato_id": a.contrato_id,
            "numero_adicion": a.numero_adicion,
            "valor_adicion": a.valor_adicion,
            "valor_adicion_letras": a.valor_adicion_letras,
            "valor_anterior": a.valor_anterior,
            "valor_nuevo_total": a.valor_nuevo_total,
            "cdp_numero": a.cdp_numero,
            "cdp_fecha": a.cdp_fecha.isoformat() if a.cdp_fecha else None,
            "cdp_rubro": a.cdp_rubro,
            "cdp_rubro_nombre": a.cdp_rubro_nombre,
            "cdp_valor": a.cdp_valor,
            "contratista_nombre": a.contratista_nombre,
            "contratista_documento": a.contratista_documento,
            "representante_legal_nombre": a.representante_legal_nombre,
            "representante_legal_documento": a.representante_legal_documento,
            "fecha_adicion": a.fecha_adicion.isoformat() if a.fecha_adicion else None,
            "justificacion": a.justificacion,
            "ruta_minuta_docx": a.ruta_minuta_docx,
            "download_url": f"/api/additions/{a.id}/download-docx"
        })
    return res


@router.get("/{addition_id}")
def get_addition_detail(addition_id: int, db: Session = Depends(get_db)):
    """
    Retorna el detalle completo de una adición específica para visualización o precarga en edición.
    """
    adicion = db.query(AdicionContrato).options(
        joinedload(AdicionContrato.contrato).joinedload(Contrato.contratista)
    ).filter(AdicionContrato.id == addition_id).first()

    if not adicion:
        raise HTTPException(status_code=404, detail="Adición no encontrada.")

    return {
        "id": adicion.id,
        "contrato_id": adicion.contrato_id,
        "numero_contrato": adicion.contrato.numero_contrato if adicion.contrato else "",
        "numero_adicion": adicion.numero_adicion,
        "valor_adicion": adicion.valor_adicion,
        "valor_adicion_letras": adicion.valor_adicion_letras,
        "valor_anterior": adicion.valor_anterior,
        "valor_nuevo_total": adicion.valor_nuevo_total,
        "justificacion": adicion.justificacion,
        "cdp_numero": adicion.cdp_numero,
        "cdp_fecha": adicion.cdp_fecha.isoformat() if adicion.cdp_fecha else None,
        "cdp_rubro": adicion.cdp_rubro,
        "cdp_rubro_nombre": adicion.cdp_rubro_nombre,
        "cdp_valor": adicion.cdp_valor,
        "contratista_nombre": adicion.contratista_nombre,
        "contratista_documento": adicion.contratista_documento,
        "representante_legal_nombre": adicion.representante_legal_nombre,
        "representante_legal_documento": adicion.representante_legal_documento,
        "fecha_adicion": adicion.fecha_adicion.isoformat() if adicion.fecha_adicion else None,
        "ruta_minuta_docx": adicion.ruta_minuta_docx,
        "download_url": f"/api/additions/{adicion.id}/download-docx"
    }


@router.put("/{addition_id}")
def update_contract_addition(
    addition_id: int,
    payload: UpdateAdditionRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """
    Actualiza los datos de una adición existente, recalcula el valor del contrato si el monto cambió,
    actualiza el representante legal en la ficha del contratista si se solicita,
    y regenera la minuta Word (.docx) oficial con la plantilla vigente.
    """
    adicion = db.query(AdicionContrato).options(
        joinedload(AdicionContrato.contrato).joinedload(Contrato.contratista)
    ).filter(AdicionContrato.id == addition_id).first()

    if not adicion:
        raise HTTPException(status_code=404, detail="Adición no encontrada.")

    contrato = adicion.contrato
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato asociado no encontrado.")

    # 1. Ajuste financiero si cambió el valor de la adición
    if payload.valor_adicion is not None and payload.valor_adicion > 0:
        diferencia = payload.valor_adicion - (adicion.valor_adicion or 0.0)
        adicion.valor_adicion = payload.valor_adicion
        _, val_letras, _ = addition_agent.format_currency_legal(payload.valor_adicion)
        adicion.valor_adicion_letras = val_letras

        # Actualizar contrato
        contrato.adicion_1 = max(0.0, (contrato.adicion_1 or 0.0) + diferencia)
        contrato.valor_total = max(contrato.valor_inicial or 0.0, (contrato.valor_total or 0.0) + diferencia)
        adicion.valor_nuevo_total = contrato.valor_total
        db.commit()

    # 2. Actualizar campos de disponibilidad y justificación
    if payload.justificacion is not None:
        adicion.justificacion = payload.justificacion.strip()
    if payload.cdp_numero is not None:
        adicion.cdp_numero = payload.cdp_numero.strip()
    if payload.cdp_fecha is not None:
        try:
            adicion.cdp_fecha = datetime.strptime(payload.cdp_fecha[:10], "%Y-%m-%d").date()
        except Exception:
            pass
    if payload.cdp_rubro is not None:
        adicion.cdp_rubro = payload.cdp_rubro.strip()
    if payload.cdp_rubro_nombre is not None:
        adicion.cdp_rubro_nombre = payload.cdp_rubro_nombre.strip()
    if payload.cdp_valor is not None:
        adicion.cdp_valor = payload.cdp_valor
    if payload.cdp_documento_id is not None:
        adicion.documento_soporte_cdp_id = payload.cdp_documento_id

    # 3. Representante Legal
    if payload.representante_legal_nombre is not None:
        adicion.representante_legal_nombre = payload.representante_legal_nombre.strip()
    if payload.representante_legal_documento is not None:
        adicion.representante_legal_documento = payload.representante_legal_documento.strip()

    # Si se solicitó actualizar en el contratista permanente
    if payload.guardar_en_contratista and contrato.contratista:
        if payload.representante_legal_nombre:
            contrato.contratista.representante_legal_nombre = payload.representante_legal_nombre.strip()
        if payload.representante_legal_documento:
            contrato.contratista.representante_legal_documento = payload.representante_legal_documento.strip()

    # 4. Fecha de suscripción
    if payload.fecha_adicion:
        try:
            adicion.fecha_adicion = datetime.strptime(payload.fecha_adicion[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    db.commit()

    # 5. Regenerar la Minuta Word (.docx) oficial con la plantilla activa y etiquetas corregidas
    c = contrato.contratista
    contratista_nom = c.nombre_o_razon_social if c else (adicion.contratista_nombre or "CONTRATISTA")
    contratista_doc = c.numero_documento if c else (adicion.contratista_documento or "")
    rep_nom = adicion.representante_legal_nombre or (c.representante_legal_nombre if c else contratista_nom)
    rep_doc = adicion.representante_legal_documento or (c.representante_legal_documento if c else contratista_doc)

    adicion_data = {
        "numero_adicion": adicion.numero_adicion,
        "valor_adicion": adicion.valor_adicion,
        "valor_anterior": adicion.valor_anterior,
        "valor_nuevo_total": adicion.valor_nuevo_total,
        "justificacion": adicion.justificacion,
        "cdp_numero": adicion.cdp_numero,
        "cdp_fecha": adicion.cdp_fecha.isoformat() if adicion.cdp_fecha else None,
        "cdp_rubro": adicion.cdp_rubro,
        "cdp_rubro_nombre": adicion.cdp_rubro_nombre,
        "cdp_valor": adicion.cdp_valor,
        "contratista_nombre": contratista_nom,
        "contratista_documento": contratista_doc,
        "representante_legal_nombre": rep_nom,
        "representante_legal_documento": rep_doc,
        "fecha_adicion": adicion.fecha_adicion.isoformat() if adicion.fecha_adicion else None
    }

    try:
        docx_path = generate_adicion_docx(contrato, adicion_data, db_session=db)
        adicion.ruta_minuta_docx = str(docx_path.relative_to(settings.BASE_DIR))
        db.commit()
    except Exception as e_gen:
        logger.error(f"Error regenerando minuta de adición al actualizar: {e_gen}")

    return {
        "status": "success",
        "message": f"Adición Nro. {adicion.numero_adicion} actualizada exitosamente y minuta Word regenerada.",
        "addition_id": adicion.id,
        "numero_adicion": adicion.numero_adicion,
        "valor_adicion": adicion.valor_adicion,
        "valor_nuevo_total": adicion.valor_nuevo_total,
        "download_url": f"/api/additions/{adicion.id}/download-docx",
        "contrato_numero": contrato.numero_contrato
    }


@router.delete("/{addition_id}")
def delete_contract_addition(
    addition_id: int, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """
    Elimina una adición contractual, revierte el valor adicionado en el contrato,
    re-secuencia las adiciones restantes y sincroniza la Matriz Excel.
    """
    adicion = db.query(AdicionContrato).options(
        joinedload(AdicionContrato.contrato)
    ).filter(AdicionContrato.id == addition_id).first()

    if not adicion:
        raise HTTPException(status_code=404, detail="Adición no encontrada.")

    contrato = adicion.contrato
    val_adic = adicion.valor_adicion or 0.0
    num_adicion = adicion.numero_adicion
    cto_id = adicion.contrato_id

    # 1. Eliminar archivo docx físico si existe
    if adicion.ruta_minuta_docx:
        try:
            p = settings.BASE_DIR / adicion.ruta_minuta_docx
            if p.exists():
                p.unlink()
        except Exception as e:
            logger.warning(f"No se pudo eliminar archivo docx de adición: {e}")

    # 2. Eliminar el registro de adición
    db.delete(adicion)
    db.commit()

    # 3. Recalcular y resecuenciar el contrato y adiciones restantes
    if contrato:
        remaining_additions = db.query(AdicionContrato).filter(
            AdicionContrato.contrato_id == cto_id
        ).order_by(AdicionContrato.id.asc()).all()

        val_inicial = contrato.valor_inicial if contrato.valor_inicial is not None else max(0.0, (contrato.valor_total or 0.0) - val_adic)
        contrato.valor_inicial = val_inicial

        nuevo_adicion_total = 0.0
        for idx, rem_ad in enumerate(remaining_additions, start=1):
            rem_ad.numero_adicion = idx
            rem_ad.valor_anterior = val_inicial + nuevo_adicion_total
            nuevo_adicion_total += (rem_ad.valor_adicion or 0.0)
            rem_ad.valor_nuevo_total = val_inicial + nuevo_adicion_total

        contrato.adicion_1 = nuevo_adicion_total
        contrato.valor_total = val_inicial + nuevo_adicion_total
        from app.utils.num_to_words import numero_a_letras_cop
        contrato.valor_en_letras = numero_a_letras_cop(contrato.valor_total)

        # Auditoría
        from app.models.audit_log import Auditoria
        audit = Auditoria(
            contrato_id=contrato.id,
            accion="ELIMINACION_ADICION",
            detalle=f"Adición Nro. {num_adicion} eliminada (${val_adic:,.0f}). Nuevo saldo de adiciones: ${contrato.adicion_1:,.0f}. Nuevo total: ${contrato.valor_total:,.0f}",
            usuario=current_user.nombre_completo or current_user.username,
            usuario_documento=current_user.documento,
            usuario_nombre=current_user.nombre_completo or current_user.username
        )
        db.add(audit)
        db.commit()
        db.refresh(contrato)

        # Sincronizar en Excel Maestro
        try:
            from app.services.excel_engine import sync_contract_to_master_excel
            sync_contract_to_master_excel(contrato)
            logger.info(f"Contrato {contrato.numero_contrato} resincronizado en Excel tras eliminar adición.")
        except Exception as e:
            logger.warning(f"Error sincronizando Excel tras eliminar adición: {e}")

    return {
        "status": "success",
        "message": f"Adición Nro. {num_adicion} eliminada correctamente. Valor contractual revertido.",
        "contrato_id": cto_id,
        "nuevo_adicion_1": contrato.adicion_1 if contrato else 0.0,
        "nuevo_valor_total": contrato.valor_total if contrato else 0.0
    }


@router.delete("/contract/{contract_id}/all")
def delete_all_contract_additions(
    contract_id: int, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """
    Elimina todas las adiciones registradas de un contrato, revierte adicion_1 a 0,
    restablece el valor total al valor inicial y sincroniza la Matriz Excel.
    """
    contrato = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contrato:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")

    adiciones = db.query(AdicionContrato).filter(AdicionContrato.contrato_id == contract_id).all()
    count_deleted = len(adiciones)
    monto_revertido = contrato.adicion_1 or 0.0

    for a in adiciones:
        if a.ruta_minuta_docx:
            try:
                p = settings.BASE_DIR / a.ruta_minuta_docx
                if p.exists():
                    p.unlink()
            except Exception:
                pass
        db.delete(a)

    val_inicial = contrato.valor_inicial if contrato.valor_inicial is not None else (contrato.valor_total - monto_revertido)
    contrato.valor_inicial = val_inicial
    contrato.adicion_1 = 0.0
    contrato.valor_total = val_inicial
    from app.utils.num_to_words import numero_a_letras_cop
    contrato.valor_en_letras = numero_a_letras_cop(contrato.valor_total)

    from app.models.audit_log import Auditoria
    audit = Auditoria(
        contrato_id=contrato.id,
        accion="ELIMINACION_ADICION",
        detalle=f"Todas las adiciones ({count_deleted} adiciones por ${monto_revertido:,.0f}) fueron eliminadas. Contrato revertido a valor inicial: ${contrato.valor_total:,.0f}",
        usuario=current_user.nombre_completo or current_user.username,
        usuario_documento=current_user.documento,
        usuario_nombre=current_user.nombre_completo or current_user.username
    )
    db.add(audit)
    db.commit()
    db.refresh(contrato)

    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contrato)
    except Exception as e:
        logger.warning(f"Error sincronizando Excel tras resetear adiciones: {e}")

    return {
        "status": "success",
        "message": f"Se eliminaron {count_deleted} adiciones del contrato {contrato.numero_contrato}. El valor contractual fue revertido al valor inicial de ${val_inicial:,.0f} COP.",
        "contrato_id": contrato.id,
        "adicion_1": 0.0,
        "valor_total": contrato.valor_total
    }
