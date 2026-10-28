import sys
from pathlib import Path
sys.path.insert(0, str(Path("backend").resolve()))

from app.database import SessionLocal
from app.models.contract import Contrato
from app.services.docx_engine import generate_docx_for_contract
from app.services.agents.risk_agent import risk_agent
from app.schemas.agent import RiskMatrixInput

def regenerate_all():
    db = SessionLocal()
    try:
        contrato = db.query(Contrato).filter(Contrato.numero_contrato == "CS-056-2026").first()
        if not contrato:
            contrato = db.query(Contrato).filter(Contrato.id == 58).first()
        if not contrato:
            print("ERROR: Contrato CS-056-2026 (ID 58) no encontrado.")
            return

        print(f"Encontrado contrato: {contrato.id} - {contrato.numero_contrato}")

        # 1. Regenerar Estudio Previo
        ep_path = generate_docx_for_contract(contrato, template_type="ESTUDIO_PREVIO_SUMINISTRO", db_session=db)
        print(f"Estudio Previo regenerado en: {ep_path}")

        # 2. Regenerar Minuta Suministro
        min_path = generate_docx_for_contract(contrato, template_type="MINUTA_SUMINISTRO", db_session=db)
        print(f"Minuta Suministro regenerada en: {min_path}")

        # 3. Regenerar Acta de Inicio
        acta_path = generate_docx_for_contract(contrato, template_type="ACTA_INICIO", db_session=db)
        print(f"Acta de Inicio regenerada en: {acta_path}")

        # 4. Regenerar Matriz de Riesgos
        risk_req = RiskMatrixInput(
            objeto=contrato.objeto,
            tipologia="SUMINISTRO",
            documentos_texto=f"{contrato.justificacion_necesidad} {contrato.objeto}",
            valor_estimado=contrato.valor_total,
            plazo_texto=f"{contrato.plazo_ejecucion} {getattr(contrato.unidad_plazo, 'value', contrato.unidad_plazo)}"
        )
        risk_result = risk_agent.generate_risk_matrix(risk_req, db=db)

        # Generar con el nombre exacto de la UI: Matriz_Riesgos_ESPY_SUMINISTRO__INSTALACI_N_Y_PUES.docx
        # y también en backend/storage/generated/
        obj_slug = (contrato.objeto or "Contractual")[:30]
        import re
        slug_clean = re.sub(r"[^a-zA-Z0-9]", "_", obj_slug)
        filename_ui = f"Matriz_Riesgos_ESPY_{slug_clean}.docx"
        
        path_matrix_ui = Path("backend/storage/generated") / filename_ui
        risk_agent.generate_docx(risk_result, path_matrix_ui)
        print(f"Matriz de Riesgos regenerada en: {path_matrix_ui}")

        # También guardar una copia en el root por si el usuario la revisa allí
        path_root = Path(filename_ui)
        risk_agent.generate_docx(risk_result, path_root)
        print(f"Matriz de Riesgos guardada en root: {path_root}")

        db.commit()
        print("Todo regenerado y guardado en la base de datos con éxito.")

    finally:
        db.close()

if __name__ == "__main__":
    regenerate_all()
