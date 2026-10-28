import uuid
import os
import shutil
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app.models.document import Documento, TipoDocumento, CategoriaDocumento
from app.models.contractor import Contratista, TipoPersona, RegimenTributario, TipoDocumento as TipoDocumentoIdentidad
from app.models.contract import Contrato
from app.models.audit_log import Auditoria
from app.schemas.agent import (
    ContratistaExtractedData, 
    ContractDraftingInput, 
    ContractDraftingResult,
    JustificacionGenerationInput,
    JustificacionGenerationResult,
    NecesidadElaborationInput,
    NecesidadElaborationResult,
    ObjetoGenerationInput,
    ObjetoGenerationResult,
    RiskMatrixInput,
    RiskMatrixResult
)
from app.schemas.contractor import ContratistaRead
from app.schemas.contract import ContratoRead
from app.services.document_parser import parse_document_text
from app.services.gemini_client import gemini_service
from app.services.agents.dispatcher import dispatcher
from app.services.agents.justification_agent import justification_agent
from app.services.agents.object_agent import object_agent
from app.services.agents.risk_agent import risk_agent
from app.services.contractor_enrichment import enrich_contractor, get_missing_contractor_fields
from app.utils.objective_normalizer import normalize_objetivos_especificos
from app.utils.object_normalizer import normalize_objeto_contractual
from app.utils.logger import logger

router = APIRouter(prefix="/agents", tags=["Agentes IA y Extracción"])

class MultiDocExtractRequest(BaseModel):
    document_ids: List[int]

class CreateContractorFromDocsRequest(BaseModel):
    document_ids: List[int] = []
    contratista_data: Optional[Dict[str, Any]] = None

@router.post("/extract-multiple-documents")
def extract_multiple_documents_data(
    payload: MultiDocExtractRequest,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Procesa en lote hasta 8 documentos del contratista (Cédula, RUT, Cotización, etc.),
    extrayendo el texto de cada uno (con OCR inteligente si es escaneado) y consolidando
    de forma unificada los datos fiscales, de contacto, propuesta económica y perfil profesional.
    """
    if not payload.document_ids or len(payload.document_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar al menos un ID de documento."
        )

    if len(payload.document_ids) > 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El límite máximo admitido es de 8 documentos por proceso."
        )

    effective_api_key = api_key if isinstance(api_key, str) and api_key.strip() else None
    docs_processed = []
    consolidated_dict: Dict[str, Any] = {
        "tipo_persona": "NATURAL",
        "tipo_documento": "CC",
        "numero_documento": None,
        "digito_verificacion": None,
        "nombre_o_razon_social": None,
        "nombre_comercial": None,
        "representante_legal_nombre": None,
        "representante_legal_documento": None,
        "direccion": None,
        "municipio": None,
        "departamento": None,
        "correo_electronico": None,
        "telefono": None,
        "regimen_tributario": None,
        "actividad_economica_ciiu": None,
        "valor_propuesto": None,
        "plazo_propuesto": None,
        "unidad_plazo_propuesto": None,
        "perfil_profesional_resumen": None,
        "banco_nombre": None,
        "banco_tipo_cuenta": None,
        "banco_numero_cuenta": None,
        "forma_pago_propuesta": None,
        "objeto_propuesto": None,
        "objetivo_general": None,
        "objetivos_especificos": [],
        "alcance_propuesto": None,
        "actividades_propuesta": [],
        "cdp_numero": None,
        "cdp_fecha": None,
        "cdp_rubro": None,
        "cdp_rubro_nombre": None,
        "cdp_valor": None,
        "cdp_objeto": None,
        "cdp_clasificadores": [],
        "cdp_texto_completo": None,
        "subdocumentos_detectados": []
    }

    all_detected_subdocs = set()

    from app.services.document_parser import is_valid_person_name, extract_colombian_cedula_data

    # Cubeta específica para datos extraídos de documento de Cédula de Ciudadanía
    cedula_persona_data = {
        "nombre_completo": None,
        "numero_documento": None
    }

    for doc_id in payload.document_ids:
        doc = db.query(Documento).filter(Documento.id == doc_id).first()
        if not doc:
            continue

        candidate_paths = [
            settings.BASE_DIR / doc.ruta_relativa,
            settings.STORAGE_DIR.parent / doc.ruta_relativa,
            settings.STORAGE_DIR / Path(doc.ruta_relativa).name,
            settings.UPLOADS_DIR / Path(doc.ruta_relativa).name,
            settings.WORKSPACE_ROOT / "backend" / doc.ruta_relativa,
            settings.WORKSPACE_ROOT / "backend" / "storage" / "uploads" / Path(doc.ruta_relativa).name,
            Path(doc.ruta_relativa)
        ]
        full_path = None
        for cp in candidate_paths:
            if cp.exists() or cp.with_suffix(".ocr.txt").exists():
                full_path = cp
                break

        if not full_path:
            continue


        try:
            raw_text = parse_document_text(full_path)
            if raw_text and raw_text.strip():
                extracted = gemini_service.extract_contractor_data(raw_text, override_api_key=effective_api_key)
                doc.datos_extraidos_json = extracted.model_dump()
                db.commit()

                # Consolidación inteligente de campos
                ext_dict = extracted.model_dump()
                subdocs = ext_dict.get("subdocumentos_detectados") or []
                for sd in subdocs:
                    all_detected_subdocs.add(sd)

                # Detección específica de Cédula de Ciudadanía
                is_rut_doc = "RUT" in subdocs or (doc and "rut" in doc.nombre_archivo_original.lower())
                is_cedula_file = (
                    (doc and any(k in doc.nombre_archivo_original.lower() for k in ["cedula", "cédula", "cc"]))
                    or ("CEDULA" in subdocs and not is_rut_doc)
                    or (raw_text and not is_rut_doc and ("NUIP" in raw_text.upper() or "CEDULA DE CIUDADANIA" in raw_text.upper() or "ICC0L" in raw_text.upper()))
                )
                if is_cedula_file:
                    ced_data = extract_colombian_cedula_data(raw_text)
                    c_nom = ced_data.get("nombre_completo") or (ext_dict.get("nombre_o_razon_social") if ext_dict.get("tipo_persona") == "NATURAL" else None)
                    c_doc = ced_data.get("numero_documento") or (ext_dict.get("numero_documento") if ext_dict.get("tipo_persona") == "NATURAL" else None)
                    if c_nom and is_valid_person_name(c_nom):
                        cedula_persona_data["nombre_completo"] = c_nom
                    if c_doc:
                        c_doc_clean = re.sub(r"[^\d]", "", str(c_doc))
                        if 6 <= len(c_doc_clean) <= 10 and not c_doc_clean.startswith(("800", "811", "830", "860", "890", "900", "901", "902")):
                            cedula_persona_data["numero_documento"] = c_doc_clean

                # 1. Datos de CDP
                if ext_dict.get("cdp_numero"):
                    consolidated_dict["cdp_numero"] = ext_dict["cdp_numero"]
                if ext_dict.get("cdp_fecha"):
                    consolidated_dict["cdp_fecha"] = ext_dict["cdp_fecha"]
                if ext_dict.get("cdp_rubro"):
                    consolidated_dict["cdp_rubro"] = ext_dict["cdp_rubro"]
                if ext_dict.get("cdp_rubro_nombre"):
                    consolidated_dict["cdp_rubro_nombre"] = ext_dict["cdp_rubro_nombre"]
                if ext_dict.get("cdp_valor"):
                    consolidated_dict["cdp_valor"] = ext_dict["cdp_valor"]
                if ext_dict.get("cdp_objeto"):
                    consolidated_dict["cdp_objeto"] = ext_dict["cdp_objeto"]
                if ext_dict.get("cdp_clasificadores"):
                    consolidated_dict["cdp_clasificadores"] = ext_dict["cdp_clasificadores"]
                if ext_dict.get("cdp_texto_completo"):
                    consolidated_dict["cdp_texto_completo"] = ext_dict["cdp_texto_completo"]

                # 2. Datos del Contratista (filtrando NIT y nombre de la ESP)
                cand_num = ext_dict.get("numero_documento")
                cand_nom = ext_dict.get("nombre_o_razon_social")
                is_espy = (cand_num == "811015112") or (cand_nom and ("YOLOMBO" in cand_nom.upper() or "REPUBLICA" in cand_nom.upper()))

                is_rut_doc = "RUT" in subdocs or (doc and "rut" in doc.nombre_archivo_original.lower())

                if not is_espy:
                    if is_rut_doc:
                        # El RUT es la fuente de verdad oficial tributaria y civil en Colombia
                        if ext_dict.get("tipo_persona"):
                            consolidated_dict["tipo_persona"] = ext_dict["tipo_persona"]
                        if ext_dict.get("tipo_documento"):
                            consolidated_dict["tipo_documento"] = ext_dict["tipo_documento"]
                        if cand_num:
                            consolidated_dict["numero_documento"] = cand_num
                        if ext_dict.get("digito_verificacion"):
                            consolidated_dict["digito_verificacion"] = ext_dict["digito_verificacion"]
                        if cand_nom and cand_nom != "Contratista Identificado":
                            consolidated_dict["nombre_o_razon_social"] = cand_nom
                        if ext_dict.get("direccion"):
                            consolidated_dict["direccion"] = ext_dict["direccion"]
                        if ext_dict.get("municipio"):
                            consolidated_dict["municipio"] = ext_dict["municipio"]
                        if ext_dict.get("departamento"):
                            consolidated_dict["departamento"] = ext_dict["departamento"]
                        if ext_dict.get("correo_electronico"):
                            consolidated_dict["correo_electronico"] = ext_dict["correo_electronico"]
                        if ext_dict.get("telefono"):
                            consolidated_dict["telefono"] = ext_dict["telefono"]
                        if ext_dict.get("regimen_tributario"):
                            consolidated_dict["regimen_tributario"] = ext_dict["regimen_tributario"]
                        if ext_dict.get("actividad_economica_ciiu"):
                            consolidated_dict["actividad_economica_ciiu"] = ext_dict["actividad_economica_ciiu"]
                        if ext_dict.get("representante_legal_nombre") and is_valid_person_name(ext_dict["representante_legal_nombre"]):
                            consolidated_dict["representante_legal_nombre"] = ext_dict["representante_legal_nombre"]
                        if ext_dict.get("representante_legal_documento"):
                            rd_clean = re.sub(r"[^\d]", "", str(ext_dict["representante_legal_documento"]))
                            if rd_clean != cand_num and not rd_clean.startswith(("800", "811", "830", "860", "890", "900", "901", "902")):
                                consolidated_dict["representante_legal_documento"] = rd_clean
                    else:
                        if ext_dict.get("tipo_persona") and not consolidated_dict.get("tipo_persona"):
                            consolidated_dict["tipo_persona"] = ext_dict["tipo_persona"]
                            consolidated_dict["tipo_documento"] = ext_dict.get("tipo_documento", "CC" if ext_dict["tipo_persona"] == "NATURAL" else "NIT")
                        if cand_num and not consolidated_dict.get("numero_documento") and not is_cedula_file:
                            consolidated_dict["numero_documento"] = cand_num
                        if ext_dict.get("digito_verificacion") and not consolidated_dict.get("digito_verificacion") and not is_cedula_file:
                            consolidated_dict["digito_verificacion"] = ext_dict["digito_verificacion"]
                        if cand_nom and cand_nom != "Contratista Identificado" and not is_cedula_file:
                            if not consolidated_dict.get("nombre_o_razon_social") or consolidated_dict.get("nombre_o_razon_social") == "Contratista Identificado":
                                consolidated_dict["nombre_o_razon_social"] = cand_nom
                        if ext_dict.get("nombre_comercial") and not consolidated_dict.get("nombre_comercial"):
                            consolidated_dict["nombre_comercial"] = ext_dict["nombre_comercial"]
                        if ext_dict.get("representante_legal_nombre") and is_valid_person_name(ext_dict["representante_legal_nombre"]) and not consolidated_dict.get("representante_legal_nombre"):
                            consolidated_dict["representante_legal_nombre"] = ext_dict["representante_legal_nombre"]
                        if ext_dict.get("representante_legal_documento") and not consolidated_dict.get("representante_legal_documento"):
                            rd_clean = re.sub(r"[^\d]", "", str(ext_dict["representante_legal_documento"]))
                            if rd_clean != cand_num and not rd_clean.startswith(("800", "811", "830", "860", "890", "900", "901", "902")):
                                consolidated_dict["representante_legal_documento"] = rd_clean
                        if ext_dict.get("direccion") and not consolidated_dict.get("direccion"):
                            consolidated_dict["direccion"] = ext_dict["direccion"]
                        if ext_dict.get("municipio") and not consolidated_dict.get("municipio"):
                            consolidated_dict["municipio"] = ext_dict["municipio"]
                        if ext_dict.get("departamento") and not consolidated_dict.get("departamento"):
                            consolidated_dict["departamento"] = ext_dict["departamento"]
                        if ext_dict.get("correo_electronico") and not consolidated_dict.get("correo_electronico"):
                            consolidated_dict["correo_electronico"] = ext_dict["correo_electronico"]
                        if ext_dict.get("telefono") and not consolidated_dict.get("telefono"):
                            consolidated_dict["telefono"] = ext_dict["telefono"]
                        if ext_dict.get("regimen_tributario") and not consolidated_dict.get("regimen_tributario"):
                            consolidated_dict["regimen_tributario"] = ext_dict["regimen_tributario"]
                        if ext_dict.get("actividad_economica_ciiu") and not consolidated_dict.get("actividad_economica_ciiu"):
                            consolidated_dict["actividad_economica_ciiu"] = ext_dict["actividad_economica_ciiu"]

                # 3. Propuesta Económica y Banco
                if ext_dict.get("valor_propuesto") and not is_espy:
                    consolidated_dict["valor_propuesto"] = ext_dict["valor_propuesto"]
                if ext_dict.get("plazo_propuesto"):
                    consolidated_dict["plazo_propuesto"] = ext_dict["plazo_propuesto"]
                    consolidated_dict["unidad_plazo_propuesto"] = ext_dict.get("unidad_plazo_propuesto", "MESES")
                if ext_dict.get("objeto_propuesto") and (not consolidated_dict.get("objeto_propuesto") or "PROPUESTA_ECONOMICA" in subdocs):
                    consolidated_dict["objeto_propuesto"] = ext_dict["objeto_propuesto"]
                if ext_dict.get("objetivo_general") and (not consolidated_dict.get("objetivo_general") or "PROPUESTA_ECONOMICA" in subdocs):
                    consolidated_dict["objetivo_general"] = ext_dict["objetivo_general"]
                if ext_dict.get("alcance_propuesto"):
                    consolidated_dict["alcance_propuesto"] = ext_dict["alcance_propuesto"]
                if ext_dict.get("actividades_propuesta") and len(ext_dict["actividades_propuesta"]) > 0:
                    norm_acts = normalize_objetivos_especificos(ext_dict["actividades_propuesta"])
                    consolidated_dict["actividades_propuesta"] = norm_acts
                    if not consolidated_dict.get("objetivos_especificos"):
                        consolidated_dict["objetivos_especificos"] = norm_acts
                if ext_dict.get("objetivos_especificos") and len(ext_dict["objetivos_especificos"]) > 0:
                    consolidated_dict["objetivos_especificos"] = normalize_objetivos_especificos(ext_dict["objetivos_especificos"])
                if ext_dict.get("forma_pago_propuesta"):
                    consolidated_dict["forma_pago_propuesta"] = ext_dict["forma_pago_propuesta"]
                if ext_dict.get("banco_nombre"):
                    consolidated_dict["banco_nombre"] = ext_dict["banco_nombre"]
                if ext_dict.get("banco_tipo_cuenta"):
                    consolidated_dict["banco_tipo_cuenta"] = ext_dict["banco_tipo_cuenta"]
                if ext_dict.get("banco_numero_cuenta"):
                    consolidated_dict["banco_numero_cuenta"] = ext_dict["banco_numero_cuenta"]
                if ext_dict.get("perfil_profesional_resumen") and not consolidated_dict.get("perfil_profesional_resumen"):
                    consolidated_dict["perfil_profesional_resumen"] = ext_dict["perfil_profesional_resumen"]

                docs_processed.append({
                    "id": doc.id,
                    "nombre_archivo": doc.nombre_archivo_original,
                    "caracteres_extraidos": len(raw_text),
                    "subdocumentos_detectados": subdocs,
                    "datos": ext_dict
                })
        except Exception as e:
            logger.warning(f"Error procesando documento {doc_id}: {e}")

    consolidated_dict["subdocumentos_detectados"] = sorted(list(all_detected_subdocs))

    # Si se extrajo valor del CDP pero no de la propuesta, usar el valor del CDP
    if not consolidated_dict.get("valor_propuesto") and consolidated_dict.get("cdp_valor"):
        consolidated_dict["valor_propuesto"] = consolidated_dict["cdp_valor"]

    cand_nom_final = consolidated_dict.get("nombre_o_razon_social")
    cand_doc_final = consolidated_dict.get("numero_documento")
    tipo_p = consolidated_dict.get("tipo_persona") or "NATURAL"

    # REGLA DE ORO DE CONSOLIDACIÓN PARA REPRESENTANTE LEGAL:
    if tipo_p == "JURIDICA":
        # 1. Asignación con prioridad absoluta desde documento CÉDULA si fue cargado
        if cedula_persona_data.get("nombre_completo"):
            consolidated_dict["representante_legal_nombre"] = cedula_persona_data["nombre_completo"]
        if cedula_persona_data.get("numero_documento"):
            consolidated_dict["representante_legal_documento"] = cedula_persona_data["numero_documento"]

        # 2. Blindaje de validez del nombre del Representante Legal
        if consolidated_dict.get("representante_legal_nombre") and not is_valid_person_name(consolidated_dict["representante_legal_nombre"]):
            consolidated_dict["representante_legal_nombre"] = None

        # 3. Blindaje contra clonación del NIT de la empresa en la Cédula del Representante Legal
        rep_doc_final = str(consolidated_dict.get("representante_legal_documento") or "").strip()
        nit_final = str(cand_doc_final or "").strip()
        if rep_doc_final and (rep_doc_final == nit_final or rep_doc_final.startswith(("800", "811", "830", "860", "890", "900", "901", "902"))):
            # Si se clonó el NIT, restaurar la cédula real si fue extraída en la cubeta
            if cedula_persona_data.get("numero_documento"):
                consolidated_dict["representante_legal_documento"] = cedula_persona_data["numero_documento"]
            else:
                consolidated_dict["representante_legal_documento"] = None
    else:
        # Persona Natural: Si se extrajo de CÉDULA, garantizar nombre y documento prioritarios
        if cedula_persona_data.get("nombre_completo") and (not cand_nom_final or cand_nom_final == "Contratista Identificado"):
            consolidated_dict["nombre_o_razon_social"] = cedula_persona_data["nombre_completo"]
        if cedula_persona_data.get("numero_documento") and not cand_doc_final:
            consolidated_dict["numero_documento"] = cedula_persona_data["numero_documento"]
        if not consolidated_dict.get("tipo_documento"):
            consolidated_dict["tipo_documento"] = "CC"

    if not consolidated_dict.get("nombre_o_razon_social"):
        consolidated_dict["nombre_o_razon_social"] = "Contratista Identificado"
    if not consolidated_dict.get("municipio"):
        consolidated_dict["municipio"] = "Yolombó"

    # Detección inteligente de si corresponde a un contratista ya registrado en la BD
    is_existing = False
    existing_id = None
    existing_nombre = None
    campos_faltantes = []
    cand_doc = consolidated_dict.get("numero_documento")
    if cand_doc:
        exist_c = db.query(Contratista).filter(Contratista.numero_documento == str(cand_doc)).first()
        if exist_c:
            is_existing = True
            existing_id = exist_c.id
            existing_nombre = exist_c.nombre_o_razon_social
            missing_items = get_missing_contractor_fields(exist_c)
            campos_faltantes = [m["label"] for m in missing_items]

    return {
        "consolidated": ContratistaExtractedData(**consolidated_dict),
        "documentos_procesados": docs_processed,
        "total_procesados": len(docs_processed),
        "is_existing_contractor": is_existing,
        "existing_contractor_id": existing_id,
        "existing_contractor_nombre": existing_nombre,
        "campos_faltantes": campos_faltantes
    }

@router.post("/create-contractor-from-docs", response_model=ContratistaRead)
def create_contractor_from_multiple_docs(
    payload: CreateContractorFromDocsRequest,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Crea o actualiza de forma no destructiva el contratista y vincula todos los documentos cargados (hasta 8)
    a su respectivo expediente en la base de datos, enriqueciendo datos de contacto, fiscales y bancarios.
    """
    if not payload.document_ids and not payload.contratista_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No se suministraron documentos ni datos del contratista.")

    data = payload.contratista_data or {}
    num_doc = data.get("numero_documento")

    # Si no vino número en los datos verificados, buscar en los documentos
    if not num_doc:
        for doc_id in payload.document_ids:
            d = db.query(Documento).filter(Documento.id == doc_id).first()
            if d and d.datos_extraidos_json and d.datos_extraidos_json.get("numero_documento"):
                num_doc = d.datos_extraidos_json["numero_documento"]
                break

    if not num_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere un número de documento o NIT para crear la ficha del contratista."
        )

    # Buscar si ya existe el contratista
    contractor = db.query(Contratista).filter(Contratista.numero_documento == str(num_doc)).first()

    tipo_p = TipoPersona.JURIDICA if data.get("tipo_persona") == "JURIDICA" else TipoPersona.NATURAL
    tipo_d = TipoDocumentoIdentidad.NIT if data.get("tipo_documento") == "NIT" else TipoDocumentoIdentidad.CC
    
    reg_val = data.get("regimen_tributario")
    if reg_val == "RESPONSABLE_IVA":
        regimen = RegimenTributario.RESPONSABLE_IVA
    elif reg_val == "GRAN_CONTRIBUYENTE":
        regimen = RegimenTributario.GRAN_CONTRIBUYENTE
    elif reg_val == "REGIMEN_SIMPLE":
        regimen = RegimenTributario.REGIMEN_SIMPLE
    else:
        regimen = RegimenTributario.NO_RESPONSABLE_IVA

    if contractor:
        # Enriquecimiento automático y no destructivo de contratista existente
        enrich_contractor(
            contractor=contractor, 
            data=data, 
            db=db, 
            source_desc="Asistente de Contratación (Expediente Documental)"
        )
        logger.info(f"Contratista existente ID {contractor.id} enriquecido y actualizado.")
    else:
        contractor = Contratista(
            tipo_persona=tipo_p,
            tipo_documento=tipo_d,
            numero_documento=str(num_doc),
            digito_verificacion=data.get("digito_verificacion"),
            nombre_o_razon_social=data.get("nombre_o_razon_social") or "Contratista Identificado",
            representante_legal_nombre=data.get("representante_legal_nombre"),
            representante_legal_documento=data.get("representante_legal_documento"),
            direccion=data.get("direccion") or "Sin dirección",
            municipio=data.get("municipio") or "Colombia",
            departamento=data.get("departamento") or "Colombia",
            correo_electronico=data.get("correo_electronico"),
            telefono=data.get("telefono"),
            regimen_tributario=regimen,
            banco_nombre=data.get("banco_nombre"),
            banco_tipo_cuenta=data.get("banco_tipo_cuenta"),
            banco_numero_cuenta=data.get("banco_numero_cuenta"),
            perfil_o_experiencia_resumen=data.get("perfil_profesional_resumen")
        )
        db.add(contractor)
        db.flush()
        logger.info(f"Nuevo contratista creado: ID {contractor.id} ({contractor.nombre_o_razon_social})")

    # Vincular todos los documentos al contratista
    for doc_id in payload.document_ids:
        d = db.query(Documento).filter(Documento.id == doc_id).first()
        if d:
            d.contratista_id = contractor.id

    db.commit()
    db.refresh(contractor)
    return contractor

@router.post("/extract-document/{document_id}", response_model=ContratistaExtractedData)
def extract_document_data(
    document_id: int, 
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Lee el archivo PDF o Word cargado, extrae su contenido y utiliza Gemini IA
    para estructurar en JSON los datos del contratista y su cotización/propuesta.
    """
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
                detail=f"Archivo físico no encontrado en disco: {doc.ruta_relativa}"
            )


    # 1. Extraer texto crudo del archivo
    raw_text = parse_document_text(full_path)
    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo extraer texto legible del documento cargado."
        )

    # 2. Procesar con Gemini / Extractor de IA
    extracted = gemini_service.extract_contractor_data(raw_text, override_api_key=api_key)

    # 3. Almacenar metadatos extraídos en la BD
    doc.datos_extraidos_json = extracted.model_dump()
    db.commit()
    db.refresh(doc)
    logger.info(f"Datos extraídos del documento ID {document_id} y guardados en base de datos.")

    return extracted

@router.post("/create-contractor-from-doc/{document_id}", response_model=ContratistaRead)
def create_contractor_from_document(
    document_id: int,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Extrae la información del documento (RUT, Propuesta) y crea o actualiza
    automáticamente la ficha del Contratista en la base de datos.
    """
    doc = db.query(Documento).filter(Documento.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID {document_id} no encontrado."
        )

    # Si aún no tiene datos extraídos, ejecutar extracción
    if not doc.datos_extraidos_json:
        full_path = settings.BASE_DIR / doc.ruta_relativa
        if not full_path.exists():
            alt_path = settings.STORAGE_DIR.parent / doc.ruta_relativa
            if alt_path.exists():
                full_path = alt_path
        raw_text = parse_document_text(full_path)
        extracted = gemini_service.extract_contractor_data(raw_text, override_api_key=api_key)
        doc.datos_extraidos_json = extracted.model_dump()
    else:

        extracted = ContratistaExtractedData(**doc.datos_extraidos_json)

    if not extracted.numero_documento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo identificar un número de documento o NIT en el archivo."
        )

    # Buscar si ya existe el contratista
    contractor = db.query(Contratista).filter(
        Contratista.numero_documento == extracted.numero_documento
    ).first()

    # Mapeo seguro de enums
    tipo_p = TipoPersona.JURIDICA if extracted.tipo_persona == "JURIDICA" else TipoPersona.NATURAL
    tipo_d = TipoDocumentoIdentidad.NIT if extracted.tipo_documento == "NIT" else TipoDocumentoIdentidad.CC
    regimen = RegimenTributario.RESPONSABLE_IVA if extracted.regimen_tributario == "RESPONSABLE_IVA" else RegimenTributario.NO_RESPONSABLE_IVA

    if contractor:
        # Actualizar datos existentes
        contractor.nombre_o_razon_social = extracted.nombre_o_razon_social or contractor.nombre_o_razon_social
        contractor.direccion = extracted.direccion or contractor.direccion
        contractor.municipio = extracted.municipio or contractor.municipio
        contractor.correo_electronico = extracted.correo_electronico or contractor.correo_electronico
        contractor.telefono = extracted.telefono or contractor.telefono
        contractor.perfil_o_experiencia_resumen = extracted.perfil_profesional_resumen or contractor.perfil_o_experiencia_resumen
        logger.info(f"Contratista ID {contractor.id} actualizado a partir de documento.")
    else:
        # Crear nuevo contratista
        contractor = Contratista(
            tipo_persona=tipo_p,
            tipo_documento=tipo_d,
            numero_documento=extracted.numero_documento,
            digito_verificacion=extracted.digito_verificacion,
            nombre_o_razon_social=extracted.nombre_o_razon_social or "Contratista sin nombre identificado",
            representante_legal_nombre=extracted.representante_legal_nombre,
            representante_legal_documento=extracted.representante_legal_documento,
            direccion=extracted.direccion or "Sin dirección",
            municipio=extracted.municipio or "Bogotá D.C.",
            departamento=extracted.departamento or "Cundinamarca",
            correo_electronico=extracted.correo_electronico,
            telefono=extracted.telefono,
            regimen_tributario=regimen,
            perfil_o_experiencia_resumen=extracted.perfil_profesional_resumen
        )
        db.add(contractor)
        db.flush()
        logger.info(f"Nuevo contratista creado a partir de documento: ID {contractor.id}")

    # Asociar documento al contratista
    doc.contratista_id = contractor.id
    db.commit()
    db.refresh(contractor)

    return contractor

@router.post("/draft", response_model=ContractDraftingResult)
def draft_contract_with_agent(
    input_data: ContractDraftingInput,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Invoca al Agente Especializado correspondiente (Servicios, Obra o Suministro)
    para estructurar y redactar de forma integral el objeto, justificación (Ley 142/1994),
    objetivos medibles, obligaciones para estudio previo y minuta, y garantías normativas.
    Si se proporciona `contrato_id`, los campos se actualizan directamente en la base de datos.
    """
    # 1. Si viene contratista_id y no viene contexto, cargarlo de la BD
    if input_data.contratista_id and not input_data.datos_contratista_contexto:
        cont = db.query(Contratista).filter(Contratista.id == input_data.contratista_id).first()
        if cont:
            input_data.datos_contratista_contexto = {
                "nombre": cont.nombre_o_razon_social,
                "documento": cont.numero_documento,
                "perfil": cont.perfil_o_experiencia_resumen
            }

    # 1.1 Si no vienen document_ids pero viene contratista_id, vincular sus documentos del expediente
    if not input_data.document_ids and input_data.contratista_id:
        c_docs = db.query(Documento).filter(Documento.contratista_id == input_data.contratista_id).all()
        if c_docs:
            input_data.document_ids = [d.id for d in c_docs]

    # 1.2 Si se suministraron o asociaron documentos, extraer contexto real para que el agente no redacte a ciegas
    doc_ext = None
    if input_data.document_ids:
        try:
            doc_context = object_agent.extract_context_from_docs(input_data.document_ids, db)
            if doc_context:
                doc_ext = gemini_service.extract_contractor_data(doc_context)
                if doc_ext.objeto_propuesto and (not input_data.necesidad_descripcion or "prestar servicios especializados" in input_data.necesidad_descripcion.lower()):
                    input_data.necesidad_descripcion = doc_ext.objeto_propuesto
                if doc_ext.alcance_propuesto and not input_data.alcance_esperado:
                    input_data.alcance_esperado = doc_ext.alcance_propuesto
                if doc_ext.valor_propuesto and not input_data.valor_estimado:
                    input_data.valor_estimado = doc_ext.valor_propuesto
                if not input_data.datos_contratista_contexto:
                    input_data.datos_contratista_contexto = {
                        "nombre": doc_ext.nombre_o_razon_social,
                        "documento": doc_ext.numero_documento,
                        "perfil": doc_ext.perfil_profesional_resumen
                    }
        except Exception as e:
            logger.warning(f"No se pudo enriquecer el contexto documental previo al draft: {e}")

    # 2. Despachar al agente especializado de tipología
    draft_result = dispatcher.dispatch_drafting(input_data, override_api_key=api_key)

    # Si se detectó propuesta con actividades u objetivos específicos concretos, usarlos con prioridad
    from app.utils.objetivos_builder import build_objetivo_general, build_objetivos_especificos, is_prohibited_objective

    if doc_ext:
        if doc_ext.objeto_propuesto:
            draft_result.objeto = normalize_objeto_contractual(doc_ext.objeto_propuesto, input_data.tipologia)
        if doc_ext.objetivo_general and "PRESTACIÓN DE SERVICIOS" not in doc_ext.objetivo_general:
            draft_result.objetivo_general = doc_ext.objetivo_general
        else:
            draft_result.objetivo_general = build_objetivo_general(draft_result.objeto, input_data.tipologia)
            
        cand_objs = doc_ext.actividades_propuesta or doc_ext.objetivos_especificos or []
        clean_cand = [o for o in cand_objs if not is_prohibited_objective(o)]
        if len(clean_cand) >= 3:
            draft_result.objetivos_especificos = normalize_objetivos_especificos(clean_cand)
        else:
            draft_result.objetivos_especificos = build_objetivos_especificos(
                objeto=draft_result.objeto,
                tipologia=input_data.tipologia,
                items_propuesta=clean_cand or None,
                contexto=draft_result.justificacion_necesidad or ""
            )
    else:
        # Sanitizar objetivos específicos generados por LLM o fallback
        clean_agent_objs = [o for o in draft_result.objetivos_especificos if not is_prohibited_objective(o)]
        if len(clean_agent_objs) < 3 or any("PRESTACIÓN DE SERVICIOS" in draft_result.objetivo_general for _ in [1]):
            draft_result.objetivo_general = build_objetivo_general(draft_result.objeto, input_data.tipologia, contexto=draft_result.justificacion_necesidad)
            draft_result.objetivos_especificos = build_objetivos_especificos(draft_result.objeto, input_data.tipologia, items_propuesta=clean_agent_objs or None, contexto=draft_result.justificacion_necesidad)
        else:
            draft_result.objetivos_especificos = normalize_objetivos_especificos(clean_agent_objs)


    # Si se suministraron documentos, enriquecer con los agentes especializados de Objeto y Justificación
    if input_data.document_ids:
        try:
            obj_res = object_agent.generate_objeto(
                ObjetoGenerationInput(
                    tipologia=input_data.tipologia,
                    necesidad_descripcion=draft_result.objeto or input_data.necesidad_descripcion,
                    document_ids=input_data.document_ids,
                    contratista_nombre=input_data.datos_contratista_contexto.get("nombre") if input_data.datos_contratista_contexto else None
                ),
                db=db,
                override_api_key=api_key
            )
            if obj_res and obj_res.objeto_sugerido:
                draft_result.objeto = normalize_objeto_contractual(obj_res.objeto_sugerido, input_data.tipologia)
        except Exception as e:
            logger.info(f"Nota: ObjectAgent en draft ({e})")

        try:
            just_res = justification_agent.generate_justificacion(
                JustificacionGenerationInput(
                    document_ids=input_data.document_ids,
                    tipologia=input_data.tipologia,
                    modalidad=input_data.modalidad,
                    objeto=draft_result.objeto,
                    necesidad_contexto=draft_result.objeto or input_data.necesidad_descripcion,
                    contratista_nombre=input_data.datos_contratista_contexto.get("nombre") if input_data.datos_contratista_contexto else None,
                    valor_estimado=input_data.valor_estimado
                ),
                db=db,
                override_api_key=api_key
            )
            if just_res and just_res.justificacion_estudio_previo:
                draft_result.justificacion_necesidad = just_res.justificacion_estudio_previo
        except Exception as e:

            logger.info(f"Nota: JustificationAgent no aplicado en draft general ({e}). Se mantiene justificación del agente de tipología.")

    # 2.1 Garantizar simetría y reglas de Escenario A / Escenario B en las obligaciones del contratista
    from app.utils.obligaciones_builder import build_obligaciones_contratista
    try:
        cand_items = []
        if doc_ext and doc_ext.actividades_propuesta:
            cand_items = doc_ext.actividades_propuesta
        elif draft_result.objetivos_especificos:
            cand_items = draft_result.objetivos_especificos
        
        # Si las obligaciones vienen mínimas o se desea garantizar simetría con la propuesta
        if not draft_result.obligaciones_minuta or len(draft_result.obligaciones_minuta) <= 3 or cand_items:
            gen_ob = build_obligaciones_contratista(
                objeto=draft_result.objeto or input_data.necesidad_descripcion or "",
                tipologia=input_data.tipologia,
                items_propuesta=cand_items if len(cand_items) >= 1 else None,
                contexto_adicional=draft_result.justificacion_necesidad or input_data.necesidad_descripcion or ""
            )
            # Si no tenía obligaciones o eran pocas, actualizar
            if not draft_result.obligaciones_minuta or len(draft_result.obligaciones_minuta) <= 6:
                draft_result.obligaciones_minuta = gen_ob["obligaciones_minuta"]
                draft_result.obligaciones_estudio_previo = gen_ob["obligaciones_estudio_previo"]
    except Exception as e:
        logger.info(f"Nota: Enriquecimiento de obligaciones del contratista ({e})")

    # 2.2 Garantizar generación dinámica y blindaje en las OBLIGACIONES DE LA EMPRESA (ESPY)
    from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa
    try:
        tipo_p = "JURIDICA" if input_data.datos_contratista_contexto and str(input_data.datos_contratista_contexto.get("tipo_persona") or "").upper() in ["JURIDICA", "JURÍDICA", "NIT"] else "NATURAL"
        plazo_full = f"{input_data.plazo} {input_data.unidad_plazo or 'meses'}"
        gen_emp = build_obligaciones_empresa(
            objeto=draft_result.objeto or input_data.necesidad_descripcion or "",
            tipologia=input_data.tipologia,
            plazo_str=plazo_full,
            plazo_val=input_data.plazo,
            unidad_plazo=input_data.unidad_plazo,
            tipo_persona=tipo_p,
            obligaciones_contratista=draft_result.obligaciones_minuta or [],
            contexto_adicional=draft_result.justificacion_necesidad or input_data.necesidad_descripcion or ""
        )
        if not draft_result.obligaciones_empresa or len(draft_result.obligaciones_empresa) <= 3:
            draft_result.obligaciones_empresa = gen_emp
        else:
            # Si el agente LLM generó obligaciones pero contienen frases genéricas estáticas ("plataformas o sistemas" en mantenimiento)
            # o "honorarios" indebidos, sustituirlas por las del builder estructurado
            t_emp_join = " ".join(draft_result.obligaciones_empresa).lower()
            if "mantenimiento" in (draft_result.objeto or "").lower() and "plataformas" in t_emp_join:
                draft_result.obligaciones_empresa = gen_emp
            elif "honorarios" in t_emp_join and any(k in (draft_result.objeto or "").lower() for k in ["mantenimiento", "todo costo", "obra", "suministro"]):
                draft_result.obligaciones_empresa = gen_emp
    except Exception as e:
        logger.info(f"Nota: Enriquecimiento de obligaciones de la empresa ({e})")

    # 3. Si se vinculó a un contrato existente, actualizarlo en BD

    if input_data.contrato_id:
        contract = db.query(Contrato).filter(Contrato.id == input_data.contrato_id).first()
        if contract:
            contract.objeto = normalize_objeto_contractual(draft_result.objeto, contract.tipologia.value if contract.tipologia else input_data.tipologia)
            contract.justificacion_necesidad = draft_result.justificacion_necesidad
            contract.objetivo_general = draft_result.objetivo_general
            contract.objetivos_especificos = normalize_objetivos_especificos(draft_result.objetivos_especificos)
            contract.obligaciones_estudio_previo = draft_result.obligaciones_estudio_previo
            contract.obligaciones_minuta = draft_result.obligaciones_minuta
            contract.obligaciones_empresa = draft_result.obligaciones_empresa
            contract.garantias_exigidas = draft_result.garantias_sugeridas
            if draft_result.marco_juridico:
                contract.marco_juridico = draft_result.marco_juridico
            contract.metadatos_agente = {
                "agente": draft_result.agente_nombre,
                "tipologia": draft_result.tipologia,
                "clausulas_especiales": draft_result.clausulas_especiales,
                "observaciones_juridicas": draft_result.observaciones_juridicas
            }

            audit = Auditoria(
                contrato_id=contract.id,
                accion="GENERACION_AGENTE",
                detalle=f"Contrato estructurado automáticamente por {draft_result.agente_nombre}.",
                usuario="Agente IA"
            )
            db.add(audit)
            db.commit()
            logger.info(f"Contrato ID {contract.id} actualizado con la redacción del {draft_result.agente_nombre}.")

    if draft_result and getattr(draft_result, "objeto", None):
        draft_result.objeto = normalize_objeto_contractual(draft_result.objeto, input_data.tipologia)

    return draft_result

@router.post("/generate-justificacion", response_model=JustificacionGenerationResult)
def generate_justificacion_estudio_previo(
    payload: JustificacionGenerationInput,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Agente especializado que elabora automáticamente la Justificación del Estudio Previo (Ley 142/1994).
    Requiere de forma OBLIGATORIA e INDISPENSABLE la presencia de un documento en PDF o DOCX
    correspondiente al Estudio de Mercado o a la Propuesta Económica del contratista.
    """
    try:
        result = justification_agent.generate_justificacion(payload, db=db, override_api_key=api_key)
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"Error generando justificación de estudio previo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al generar la justificación: {str(e)}"
        )

@router.post("/build-necesidad", response_model=NecesidadElaborationResult)
def build_necesidad_estudio_previo(payload: NecesidadElaborationInput):
    """
    Elabora dinámicamente la sección 'DESCRIPCIÓN DE LA NECESIDAD A SATISFACER'
    para los Estudios Previos conforme a la Ley 142 de 1994, la Regla de Oro
    y los niveles de extensión CORTA, MEDIA o COMPLETA.
    """
    from app.utils.necesidad_builder import build_necesidad_structured
    res = build_necesidad_structured(
        objeto=payload.objeto,
        tipologia=payload.tipologia,
        contexto_adicional=payload.contexto_adicional,
        items_o_actividades=payload.items_o_actividades,
        nivel_extension=payload.nivel_extension or "MEDIA",
        instrucciones_adicionales=payload.instrucciones_adicionales,
        propuesta_items=payload.propuesta_items
    )
    return NecesidadElaborationResult(**res)

@router.post("/generate-objetivos")
def generate_objetivos_endpoint(payload: Dict[str, Any]):
    """
    Formula el Objetivo General y los Objetivos Específicos según el nivel de extensión
    (CORTA, MEDIA, COMPLETA) y la propuesta económica.
    """
    from app.utils.objetivos_builder import build_objetivos_contrato
    objeto = payload.get("objeto", "")
    tipologia = payload.get("tipologia", "PRESTACION_SERVICIOS")
    contexto = payload.get("contexto") or payload.get("propuesta_texto")
    items = payload.get("propuesta_items") or payload.get("items")
    nivel = payload.get("nivel_extension", "MEDIA") or "MEDIA"
    instrucciones = payload.get("instrucciones_adicionales")

    result = build_objetivos_contrato(
        objeto=objeto,
        tipologia=tipologia,
        items_propuesta=items,
        contexto=contexto,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )
    return result

@router.post("/generate-obligaciones")
def generate_obligaciones_endpoint(payload: Dict[str, Any]):
    """
    Formula las Obligaciones del Contratista (específicas y generales) y de la ESPY
    según el nivel de extensión (CORTA, MEDIA, COMPLETA) y la propuesta económica.
    """
    from app.utils.obligaciones_builder import build_obligaciones_contratista
    from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa

    objeto = payload.get("objeto", "")
    tipologia = payload.get("tipologia", "PRESTACION_SERVICIOS")
    items = payload.get("propuesta_items") or payload.get("items")
    contexto = payload.get("contexto") or payload.get("propuesta_texto")
    nivel = payload.get("nivel_extension", "MEDIA") or "MEDIA"
    instrucciones = payload.get("instrucciones_adicionales")

    plazo_str = payload.get("plazo_texto")
    plazo_val = payload.get("plazo_ejecucion", 1)
    unidad_plazo = payload.get("unidad_plazo", "MESES")
    tipo_persona = payload.get("tipo_persona", "NATURAL")

    contratista_res = build_obligaciones_contratista(
        objeto=objeto,
        tipologia=tipologia,
        items_propuesta=items,
        contexto_adicional=contexto,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )

    empresa_res = build_obligaciones_empresa(
        objeto=objeto,
        tipologia=tipologia,
        plazo_str=plazo_str,
        plazo_val=plazo_val,
        unidad_plazo=unidad_plazo,
        tipo_persona=tipo_persona,
        obligaciones_contratista=contratista_res["obligaciones_minuta"],
        contexto_adicional=contexto,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )

    return {
        "obligaciones_especificas": contratista_res["obligaciones_especificas"],
        "obligaciones_generales": contratista_res["obligaciones_generales"],
        "obligaciones_estudio_previo": contratista_res["obligaciones_estudio_previo"],
        "obligaciones_minuta": contratista_res["obligaciones_minuta"],
        "obligaciones_empresa": empresa_res
    }

@router.post("/generate-objeto", response_model=ObjetoGenerationResult)
def generate_objeto_contractual(
    payload: ObjetoGenerationInput,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Agente especializado que formula automáticamente el Objeto Contractual en infinitivo
    a partir del Estudio de Mercado, Propuesta Económica y tipología, permitiendo al usuario
    su posterior modificación libre a su gusto.
    """
    try:
        result = object_agent.generate_objeto(payload, db=db, override_api_key=api_key)
        return result
    except Exception as e:
        logger.error(f"Error generando objeto contractual: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al formular el objeto: {str(e)}"
        )

@router.post("/generate-risk-matrix", response_model=RiskMatrixResult)
def generate_risk_matrix_endpoint(
    payload: RiskMatrixInput,
    api_key: Optional[str] = Query(None, description="API Key opcional de Gemini"),
    db: Session = Depends(get_db)
):
    """
    Agente Especialista en Matrices de Riesgos Contractuales (ESPY S.A. E.S.P. & CCE).
    Evalúa insumos del estudio previo, advierte vacíos, tipifica 14 columnas CCE,
    garantiza consistencia aritmética absoluta (Valoración = P + I)
    y almacena la matriz en metadatos del contrato si se suministra `contrato_id`.
    """
    try:
        result = risk_agent.generate_risk_matrix(payload, db=db, override_api_key=api_key)

        # Si viene asociado a un contrato existente, almacenar en BD
        if payload.contrato_id:
            contract = db.query(Contrato).filter(Contrato.id == payload.contrato_id).first()
            if contract:
                current_meta = contract.metadatos_agente or {}
                current_meta["matriz_riesgos"] = result.model_dump()
                contract.metadatos_agente = current_meta

                audit = Auditoria(
                    contrato_id=contract.id,
                    accion="GENERACION_MATRIZ_RIESGOS",
                    detalle=f"Matriz de riesgos CCE generada por {result.agente_nombre} ({result.total_riesgos} riesgos).",
                    usuario="Agente Especialista de Riesgos"
                )
                db.add(audit)
                db.commit()
                logger.info(f"Matriz de riesgos asociada al contrato ID {contract.id}")

        return result
    except Exception as e:
        logger.error(f"Error generando matriz de riesgos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al estructurar matriz de riesgos: {str(e)}"
        )

@router.post("/generate-risk-matrix-docx")
def generate_risk_matrix_docx_endpoint(
    payload: RiskMatrixResult,
    db: Session = Depends(get_db)
):
    """
    Genera y descarga el documento oficial de la Matriz de Riesgos en formato DOCX
    con orientación horizontal (Landscape), tablas estilizadas CCE, encabezado ESPY y firmas oficiales.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"Matriz_Riesgos_ESPY_{timestamp}.docx"
        output_path = settings.GENERATED_DIR / safe_name

        risk_agent.generate_docx(payload, output_path)

        return FileResponse(
            path=str(output_path),
            filename=safe_name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        logger.error(f"Error generando DOCX de matriz de riesgos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando archivo DOCX de matriz de riesgos: {str(e)}"
        )

@router.post("/generate-risk-matrix-pdf")
def generate_risk_matrix_pdf_endpoint(
    payload: RiskMatrixResult,
    db: Session = Depends(get_db)
):
    """
    Genera y descarga el documento oficial de la Matriz de Riesgos en formato PDF Horizontal (Landscape)
    con membrete corporativo, marcas de agua, logo oficial ESPY, tablas estilizadas CCE y firmas oficiales.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"Matriz_Riesgos_ESPY_{timestamp}.pdf"
        output_path = settings.GENERATED_DIR / safe_name

        risk_agent.generate_pdf(payload, output_path)

        return FileResponse(
            path=str(output_path),
            filename=safe_name,
            media_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Error generando PDF de matriz de riesgos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generando archivo PDF de matriz de riesgos: {str(e)}"
        )

@router.post("/upload-letterhead-logo")
async def upload_letterhead_logo_endpoint(
    file: UploadFile = File(...)
):
    """
    Permite cargar un logotipo o membrete personalizado en imagen (PNG, JPG, JPEG)
    para ser utilizado en la generación de matrices de riesgos oficiales.
    """
    try:
        ext = Path(file.filename).suffix.lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de imagen no soportado. Por favor suba un archivo PNG, JPG o JPEG."
            )

        logos_dir = settings.STORAGE_DIR / "uploads" / "custom_logos"
        logos_dir.mkdir(parents=True, exist_ok=True)
        unique_name = f"logo_{uuid.uuid4().hex[:8]}{ext}"
        saved_path = logos_dir / unique_name

        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Relativo para portabilidad
        rel_path = str(saved_path.relative_to(settings.BASE_DIR)).replace("\\", "/")

        return {
            "success": True,
            "filename": file.filename,
            "logo_path": str(saved_path),
            "logo_url": f"/{rel_path}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subiendo logotipo de membrete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error procesando imagen de membrete: {str(e)}"
        )

class ParseRiskDocumentResponse(BaseModel):
    document_id: int
    nombre_archivo: str
    texto_extraido: str
    objeto_detectado: Optional[str] = None
    tipologia_detectada: Optional[str] = None
    contratista_detectado: Optional[str] = None
    valor_detectado: Optional[float] = None
    plazo_detectado: Optional[str] = None
    polizas_detectada: Optional[bool] = None

@router.post("/upload-and-parse-risk-document", response_model=ParseRiskDocumentResponse)
async def upload_and_parse_risk_document_endpoint(
    file: UploadFile = File(...),
    contrato_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Recibe un archivo PDF o Word del Estudio Previo o Términos de Referencia,
    lo registra en el repositorio del contrato y extrae inteligentemente su texto
    junto con los parámetros clave para precargar la Matriz de Riesgos CCE.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo inválido."
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in {".pdf", ".docx", ".doc"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato no permitido ({file_ext}). Solo se admiten archivos PDF o Word (.docx/.doc)."
        )

    unique_prefix = uuid.uuid4().hex[:10]
    safe_filename = f"{unique_prefix}_{Path(file.filename).name}"
    target_path = settings.UPLOADS_DIR / safe_filename

    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_size = os.path.getsize(target_path)
    except Exception as e:
        logger.error(f"Error guardando documento de riesgos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error guardando el archivo en disco: {str(e)}"
        )
    finally:
        await file.close()

    relative_path = str(target_path.relative_to(settings.BASE_DIR))
    db_doc = Documento(
        contrato_id=contrato_id,
        tipo_documento=TipoDocumento.OTRO,
        categoria=CategoriaDocumento.SOPORTE_CONTRATISTA,
        nombre_archivo_original=file.filename,
        nombre_archivo_almacenado=safe_filename,
        ruta_relativa=relative_path,
        mime_type=file.content_type,
        tamano_bytes=file_size
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)

    # Extraer texto del documento (PDF digital o con OCR local rápido si es escaneado)
    txt = parse_document_text(target_path) or ""

    # Detección inteligente de parámetros
    obj_detectado = None
    obj_m = re.search(r"OBJETO\s*:\s*([^\n\r]+(?:\n[^\n\r]+)?)", txt, re.IGNORECASE)
    if obj_m:
        raw_obj = obj_m.group(1).strip()
        raw_obj = re.sub(r'["\']', '', raw_obj)
        raw_obj = re.sub(r"\bgenti[oó]n\b", "GESTIÓN", raw_obj, flags=re.IGNORECASE)
        raw_obj = re.sub(r"\bconplementarias\b", "COMPLEMENTARIAS", raw_obj, flags=re.IGNORECASE)
        raw_obj = re.sub(r"\s+TIPO\s+DE\s+CONTRATO.*", "", raw_obj, flags=re.IGNORECASE).strip()
        obj_detectado = raw_obj.upper()

    contratista_detectado = None
    cont_m = re.search(r"propuesta\s+(?:suministrada|presentada)\s+por\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{4,40})", txt, re.IGNORECASE)
    if not cont_m:
        cont_m = re.search(r"contratista\s*:\s*([A-ZÁÉÍÓÚÑa-záéíóúñ\s]{4,40})", txt, re.IGNORECASE)
    if cont_m:
        cand_cont = cont_m.group(1).strip()
        cand_cont = re.sub(r"\s+(?:el\s+alcance|con|de|en)\b.*", "", cand_cont, flags=re.IGNORECASE).strip()
        contratista_detectado = cand_cont.upper()

    valor_detectado = None
    val_m = re.search(r"(?:VALOR\s+DEL\s+PRESUPUESTO|PRESUPUESTO\s+OFICIAL|CDP[^\n]*)\$?[\s]*([0-9]{1,3}(?:\.[0-9]{3})+)", txt, re.IGNORECASE)
    if not val_m:
        val_m = re.search(r"\$\s*([0-9]{1,3}(?:\.[0-9]{3})+)\b", txt)
    if val_m:
        raw_v = val_m.group(1).replace(".", "")
        try:
            valor_detectado = float(raw_v)
        except Exception:
            pass

    plazo_detectado = None
    plz_m = re.search(r"PLAZO\s*(?:DE\s*EJECUCI[OÓ]N)?\s*:\s*([0-9]+\s*(?:meses|d[ií]as|mes|d[ií]a))", txt, re.IGNORECASE)
    if plz_m:
        plazo_detectado = plz_m.group(1).strip()

    tipologia_detectada = "PRESTACION_SERVICIOS"
    if re.search(r"CONTRATO\s+DE\s+OBRA|tipo\s+de\s+contrato\s*:\s*obra", txt, re.IGNORECASE):
        tipologia_detectada = "OBRA"
    elif re.search(r"CONTRATO\s+DE\s+SUMINISTRO|tipo\s+de\s+contrato\s*:\s*suministro", txt, re.IGNORECASE):
        tipologia_detectada = "SUMINISTRO"
    elif re.search(r"PRESTACI[OÓ]N\s+DE\s+SERVICIOS", txt, re.IGNORECASE):
        tipologia_detectada = "PRESTACION_SERVICIOS"

    polizas_detectada = True
    if re.search(r"no\s+se\s+requerir[aá]\s+(?:la\s+constituci[oó]n\s+de\s+)?p[oó]lizas|no\s+se\s+exigen\s+garant[ií]as", txt, re.IGNORECASE):
        polizas_detectada = False

    return ParseRiskDocumentResponse(
        document_id=db_doc.id,
        nombre_archivo=file.filename,
        texto_extraido=txt[:25000],
        objeto_detectado=obj_detectado,
        tipologia_detectada=tipologia_detectada,
        contratista_detectado=contratista_detectado,
        valor_detectado=valor_detectado,
        plazo_detectado=plazo_detectado,
        polizas_detectada=polizas_detectada
    )



