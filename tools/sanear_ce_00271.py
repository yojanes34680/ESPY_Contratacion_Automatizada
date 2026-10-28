"""
Script de saneamiento para el Comprobante de Egreso CE N° 00271.
Reasigna el pago al contrato CS-023-2026 y corrige los valores numéricos íntegros.
"""
import sys
from pathlib import Path

backend_path = Path(__file__).resolve().parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.database import SessionLocal
from app.models.execution import PagoContrato
from app.models.contract import Contrato
from app.services.payment_packet_parser import format_record_to_txt_line


def sanear_pago_ce_00271():
    db = SessionLocal()
    try:
        pago = db.query(PagoContrato).filter(PagoContrato.codigo_egreso.like('%271%')).first()
        contrato = db.query(Contrato).filter(Contrato.numero_contrato == 'CS-023-2026').first()
        
        if not pago:
            print("No se encontró el registro de pago CE N° 00271")
            return
        if not contrato:
            print("No se encontró el contrato CS-023-2026")
            return

        print(f"Estado anterior: ID={pago.id}, Contrato={pago.codigo_contrato}, Orden={pago.total_orden}, Ret={pago.total_retencion}, Pagar={pago.total_pagar}")

        # Valores íntegros
        total_orden = 3104100.00
        total_retencion = 344555.10
        total_pagar = round(total_orden - total_retencion, 2)  # 2759544.90

        pago.codigo_contrato = 'CS-023-2026'
        pago.contrato_id = contrato.id
        pago.contratista_id = contrato.contratista_id
        pago.nombre_beneficiario = 'LUIS ALEJANDRO MARIN ARBOLEDA'
        pago.rubro_egreso = '2.1.2.02.02.008'
        pago.total_orden = total_orden
        pago.total_retencion = total_retencion
        pago.total_pagar = total_pagar
        
        # Desglose de 6 retenciones
        retenciones_detalle = [
            {"concepto": "Industria y comercio ICA", "porcentaje": 0.60, "valor": 18624.60, "es_estampilla": False},
            {"concepto": "Estampilla Pro Cultura", "porcentaje": 2.00, "valor": 62082.00, "es_estampilla": True},
            {"concepto": "Estampilla Pro-Hospital", "porcentaje": 1.00, "valor": 31041.00, "es_estampilla": True},
            {"concepto": "Compras No declarantes", "porcentaje": 3.50, "valor": 108643.50, "es_estampilla": False},
            {"concepto": "Tasa Pro Deporte y Recreación", "porcentaje": 2.00, "valor": 62082.00, "es_estampilla": True},
            {"concepto": "Estampilla Pro-Justicia Familiar", "porcentaje": 2.00, "valor": 62082.00, "es_estampilla": True}
        ]
        pago.retenciones_detalle = retenciones_detalle
        pago.total_estampillas = sum(r["valor"] for r in retenciones_detalle if r["es_estampilla"])
        pago.retenciones_raw = ", ".join(f"{it['concepto']} ({it['porcentaje']:.2f}%: {it['valor']:.2f})" for it in retenciones_detalle)

        db.commit()
        db.refresh(pago)

        print(f"Estado saneado: ID={pago.id}, Contrato={pago.codigo_contrato}, Orden={pago.total_orden}, Ret={pago.total_retencion}, Pagar={pago.total_pagar}")

        # Generar registro TXT
        record = {
            "codigo_contrato": pago.codigo_contrato,
            "codigo_egreso": pago.codigo_egreso,
            "fecha_expedicion_str": pago.fecha_expedicion.strftime("%d/%m/%Y") if pago.fecha_expedicion else "25/05/2026",
            "nombre_beneficiario": pago.nombre_beneficiario,
            "rubro_egreso": pago.rubro_egreso,
            "total_orden": pago.total_orden,
            "total_retencion": pago.total_retencion,
            "total_pagar": pago.total_pagar,
            "retenciones_detalle": pago.retenciones_detalle,
            "retenciones_raw": pago.retenciones_raw
        }
        txt_line = format_record_to_txt_line(record)
        print("\n--- LÍNEA TXT GENERADA ---")
        print(txt_line)

    finally:
        db.close()

if __name__ == "__main__":
    sanear_pago_ce_00271()
