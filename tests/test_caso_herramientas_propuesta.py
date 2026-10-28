import sys
from pathlib import Path

sys.path.insert(0, str(Path("backend").resolve()))

from app.services.gemini_client import gemini_service
from app.services.agents.object_agent import object_agent
from app.schemas.agent import ObjetoGenerationInput

def test_user_exact_proposal_extraction_and_objeto():
    print("\n--- PRUEBA: EXTRACCIÓN Y FORMULACIÓN DEL CASO REAL DE PROPUESTA ---")
    ocr_file = Path("backend/storage/uploads/19c1f42fcf_PROPUESTA.ocr.txt")
    assert ocr_file.exists(), f"El archivo {ocr_file} no existe"
    text = ocr_file.read_text(encoding="utf-8")
    
    # 1. Probar extracción heurística de la propuesta con tabla y producto
    extracted = gemini_service.extract_contractor_data(text)
    print(f"Objeto propuesto extraído: '{extracted.objeto_propuesto}'")
    print(f"Valor propuesto extraído: {extracted.valor_propuesto}")
    
    assert extracted.objeto_propuesto is not None, "Debe extraer el objeto de la propuesta"
    assert "HERRAMIENTAS" in extracted.objeto_propuesto, f"No encontró HERRAMIENTAS en {extracted.objeto_propuesto}"
    assert "ELECTRICAS" in extracted.objeto_propuesto, f"No encontró ELECTRICAS en {extracted.objeto_propuesto}"
    assert "DISPONIBILIDAD" not in extracted.objeto_propuesto, "No debe contener DISPONIBILIDAD"
    assert "INFRAESTRUCTURA Y EQUIPOS" not in extracted.objeto_propuesto, "No debe contener fallback inventado"
    
    # 2. Probar que ObjectAgent genere el objeto basándose en este texto
    inp = ObjetoGenerationInput(
        tipologia="PRESTACION_SERVICIOS",
        texto_propuesta_o_estudio=text,
        contratista_nombre="ASOCOMUNAL YOLOMBO"
    )
    res = object_agent.generate_objeto(inp)
    print(f"Objeto generado por ObjectAgent:\n-> '{res.objeto_sugerido}'")
    
    assert "HERRAMIENTAS" in res.objeto_sugerido
    assert "ELECTRICAS" in res.objeto_sugerido
    assert "DISPONIBILIDAD" not in res.objeto_sugerido
    assert "INFRAESTRUCTURA Y EQUIPOS" not in res.objeto_sugerido
    assert res.objeto_sugerido.count("PRESTACI") <= 1
    assert res.objeto_sugerido.count("APOYO A LA GESTI") <= 1
    print("[OK] El objeto se basa 100% en el texto del PDF de la propuesta sin cadenas inventadas.")

if __name__ == "__main__":
    test_user_exact_proposal_extraction_and_objeto()
