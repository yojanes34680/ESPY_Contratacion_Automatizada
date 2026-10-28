import sys
from pathlib import Path

sys.path.insert(0, str(Path("backend").resolve()))

from app.utils.objeto_builder import build_objeto_contractual, is_vague_or_prohibited_objeto
from app.utils.object_normalizer import normalize_objeto_contractual
from app.services.agents.object_agent import object_agent
from app.schemas.agent import ObjetoGenerationInput

def test_no_loop_repetition_on_successive_cycles():
    print("\n--- PRUEBA DE NO-REPETICIÓN Y ANTI-BUCLE RECURSIVO ---")
    
    # Simular objeto inicial
    initial_text = "Mantenimiento preventivo y correctivo de herramientas eléctricas a todo costo"
    
    current = initial_text
    for i in range(1, 6):
        current = build_objeto_contractual(
            propuesta_o_cotizacion=current,
            tipologia="PRESTACION_SERVICIOS",
            necesidad_descripcion=current,
            contexto="área operativa de la empresa"
        )
        current = normalize_objeto_contractual(current, "PRESTACION_SERVICIOS")
        print(f"  Ciclo {i}: {current}")
        
        # Verificar que no repita prefijos ni sufijos
        count_prestacion = current.count("PRESTACI")
        count_apoyo = current.count("APOYO A LA GESTI")
        count_operativa = current.count("ÁREA OPERATIVA") + current.count("AREA OPERATIVA")
        count_yolombo = current.count("YOLOMB")
        
        assert count_prestacion <= 1, f"Repetición de 'PRESTACIÓN DE SERVICIOS' en ciclo {i}: {count_prestacion}"
        assert count_apoyo <= 1, f"Repetición de 'APOYO A LA GESTIÓN' en ciclo {i}: {count_apoyo}"
        assert count_operativa <= 1, f"Repetición de 'ÁREA OPERATIVA' en ciclo {i}: {count_operativa}"
        assert count_yolombo <= 1, f"Repetición de 'YOLOMBÓ' en ciclo {i}: {count_yolombo}"
        assert not is_vague_or_prohibited_objeto(current)

    print("[OK] Test de no-repetición y anti-bucle superado al 100%.")

if __name__ == "__main__":
    test_no_loop_repetition_on_successive_cycles()
