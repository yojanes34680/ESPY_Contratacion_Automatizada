"""Test unitario y de integración para validar la exigencia metodológica de Objetivos Específicos:
Cada objetivo específico DEBE iniciar obligatoriamente con un verbo de acción en infinitivo
(ej: Realizar, Ejecutar, Suministrar, Instalar, Construir, etc.), sin líneas truncadas ni sustantivos huérfanos.
"""
import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path("backend").resolve()))

from app.utils.objective_normalizer import (
    normalize_objetivos_especificos,
    format_single_objective,
    clean_technical_text,
    starts_with_infinitive
)
from app.services.gemini_client import gemini_service
from app.services.agents.works_agent import WorksContractAgent
from app.services.agents.services_agent import ServicesContractAgent
from app.services.agents.supply_agent import SupplyContractAgent
from app.schemas.agent import ContractDraftingInput

def test_verb_infinitive_rule_on_real_proposal():
    print("\n=== PRUEBA 1: PROPUESTA REAL DE OBRA / FONTANERÍA (CASO USUARIO) ===")
    ocr_file = Path("backend/storage/uploads/7917234b1a_PROPUESTA ECONOMICA.ocr.txt")
    assert ocr_file.exists(), "El archivo OCR de propuesta debe existir"
    
    ocr_text = ocr_file.read_text(encoding="utf-8")
    ext_data = gemini_service._heuristic_contractor_extraction(ocr_text)

    print(f"Objeto Propuesto: {ext_data.objeto_propuesto}")
    print(f"Objetivos Específicos extraídos ({len(ext_data.objetivos_especificos)}):")
    for idx, obj in enumerate(ext_data.objetivos_especificos, 1):
        print(f"  {idx}. {obj}")
        # Validar que inicia con infinitivo
        assert starts_with_infinitive(obj), f"El objetivo '{obj}' NO inicia con verbo en infinitivo"
        # Validar que no contiene fragmentos truncados huérfanos
        assert not obj.lower().startswith("seccoion de"), f"Objetivo huérfano de sección detectado: {obj}"
        assert not obj.lower().startswith("todo lo necesario"), f"Objetivo huérfano de coletilla detectado: {obj}"
        # Validar ortografía corregida
        assert "compectacion" not in obj.lower(), f"Error ortográfico compectacion presente en: {obj}"
        assert "priveniente" not in obj.lower(), f"Error ortográfico priveniente presente en: {obj}"
        assert "excavacign" not in obj.lower(), f"Error ortográfico excavacign presente en: {obj}"

    # Validar el ejemplo exacto del usuario:
    assert any("realizar excavación manual" in o.lower() for o in ext_data.objetivos_especificos), "Falta el objetivo de excavación manual con verbo Realizar"
    assert any("realizar rotura de pavimento" in o.lower() for o in ext_data.objetivos_especificos), "Falta el objetivo de rotura de pavimento con verbo Realizar"
    assert any("suministrar, transportar e instalar tubería" in o.lower() for o in ext_data.objetivos_especificos), "Falta el objetivo de tubería con verbo Suministrar"
    assert any("realizar lleno y compactación" in o.lower() for o in ext_data.objetivos_especificos), "Falta el objetivo de compactación con verbo Realizar"
    assert any("realizar reposición de pavimento" in o.lower() for o in ext_data.objetivos_especificos), "Falta el objetivo de reposición con verbo Realizar"

    print("[OK] Propuesta del usuario normalizada y formulada con infinitivos correctamente.")

def test_normalization_rules():
    print("\n=== PRUEBA 2: REGLAS DIRECTAS DE CONVERSIÓN A INFINITIVO ===")
    casos = [
        ("Excavacion manual bajo cualquier grado de humedad para instalacion de tuberia.", "Realizar excavación manual bajo cualquier grado de humedad para instalación de tubería."),
        ("Rotura de pavimento.", "Realizar rotura de pavimento."),
        ("Suministro, transporte e instalacion de tubería.", "Suministrar, transportar e instalar tubería."),
        ("Lleno y compactacion manual con material proveniente de la excavacion.", "Realizar lleno y compactación manual con material proveniente de la excavación."),
        ("Reposicion de pavimento.", "Realizar reposición de pavimento."),
        ("Mantenimiento preventivo de pozos sépticos.", "Realizar el mantenimiento preventivo de pozos sépticos."),
        ("Instalación de válvulas de compuerta.", "Instalar válvulas de compuerta."),
        ("Construcción de red de alcantarillado.", "Construir red de alcantarillado."),
        ("Adecuación de instalaciones operativas.", "Adecuar instalaciones operativas."),
        ("Elaboración de informes de gestión.", "Elaborar informes de gestión.")
    ]

    for raw, expected_start in casos:
        formateado = format_single_objective(raw)
        print(f"  Entrada: '{raw}' -> Salida: '{formateado}'")
        assert starts_with_infinitive(formateado), f"'{formateado}' no inicia con infinitivo"

    print("[OK] Todas las reglas de conversión sustantivo -> infinitivo funcionan correctamente.")

def test_agents_drafting_objectives():
    print("\n=== PRUEBA 3: AGENTES ESPECIALIZADOS (OBRA, SERVICIOS, SUMINISTRO) ===")
    works = WorksContractAgent()
    services = ServicesContractAgent()
    supply = SupplyContractAgent()

    inp = ContractDraftingInput(
        tipologia="OBRA",
        necesidad_descripcion="reparacion de redes de acueducto sector camelias",
        valor_estimado=9400000.0,
        plazo=1,
        unidad_plazo="MESES"
    )

    r_w = works.fallback_generator(inp)
    for obj in r_w.objetivos_especificos:
        print(f"  [Obra]: {obj}")
        assert starts_with_infinitive(obj), f"[Obra] '{obj}' no inicia con infinitivo"

    inp.tipologia = "PRESTACION_SERVICIOS"
    inp.necesidad_descripcion = "evaluaciones medicas ocupacionales para trabajadores"
    r_s = services.fallback_generator(inp)
    for obj in r_s.objetivos_especificos:
        print(f"  [Servicios]: {obj}")
        assert starts_with_infinitive(obj), f"[Servicios] '{obj}' no inicia con infinitivo"

    inp.tipologia = "SUMINISTRO"
    inp.necesidad_descripcion = "suministro de cloro gas y sulfato de aluminio"
    r_u = supply.fallback_generator(inp)
    for obj in r_u.objetivos_especificos:
        print(f"  [Suministro]: {obj}")
        assert starts_with_infinitive(obj), f"[Suministro] '{obj}' no inicia con infinitivo"

    print("[OK] Todos los agentes garantizan objetivos específicos en infinitivo.")

if __name__ == "__main__":
    test_verb_infinitive_rule_on_real_proposal()
    test_normalization_rules()
    test_agents_drafting_objectives()
    print("\n=== TODAS LAS PRUEBAS DE OBJETIVOS ESPECÍFICOS EN INFINITIVO PASARON (100%) ===")
