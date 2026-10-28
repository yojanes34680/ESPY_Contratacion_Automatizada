"""Execution Router: Handles contract financial execution, payments, vouchers, and metrics."""
import csv
import io
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc

from app.database import get_db
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.execution import PagoContrato
from app.services.payment_packet_parser import (
    extract_payment_packet_data,
    format_record_to_txt_line,
    parse_retencion_token,
    normalize_retencion_name
)
from app.schemas.execution import (
    PagoContratoCreate,
    PagoContratoUpdate,
    PagoContratoReassign,
    PagoContratoResponse,
    PagoContratoDetailResponse,
    ContratoEjecucionSummary,
    ContratistaEjecucionSummary,
    RubroEjecucionItem,
    MesEjecucionItem,
    ResumenEjecucionGlobal,
    RetencionConceptoSummary
)
from app.utils.logger import logger
from app.routers.auth import require_admin, require_editor
from app.models.user import Usuario

execution_router = APIRouter(prefix="/execution", tags=["Ejecución Contractual y Pagos"])

MONTH_NAMES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

CONTRACT_ALIASES = {
    "029-2026": "CO-029-2026",
    "CPS-021-2026": "CS-021-2026",
}

@execution_router.get("/summary", response_model=ResumenEjecucionGlobal)
def get_execution_summary(
    vigencia: Optional[str] = Query(None, description="Año de vigencia o 'ALL'"),
    db: Session = Depends(get_db)
):
    """Retrieve global contract execution metrics, financial KPIs, and breakdowns."""
    # Base query for contracts
    contract_q = db.query(Contrato)
    payment_q = db.query(PagoContrato)

    if vigencia and vigencia.upper() != "ALL":
        try:
            year_int = int(vigencia)
            contract_q = contract_q.filter(Contrato.vigencia == year_int)
            payment_q = payment_q.filter(PagoContrato.vigencia == year_int)
        except ValueError:
            pass

    contracts = contract_q.all()
    payments = payment_q.all()

    total_contratos = len(contracts)
    total_contratado = sum((c.valor_total or 0.0) for c in contracts)

    total_orden = sum(p.total_orden for p in payments)
    total_retencion = sum(p.total_retencion for p in payments)
    total_pagar = sum(p.total_pagar for p in payments)
    total_estampillas = sum(p.total_estampillas for p in payments)

    contratos_con_pagos_ids = set(p.contrato_id for p in payments if p.contrato_id)
    total_contratos_con_pagos = len(contratos_con_pagos_ids)

    contratistas_ids = set(c.contratista_id for c in contracts if c.contratista_id)
    total_contratistas = len(contratistas_ids)

    saldo_por_ejecutar = max(0.0, total_contratado - total_orden)
    pct_global = round((total_orden / total_contratado * 100), 2) if total_contratado > 0 else 0.0

    # Agrupación por Rubro
    rubros_dict = {}
    for p in payments:
        rub = p.rubro_egreso or "Sin Rubro"
        if rub not in rubros_dict:
            rubros_dict[rub] = {"total_orden": 0.0, "total_neto": 0.0, "count": 0}
        rubros_dict[rub]["total_orden"] += p.total_orden
        rubros_dict[rub]["total_neto"] += p.total_pagar
        rubros_dict[rub]["count"] += 1

    rubros_list = []
    for rub, val in sorted(rubros_dict.items(), key=lambda x: x[1]["total_orden"], reverse=True):
        rubros_list.append(RubroEjecucionItem(
            rubro=rub,
            total_ejecutado=val["total_orden"],
            total_neto=val["total_neto"],
            conteo_pagos=val["count"],
            porcentaje_del_total=round((val["total_orden"] / total_orden * 100), 2) if total_orden > 0 else 0.0
        ))

    # Agrupación por Mes (Evolución temporal de pagos)
    meses_dict = {}
    for p in payments:
        if p.fecha_expedicion:
            y = p.fecha_expedicion.year
            m = p.fecha_expedicion.month
            k = f"{y}-{m:02d}"
            nombre = f"{MONTH_NAMES_ES.get(m, m)} {y}"
        else:
            k = "2026-00"
            nombre = "Sin Fecha"

        if k not in meses_dict:
            meses_dict[k] = {
                "mes_nombre": nombre,
                "total_orden": 0.0,
                "total_ret": 0.0,
                "total_neto": 0.0,
                "count": 0
            }
        meses_dict[k]["total_orden"] += p.total_orden
        meses_dict[k]["total_ret"] += p.total_retencion
        meses_dict[k]["total_neto"] += p.total_pagar
        meses_dict[k]["count"] += 1

    meses_list = []
    for k in sorted(meses_dict.keys()):
        val = meses_dict[k]
        meses_list.append(MesEjecucionItem(
            mes_key=k,
            mes_nombre=val["mes_nombre"],
            total_ejecutado=val["total_orden"],
            total_retencion=val["total_ret"],
            total_neto=val["total_neto"],
            conteo_pagos=val["count"]
        ))

    # Top Contratistas por valor ejecutado
    contractor_totals = {}
    for p in payments:
        cid = p.contratista_id
        if not cid:
            continue
        if cid not in contractor_totals:
            contractor_totals[cid] = {"total_orden": 0.0, "total_ret": 0.0, "total_neto": 0.0, "total_estampillas": 0.0, "count": 0}
        contractor_totals[cid]["total_orden"] += p.total_orden
        contractor_totals[cid]["total_ret"] += p.total_retencion
        contractor_totals[cid]["total_neto"] += p.total_pagar
        contractor_totals[cid]["total_estampillas"] += p.total_estampillas
        contractor_totals[cid]["count"] += 1

    top_contratistas_list = []
    sorted_cids = sorted(contractor_totals.keys(), key=lambda x: contractor_totals[x]["total_orden"], reverse=True)[:10]

    for cid in sorted_cids:
        c_obj = db.query(Contratista).filter(Contratista.id == cid).first()
        if not c_obj:
            continue
        c_contracts = [c for c in c_obj.contratos if vigencia in (None, "ALL") or str(c.vigencia) == str(vigencia)]
        total_c_val = sum((c.valor_total or 0.0) for c in c_contracts)
        stats = contractor_totals[cid]
        top_contratistas_list.append(ContratistaEjecucionSummary(
            id=c_obj.id,
            nombre_o_razon_social=c_obj.nombre_o_razon_social,
            numero_documento=c_obj.numero_documento,
            tipo_documento=str(c_obj.tipo_documento.value if hasattr(c_obj.tipo_documento, 'value') else c_obj.tipo_documento),
            tipo_persona=str(c_obj.tipo_persona.value if hasattr(c_obj.tipo_persona, 'value') else c_obj.tipo_persona),
            banco_nombre=c_obj.banco_nombre,
            banco_tipo_cuenta=c_obj.banco_tipo_cuenta,
            banco_numero_cuenta=c_obj.banco_numero_cuenta,
            total_contratos=len(c_contracts),
            valor_total_contratado=total_c_val,
            total_ejecutado=stats["total_orden"],
            total_retenciones=stats["total_ret"],
            total_estampillas=stats["total_estampillas"],
            total_neto_pagado=stats["total_neto"],
            saldo_por_ejecutar=max(0.0, total_c_val - stats["total_orden"]),
            porcentaje_ejecucion=round((stats["total_orden"] / total_c_val * 100), 2) if total_c_val > 0 else 0.0,
            conteo_pagos=stats["count"]
        ))

    # Discriminación agregada de retenciones y estampillas
    ret_agg = {}
    for p in payments:
        details = p.retenciones_detalle or []
        for it in details:
            c_name = normalize_retencion_name(it.get("concepto", ""))
            val = float(it.get("valor", 0.0) or 0.0)
            es_est = bool(it.get("es_estampilla", False)) or ('Estampilla' in c_name or 'Deporte' in c_name)
            if c_name not in ret_agg:
                ret_agg[c_name] = {
                    "concepto": c_name,
                    "total_retenido": 0.0,
                    "conteo_pagos": 0,
                    "es_estampilla": es_est
                }
            ret_agg[c_name]["total_retenido"] += val
            ret_agg[c_name]["conteo_pagos"] += 1

    retenciones_breakdown = []
    for c_name, info in sorted(ret_agg.items(), key=lambda x: x[1]["total_retenido"], reverse=True):
        pct = round((info["total_retenido"] / total_retencion * 100), 2) if total_retencion > 0 else 0.0
        retenciones_breakdown.append(RetencionConceptoSummary(
            concepto=info["concepto"],
            total_retenido=round(info["total_retenido"], 2),
            porcentaje_del_total=pct,
            conteo_pagos=info["conteo_pagos"],
            es_estampilla=info["es_estampilla"]
        ))

    return ResumenEjecucionGlobal(
        vigencia=str(vigencia or "2026"),
        total_contratos=total_contratos,
        total_contratos_con_pagos=total_contratos_con_pagos,
        total_contratistas=total_contratistas,
        total_contratado=total_contratado,
        total_ejecutado=total_orden,
        total_retenciones=total_retencion,
        total_estampillas=total_estampillas,
        total_neto_pagado=total_pagar,
        saldo_por_ejecutar=saldo_por_ejecutar,
        porcentaje_ejecucion_global=pct_global,
        conteo_comprobantes=len(payments),
        rubros=rubros_list,
        meses=meses_list,
        top_contratistas=top_contratistas_list,
        retenciones_breakdown=retenciones_breakdown
    )

@execution_router.get("/contractors", response_model=List[ContratistaEjecucionSummary])
def get_contractors_execution(
    query: Optional[str] = Query(None, description="Búsqueda por nombre o documento"),
    vigencia: Optional[str] = Query(None, description="Vigencia o 'ALL'"),
    db: Session = Depends(get_db)
):
    """List all contractors with their financial execution metrics."""
    c_query = db.query(Contratista)
    if query:
        q_like = f"%{query.strip()}%"
        c_query = c_query.filter(
            or_(
                Contratista.nombre_o_razon_social.ilike(q_like),
                Contratista.numero_documento.ilike(q_like)
            )
        )
    contractors = c_query.all()

    # Pre-fetch payments mapped by contractor_id
    payments_q = db.query(PagoContrato)
    if vigencia and vigencia.upper() != "ALL":
        try:
            payments_q = payments_q.filter(PagoContrato.vigencia == int(vigencia))
        except ValueError:
            pass
    all_payments = payments_q.all()

    payments_by_contractor = {}
    for p in all_payments:
        if p.contratista_id:
            payments_by_contractor.setdefault(p.contratista_id, []).append(p)

    results = []
    for c in contractors:
        c_contracts = c.contratos
        if vigencia and vigencia.upper() != "ALL":
            try:
                v_int = int(vigencia)
                c_contracts = [ct for ct in c_contracts if ct.vigencia == v_int]
            except ValueError:
                pass

        c_payments = payments_by_contractor.get(c.id, [])
        total_c_val = sum((ct.valor_total or 0.0) for ct in c_contracts)
        tot_orden = sum(p.total_orden for p in c_payments)
        tot_ret = sum(p.total_retencion for p in c_payments)
        tot_estampillas = sum((getattr(p, 'total_estampillas', 0.0) or 0.0) for p in c_payments)
        tot_pagar = sum(p.total_pagar for p in c_payments)

        # Si no tiene contratos ni pagos en la vigencia y no se buscó explícitamente, saltar
        if not query and len(c_contracts) == 0 and len(c_payments) == 0:
            continue

        pct = round((tot_orden / total_c_val * 100), 2) if total_c_val > 0 else 0.0

        results.append(ContratistaEjecucionSummary(
            id=c.id,
            nombre_o_razon_social=c.nombre_o_razon_social,
            numero_documento=c.numero_documento,
            tipo_documento=str(c.tipo_documento.value if hasattr(c.tipo_documento, 'value') else c.tipo_documento),
            tipo_persona=str(c.tipo_persona.value if hasattr(c.tipo_persona, 'value') else c.tipo_persona),
            banco_nombre=c.banco_nombre,
            banco_tipo_cuenta=c.banco_tipo_cuenta,
            banco_numero_cuenta=c.banco_numero_cuenta,
            total_contratos=len(c_contracts),
            valor_total_contratado=total_c_val,
            total_ejecutado=tot_orden,
            total_retenciones=tot_ret,
            total_estampillas=tot_estampillas,
            total_neto_pagado=tot_pagar,
            saldo_por_ejecutar=max(0.0, total_c_val - tot_orden),
            porcentaje_ejecucion=pct,
            conteo_pagos=len(c_payments)
        ))

    # Ordenar por valor ejecutado descendente
    results.sort(key=lambda x: x.total_ejecutado, reverse=True)
    return results

@execution_router.get("/contractors/{contractor_id}", response_model=ContratistaEjecucionSummary)
def get_contractor_execution_detail(
    contractor_id: int,
    vigencia: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieve full execution profile of a specific contractor, including contracts and payments."""
    contractor = db.query(Contratista).filter(Contratista.id == contractor_id).first()
    if not contractor:
        raise HTTPException(status_code=404, detail="Contratista no encontrado")

    c_contracts = contractor.contratos
    if vigencia and vigencia.upper() != "ALL":
        try:
            v_int = int(vigencia)
            c_contracts = [ct for ct in c_contracts if ct.vigencia == v_int]
        except ValueError:
            pass

    p_query = db.query(PagoContrato).filter(PagoContrato.contratista_id == contractor_id)
    if vigencia and vigencia.upper() != "ALL":
        try:
            p_query = p_query.filter(PagoContrato.vigencia == int(vigencia))
        except ValueError:
            pass
    payments = p_query.order_by(desc(PagoContrato.fecha_expedicion)).all()

    total_c_val = sum((ct.valor_total or 0.0) for ct in c_contracts)
    tot_orden = sum(p.total_orden for p in payments)
    tot_ret = sum(p.total_retencion for p in payments)
    tot_estampillas = sum((getattr(p, 'total_estampillas', 0.0) or 0.0) for p in payments)
    tot_pagar = sum(p.total_pagar for p in payments)

    pct = round((tot_orden / total_c_val * 100), 2) if total_c_val > 0 else 0.0

    # Construir desglose de contratos
    contracts_summary_list = []
    payments_by_contract_id = {}
    for p in payments:
        if p.contrato_id:
            payments_by_contract_id.setdefault(p.contrato_id, []).append(p)

    for ct in c_contracts:
        ct_payments = payments_by_contract_id.get(ct.id, [])
        ct_orden = sum(p.total_orden for p in ct_payments)
        ct_ret = sum(p.total_retencion for p in ct_payments)
        ct_estampillas = sum((getattr(p, 'total_estampillas', 0.0) or 0.0) for p in ct_payments)
        ct_pagar = sum(p.total_pagar for p in ct_payments)
        ct_total = ct.valor_total or 0.0
        ct_pct = round((ct_orden / ct_total * 100), 2) if ct_total > 0 else 0.0

        contracts_summary_list.append(ContratoEjecucionSummary(
            id=ct.id,
            numero_contrato=ct.numero_contrato,
            tipologia=str(ct.tipologia.value if hasattr(ct.tipologia, 'value') else ct.tipologia),
            contratista_id=contractor.id,
            contratista_nombre=contractor.nombre_o_razon_social,
            valor_total=ct_total,
            valor_inicial=ct.valor_inicial or 0.0,
            adicion_1=ct.adicion_1 or 0.0,
            estado=str(ct.estado.value if hasattr(ct.estado, 'value') else ct.estado),
            total_ejecutado=ct_orden,
            total_retenciones=ct_ret,
            total_estampillas=ct_estampillas,
            total_neto_pagado=ct_pagar,
            saldo_por_ejecutar=max(0.0, ct_total - ct_orden),
            porcentaje_ejecucion=ct_pct,
            conteo_pagos=len(ct_payments)
        ))

    payments_response = [PagoContratoResponse.model_validate(p) for p in payments]

    return ContratistaEjecucionSummary(
        id=contractor.id,
        nombre_o_razon_social=contractor.nombre_o_razon_social,
        numero_documento=contractor.numero_documento,
        tipo_documento=str(contractor.tipo_documento.value if hasattr(contractor.tipo_documento, 'value') else contractor.tipo_documento),
        tipo_persona=str(contractor.tipo_persona.value if hasattr(contractor.tipo_persona, 'value') else contractor.tipo_persona),
        banco_nombre=contractor.banco_nombre,
        banco_tipo_cuenta=contractor.banco_tipo_cuenta,
        banco_numero_cuenta=contractor.banco_numero_cuenta,
        total_contratos=len(c_contracts),
        valor_total_contratado=total_c_val,
        total_ejecutado=tot_orden,
        total_retenciones=tot_ret,
        total_estampillas=tot_estampillas,
        total_neto_pagado=tot_pagar,
        saldo_por_ejecutar=max(0.0, total_c_val - tot_orden),
        porcentaje_ejecucion=pct,
        conteo_pagos=len(payments),
        contratos=contracts_summary_list,
        pagos=payments_response
    )

@execution_router.get("/contracts", response_model=List[ContratoEjecucionSummary])
def get_contracts_execution(
    query: Optional[str] = Query(None, description="Búsqueda por número de contrato o contratista"),
    vigencia: Optional[str] = Query(None, description="Vigencia o 'ALL'"),
    contractor_id: Optional[int] = Query(None, description="Filtrar por contratista"),
    db: Session = Depends(get_db)
):
    """List contracts with financial progress bars and execution totals."""
    q = db.query(Contrato)
    if vigencia and vigencia.upper() != "ALL":
        try:
            q = q.filter(Contrato.vigencia == int(vigencia))
        except ValueError:
            pass

    if contractor_id:
        q = q.filter(Contrato.contratista_id == contractor_id)

    if query:
        term = f"%{query.strip()}%"
        q = q.join(Contratista).filter(
            or_(
                Contrato.numero_contrato.ilike(term),
                Contratista.nombre_o_razon_social.ilike(term)
            )
        )

    contracts = q.all()

    # Pre-fetch payments
    payments = db.query(PagoContrato).all()
    payments_by_contract_id = {}
    for p in payments:
        if p.contrato_id:
            payments_by_contract_id.setdefault(p.contrato_id, []).append(p)

    results = []
    for ct in contracts:
        c_name = ct.contratista.nombre_o_razon_social if ct.contratista else "N/A"
        c_payments = payments_by_contract_id.get(ct.id, [])
        ct_orden = sum(p.total_orden for p in c_payments)
        ct_ret = sum(p.total_retencion for p in c_payments)
        ct_estampillas = sum((getattr(p, 'total_estampillas', 0.0) or 0.0) for p in c_payments)
        ct_pagar = sum(p.total_pagar for p in c_payments)
        ct_total = ct.valor_total or 0.0
        pct = round((ct_orden / ct_total * 100), 2) if ct_total > 0 else 0.0

        results.append(ContratoEjecucionSummary(
            id=ct.id,
            numero_contrato=ct.numero_contrato,
            tipologia=str(ct.tipologia.value if hasattr(ct.tipologia, 'value') else ct.tipologia),
            contratista_id=ct.contratista_id,
            contratista_nombre=c_name,
            valor_total=ct_total,
            valor_inicial=ct.valor_inicial or 0.0,
            adicion_1=ct.adicion_1 or 0.0,
            estado=str(ct.estado.value if hasattr(ct.estado, 'value') else ct.estado),
            total_ejecutado=ct_orden,
            total_retenciones=ct_ret,
            total_estampillas=ct_estampillas,
            total_neto_pagado=ct_pagar,
            saldo_por_ejecutar=max(0.0, ct_total - ct_orden),
            porcentaje_ejecucion=pct,
            conteo_pagos=len(c_payments)
        ))

    results.sort(key=lambda x: x.total_ejecutado, reverse=True)
    return results

@execution_router.get("/contracts/{contract_id}")
def get_contract_execution_detail(
    contract_id: int,
    db: Session = Depends(get_db)
):
    """Retrieve detailed execution stats and all payment vouchers for a specific contract."""
    ct = db.query(Contrato).filter(Contrato.id == contract_id).first()
    if not ct:
        raise HTTPException(status_code=404, detail="Contrato no encontrado")

    payments = db.query(PagoContrato).filter(PagoContrato.contrato_id == contract_id).order_by(desc(PagoContrato.fecha_expedicion)).all()
    ct_orden = sum(p.total_orden for p in payments)
    ct_ret = sum(p.total_retencion for p in payments)
    ct_estampillas = sum((getattr(p, 'total_estampillas', 0.0) or 0.0) for p in payments)
    ct_pagar = sum(p.total_pagar for p in payments)
    ct_total = ct.valor_total or 0.0
    pct = round((ct_orden / ct_total * 100), 2) if ct_total > 0 else 0.0

    return {
        "contrato": {
            "id": ct.id,
            "numero_contrato": ct.numero_contrato,
            "vigencia": ct.vigencia,
            "tipologia": str(ct.tipologia.value if hasattr(ct.tipologia, 'value') else ct.tipologia),
            "objeto": ct.objeto,
            "valor_inicial": ct.valor_inicial,
            "adicion_1": ct.adicion_1,
            "valor_total": ct_total,
            "estado": str(ct.estado.value if hasattr(ct.estado, 'value') else ct.estado),
            "contratista": {
                "id": ct.contratista.id if ct.contratista else None,
                "nombre_o_razon_social": ct.contratista.nombre_o_razon_social if ct.contratista else "N/A",
                "numero_documento": ct.contratista.numero_documento if ct.contratista else "N/A"
            }
        },
        "metricas": {
            "total_ejecutado": ct_orden,
            "total_retenciones": ct_ret,
            "total_estampillas": ct_estampillas,
            "total_neto_pagado": ct_pagar,
            "saldo_por_ejecutar": max(0.0, ct_total - ct_orden),
            "porcentaje_ejecucion": pct,
            "conteo_pagos": len(payments)
        },
        "pagos": [PagoContratoResponse.model_validate(p) for p in payments]
    }

@execution_router.get("/payments", response_model=List[PagoContratoResponse])
def get_payments(
    query: Optional[str] = Query(None, description="Búsqueda por contrato, egreso o beneficiario"),
    contractor_id: Optional[int] = Query(None),
    contract_id: Optional[int] = Query(None),
    rubro: Optional[str] = Query(None),
    vigencia: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List payment vouchers with advanced search and filtering."""
    q = db.query(PagoContrato)

    if vigencia and vigencia.upper() != "ALL":
        try:
            q = q.filter(PagoContrato.vigencia == int(vigencia))
        except ValueError:
            pass

    if contractor_id:
        q = q.filter(PagoContrato.contratista_id == contractor_id)

    if contract_id:
        q = q.filter(PagoContrato.contrato_id == contract_id)

    if rubro:
        q = q.filter(PagoContrato.rubro_egreso == rubro.strip())

    if query:
        term = f"%{query.strip()}%"
        q = q.filter(
            or_(
                PagoContrato.codigo_contrato.ilike(term),
                PagoContrato.codigo_egreso.ilike(term),
                PagoContrato.nombre_beneficiario.ilike(term),
                PagoContrato.rubro_egreso.ilike(term)
            )
        )

    # Ordenar por fecha o id descendente
    pagos = q.order_by(desc(PagoContrato.fecha_expedicion), desc(PagoContrato.id)).offset(offset).limit(limit).all()
    return pagos

@execution_router.post("/payments", response_model=PagoContratoResponse, status_code=201)
def create_payment(
    pago_in: PagoContratoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """Register a new payment voucher manually."""
    # Buscar contrato si no viene explícito
    contrato_id = pago_in.contrato_id
    contratista_id = pago_in.contratista_id

    norm_code = CONTRACT_ALIASES.get(pago_in.codigo_contrato.strip(), pago_in.codigo_contrato.strip())

    if not contrato_id:
        ct = db.query(Contrato).filter(Contrato.numero_contrato == norm_code).first()
        if ct:
            contrato_id = ct.id
            if not contratista_id:
                contratista_id = ct.contratista_id

    if not contratista_id:
        c = db.query(Contratista).filter(Contratista.nombre_o_razon_social.ilike(f"%{pago_in.nombre_beneficiario.strip()}%")).first()
        if c:
            contratista_id = c.id

    ret_detalle = [d.model_dump() if hasattr(d, "model_dump") else dict(d) for d in (pago_in.retenciones_detalle or [])]
    tot_estampillas = pago_in.total_estampillas or 0.0
    if tot_estampillas == 0.0 and ret_detalle:
        tot_estampillas = sum(
            float(it.get("valor", 0.0) or 0.0)
            for it in ret_detalle
            if it.get("es_estampilla") or any(k in it.get("concepto", "").lower() for k in ["estampilla", "cultura", "hospital", "justicia", "deporte"])
        )

    nuevo_pago = PagoContrato(
        codigo_contrato=norm_code,
        codigo_egreso=pago_in.codigo_egreso.strip(),
        fecha_expedicion=pago_in.fecha_expedicion,
        nombre_beneficiario=pago_in.nombre_beneficiario.strip(),
        rubro_egreso=pago_in.rubro_egreso.strip() if pago_in.rubro_egreso else None,
        total_orden=pago_in.total_orden,
        total_retencion=pago_in.total_retencion,
        total_estampillas=tot_estampillas,
        total_pagar=pago_in.total_pagar,
        retenciones_detalle=ret_detalle,
        retenciones_raw=pago_in.retenciones_raw or (", ".join([f"{it.get('concepto')} ({it.get('porcentaje', 0):.2f}%: {it.get('valor', 0):.2f})" for it in ret_detalle]) if ret_detalle else "Sin retenciones"),
        contrato_id=contrato_id,
        contratista_id=contratista_id,
        vigencia=pago_in.vigencia,
        observaciones=pago_in.observaciones
    )
    db.add(nuevo_pago)
    db.commit()
    db.refresh(nuevo_pago)
    logger.info(f"Comprobante de egreso creado: {nuevo_pago.codigo_egreso} para contrato {nuevo_pago.codigo_contrato}")
    return nuevo_pago

@execution_router.get("/payments/{payment_id}", response_model=PagoContratoDetailResponse)
def get_payment_detail(payment_id: int, db: Session = Depends(get_db)):
    """Retrieve full details of a specific payment voucher including contractor and contract enrichment."""
    pago = db.query(PagoContrato).filter(PagoContrato.id == payment_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Comprobante de egreso no encontrado")
    
    resp = PagoContratoDetailResponse.model_validate(pago)
    if pago.contratista:
        c = pago.contratista
        resp.contratista_documento = f"{c.numero_documento}-{c.digito_verificacion}" if c.digito_verificacion else c.numero_documento
        resp.contratista_tipo_documento = str(c.tipo_documento.value if hasattr(c.tipo_documento, 'value') else c.tipo_documento)
        resp.contratista_banco = c.banco_nombre
        resp.contratista_tipo_cuenta = c.banco_tipo_cuenta
        resp.contratista_numero_cuenta = c.banco_numero_cuenta
    if pago.contrato:
        resp.contrato_objeto = pago.contrato.objeto
        resp.contrato_valor_total = pago.contrato.valor_total
    return resp

@execution_router.put("/payments/{payment_id}", response_model=PagoContratoDetailResponse)
@execution_router.patch("/payments/{payment_id}", response_model=PagoContratoDetailResponse)
def update_payment_values(
    payment_id: int,
    pago_update: PagoContratoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """
    Actualiza y recalcula en vivo los valores monetarios, retenciones y estampillas
    de un Comprobante de Egreso existente.
    """
    pago = db.query(PagoContrato).filter(PagoContrato.id == payment_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Comprobante de egreso no encontrado")

    if pago_update.codigo_contrato is not None:
        pago.codigo_contrato = CONTRACT_ALIASES.get(pago_update.codigo_contrato.strip(), pago_update.codigo_contrato.strip())
    if pago_update.codigo_egreso is not None:
        pago.codigo_egreso = pago_update.codigo_egreso.strip()
    if pago_update.fecha_expedicion is not None:
        pago.fecha_expedicion = pago_update.fecha_expedicion
    if pago_update.nombre_beneficiario is not None:
        pago.nombre_beneficiario = pago_update.nombre_beneficiario.strip()
    if pago_update.rubro_egreso is not None:
        pago.rubro_egreso = pago_update.rubro_egreso.strip()

    if pago_update.total_orden is not None:
        pago.total_orden = float(pago_update.total_orden)
    if pago_update.total_retencion is not None:
        pago.total_retencion = float(pago_update.total_retencion)
    if pago_update.total_pagar is not None:
        pago.total_pagar = float(pago_update.total_pagar)
    else:
        pago.total_pagar = max(0.0, round(pago.total_orden - pago.total_retencion, 2))

    if pago_update.retenciones_detalle is not None:
        ret_list = [d.model_dump() if hasattr(d, "model_dump") else dict(d) for d in pago_update.retenciones_detalle]
        pago.retenciones_detalle = ret_list
        pago.total_estampillas = sum(
            float(it.get("valor", 0.0) or 0.0)
            for it in ret_list
            if it.get("es_estampilla") or any(k in str(it.get("concepto", "")).lower() for k in ["estampilla", "cultura", "hospital", "justicia", "deporte", "adulto mayor", "seguridad"])
        )
    elif pago_update.total_estampillas is not None:
        pago.total_estampillas = float(pago_update.total_estampillas)

    if pago_update.retenciones_raw is not None:
        pago.retenciones_raw = pago_update.retenciones_raw
    elif pago.retenciones_detalle:
        pago.retenciones_raw = ", ".join(f"{it.get('concepto')} ({float(it.get('porcentaje', 0)):.2f}%: {float(it.get('valor', 0)):.2f})" for it in pago.retenciones_detalle)

    if pago_update.observaciones is not None:
        pago.observaciones = pago_update.observaciones

    db.commit()
    db.refresh(pago)
    logger.info(f"Comprobante ID {payment_id} ({pago.codigo_egreso}) actualizado exitosamente. Total Orden: {pago.total_orden}, Retenciones: {pago.total_retencion}, Total a Pagar: {pago.total_pagar}")

    resp = PagoContratoDetailResponse.model_validate(pago)
    if pago.contratista:
        c = pago.contratista
        resp.contratista_documento = f"{c.numero_documento}-{c.digito_verificacion}" if c.digito_verificacion else c.numero_documento
        resp.contratista_tipo_documento = str(c.tipo_documento.value if hasattr(c.tipo_documento, 'value') else c.tipo_documento)
        resp.contratista_banco = c.banco_nombre
        resp.contratista_tipo_cuenta = c.banco_tipo_cuenta
        resp.contratista_numero_cuenta = c.banco_numero_cuenta
    if pago.contrato:
        resp.contrato_objeto = pago.contrato.objeto
        resp.contrato_valor_total = pago.contrato.valor_total
    return resp

@execution_router.delete("/payments/{payment_id}", status_code=204)
def delete_payment(
    payment_id: int, 
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """Delete a payment voucher."""
    pago = db.query(PagoContrato).filter(PagoContrato.id == payment_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Comprobante de egreso no encontrado")
    ce_num = pago.codigo_egreso
    contract_code = pago.codigo_contrato
    db.delete(pago)
    db.commit()
    logger.info(f"Comprobante de egreso eliminado: ID {payment_id} ({ce_num}) del contrato {contract_code}")
    return None

@execution_router.patch("/payments/{payment_id}/reassign", response_model=PagoContratoDetailResponse)
def reassign_payment(
    payment_id: int,
    payload: PagoContratoReassign,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_editor)
):
    """Reassign an existing payment voucher to another contract of the contractor."""
    pago = db.query(PagoContrato).filter(PagoContrato.id == payment_id).first()
    if not pago:
        raise HTTPException(status_code=404, detail="Comprobante de egreso no encontrado")

    target_contract = None
    if payload.contrato_id:
        target_contract = db.query(Contrato).filter(Contrato.id == payload.contrato_id).first()
    elif payload.codigo_contrato:
        norm_code = CONTRACT_ALIASES.get(payload.codigo_contrato.strip(), payload.codigo_contrato.strip())
        target_contract = db.query(Contrato).filter(Contrato.numero_contrato == norm_code).first()

    if not target_contract:
        raise HTTPException(status_code=404, detail="Contrato destino no encontrado para reasignar el pago")

    prev_contract = pago.codigo_contrato
    pago.contrato_id = target_contract.id
    pago.codigo_contrato = target_contract.numero_contrato
    if target_contract.contratista_id:
        pago.contratista_id = target_contract.contratista_id
    if payload.observaciones:
        pago.observaciones = f"{pago.observaciones or ''} | Reasignado: {payload.observaciones}".strip(" |")

    db.commit()
    db.refresh(pago)
    logger.info(f"Comprobante ID {payment_id} ({pago.codigo_egreso}) reasignado exitosamente de {prev_contract} a {target_contract.numero_contrato}")

    resp = PagoContratoDetailResponse.model_validate(pago)
    if pago.contratista:
        c = pago.contratista
        resp.contratista_documento = f"{c.numero_documento}-{c.digito_verificacion}" if c.digito_verificacion else c.numero_documento
        resp.contratista_tipo_documento = str(c.tipo_documento.value if hasattr(c.tipo_documento, 'value') else c.tipo_documento)
        resp.contratista_banco = c.banco_nombre
        resp.contratista_tipo_cuenta = c.banco_tipo_cuenta
        resp.contratista_numero_cuenta = c.banco_numero_cuenta
    if pago.contrato:
        resp.contrato_objeto = pago.contrato.objeto
        resp.contrato_valor_total = pago.contrato.valor_total
    return resp

@execution_router.post("/import")
async def import_payments_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """Import new payments file (TXT / CSV format) with automatic contract linking and retention breakdowns."""
    contents = await file.read()
    try:
        text_data = contents.decode("utf-8")
    except UnicodeDecodeError:
        text_data = contents.decode("latin-1")

    # Detect delimiter: comma, semicolon or tab
    first_line = text_data.strip().split("\n")[0] if text_data.strip() else ""
    delimiter = ";" if ";" in first_line and first_line.count(";") > first_line.count(",") else ","
    
    rows = list(csv.reader(io.StringIO(text_data.strip()), delimiter=delimiter))
    if not rows:
        return {"success": False, "error": "El archivo está vacío."}

    header = [h.strip() for h in rows[0]]
    header_lower = [h.lower().replace("_", " ") for h in header]

    def find_col_idx(candidates):
        for cand in candidates:
            for idx, h in enumerate(header_lower):
                if cand in h:
                    return idx
        return None

    idx_contrato = find_col_idx(["código del contrato", "codigo del contrato", "codigo contrato", "contrato"])
    idx_egreso = find_col_idx(["código del egreso", "codigo del egreso", "codigo egreso", "egreso"])
    idx_fecha = find_col_idx(["fecha de expedición", "fecha expedicion", "fecha"])
    idx_benef = find_col_idx(["nombre del beneficiario", "nombre beneficiario", "beneficiario"])
    idx_rubro = find_col_idx(["rubro egreso", "rubro"])
    idx_orden = find_col_idx(["total orden", "valor orden", "orden"])
    idx_ret = find_col_idx(["total retención", "total retencion", "retencion"])
    idx_pagar = find_col_idx(["total a pagar", "valor a pagar", "neto pagar", "pagar"])

    if idx_contrato is None and len(header) >= 8:
        idx_contrato, idx_egreso, idx_fecha, idx_benef, idx_rubro, idx_orden, idx_ret, idx_pagar = range(8)

    contracts_map = {c.numero_contrato: c for c in db.query(Contrato).all()}
    contractors_by_name = {c.nombre_o_razon_social.strip().upper(): c for c in db.query(Contratista).all()}

    def parse_num(val):
        if not val:
            return 0.0
        v = str(val).replace("$", "").replace(" ", "").strip()
        if "." in v and "," in v:
            v = v.replace(".", "").replace(",", ".")
        elif "," in v and "." not in v:
            v = v.replace(",", ".")
        try:
            return float(v)
        except ValueError:
            return 0.0

    inserted = 0
    updated = 0
    errors = []

    for row_idx, row in enumerate(rows[1:], 2):
        if not row or not any(field.strip() for field in row):
            continue
        try:
            raw_code = (row[idx_contrato] if idx_contrato is not None and idx_contrato < len(row) else "").strip()
            norm_code = CONTRACT_ALIASES.get(raw_code, raw_code)
            egreso_code = (row[idx_egreso] if idx_egreso is not None and idx_egreso < len(row) else "").strip()

            if not raw_code or not egreso_code:
                errors.append(f"Línea {row_idx}: falta Código del Contrato o Código del Egreso")
                continue

            contract = contracts_map.get(norm_code)
            contrato_id = contract.id if contract else None
            contratista_id = contract.contratista_id if contract else None

            benef_name = (row[idx_benef] if idx_benef is not None and idx_benef < len(row) else "").strip()
            if not contratista_id and benef_name:
                c_match = contractors_by_name.get(benef_name.upper())
                if c_match:
                    contratista_id = c_match.id

            fecha_str = (row[idx_fecha] if idx_fecha is not None and idx_fecha < len(row) else "").strip()
            fecha_exp = None
            if fecha_str:
                for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                    try:
                        fecha_exp = datetime.strptime(fecha_str, fmt).date()
                        break
                    except ValueError:
                        pass

            rubro = (row[idx_rubro] if idx_rubro is not None and idx_rubro < len(row) else "").strip()
            tot_orden = parse_num(row[idx_orden] if idx_orden is not None and idx_orden < len(row) else 0.0)
            tot_ret = parse_num(row[idx_ret] if idx_ret is not None and idx_ret < len(row) else 0.0)
            tot_pagar = parse_num(row[idx_pagar] if idx_pagar is not None and idx_pagar < len(row) else 0.0)

            # Extraer columnas adicionales de retenciones
            ret_items = []
            c_idx = 8
            while c_idx < len(row):
                c_val = str(row[c_idx]).strip()
                if not c_val or c_val.lower() == 'sin retenciones':
                    c_idx += 1
                    continue
                # Si es un par: Nombre retenciones y (% / Valor)
                if c_idx + 1 < len(row) and ('%' in str(row[c_idx + 1]) or ':' in str(row[c_idx + 1])):
                    val_part = str(row[c_idx + 1]).strip()
                    token = f"{c_val} ({val_part.strip('() ')})"
                    parsed = parse_retencion_token(token)
                    if parsed:
                        ret_items.append(parsed)
                    c_idx += 2
                else:
                    # Token individual ya formateado tipo "ICA (0.60%: 40285.80)"
                    parsed = parse_retencion_token(c_val)
                    if parsed:
                        ret_items.append(parsed)
                    c_idx += 1

            total_estampillas = sum(
                float(it.get("valor", 0.0) or 0.0)
                for it in ret_items
                if it.get("es_estampilla") or any(k in it.get("concepto", "").lower() for k in ["estampilla", "cultura", "hospital", "justicia", "deporte"])
            )
            ret_raw = ", ".join([f"{it['concepto']} ({it['porcentaje']:.2f}%: {it['valor']:.2f})" for it in ret_items]) if ret_items else "Sin retenciones"

            existing = db.query(PagoContrato).filter(
                PagoContrato.codigo_contrato == norm_code,
                PagoContrato.codigo_egreso == egreso_code
            ).first()

            if existing:
                existing.fecha_expedicion = fecha_exp or existing.fecha_expedicion
                existing.nombre_beneficiario = benef_name or existing.nombre_beneficiario
                existing.rubro_egreso = rubro or existing.rubro_egreso
                existing.total_orden = tot_orden
                existing.total_retencion = tot_ret
                existing.total_pagar = tot_pagar
                existing.contrato_id = contrato_id or existing.contrato_id
                existing.contratista_id = contratista_id or existing.contratista_id
                if ret_items:
                    existing.retenciones_detalle = ret_items
                    existing.total_estampillas = total_estampillas
                    existing.retenciones_raw = ret_raw
                updated += 1
            else:
                new_p = PagoContrato(
                    codigo_contrato=norm_code,
                    codigo_egreso=egreso_code,
                    fecha_expedicion=fecha_exp,
                    nombre_beneficiario=benef_name,
                    rubro_egreso=rubro,
                    total_orden=tot_orden,
                    total_retencion=tot_ret,
                    total_estampillas=total_estampillas,
                    total_pagar=tot_pagar,
                    retenciones_detalle=ret_items,
                    retenciones_raw=ret_raw,
                    contrato_id=contrato_id,
                    contratista_id=contratista_id,
                    vigencia=2026,
                    observaciones="Importado desde archivo por usuario"
                )
                db.add(new_p)
                inserted += 1
        except Exception as ex:
            errors.append(f"Línea {row_idx}: {str(ex)}")

    db.commit()
    logger.info(f"Importación de pagos finalizada. Insertados: {inserted}, Actualizados: {updated}, Errores: {len(errors)}")

    return {
        "success": True,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "total_procesados": inserted + updated
    }

@execution_router.post("/import-pdf-packets")
async def import_pdf_payment_packets(
    files: List[UploadFile] = File(...),
    vigencia: int = Form(2026),
    overwrite_duplicates: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    """
    Importa uno o múltiples paquetes de pago en formato PDF (Comprobante de Egreso, OP, Factura, Supervisión).
    Extrae la información bajo la estructura del TXT y vincula al contratista/contrato correspondiente.
    REGLA ESTRICTA: La información de pagos y estampillas se extrae exclusivamente del Comprobante de Egreso.
    Si overwrite_duplicates es False: reporta duplicados y omite su sobrescritura para proteger integridad.
    Si overwrite_duplicates es True: actualiza los valores, retenciones, fechas y estampillas del comprobante existente.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Debe adjuntar al menos un archivo PDF.")

    total_files = len(files)
    inserted = []
    updated = []
    duplicates = []
    ambiguous = []
    errors = []
    seen_in_batch = set()

    contracts_map = {c.numero_contrato: c for c in db.query(Contrato).all()}
    
    txt_lines = [
        "Código del Contrato,Código del Egreso,Fecha de Expedición,Nombre del Beneficiario,Rubro Egreso,Total Orden,Total Retención,Total a Pagar,Nombre retenciones, (% / Valor)"
    ]

    for file in files:
        try:
            filename = file.filename or "paquete_pago.pdf"
            if not filename.lower().endswith(".pdf"):
                errors.append(f"'{filename}': Formato no soportado, se esperaba un archivo .pdf")
                continue

            file_bytes = await file.read()
            if len(file_bytes) < 100:
                errors.append(f"'{filename}': Archivo vacío o corrupto")
                continue

            # Extraer información estructurada del paquete PDF (exclusivamente del Egreso)
            record = extract_payment_packet_data(file_bytes, filename, db, vigencia_default=vigencia)
            
            raw_contract = record.get("codigo_contrato") or ""
            norm_contract = CONTRACT_ALIASES.get(raw_contract, raw_contract)
            record["codigo_contrato"] = norm_contract

            egreso_code = record.get("codigo_egreso") or ""
            if not egreso_code or "PENDIENTE" in egreso_code:
                errors.append(f"'{filename}': No se pudo identificar el número de Comprobante de Egreso (CE Nº ...)")
                continue

            # Si se identificó un contrato específico (ej. desde la Certificación de Supervisión) pero no existe en la base de datos:
            # Notificar: "El pago pertenece al contrato CS-023-2026, pero este contrato aún no ha sido creado en el sistema. ¿Deseas registrarlo?"
            cert_code = record.get("cert_contrato_codigo") or (norm_contract if norm_contract and norm_contract not in ("SIN_ASIGNAR", "PENDIENTE_SELECCION") else None)
            if cert_code and not contracts_map.get(cert_code) and not record.get("contrato_id"):
                c_exists = db.query(Contrato).filter(Contrato.numero_contrato == cert_code).first()
                if not c_exists:
                    msg = f"'{filename}': El pago pertenece al contrato {cert_code}, pero este contrato aún no ha sido creado en el sistema. ¿Deseas registrarlo?"
                    logger.warning(msg)
                    errors.append(msg)
                    continue

            # Verificación Crítica de Multicontrato Ambiguo:
            # Si el contratista posee 2 o más contratos y el PDF no especificó de forma unívoca el código:
            # ESTÁ PROHIBIDO asignarlo automáticamente. Pausar y reportar para selección interactiva.
            if record.get("requiere_seleccion_contrato"):
                logger.warning(f"Comprobante {egreso_code} de {record.get('nombre_beneficiario')} requiere selección de contrato entre: {[c['numero_contrato'] for c in record.get('contratos_candidatos', [])]}")
                ambiguous.append({
                    "archivo": filename,
                    "codigo_egreso": egreso_code,
                    "nombre_beneficiario": record.get("nombre_beneficiario"),
                    "nit_beneficiario": record.get("nit_beneficiario"),
                    "fecha_expedicion": record.get("fecha_expedicion_str"),
                    "total_orden": record.get("total_orden"),
                    "total_retencion": record.get("total_retencion"),
                    "total_estampillas": record.get("total_estampillas", 0.0),
                    "total_pagar": record.get("total_pagar"),
                    "contratos_candidatos": record.get("contratos_candidatos", []),
                    "payload_pago": {
                        "codigo_egreso": egreso_code,
                        "fecha_expedicion": str(record.get("fecha_expedicion")) if record.get("fecha_expedicion") else None,
                        "nombre_beneficiario": record.get("nombre_beneficiario"),
                        "rubro_egreso": record.get("rubro_egreso"),
                        "total_orden": record.get("total_orden", 0.0),
                        "total_retencion": record.get("total_retencion", 0.0),
                        "total_estampillas": record.get("total_estampillas", 0.0),
                        "total_pagar": record.get("total_pagar", 0.0),
                        "retenciones_detalle": record.get("retenciones_detalle", []),
                        "retenciones_raw": record.get("retenciones_raw", "Sin retenciones"),
                        "contratista_id": record.get("contratista_id"),
                        "vigencia": vigencia,
                        "observaciones": f"Importado desde paquete PDF '{filename}'. Factura: {record.get('factura_numero') or 'N/A'}. OP: {record.get('orden_pago') or 'N/A'}."
                    }
                })
                continue

            # 1. Validar duplicado dentro del mismo lote de carga
            if egreso_code in seen_in_batch:
                duplicates.append({
                    "archivo": filename,
                    "codigo_egreso": egreso_code,
                    "codigo_contrato": norm_contract,
                    "nombre_beneficiario": record.get("nombre_beneficiario"),
                    "total_orden": record.get("total_orden"),
                    "total_retencion": record.get("total_retencion"),
                    "total_pagar": record.get("total_pagar"),
                    "total_estampillas": record.get("total_estampillas", 0.0),
                    "motivo": f"El comprobante {egreso_code} está repetido dentro del mismo grupo de archivos adjuntos."
                })
                continue

            # 2. Validar si ya existe en la base de datos
            normalized_ce = egreso_code.replace("º", "°").strip()
            existing = db.query(PagoContrato).filter(
                or_(
                    PagoContrato.codigo_egreso == egreso_code,
                    func.replace(PagoContrato.codigo_egreso, "º", "°") == normalized_ce
                )
            ).first()

            if existing:
                if overwrite_duplicates:
                    # Actualizar el registro existente con los datos corregidos extraídos del PDF
                    contract = contracts_map.get(norm_contract)
                    contrato_id = record.get("contrato_id") or (contract.id if contract else existing.contrato_id)
                    contratista_id = record.get("contratista_id") or (contract.contratista_id if contract else existing.contratista_id)

                    existing.codigo_contrato = norm_contract or existing.codigo_contrato
                    if record.get("fecha_expedicion"):
                        existing.fecha_expedicion = record.get("fecha_expedicion")
                    if record.get("nombre_beneficiario"):
                        existing.nombre_beneficiario = record.get("nombre_beneficiario")
                    if record.get("rubro_egreso"):
                        existing.rubro_egreso = record.get("rubro_egreso")
                    
                    existing.total_orden = record.get("total_orden", existing.total_orden)
                    existing.total_retencion = record.get("total_retencion", existing.total_retencion)
                    existing.total_estampillas = record.get("total_estampillas", existing.total_estampillas)
                    existing.total_pagar = record.get("total_pagar", existing.total_pagar)
                    existing.retenciones_detalle = record.get("retenciones_detalle", existing.retenciones_detalle)
                    existing.retenciones_raw = record.get("retenciones_raw", existing.retenciones_raw)
                    existing.contrato_id = contrato_id
                    existing.contratista_id = contratista_id
                    existing.vigencia = vigencia
                    existing.observaciones = f"Actualizado desde paquete PDF '{filename}'. Factura: {record.get('factura_numero') or 'N/A'}. OP: {record.get('orden_pago') or 'N/A'}."

                    updated.append({
                        "archivo": filename,
                        "codigo_contrato": existing.codigo_contrato,
                        "codigo_egreso": egreso_code,
                        "fecha_expedicion": record.get("fecha_expedicion_str"),
                        "nombre_beneficiario": existing.nombre_beneficiario,
                        "rubro_egreso": existing.rubro_egreso,
                        "total_orden": existing.total_orden,
                        "total_retencion": existing.total_retencion,
                        "total_estampillas": existing.total_estampillas,
                        "total_pagar": existing.total_pagar,
                        "retenciones_detalle": existing.retenciones_detalle,
                        "retenciones_raw": existing.retenciones_raw,
                        "contratista_nombre": record.get("contratista_nombre")
                    })
                    txt_lines.append(format_record_to_txt_line(record))
                    seen_in_batch.add(egreso_code)
                    continue
                else:
                    duplicates.append({
                        "archivo": filename,
                        "codigo_egreso": egreso_code,
                        "codigo_contrato": existing.codigo_contrato,
                        "nombre_beneficiario": existing.nombre_beneficiario,
                        "total_orden": existing.total_orden,
                        "total_retencion": existing.total_retencion,
                        "total_estampillas": existing.total_estampillas,
                        "total_pagar": existing.total_pagar,
                        "motivo": f"El comprobante {egreso_code} ya se encuentra registrado previamente en el contrato {existing.codigo_contrato} ({existing.nombre_beneficiario}). No se cargó de nuevo para evitar duplicidad."
                    })
                    continue

            # 3. Si no existe, asociar y crear nuevo PagoContrato
            contract = contracts_map.get(norm_contract)
            contrato_id = record.get("contrato_id") or (contract.id if contract else None)
            contratista_id = record.get("contratista_id") or (contract.contratista_id if contract else None)

            if contrato_id and (not norm_contract or norm_contract == "SIN_ASIGNAR"):
                c_cand = db.query(Contrato).filter(Contrato.id == contrato_id).first()
                if c_cand:
                    norm_contract = c_cand.numero_contrato
                    record["codigo_contrato"] = norm_contract

            if not contratista_id and record.get("nombre_beneficiario"):
                c_cand = db.query(Contratista).filter(
                    Contratista.nombre_o_razon_social.ilike(f"%{record['nombre_beneficiario'][:10]}%")
                ).first()
                if c_cand:
                    contratista_id = c_cand.id

            new_payment = PagoContrato(
                codigo_contrato=norm_contract,
                codigo_egreso=egreso_code,
                fecha_expedicion=record.get("fecha_expedicion"),
                nombre_beneficiario=record.get("nombre_beneficiario"),
                rubro_egreso=record.get("rubro_egreso"),
                total_orden=record.get("total_orden", 0.0),
                total_retencion=record.get("total_retencion", 0.0),
                total_estampillas=record.get("total_estampillas", 0.0),
                total_pagar=record.get("total_pagar", 0.0),
                retenciones_detalle=record.get("retenciones_detalle", []),
                retenciones_raw=record.get("retenciones_raw", "Sin retenciones"),
                contrato_id=contrato_id,
                contratista_id=contratista_id,
                vigencia=vigencia,
                observaciones=f"Importado desde paquete PDF '{filename}'. Factura: {record.get('factura_numero') or 'N/A'}. OP: {record.get('orden_pago') or 'N/A'}."
            )
            db.add(new_payment)
            seen_in_batch.add(egreso_code)
            
            inserted.append({
                "archivo": filename,
                "codigo_contrato": norm_contract,
                "codigo_egreso": egreso_code,
                "fecha_expedicion": record.get("fecha_expedicion_str"),
                "nombre_beneficiario": record.get("nombre_beneficiario"),
                "rubro_egreso": record.get("rubro_egreso"),
                "total_orden": record.get("total_orden"),
                "total_retencion": record.get("total_retencion"),
                "total_estampillas": record.get("total_estampillas", 0.0),
                "total_pagar": record.get("total_pagar"),
                "retenciones_detalle": record.get("retenciones_detalle", []),
                "retenciones_raw": record.get("retenciones_raw", "Sin retenciones"),
                "contratista_nombre": record.get("contratista_nombre")
            })

            txt_lines.append(format_record_to_txt_line(record))

        except Exception as ex:
            logger.error(f"Error procesando archivo '{file.filename}': {ex}")
            errors.append(f"'{file.filename}': {str(ex)}")

    if inserted or updated:
        db.commit()
        logger.info(f"Carga de paquetes PDF finalizada: {len(inserted)} comprobantes nuevos insertados, {len(updated)} actualizados, {len(duplicates)} repetidos omitidos, {len(ambiguous)} pendientes de asignación.")

    return {
        "success": True,
        "total_files": total_files,
        "inserted_count": len(inserted),
        "updated_count": len(updated),
        "duplicates_count": len(duplicates),
        "ambiguous_count": len(ambiguous),
        "errors_count": len(errors),
        "inserted": inserted,
        "updated": updated,
        "duplicates": duplicates,
        "ambiguous": ambiguous,
        "errors": errors,
        "txt_content": "\n".join(txt_lines)
    }

@execution_router.get("/export")
def export_execution_csv(
    vigencia: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Export all payments as a downloadable CSV file including retenciones and estampillas."""
    q = db.query(PagoContrato)
    if vigencia and vigencia.upper() != "ALL":
        try:
            q = q.filter(PagoContrato.vigencia == int(vigencia))
        except ValueError:
            pass
    pagos = q.order_by(PagoContrato.codigo_contrato, PagoContrato.fecha_expedicion).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Código del Contrato",
        "Código del Egreso",
        "Fecha de Expedición",
        "Nombre del Beneficiario",
        "Rubro Egreso",
        "Total Orden",
        "Total Retención",
        "Total Estampillas",
        "Total a Pagar",
        "Retenciones Detalladas",
        "Vigencia"
    ])

    for p in pagos:
        f_str = p.fecha_expedicion.strftime("%d/%m/%Y") if p.fecha_expedicion else ""
        writer.writerow([
            p.codigo_contrato,
            p.codigo_egreso,
            f_str,
            p.nombre_beneficiario,
            p.rubro_egreso or "",
            f"{p.total_orden:.2f}",
            f"{p.total_retencion:.2f}",
            f"{getattr(p, 'total_estampillas', 0.0) or 0.0:.2f}",
            f"{p.total_pagar:.2f}",
            getattr(p, 'retenciones_raw', '') or "Sin retenciones",
            p.vigencia
        ])

    csv_data = output.getvalue()
    filename = f"ESPY_Ejecucion_Pagos_{vigencia or '2026'}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
