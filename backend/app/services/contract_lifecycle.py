"""Contract Lifecycle Automation Service.

Handles automatic status transitions, such as marking contracts as TERMINADO
when their fecha_terminacion has passed, while preserving manual administrative overrides.
"""
from datetime import date, datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.models.contract import Contrato, EstadoContrato
from app.models.audit_log import Auditoria
from app.utils.logger import logger


def check_and_update_expired_contracts(db: Session, sync_excel: bool = True) -> int:
    """
    Identifica y actualiza automáticamente a 'TERMINADO' los contratos cuya
    fecha_terminacion ya se haya cumplido (fecha_terminacion < date.today())
    y que se encuentren actualmente en estado 'EN_EJECUCION'.
    
    Respeta la decisión del usuario si existe un override manual explícito en metadatos_agente.
    """
    today = date.today()
    try:
        expired_candidates = db.query(Contrato).filter(
            Contrato.fecha_terminacion != None,
            Contrato.fecha_terminacion < today,
            Contrato.estado == EstadoContrato.EN_EJECUCION
        ).all()

        updated_count = 0
        updated_contracts: List[Contrato] = []

        for contract in expired_candidates:
            meta = contract.metadatos_agente or {}
            # Si el administrador forzó manualmente un estado diferente recientemente, respetarlo
            if meta.get("manual_status_override") is True:
                continue

            estado_anterior = contract.estado.value
            contract.estado = EstadoContrato.TERMINADO
            contract.updated_at = datetime.now()
            updated_count += 1
            updated_contracts.append(contract)

            # Registrar trazabilidad en auditoría
            audit = Auditoria(
                contrato_id=contract.id,
                accion="AUTO_TERMINADO",
                detalle=(
                    f"Contrato {contract.numero_contrato} actualizado automáticamente de {estado_anterior} "
                    f"a TERMINADO al vencer su plazo el {contract.fecha_terminacion}."
                ),
                usuario="Sistema (Regla Automática por Fecha)"
            )
            db.add(audit)

        if updated_count > 0:
            db.commit()
            logger.info(
                f"[AutoLifecycle] {updated_count} contratos actualizados automáticamente a TERMINADO por fecha cumplida."
            )

            # Sincronizar en el archivo Excel maestro si se solicitó
            if sync_excel:
                try:
                    from app.services.excel_engine import sync_contract_to_master_excel
                    for c in updated_contracts:
                        sync_contract_to_master_excel(c)
                    logger.info(f"[AutoLifecycle] {len(updated_contracts)} contratos sincronizados con Matriz Excel.")
                except Exception as e:
                    logger.warning(f"[AutoLifecycle] No se pudo sincronizar automáticamente con Excel: {e}")

        return updated_count

    except Exception as e:
        logger.error(f"[AutoLifecycle] Error verificando contratos vencidos: {e}", exc_info=True)
        return 0
