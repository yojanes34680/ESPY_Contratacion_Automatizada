"""Contract endpoints router."""
import os
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func

from app.database import get_db
from app.models.contract import Contrato, TipologiaContrato, ModalidadSeleccion, EstadoContrato, UnidadPlazo
from app.models.contractor import Contratista
from app.models.audit_log import Auditoria
from app.models.vigencia import VigenciaFiscal
from app.schemas.contract import (
    ContratoCreate,
    ContratoRead,
    ContratoUpdate,
    ContratoStatusUpdate,
    ContratoAnulacionRequest,
    ContratoAdicionUpdate,
    ContratoObjetoUpdate,
    ContratoNumeroUpdate,
    BatchRefreshNecesidadInput,
    BatchRefreshNecesidadResult,
    TipologiaCatalogoItem,
    VigenciaFiscalCreate,
    VigenciaFiscalRead,
    ConsecutivoSugeridoRead,
)
from app.utils.num_to_words import numero_a_letras_cop
from app.utils.objective_normalizer import normalize_objetivos_especificos
from app.utils.object_normalizer import normalize_objeto_contractual
from app.utils.contract_prefix_helper import normalize_contract_code, get_required_prefix
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario, RolUsuario

router = APIRouter(prefix="/contracts", tags=["Contratos"])

@router.get("/catalogs/typologies", response_model=List[TipologiaCatalogoItem])
def get_typologies_catalog():
    """Catálogo normativo de tipologías contractuales para ESP."""
    return [
        TipologiaCatalogoItem(
            codigo=TipologiaContrato.PRESTACION_SERVICIOS.value,
            nombre="Prestación de Servicios Profesionales y de Apoyo a la Gestión",
            descripcion="Contratos con personas naturales o jurídicas para labores calificadas o de soporte institucional.",
            enfoque_normativo="Autonomía técnica y directiva, sin subordinación laboral, honorarios y pago contra informe de actividades y parafiscales.",
            agente_responsable="Agente de Prestación de Servicios"
        ),
        TipologiaCatalogoItem(
            codigo=TipologiaContrato.OBRA.value,
            nombre="Contratos de Obra e Infraestructura",
            descripcion="Construcción, mantenimiento, adecuación o reparación de infraestructura de acueducto, alcantarillado, plantas y redes.",
            enfoque_normativo="Cronograma, AIU, pólizas de estabilidad, supervisión/interventoría técnica y seguridad y salud en el trabajo (SST).",
            agente_responsable="Agente de Contratos de Obra"
        ),
        TipologiaCatalogoItem(
            codigo=TipologiaContrato.SUMINISTRO.value,
            nombre="Contratos de Suministro y Adquisición de Bienes",
            descripcion="Adquisición de insumos químicos (cloro, sulfato), tuberías, micromedidores, herramientas y materiales de operación.",
            enfoque_normativo="Fichas técnicas, condiciones de entrega en almacén de la ESP, recibo a satisfacción y garantías de calidad/fábrica.",
            agente_responsable="Agente de Contratos de Suministro"
        ),
        TipologiaCatalogoItem(
            codigo=TipologiaContrato.CONSULTORIA.value,
            nombre="Consultoría y Estudios Técnicos",
            descripcion="Estudios de diseño hidráulico, planes maestros de acueducto, consultorías ambientales y tarifarias.",
            enfoque_normativo="Entregables técnicos por fases, derechos patrimoniales de autor e informes periciales.",
            agente_responsable="Agente de Prestación de Servicios (Especializado)"
        ),
        TipologiaCatalogoItem(
            codigo=TipologiaContrato.ARRENDAMIENTO.value,
            nombre="Contratos de Arrendamiento (Arriendo de Inmuebles)",
            descripcion="Arrendamiento de bienes inmuebles, bodegas, oficinas operativas o predios para el servicio de la ESP.",
            enfoque_normativo="Código Civil (Art. 1973+), canon de arrendamiento periódico, acta de entrega material e inventario de instalaciones.",
            agente_responsable="Agente de Prestación de Servicios / Jurídico"
        ),
    ]

@router.get("/catalogs/modalities")
def get_modalities_catalog():
    """Catálogo de modalidades de selección conforme al régimen de la ESP (Ley 142 de 1994)."""
    return [
        {
            "codigo": ModalidadSeleccion.CONTRATACION_DIRECTA.value,
            "nombre": "Contratación Directa",
            "descripcion": "Aplicable para servicios profesionales, exclusividad de proveedor, o menor cuantía según Manual Interno."
        },
        {
            "codigo": ModalidadSeleccion.INVITACION_PRIVADA.value,
            "nombre": "Invitación Privada",
            "descripcion": "Solicitud de ofertas a una pluralidad de oferentes calificados preseleccionados."
        },
        {
            "codigo": ModalidadSeleccion.INVITACION_PUBLICA.value,
            "nombre": "Invitación Pública / Convocatoria Abierta",
            "descripcion": "Convocatoria abierta para proyectos de infraestructura o suministros de mayor cuantía."
        },
        {
            "codigo": ModalidadSeleccion.MINIMA_CUANTIA.value,
            "nombre": "Mínima Cuantía",
            "descripcion": "Adquisiciones ágiles de bienes y servicios por debajo del umbral del Manual de Contratación."
        }
    ]

@router.post("", response_model=ContratoRead, status_code=status.HTTP_201_CREATED)
def create_contract(
    contract_in: ContratoCreate, 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Crea un nuevo contrato validando la existencia del contratista y calculando valor en letras."""
    # Validar contratista existente
    contractor = db.query(Contratista).filter(Contratista.id == contract_in.contratista_id).first()
    if not contractor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El contratista con ID {contract_in.contratista_id} no existe en el sistema."
        )

    contract_data = contract_in.model_dump()

    # Normalizar número de contrato aplicando la nomenclatura oficial por tipología (CPS, CS, CA, CO)
    if contract_data.get("numero_contrato"):
        contract_data["numero_contrato"] = normalize_contract_code(
            contract_data["numero_contrato"],
            contract_data.get("tipologia"),
            contract_data.get("vigencia")
        )

    # Validar número de contrato único
    existing = db.query(Contrato).filter(Contrato.numero_contrato == contract_data["numero_contrato"]).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un contrato registrado con el número '{contract_data['numero_contrato']}'."
        )

    # Si no se pasó el valor en letras, se calcula automáticamente
    if not contract_data.get("valor_en_letras") and contract_data.get("valor_total"):
        contract_data["valor_en_letras"] = numero_a_letras_cop(contract_data["valor_total"])

    # Normalizar objeto contractual para que esté en mayúsculas sostenidas
    if contract_data.get("objeto"):
        contract_data["objeto"] = normalize_objeto_contractual(contract_data["objeto"], contract_data.get("tipologia"))

    # Normalizar objetivos específicos para que inicien con verbo en infinitivo
    if contract_data.get("objetivos_especificos"):
        contract_data["objetivos_especificos"] = normalize_objetivos_especificos(contract_data["objetivos_especificos"])

    # Higienizar cdp_texto_completo si viene en metadatos_agente
    if contract_data.get("metadatos_agente") and isinstance(contract_data["metadatos_agente"], dict):
        if contract_data["metadatos_agente"].get("cdp_texto_completo"):
            from app.utils.cdp_cleaner import limpiar_texto_cdp
            contract_data["metadatos_agente"]["cdp_texto_completo"] = limpiar_texto_cdp(
                contract_data["metadatos_agente"]["cdp_texto_completo"]
            )

    # Auto-generar descripción de la necesidad si no fue proporcionada o viene vacía
    if not contract_data.get("justificacion_necesidad") or not str(contract_data["justificacion_necesidad"]).strip():
        from app.utils.necesidad_builder import build_descripcion_necesidad
        contract_data["justificacion_necesidad"] = build_descripcion_necesidad(
            objeto=contract_data.get("objeto", ""),
            tipologia=contract_data.get("tipologia", "PRESTACION_SERVICIOS")
        )


    db_obj = Contrato(**contract_data)
    db.add(db_obj)
    db.flush()

    # Auto-registrar vigencia en VigenciaFiscal si no existe aún
    v_year = db_obj.vigencia
    if v_year:
        v_exists = db.query(VigenciaFiscal).filter(VigenciaFiscal.year == v_year).first()
        if not v_exists:
            v_new = VigenciaFiscal(
                year=v_year,
                nombre=f"Vigencia Fiscal {v_year}",
                descripcion=f"Contratación Oficial ESP Yolombó - Vigencia {v_year}",
                presupuesto_base=0.0,
                estado="ABIERTA",
                es_vigencia_actual=False
            )
            db.add(v_new)

    # Registro de auditoría
    audit = Auditoria(
        contrato_id=db_obj.id,
        accion="CREACION_CONTRATO",
        detalle=f"Contrato {db_obj.numero_contrato} (Vigencia {db_obj.vigencia}) creado bajo tipología {db_obj.tipologia.value} para {contractor.nombre_o_razon_social}.",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(db_obj)

    # Sincronización automática con Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(db_obj)
        logger.info(f"Contrato {db_obj.numero_contrato} sincronizado en Matriz Excel al ser creado.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar contrato {db_obj.numero_contrato} en Excel: {e}")

    logger.info(f"Contrato creado: ID {db_obj.id} - {db_obj.numero_contrato}")
    return db_obj

@router.get("", response_model=List[ContratoRead])
def list_contracts(
    tipologia: Optional[TipologiaContrato] = None,
    estado: Optional[EstadoContrato] = None,
    vigencia: Optional[int] = None,
    contratista_id: Optional[int] = None,
    ocultar_anulados: bool = Query(False, description="Si es True, oculta los contratos en estado ANULADO"),
    query: Optional[str] = Query(None, description="Buscar por número de contrato, objeto, contratista o documento"),
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db)
):
    """Lista contratos con filtros avanzados, carga de contratista y paginación."""
    # Verificar y actualizar automáticamente contratos cuya fecha de terminación ya venció
    try:
        from app.services.contract_lifecycle import check_and_update_expired_contracts
        check_and_update_expired_contracts(db, sync_excel=True)
    except Exception as e:
        logger.warning(f"No se pudo ejecutar la actualización automática de vencimiento: {e}")

    q = db.query(Contrato).options(joinedload(Contrato.contratista))

    if ocultar_anulados:
        q = q.filter(Contrato.estado != EstadoContrato.ANULADO)
    if tipologia:
        q = q.filter(Contrato.tipologia == tipologia)
    if estado:
        q = q.filter(Contrato.estado == estado)
    if vigencia:
        q = q.filter(Contrato.vigencia == vigencia)
    if contratista_id:
        q = q.filter(Contrato.contratista_id == contratista_id)
    if query and isinstance(query, str):
        search = f"%{query.strip()}%"
        q = q.outerjoin(Contrato.contratista).filter(
            or_(
                Contrato.numero_contrato.ilike(search),
                Contrato.objeto.ilike(search),
                Contrato.supervisor_nombre.ilike(search),
                Contratista.nombre_o_razon_social.ilike(search),
                Contratista.numero_documento.ilike(search)
            )
        )

    return q.order_by(Contrato.numero_contrato.asc()).offset(skip).limit(limit).all()

# -------------------------------------------------------------
# GESTIÓN MULTI-VIGENCIA Y CONSECUTIVOS INTELIGENTES
# -------------------------------------------------------------
TIPOLOGIA_PREFIXES = {
    TipologiaContrato.PRESTACION_SERVICIOS: "CPS",
    TipologiaContrato.SUMINISTRO: "CS",
    TipologiaContrato.OBRA: "CO",
    TipologiaContrato.ARRENDAMIENTO: "CA",
    TipologiaContrato.CONSULTORIA: "CC",
    TipologiaContrato.INTERVENTORIA: "CI",
}

@router.get("/vigencias", response_model=List[VigenciaFiscalRead])
def list_vigencias(db: Session = Depends(get_db)):
    """
    Lista todas las vigencias fiscales configuradas y detectadas en la base de datos,
    con el conteo de contratos y valor total contratado en cada una.
    """
    db_vigencias = db.query(VigenciaFiscal).all()
    vigencia_years = {v.year: v for v in db_vigencias}

    # Detectar años presentes en contratos
    contract_years = db.query(Contrato.vigencia).distinct().all()
    contract_years = [y[0] for y in contract_years if y[0]]

    # Si no hay vigencias en DB y hay contratos o es la primera vez, crear 2026
    if not db_vigencias:
        base_years = set(contract_years) if contract_years else {2026}
        for y in sorted(base_years):
            v_obj = VigenciaFiscal(
                year=y,
                nombre=f"Vigencia Fiscal {y}",
                descripcion=f"Contratación Oficial ESP Yolombó - Vigencia {y}",
                presupuesto_base=0.0,
                estado="ABIERTA",
                es_vigencia_actual=(y == 2026 if 2026 in base_years else True)
            )
            db.add(v_obj)
            vigencia_years[y] = v_obj
        db.commit()
    else:
        # Si hay años en contratos que no están en vigencia_years, agregarlos
        created_any = False
        for y in contract_years:
            if y not in vigencia_years:
                v_obj = VigenciaFiscal(
                    year=y,
                    nombre=f"Vigencia Fiscal {y}",
                    descripcion=f"Contratación Oficial ESP Yolombó - Vigencia {y}",
                    presupuesto_base=0.0,
                    estado="ABIERTA",
                    es_vigencia_actual=False
                )
                db.add(v_obj)
                vigencia_years[y] = v_obj
                created_any = True
        if created_any:
            db.commit()

    # Re-consultar todas
    all_vigencias = db.query(VigenciaFiscal).order_by(VigenciaFiscal.year.desc()).all()
    results = []
    for v in all_vigencias:
        total_c = db.query(func.count(Contrato.id)).filter(Contrato.vigencia == v.year).scalar() or 0
        total_val = db.query(func.sum(Contrato.valor_total)).filter(Contrato.vigencia == v.year).scalar() or 0.0
        results.append(
            VigenciaFiscalRead(
                year=v.year,
                nombre=v.nombre,
                descripcion=v.descripcion,
                presupuesto_base=v.presupuesto_base or 0.0,
                estado=v.estado or "ABIERTA",
                es_vigencia_actual=bool(v.es_vigencia_actual),
                total_contratos=total_c,
                valor_total_contratado=float(total_val),
                created_at=v.created_at
            )
        )
    return results

@router.post("/vigencias", response_model=VigenciaFiscalRead, status_code=status.HTTP_201_CREATED)
def create_vigencia(
    data_in: VigenciaFiscalCreate, 
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """
    Apertura una nueva era de contratación / vigencia fiscal (ej: 2027),
    permitiendo contratar inmediatamente a todos los contratistas del sistema.
    """
    existing = db.query(VigenciaFiscal).filter(VigenciaFiscal.year == data_in.year).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"La vigencia fiscal {data_in.year} ya se encuentra registrada en el sistema."
        )

    # Si se marca como vigencia actual, desmarcar las anteriores
    if data_in.es_vigencia_actual:
        db.query(VigenciaFiscal).update({VigenciaFiscal.es_vigencia_actual: False})

    nombre = data_in.nombre or f"Vigencia Fiscal {data_in.year}"
    descripcion = data_in.descripcion or f"Era de Contratación Anual ESP Yolombó - Vigencia {data_in.year}"

    v_obj = VigenciaFiscal(
        year=data_in.year,
        nombre=nombre,
        descripcion=descripcion,
        presupuesto_base=data_in.presupuesto_base or 0.0,
        estado=data_in.estado or "ABIERTA",
        es_vigencia_actual=bool(data_in.es_vigencia_actual)
    )
    db.add(v_obj)

    audit = Auditoria(
        accion="APERTURA_VIGENCIA",
        detalle=f"Aperturada nueva vigencia fiscal {v_obj.year} ({v_obj.nombre}). Base presupuestal: ${v_obj.presupuesto_base:,.0f} COP.",
        usuario=_admin.nombre_completo if _admin else "Administrador",
        usuario_documento=_admin.documento if _admin else None,
        usuario_nombre=_admin.nombre_completo if _admin else None
    )
    db.add(audit)
    db.commit()
    db.refresh(v_obj)

    total_c = db.query(func.count(Contrato.id)).filter(Contrato.vigencia == v_obj.year).scalar() or 0
    total_val = db.query(func.sum(Contrato.valor_total)).filter(Contrato.vigencia == v_obj.year).scalar() or 0.0

    logger.info(f"Nueva vigencia fiscal creada: {v_obj.year} - {v_obj.nombre}")
    return VigenciaFiscalRead(
        year=v_obj.year,
        nombre=v_obj.nombre,
        descripcion=v_obj.descripcion,
        presupuesto_base=v_obj.presupuesto_base or 0.0,
        estado=v_obj.estado or "ABIERTA",
        es_vigencia_actual=bool(v_obj.es_vigencia_actual),
        total_contratos=total_c,
        valor_total_contratado=float(total_val),
        created_at=v_obj.created_at
    )

@router.patch("/vigencias/{year}/activate", response_model=VigenciaFiscalRead)
def activate_vigencia(
    year: int, 
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """Conmuta una vigencia fiscal para convertirla en la vigencia activa por defecto."""
    v_obj = db.query(VigenciaFiscal).filter(VigenciaFiscal.year == year).first()
    if not v_obj:
        v_obj = VigenciaFiscal(
            year=year,
            nombre=f"Vigencia Fiscal {year}",
            descripcion=f"Contratación Oficial ESP Yolombó - Vigencia {year}",
            presupuesto_base=0.0,
            estado="ABIERTA",
            es_vigencia_actual=True
        )
        db.add(v_obj)

    db.query(VigenciaFiscal).update({VigenciaFiscal.es_vigencia_actual: False})
    v_obj.es_vigencia_actual = True
    db.commit()
    db.refresh(v_obj)

    total_c = db.query(func.count(Contrato.id)).filter(Contrato.vigencia == v_obj.year).scalar() or 0
    total_val = db.query(func.sum(Contrato.valor_total)).filter(Contrato.vigencia == v_obj.year).scalar() or 0.0

    logger.info(f"Vigencia fiscal activa conmutada a: {year}")
    return VigenciaFiscalRead(
        year=v_obj.year,
        nombre=v_obj.nombre,
        descripcion=v_obj.descripcion,
        presupuesto_base=v_obj.presupuesto_base or 0.0,
        estado=v_obj.estado or "ABIERTA",
        es_vigencia_actual=True,
        total_contratos=total_c,
        valor_total_contratado=float(total_val),
        created_at=v_obj.created_at
    )

@router.get("/next-number", response_model=ConsecutivoSugeridoRead)
def get_next_contract_number(
    vigencia: int = Query(..., description="Año de la vigencia fiscal para el contrato"),
    tipologia: Optional[TipologiaContrato] = None,
    db: Session = Depends(get_db)
):
    """
    Calcula y sugiere el siguiente número consecutivo de contrato para una vigencia y tipología dada.
    Ejemplo: 'CPS-001-2027', 'CS-002-2027', 'CO-003-2027'.
    """
    prefix = get_required_prefix(tipologia)

    # Buscar todos los contratos de esta vigencia
    contratos = db.query(Contrato.numero_contrato).filter(Contrato.vigencia == vigencia).all()

    max_consecutivo = 0
    for (num_str,) in contratos:
        if not num_str:
            continue
        # Intento 1: coincidencia exacta -(\d+)-{vigencia}
        m1 = re.search(r'-(\d+)-' + str(vigencia), str(num_str))
        if m1:
            try:
                val = int(m1.group(1))
                if val > max_consecutivo:
                    max_consecutivo = val
                continue
            except ValueError:
                pass

        # Intento 2: cualquier número que no sea el año de la vigencia ni años recientes
        digits = re.findall(r'\d+', str(num_str))
        for d in digits:
            if d != str(vigencia) and not re.match(r'^20\d\d$', d):
                try:
                    val = int(d)
                    if val > max_consecutivo:
                        max_consecutivo = val
                except ValueError:
                    pass

    siguiente = max_consecutivo + 1
    codigo_sugerido = f"{prefix}-{siguiente:03d}-{vigencia}"

    # Asegurar que el código sea único
    while db.query(Contrato).filter(Contrato.numero_contrato == codigo_sugerido).first():
        siguiente += 1
        codigo_sugerido = f"{prefix}-{siguiente:03d}-{vigencia}"

    return ConsecutivoSugeridoRead(
        sugerido=codigo_sugerido,
        consecutivo=siguiente,
        prefijo=prefix,
        vigencia=vigencia
    )

@router.get("/{contract_id}", response_model=ContratoRead)
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    """Obtiene el detalle completo de un contrato por su ID."""
    contract = db.query(Contrato).options(
        joinedload(Contrato.contratista),
        joinedload(Contrato.documentos)
    ).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )
    return contract

@router.put("/{contract_id}", response_model=ContratoRead)
def update_contract(
    contract_id: int, 
    update_data: ContratoUpdate, 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Actualiza la información de un contrato."""
    contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    old_numero = contract.numero_contrato

    # Normalizar número de contrato si fue indicado
    if update_data.numero_contrato:
        target_tip = update_data.tipologia or contract.tipologia
        update_data.numero_contrato = normalize_contract_code(
            update_data.numero_contrato, target_tip, contract.vigencia
        )

    # Validar número de contrato si fue cambiado
    if update_data.numero_contrato and update_data.numero_contrato != old_numero:
        duplicate = db.query(Contrato).filter(
            Contrato.numero_contrato == update_data.numero_contrato,
            Contrato.id != contract.id
        ).first()
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El número de contrato '{update_data.numero_contrato}' ya se encuentra en uso."
            )

    update_dict = update_data.model_dump(exclude_unset=True)

    # Recalcular valor en letras si se modificó el valor numérico y no se indicó letras
    if "valor_total" in update_dict and "valor_en_letras" not in update_dict:
        update_dict["valor_en_letras"] = numero_a_letras_cop(update_dict["valor_total"])

    # Normalizar objeto contractual si fue actualizado
    if "objeto" in update_dict and update_dict["objeto"]:
        tip = update_dict.get("tipologia") or (contract.tipologia.value if contract.tipologia else "PRESTACION_SERVICIOS")
        update_dict["objeto"] = normalize_objeto_contractual(update_dict["objeto"], tip)

    # Normalizar objetivos específicos si fueron actualizados
    if "objetivos_especificos" in update_dict and update_dict["objetivos_especificos"]:
        update_dict["objetivos_especificos"] = normalize_objetivos_especificos(update_dict["objetivos_especificos"])

    # Combinar metadatos_agente preservando claves existentes si se actualiza
    if "metadatos_agente" in update_dict and isinstance(update_dict["metadatos_agente"], dict):
        current_meta = dict(contract.metadatos_agente or {})
        current_meta.update(update_dict["metadatos_agente"])
        if current_meta.get("cdp_texto_completo"):
            from app.utils.cdp_cleaner import limpiar_texto_cdp
            current_meta["cdp_texto_completo"] = limpiar_texto_cdp(current_meta["cdp_texto_completo"])
        update_dict["metadatos_agente"] = current_meta


    for key, value in update_dict.items():
        setattr(contract, key, value)

    # Auto-corrección de inconsistencia en justificación de la necesidad:
    # Si el contrato es SUMINISTRO y la justificación menciona "planta de personal", o cambiaron tipología u objeto
    eff_tip = contract.tipologia.value if contract.tipologia else "PRESTACION_SERVICIOS"
    current_just = contract.justificacion_necesidad or ""
    is_sum = "SUMINISTRO" in eff_tip or any(k in eff_tip for k in ["COMPRAVENTA", "BIENES"])
    has_labor_inconsistency = is_sum and any(
        p in current_just.lower() for p in ["planta de personal", "recurso humano suficiente", "contratar servicios de apoyo"]
    )
    if ("tipologia" in update_dict or "objeto" in update_dict or has_labor_inconsistency):
        if is_sum and (has_labor_inconsistency or "tipologia" in update_dict):
            from app.utils.necesidad_builder import build_descripcion_necesidad
            contract.justificacion_necesidad = build_descripcion_necesidad(
                objeto=contract.objeto or "",
                tipologia=eff_tip,
                contexto_adicional=current_just or None
            )

    # Auditoría
    audit = Auditoria(
        contrato_id=contract.id,
        accion="ACTUALIZACION_CONTRATO",
        detalle=f"Campos actualizados: {', '.join(update_dict.keys())}",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # Si se modificó el número de contrato, limpiar el código anterior en Excel y renombrar soportes
    if "numero_contrato" in update_dict and contract.numero_contrato != old_numero:
        try:
            from app.services.excel_engine import delete_contract_from_master_excel
            delete_contract_from_master_excel(old_numero)
        except Exception as e_del:
            logger.warning(f"Aviso al limpiar código anterior en Excel: {e_del}")

        # Renombrar documentos físicos si tenían el número anterior
        try:
            from app.models.document import Documento
            from app.config import settings
            docs = db.query(Documento).filter(Documento.contrato_id == contract.id).all()
            for d in docs:
                if old_numero in (d.nombre_archivo_original or ""):
                    new_orig = d.nombre_archivo_original.replace(old_numero, contract.numero_contrato)
                    new_stored = (d.nombre_archivo_almacenado or "").replace(old_numero, contract.numero_contrato)
                    new_rel = (d.ruta_relativa or "").replace(old_numero, contract.numero_contrato)
                    if d.ruta_relativa:
                        old_p = settings.BASE_DIR / d.ruta_relativa
                        new_p = settings.BASE_DIR / new_rel
                        if old_p.exists():
                            old_p.rename(new_p)
                    d.nombre_archivo_original = new_orig
                    d.nombre_archivo_almacenado = new_stored
                    d.ruta_relativa = new_rel
            db.commit()
        except Exception as e_docs:
            logger.warning(f"Aviso al renombrar documentos de contrato {contract.numero_contrato}: {e_docs}")

    # Sincronizar inmediatamente con la Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
        logger.info(f"Contrato {contract.numero_contrato} sincronizado en Excel tras actualización.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar contrato {contract.numero_contrato} en Excel tras actualización: {e}")

    logger.info(f"Contrato ID {contract_id} actualizado.")
    return contract

@router.patch("/{contract_id}/status", response_model=ContratoRead)
def update_contract_status(
    contract_id: int, 
    status_in: ContratoStatusUpdate, 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Actualiza el estado del contrato en el flujo contractual con trazabilidad."""
    contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    estado_anterior = contract.estado.value
    nuevo_estado_val = status_in.nuevo_estado.value

    # Grafo de transiciones permitidas según el Prompt 4:
    # BORRADOR → EN_REVISION; EN_REVISION → APROBADO o BORRADOR; APROBADO → EN_EJECUCION;
    # EN_EJECUCION → SUSPENDIDO o TERMINADO; SUSPENDIDO → EN_EJECUCION; TERMINADO → LIQUIDADO;
    # cualquiera → ANULADO (por el endpoint de anulación).
    TRANSICIONES_PERMITIDAS = {
        "BORRADOR": ["EN_REVISION"],
        "EN_REVISION": ["APROBADO", "BORRADOR"],
        "APROBADO": ["EN_EJECUCION"],
        "EN_EJECUCION": ["SUSPENDIDO", "TERMINADO"],
        "SUSPENDIDO": ["EN_EJECUCION"],
        "TERMINADO": ["LIQUIDADO"],
        "LIQUIDADO": [],
        "ANULADO": []
    }

    es_admin = _user and (
        _user.rol == RolUsuario.ADMIN or 
        (hasattr(_user.rol, "value") and _user.rol.value == "ADMIN") or 
        str(_user.rol) == "ADMIN"
    )

    es_transicion_valida = nuevo_estado_val in TRANSICIONES_PERMITIDAS.get(estado_anterior, [])

    if not es_transicion_valida:
        # Una transición fuera de la lista solo la puede hacer un ADMIN y con observación obligatoria
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Transición no permitida: No se puede cambiar el estado de '{estado_anterior}' a '{nuevo_estado_val}'. "
                    f"Esta acción excepcional requiere permisos de Administrador y justificación obligatoria."
                )
            )
        if not status_in.observacion or len(status_in.observacion.strip()) < 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Para realizar una transición excepcional de estado, debe ingresar una observación justificativa obligatoria."
            )

    contract.estado = status_in.nuevo_estado

    meta = dict(contract.metadatos_agente or {})
    # Si un contrato vuelve a EN_EJECUCION por un cambio manual, borra manual_status_override para que la regla de vencimiento vuelva a aplicarse
    if nuevo_estado_val == "EN_EJECUCION":
        meta.pop("manual_status_override", None)
        meta.pop("manual_status_updated_at", None)
    else:
        meta["manual_status_override"] = True
        meta["manual_status_updated_at"] = datetime.now().isoformat()

    contract.metadatos_agente = meta
    contract.updated_at = datetime.now()

    obs_texto = f" - Obs: {status_in.observacion}" if status_in.observacion else ""
    if not es_transicion_valida:
        tipo_accion = "TRANSICION_EXCEPCIONAL"
        detalle_audit = f"Transición excepcional de estado de {estado_anterior} a {nuevo_estado_val} autorizada por Administrador{obs_texto}"
    else:
        tipo_accion = "CAMBIO_ESTADO"
        detalle_audit = f"Estado contractual modificado de {estado_anterior} a {nuevo_estado_val}{obs_texto}"

    audit = Auditoria(
        contrato_id=contract.id,
        accion=tipo_accion,
        detalle=detalle_audit,
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # Sincronizar inmediatamente con la Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
        logger.info(f"Contrato {contract.numero_contrato} sincronizado en Excel tras cambio manual de estado a {contract.estado.value}.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar estado en Excel para {contract.numero_contrato}: {e}")

    logger.info(f"Contrato {contract.numero_contrato} cambió de {estado_anterior} a {status_in.nuevo_estado.value}")
    return contract

@router.post("/check-expired", response_model=Dict[str, Any])
def trigger_check_expired_contracts(
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Ejecuta la revisión y transición automática de contratos con fecha de terminación cumplida."""
    from app.services.contract_lifecycle import check_and_update_expired_contracts
    count = check_and_update_expired_contracts(db, sync_excel=True)
    return {
        "status": "success",
        "contratos_actualizados": count,
        "mensaje": f"Evaluación completada. {count} contratos actualizados automáticamente a TERMINADO."
    }

@router.patch("/{contract_id}/adicion", response_model=ContratoRead)
def update_contract_adicion(
    contract_id: int,
    data_in: ContratoAdicionUpdate,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Actualiza directamente el valor de la adición y recalcula el valor total y en letras del contrato."""
    contract = db.query(Contrato).options(joinedload(Contrato.contratista)).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    # Si no tenía valor inicial, fijarlo al valor actual antes de la adición
    if contract.valor_inicial is None:
        contract.valor_inicial = contract.valor_total - (contract.adicion_1 or 0.0)

    adicion_anterior = contract.adicion_1 or 0.0
    contract.adicion_1 = data_in.adicion_1
    contract.valor_total = (contract.valor_inicial or 0.0) + contract.adicion_1
    contract.valor_en_letras = numero_a_letras_cop(contract.valor_total)

    if data_in.prorroga_1 is not None:
        contract.prorroga_1 = data_in.prorroga_1

    # Si la adición se establece en 0, limpiar registros formales asociados de AdicionContrato
    if data_in.adicion_1 == 0.0:
        from app.models.contract_addition import AdicionContrato
        old_ads = db.query(AdicionContrato).filter(AdicionContrato.contrato_id == contract.id).all()
        for oa in old_ads:
            if oa.ruta_minuta_docx:
                try:
                    p = settings.BASE_DIR / oa.ruta_minuta_docx
                    if p.exists():
                        p.unlink()
                except Exception:
                    pass
            db.delete(oa)

    audit = Auditoria(
        contrato_id=contract.id,
        accion="EDICION_ADICION" if data_in.adicion_1 > 0 else "ELIMINACION_ADICION",
        detalle=f"Adición modificada de ${adicion_anterior:,.0f} a ${contract.adicion_1:,.0f}. Nuevo total: ${contract.valor_total:,.0f}",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # Sincronizar automáticamente con la Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
        logger.info(f"Contrato {contract.numero_contrato} sincronizado en Matriz Excel tras actualizar adición.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar contrato {contract.numero_contrato} en Excel tras adición: {e}")

    logger.info(f"Contrato {contract.numero_contrato}: adición actualizada a ${contract.adicion_1:,.0f} (Total: ${contract.valor_total:,.0f})")
    return contract

@router.patch("/{contract_id}/objeto", response_model=ContratoRead)
def update_contract_objeto(
    contract_id: int,
    data_in: ContratoObjetoUpdate,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Actualiza directamente el objeto contractual con normalización institucional y sincronización en Excel."""
    contract = db.query(Contrato).options(joinedload(Contrato.contratista)).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    clean_obj = data_in.objeto.strip()
    if not clean_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El objeto contractual no puede estar vacío."
        )

    tip = contract.tipologia.value if contract.tipologia else "PRESTACION_SERVICIOS"
    normalized_obj = normalize_objeto_contractual(clean_obj, tip)

    objeto_anterior = contract.objeto or ""
    contract.objeto = normalized_obj
    contract.updated_at = datetime.now()

    audit = Auditoria(
        contrato_id=contract.id,
        accion="EDICION_OBJETO",
        detalle=f"Objeto contractual modificado. Anterior: '{objeto_anterior[:80]}...' | Nuevo: '{normalized_obj[:80]}...'",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # Sincronizar automáticamente con la Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
        logger.info(f"Contrato {contract.numero_contrato} sincronizado en Matriz Excel tras editar objeto.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar contrato {contract.numero_contrato} en Excel tras editar objeto: {e}")

    logger.info(f"Contrato {contract.numero_contrato} objeto actualizado a: {normalized_obj}")
    return contract

@router.patch("/{contract_id}/numero", response_model=ContratoRead)
def update_contract_number(
    contract_id: int,
    data_in: ContratoNumeroUpdate,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """
    Modifica el código o número de un contrato aplicando la norma oficial de nomenclatura
    por tipología (CPS para Servicios, CS para Suministro, CA para Arrendamiento, CO para Obra).
    Actualiza la base de datos, renombra soportes físicos en disco y sincroniza la Matriz Excel.
    """
    contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    nuevo_num = data_in.nuevo_numero.strip().upper()
    if data_in.forzar_prefijo:
        nuevo_num = normalize_contract_code(nuevo_num, contract.tipologia, contract.vigencia)

    if nuevo_num == contract.numero_contrato:
        return contract

    # Verificar que el nuevo código no esté ya en uso por otro contrato
    duplicate = db.query(Contrato).filter(Contrato.numero_contrato == nuevo_num, Contrato.id != contract.id).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El número de contrato '{nuevo_num}' ya se encuentra en uso por otro contrato."
        )

    old_num = contract.numero_contrato
    contract.numero_contrato = nuevo_num
    contract.updated_at = datetime.now()

    # 1. Renombrar archivos físicos y actualizar registros de documentos
    from app.models.document import Documento
    from app.config import settings
    docs = db.query(Documento).filter(Documento.contrato_id == contract.id).all()
    for d in docs:
        if old_num in (d.nombre_archivo_original or ""):
            new_orig = d.nombre_archivo_original.replace(old_num, nuevo_num)
            new_stored = (d.nombre_archivo_almacenado or "").replace(old_num, nuevo_num)
            new_rel = (d.ruta_relativa or "").replace(old_num, nuevo_num)
            if d.ruta_relativa:
                old_p = settings.BASE_DIR / d.ruta_relativa
                new_p = settings.BASE_DIR / new_rel
                if old_p.exists():
                    try:
                        old_p.rename(new_p)
                        logger.info(f"Archivo físico renombrado: {old_p.name} -> {new_p.name}")
                    except Exception as e_ren:
                        logger.warning(f"No se pudo renombrar archivo {old_p.name}: {e_ren}")
            d.nombre_archivo_original = new_orig
            d.nombre_archivo_almacenado = new_stored
            d.ruta_relativa = new_rel

    # 2. Registrar auditoría
    audit = Auditoria(
        contrato_id=contract.id,
        accion="CAMBIO_NUMERO_CONTRATO",
        detalle=f"Código de contrato modificado de '{old_num}' a '{nuevo_num}' conforme a la tipología {contract.tipologia.value}.",
        usuario=_admin.nombre_completo if _admin else "Administrador",
        usuario_documento=_admin.documento if _admin else None,
        usuario_nombre=_admin.nombre_completo if _admin else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # 3. Sincronizar en Matriz Excel
    try:
        from app.services.excel_engine import delete_contract_from_master_excel, sync_contract_to_master_excel
        delete_contract_from_master_excel(old_num)
        sync_contract_to_master_excel(contract)
        logger.info(f"Matriz Excel actualizada: {old_num} -> {nuevo_num}")
    except Exception as e_xl:
        logger.warning(f"Error sincronizando nuevo número en Excel: {e_xl}")

    logger.info(f"Contrato ID {contract.id} código actualizado exitosamente a {nuevo_num}.")
    return contract

@router.post("/batch-refresh-necesidades", response_model=BatchRefreshNecesidadResult)
def batch_refresh_necesidades(
    data_in: BatchRefreshNecesidadInput,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """
    Aplica a los contratos ya elaborados el estándar obligatorio de 4 párrafos
    de la DESCRIPCIÓN DE LA NECESIDAD A SATISFACER (Regla de Oro),
    especialmente desde CPS-050-2026 en adelante o según el filtro seleccionado.
    """
    from app.utils.necesidad_builder import build_descripcion_necesidad

    query = db.query(Contrato).order_by(Contrato.id)

    if data_in.contract_ids:
        query = query.filter(Contrato.id.in_(data_in.contract_ids))
    elif not data_in.actualizar_todos:
        # Por defecto, desde CPS-050-2026 en adelante o ID >= 50
        if data_in.desde_numero:
            desde_ref = db.query(Contrato).filter(Contrato.numero_contrato == data_in.desde_numero).first()
            if desde_ref:
                query = query.filter(Contrato.id >= desde_ref.id)
            else:
                query = query.filter(or_(Contrato.numero_contrato >= data_in.desde_numero, Contrato.id >= 50))
        else:
            query = query.filter(Contrato.id >= 50)

    contracts_to_update = query.all()

    updated_count = 0
    detalles = []

    for c in contracts_to_update:
        tip = c.tipologia.value if c.tipologia else "PRESTACION_SERVICIOS"
        new_necesidad = build_descripcion_necesidad(objeto=c.objeto, tipologia=tip)

        c.justificacion_necesidad = new_necesidad
        c.updated_at = datetime.now()

        audit = Auditoria(
            contrato_id=c.id,
            accion="ACTUALIZACION_LOTE_NECESIDAD",
            detalle=f"Necesidad actualizada al estándar de 4 párrafos (Regla de Oro). Objeto: {c.objeto[:60]}...",
            usuario=_admin.nombre_completo if _admin else "Administrador",
            usuario_documento=_admin.documento if _admin else None,
            usuario_nombre=_admin.nombre_completo if _admin else None
        )
        db.add(audit)
        updated_count += 1

        paras = [p for p in new_necesidad.split("\n\n") if p.strip()]
        detalles.append({
            "id": c.id,
            "numero_contrato": c.numero_contrato,
            "tipologia": tip,
            "objeto": c.objeto,
            "parrafos_generados": len(paras),
            "primer_parrafo": paras[0][:80] + "..." if paras else "",
            "segundo_parrafo_formula": paras[1][:80] + "..." if len(paras) > 1 else ""
        })

    db.commit()
    logger.info(f"Lote de necesidades actualizado: {updated_count} contratos procesados.")
    return BatchRefreshNecesidadResult(
        status="success",
        contratos_actualizados=updated_count,
        detalles=detalles
    )

class RefreshSectionPayload(BaseModel):
    nivel_extension: Optional[str] = "MEDIA"
    instrucciones_adicionales: Optional[str] = None

@router.post("/{contract_id}/refresh-necesidad", response_model=ContratoRead)
def refresh_single_necesidad(
    contract_id: int,
    payload: Optional[RefreshSectionPayload] = None,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """Regenera la justificación/necesidad de un contrato individual conforme al nivel de extensión seleccionado."""
    from app.utils.necesidad_builder import build_descripcion_necesidad
    from app.services.document_parser import parse_document_text

    contract = db.query(Contrato).options(joinedload(Contrato.contratista)).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    nivel = (payload.nivel_extension if payload else "MEDIA") or "MEDIA"
    instrucciones = payload.instrucciones_adicionales if payload else None

    # Buscar si hay propuesta económica o cotización vinculada al contrato o contratista
    doc_text = ""
    docs = db.query(Documento).filter(
        (Documento.contrato_id == contract_id) | 
        (Documento.contratista_id == contract.contratista_id)
    ).all()
    for d in docs:
        if d.tipo_documento in (TipoDocumento.PROPUESTA, TipoDocumento.ESTUDIO_MERCADO) or any(k in (d.nombre_archivo_original or '').lower() for k in ["propuesta", "cotizacion", "cotización", "oferta"]):
            full_p = settings.BASE_DIR / d.ruta_relativa
            if full_p.exists():
                try:
                    doc_text = parse_document_text(full_p)
                    if doc_text:
                        break
                except Exception:
                    pass

    tip = contract.tipologia.value if contract.tipologia else "PRESTACION_SERVICIOS"
    new_necesidad = build_descripcion_necesidad(
        objeto=contract.objeto, 
        tipologia=tip,
        contexto_adicional=doc_text or None,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )

    contract.justificacion_necesidad = new_necesidad
    contract.updated_at = datetime.now()

    audit = Auditoria(
        contrato_id=contract.id,
        accion="REGENERACION_NECESIDAD",
        detalle=f"Necesidad regenerada con nivel {nivel} para contrato {contract.numero_contrato}",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # Sincronizar en la Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
    except Exception as e:
        logger.warning(f"No se pudo sincronizar contrato {contract.numero_contrato} en Excel tras refresh-necesidad: {e}")

    logger.info(f"Contrato {contract.numero_contrato} necesidad regenerada con éxito.")
    return contract


@router.post("/{contract_id}/refresh-all-sections", response_model=ContratoRead)
def refresh_all_contract_sections(
    contract_id: int,
    payload: Optional[RefreshSectionPayload] = None,
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """
    Regenera integralmente la Necesidad, Objetivos (General y Específicos) y Obligaciones
    (Contratista y ESPY) de un contrato existente, tomando su propuesta económica y el nivel de extensión.
    """
    from app.utils.necesidad_builder import build_descripcion_necesidad
    from app.utils.objetivos_builder import build_objetivos_contrato
    from app.utils.obligaciones_builder import build_obligaciones_contratista
    from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa
    from app.services.document_parser import parse_document_text

    contract = db.query(Contrato).options(joinedload(Contrato.contratista)).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    nivel = (payload.nivel_extension if payload else "MEDIA") or "MEDIA"
    instrucciones = payload.instrucciones_adicionales if payload else None

    # Buscar propuesta económica asociada
    doc_text = ""
    docs = db.query(Documento).filter(
        (Documento.contrato_id == contract_id) | 
        (Documento.contratista_id == contract.contratista_id)
    ).all()
    for d in docs:
        if d.tipo_documento in (TipoDocumento.PROPUESTA, TipoDocumento.ESTUDIO_MERCADO) or any(k in (d.nombre_archivo_original or '').lower() for k in ["propuesta", "cotizacion", "cotización", "oferta"]):
            full_p = settings.BASE_DIR / d.ruta_relativa
            if full_p.exists():
                try:
                    doc_text = parse_document_text(full_p)
                    if doc_text:
                        break
                except Exception:
                    pass

    tip = contract.tipologia.value if contract.tipologia else "PRESTACION_SERVICIOS"

    # 1. Regenerar Necesidad
    contract.justificacion_necesidad = build_descripcion_necesidad(
        objeto=contract.objeto,
        tipologia=tip,
        contexto_adicional=doc_text or None,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )

    # 2. Regenerar Objetivos
    obj_data = build_objetivos_contrato(
        objeto=contract.objeto,
        tipologia=tip,
        contexto=doc_text or None,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )
    contract.objetivo_general = obj_data["objetivo_general"]
    contract.objetivos_especificos = obj_data["objetivos_especificos"]

    # 3. Regenerar Obligaciones del Contratista
    oblig_res = build_obligaciones_contratista(
        objeto=contract.objeto,
        tipologia=tip,
        contexto_adicional=doc_text or None,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )
    contract.obligaciones_estudio_previo = oblig_res["obligaciones_estudio_previo"]
    contract.obligaciones_minuta = oblig_res["obligaciones_minuta"]

    # 4. Regenerar Obligaciones de la ESPY
    tipo_p = "JURIDICA" if contract.contratista and str(contract.contratista.tipo_persona or "").upper() in ["JURIDICA", "JURÍDICA", "NIT"] else "NATURAL"
    unidad_str = contract.unidad_plazo.value if contract.unidad_plazo else "MESES"
    contract.obligaciones_empresa = build_obligaciones_empresa(
        objeto=contract.objeto,
        tipologia=tip,
        plazo_str=contract.plazo_texto,
        plazo_val=contract.plazo_ejecucion,
        unidad_plazo=unidad_str,
        tipo_persona=tipo_p,
        obligaciones_contratista=contract.obligaciones_minuta,
        contexto_adicional=doc_text or None,
        nivel_extension=nivel,
        instrucciones_adicionales=instrucciones
    )

    contract.updated_at = datetime.now()

    audit = Auditoria(
        contrato_id=contract.id,
        accion="REGENERACION_SECCIONES_INTEGRAL",
        detalle=f"Todas las secciones regeneradas con nivel {nivel} para contrato {contract.numero_contrato}",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    # Sincronizar en la Matriz Excel
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
    except Exception as e:
        logger.warning(f"No se pudo sincronizar contrato {contract.numero_contrato} en Excel tras refresh-all-sections: {e}")

    logger.info(f"Contrato {contract.numero_contrato} todas las secciones regeneradas con éxito.")
    return contract

@router.delete("/{contract_id}")
def delete_contract(
    contract_id: int, 
    payload: Optional[ContratoAnulacionRequest] = None,
    motivo: Optional[str] = Query(None, description="Motivo de anulación o borrado"),
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """
    Regla Prompt 4: Anular en vez de borrar.
    - Recibe un motivo obligatorio (mínimo 15 caracteres) por cuerpo JSON o query.
    - Si el contrato está en BORRADOR y no tiene pagos ni adiciones, se permite BORRADO FÍSICO;
      la auditoría se preserva con contrato_id=None y el número en el detalle.
    - Si el contrato NO está en BORRADOR o tiene adiciones/pagos, pasa a estado 'ANULADO',
      se llenan motivo_anulacion, anulado_por, fecha_anulacion, se registra auditoría y
      en la matriz Excel se actualiza con estado ANULADO.
    """
    contract = db.query(Contrato).options(
        joinedload(Contrato.adiciones),
        joinedload(Contrato.pagos),
        joinedload(Contrato.documentos)
    ).filter(Contrato.id == contract_id).first()

    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    motivo_final = ""
    if payload and payload.motivo:
        motivo_final = payload.motivo.strip()
    elif motivo:
        motivo_final = motivo.strip()

    if len(motivo_final) < 15:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe proporcionar un motivo obligatorio de al menos 15 caracteres para anular o eliminar el contrato."
        )

    contract_number = contract.numero_contrato
    estado_actual = contract.estado.value if hasattr(contract.estado, "value") else str(contract.estado)
    tiene_pagos = len(contract.pagos or []) > 0
    tiene_adiciones = len(contract.adiciones or []) > 0

    nombre_autor = _admin.nombre_completo if _admin else "Administrador"
    doc_autor = _admin.documento if _admin else None

    # CASO 1: BORRADO FÍSICO
    # Se permite borrar físicamente si el contrato está en BORRADOR o ya está ANULADO, no tiene pagos ni adiciones, y lo hace un ADMIN
    if estado_actual in ("BORRADOR", "ANULADO") and not tiene_pagos and not tiene_adiciones:
        # Remover de la matriz Excel
        try:
            from app.services.excel_engine import delete_contract_from_master_excel
            delete_contract_from_master_excel(contract_number)
            logger.info(f"Contrato {contract_number} ({estado_actual}) removido de la Matriz Excel.")
        except Exception as e:
            logger.warning(f"No se pudo remover el contrato {contract_number} de Excel: {e}")

        # Limpieza de archivos físicos generados
        try:
            from app.config import settings
            for doc in (contract.documentos or []):
                rel_path = getattr(doc, "ruta_relativa", None)
                if rel_path:
                    full_path = settings.BASE_DIR / rel_path
                    if full_path.exists():
                        try:
                            full_path.unlink()
                        except Exception:
                            pass
        except Exception as e:
            logger.warning(f"Error durante limpieza de archivos de contrato {contract_number}: {e}")

        # Desvincular auditorías existentes para que no se borren en cascada
        audit_records = db.query(Auditoria).filter(Auditoria.contrato_id == contract.id).all()
        for ar in audit_records:
            ar.contrato_id = None
            ar.detalle = f"[{contract_number}] {ar.detalle or ''}"

        # Registrar auditoría de borrado físico con contrato_id nulo
        db.add(Auditoria(
            contrato_id=None,
            accion="BORRADO_FISICO_CONTRATO",
            detalle=f"Contrato {contract_number} ({estado_actual}) eliminado físicamente del sistema. Motivo: {motivo_final}",
            usuario=nombre_autor,
            usuario_documento=doc_autor,
            usuario_nombre=nombre_autor
        ))

        db.delete(contract)
        db.commit()
        logger.info(f"Contrato ID {contract_id} ({contract_number}) ({estado_actual}) eliminado físicamente.")
        return {
            "status": "success",
            "accion": "BORRADO_FISICO",
            "eliminado_fisicamente": True,
            "mensaje": f"Contrato {contract_number} eliminado físicamente del sistema y de la matriz Excel.",
            "contrato_id": contract_id,
            "numero_contrato": contract_number
        }

    # CASO 2: ANULACIÓN CONTRACTUAL
    # Pasa el contrato a ANULADO, llena columnas nuevas, preserva auditorías y actualiza Excel
    contract.estado = EstadoContrato.ANULADO
    contract.motivo_anulacion = motivo_final
    contract.anulado_por = nombre_autor
    contract.fecha_anulacion = datetime.now()
    contract.updated_at = datetime.now()

    # Auditoría de anulación
    db.add(Auditoria(
        contrato_id=contract.id,
        accion="ANULACION_CONTRATO",
        detalle=f"Contrato {contract_number} anulado formalmente. Motivo: {motivo_final}",
        usuario=nombre_autor,
        usuario_documento=doc_autor,
        usuario_nombre=nombre_autor
    ))
    db.commit()
    db.refresh(contract)

    # Actualizar estado ANULADO en Excel (no se elimina de Excel según Prompt 4)
    try:
        from app.services.excel_engine import sync_contract_to_master_excel
        sync_contract_to_master_excel(contract)
        logger.info(f"Contrato {contract_number} actualizado en Excel con estado ANULADO.")
    except Exception as e:
        logger.warning(f"No se pudo sincronizar estado ANULADO en Excel para {contract_number}: {e}")

    logger.info(f"Contrato {contract_number} pasó de {estado_actual} a ANULADO exitosamente.")
    return {
        "status": "success",
        "accion": "ANULADO",
        "anulado": True,
        "estado": "ANULADO",
        "mensaje": f"Contrato {contract_number} anulado exitosamente. Se preserva su historial y registros.",
        "contrato_id": contract_id,
        "numero_contrato": contract_number,
        "motivo": motivo_final,
        "anulado_por": nombre_autor,
        "fecha_anulacion": contract.fecha_anulacion.isoformat()
    }


@router.get("/{contract_id}/estudio-mercado")
def get_contract_estudio_mercado(contract_id: int, db: Session = Depends(get_db)):
    """Consulta el estudio de mercado y APU incorporado a un contrato específico."""
    contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    estudio = getattr(contract, "estudio_mercado", None)
    if not estudio:
        meta = contract.metadatos_agente or {}
        if isinstance(meta, dict):
            estudio = meta.get("estudio_mercado")

    resumen = None
    if estudio:
        from app.services.agents.apu_agent import apu_agent
        resumen = apu_agent.build_resumen_estudio_mercado(estudio)

    return {
        "contrato_id": contract.id,
        "numero_contrato": contract.numero_contrato,
        "tiene_estudio_mercado": bool(estudio),
        "estudio_mercado": estudio,
        "resumen": resumen
    }


@router.post("/{contract_id}/estudio-mercado")
def save_contract_estudio_mercado(
    contract_id: int, 
    payload: Dict[str, Any], 
    db: Session = Depends(get_db),
    _user: Usuario = Depends(require_editor)
):
    """
    Incorpora o actualiza el ESTUDIO DE MERCADO (Análisis de precios unitarios APU y Elección de Contratista)
    en el contrato indicado. Al generar el documento Word (.docx) del Estudio Previo, se inyectará automáticamente
    el resumen estructurado de las propuestas bajo el subtítulo:
    'ANALISIS DE LAS PROPUESTAS DE MERCADO:' inmediatamente después de las obligaciones del contratista.
    """
    contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    from app.services.agents.apu_agent import apu_agent

    estudio_result = payload
    # Si payload contiene proceso_config y ofertas pero no el resultado evaluado, ejecutar la evaluación
    if "ofertas" in payload and "proponente_ganador" not in payload:
        try:
            from app.schemas.apu import EvaluacionComparativaPayload
            eval_payload = EvaluacionComparativaPayload(**payload)
            eval_res = apu_agent.evaluate_proposals(eval_payload)
            estudio_result = eval_res.model_dump()
        except Exception as e_ev:
            logger.warning(f"Aviso evaluando payload de ofertas recibido: {e_ev}")

    resumen = apu_agent.build_resumen_estudio_mercado(estudio_result)

    # Persistir en la columna dedicada y en metadatos_agente para doble compatibilidad
    contract.estudio_mercado = estudio_result
    meta = dict(contract.metadatos_agente or {})
    meta["tiene_estudio_mercado"] = True
    meta["estudio_mercado"] = estudio_result
    contract.metadatos_agente = meta
    contract.updated_at = datetime.now()

    # Registrar trazabilidad en auditoría
    winner_name = resumen.get("proponente_ganador", {}).get("nombre", "Oferente Seleccionado")
    audit = Auditoria(
        contrato_id=contract.id,
        accion="INCORPORACION_ESTUDIO_MERCADO",
        detalle=f"Estudio de mercado y APU incorporado al contrato. Ganador seleccionado: {winner_name}",
        usuario=_user.nombre_completo if _user else "Administrador",
        usuario_documento=_user.documento if _user else None,
        usuario_nombre=_user.nombre_completo if _user else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    logger.info(f"Estudio de mercado incorporado exitosamente al contrato {contract.numero_contrato} (ID: {contract_id}).")

    return {
        "status": "success",
        "mensaje": f"Estudio de mercado incorporado exitosamente al contrato {contract.numero_contrato}. Se plasmará en el Estudio Previo (.docx) tras las obligaciones del contratista.",
        "contrato_id": contract.id,
        "numero_contrato": contract.numero_contrato,
        "tiene_estudio_mercado": True,
        "estudio_mercado": estudio_result,
        "resumen": resumen
    }


@router.delete("/{contract_id}/estudio-mercado")
def delete_contract_estudio_mercado(
    contract_id: int, 
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """
    Desvincula o elimina el estudio de mercado del contrato.
    El documento de Estudio Previo ya NO incluirá la sección de Análisis de Propuestas de Mercado.
    """
    contract = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contrato con ID {contract_id} no encontrado."
        )

    contract.estudio_mercado = None
    meta = dict(contract.metadatos_agente or {})
    meta["tiene_estudio_mercado"] = False
    if "estudio_mercado" in meta:
        del meta["estudio_mercado"]
    contract.metadatos_agente = meta
    contract.updated_at = datetime.now()

    audit = Auditoria(
        contrato_id=contract.id,
        accion="DESVINCULACION_ESTUDIO_MERCADO",
        detalle="Estudio de mercado desvinculado del contrato. No se incluirá en el Estudio Previo.",
        usuario=_admin.nombre_completo if _admin else "Administrador",
        usuario_documento=_admin.documento if _admin else None,
        usuario_nombre=_admin.nombre_completo if _admin else None
    )
    db.add(audit)
    db.commit()
    db.refresh(contract)

    logger.info(f"Estudio de mercado desvinculado del contrato {contract.numero_contrato} (ID: {contract_id}).")

    return {
        "status": "success",
        "mensaje": f"Estudio de mercado desvinculado del contrato {contract.numero_contrato}. El Estudio Previo ya no incluirá este análisis.",
        "contrato_id": contract.id,
        "numero_contrato": contract.numero_contrato,
        "tiene_estudio_mercado": False
    }

