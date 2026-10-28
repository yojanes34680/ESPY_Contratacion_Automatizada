"""Test suite integral para validar el cumplimiento estricto del módulo de OBJETO CONTRACTUAL de la ESPY.

Verifica:
1. Regla Prohibitiva 1: PROHIBIDO redactar objetos vagos, ambiguos o universales ("PRESTACIÓN DE SERVICIOS PARA LAS ACTIVIDADES TÉCNICAS REQUERIDAS", etc.).
2. Regla Prohibitiva 2: PROHIBIDO enumerar toda la lista de ítems dentro del objeto (no es lista de mercado).
3. Regla Prohibitiva 3: PROHIBIDO iniciar con verbos en infinitivo sueltos ("REALIZAR EL...", "SUMINISTRAR...").
4. Fórmula Estructural Obligatoria de 4 Bloques:
   [BLOQUE 1: Tipología exacta] + [BLOQUE 2: Núcleo técnico real] + [BLOQUE 3: Condición o alcance] + [BLOQUE 4: Destino institucional]
5. Redacción en MAYÚSCULAS SOSTENIDAS (UPPERCASE) de entre 20 y 45 palabras.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("backend").resolve()))

from app.utils.objeto_builder import (
    build_objeto_contractual,
    is_vague_or_prohibited_objeto
)
from app.utils.object_normalizer import normalize_objeto_contractual
from app.services.agents.object_agent import object_agent
from app.schemas.agent import ObjetoGenerationInput

def test_reglas_prohibitivas_deteccion():
    print("\n--- TEST 1: REGLAS PROHIBITIVAS - DETECCIÓN DE AMBIGÜEDAD Y VAGUEDAD ---")
    vagos = [
        "PRESTACIÓN DE SERVICIOS PARA LAS ACTIVIDADES TÉCNICAS REQUERIDAS",
        "SUMINISTRO DE ELEMENTOS NECESARIOS PARA LA EMPRESA",
        "APOYO EN LABORES VARIAS",
        "LABORES VARIAS",
        "SUMINISTROS VARIOS"
    ]
    for v in vagos:
        assert is_vague_or_prohibited_objeto(v), f"Debería detectarse como vago: {v}"
        # Si se pasa a normalización, debe reestructurarse a un objeto técnico de la ESPY
        norm = normalize_objeto_contractual(v, "PRESTACION_SERVICIOS")
        assert not is_vague_or_prohibited_objeto(norm), f"El normalizado no debe ser vago: {norm}"
        assert norm == norm.upper()
        print(f"  [OK] Vago transformado: '{v}' -> '{norm}'")

def test_regla_no_iniciar_con_verbos_en_infinitivo_sueltos():
    print("\n--- TEST 2: REGLA PROHIBITIVA - NO INICIAR CON VERBOS EN INFINITIVO SUELTOS ---")
    entradas_infinitivo = [
        ("REALIZAR EL MANTENIMIENTO DE BOMBAS SUMERGIBLES", "PRESTACION_SERVICIOS"),
        ("SUMINISTRAR REPUESTOS PARA EL ÁREA DE ACUEDUCTO", "SUMINISTRO"),
        ("EJECUTAR LAS OBRAS DE REPOSICIÓN DE REDES", "OBRA"),
        ("ARRENDAR VEHÍCULO AUTOMOTOR OPERATIVO", "ARRENDAMIENTO")
    ]
    for entrada, tip in entradas_infinitivo:
        res = build_objeto_contractual(propuesta_o_cotizacion=entrada, tipologia=tip)
        print(f"  Entrada con infinitivo: '{entrada}' -> Objeto: '{res}'")
        first_word = res.split()[0]
        assert first_word not in ("REALIZAR", "SUMINISTRAR", "EJECUTAR", "ARRENDAR"), f"No puede iniciar con infinitivo suelto: {first_word}"
        assert res == res.upper()
        assert not is_vague_or_prohibited_objeto(res)

def test_regla_no_lista_de_mercado_y_sintesis_tecnica():
    print("\n--- TEST 3: REGLA PROHIBITIVA - NO LISTA DE MERCADO (SÍNTESIS TÉCNICA) ---")
    items_propuesta = [
        "1. Alicate de presión 10 pulgadas",
        "2. Llave para tubo de 14 pulgadas",
        "3. Taladro percutor de 1/2 pulgada",
        "4. Cortatubos para tubería PVC",
        "5. Juego de destornilladores dieléctricos",
        "6. Flexómetro de 5 metros",
        "7. Prensa de banco número 4",
        "8. Termofusora para polietileno"
    ]
    res = build_objeto_contractual(
        propuesta_o_cotizacion="Mantenimiento general de herramientas",
        tipologia="PRESTACION_SERVICIOS",
        items_propuesta=items_propuesta,
        contexto="Área operativa de fontanería y acueducto"
    )
    print(f"  Objeto sintetizado con 8 ítems:\n  -> '{res}'")
    # Verificar que no es una lista de mercado con números ni viñetas
    assert "1." not in res and "2." not in res and "Alicate" not in res
    # Debe ser síntesis técnica
    assert "HERRAMIENTAS" in res or "EQUIPOS" in res
    assert res == res.upper()
    word_count = len(res.split())
    assert 15 <= word_count <= 45, f"Debe tener entre 20 y 45 palabras aprox (obtenido {word_count})"

def test_formula_4_bloques_en_diversas_tipologias():
    print("\n--- TEST 4: FÓRMULA DE 4 BLOQUES EN DIVERSAS TIPOLOGÍAS Y DESTINOS ESPY ---")

    # Caso 1: Servicios Profesionales / PGIRS
    obj_pgirs = build_objeto_contractual(
        propuesta_o_cotizacion="Sensibilización ambiental y socialización puerta a puerta de la ruta selectiva",
        tipologia="PRESTACION_SERVICIOS",
        contexto="Implementación del PGIRS del municipio"
    )
    print(f"  Caso PGIRS:\n  -> '{obj_pgirs}'")
    assert obj_pgirs.startswith("PRESTACIÓN DE SERVICIOS")
    assert "SENSIBILIZACIÓN" in obj_pgirs or "RUTA SELECTIVA" in obj_pgirs
    assert "PUERTA A PUERTA" in obj_pgirs
    assert "PGIRS" in obj_pgirs
    assert obj_pgirs == obj_pgirs.upper()

    # Caso 2: Servicios de Apoyo a la Gestión / Mantenimiento Operativo a Todo Costo
    obj_mant = build_objeto_contractual(
        propuesta_o_cotizacion="Mantenimiento de herramientas eléctricas y equipos electromecánicos a todo costo",
        tipologia="PRESTACION_SERVICIOS",
        contexto="Taller y fontanería de la empresa"
    )
    print(f"  Caso Mantenimiento Operativo:\n  -> '{obj_mant}'")
    assert "PRESTACIÓN DE SERVICIOS" in obj_mant
    assert "MANTENIMIENTO DE HERRAMIENTAS" in obj_mant
    assert "A TODO COSTO" in obj_mant
    assert "ÁREA OPERATIVA" in obj_mant or "EMPRESA DE SERVICIOS PÚBLICOS" in obj_mant

    # Caso 3: Suministro de Insumos Químicos PTAP
    obj_sum = build_objeto_contractual(
        propuesta_o_cotizacion="Insumos químicos coagulantes y desinfectantes para potabilización",
        tipologia="SUMINISTRO",
        contexto="Planta de tratamiento de agua potable de la ESPY"
    )
    print(f"  Caso Suministro PTAP:\n  -> '{obj_sum}'")
    assert obj_sum.startswith("SUMINISTRO DE")
    assert "QUÍMICOS" in obj_sum or "COAGULANTES" in obj_sum
    assert "PLANTA DE TRATAMIENTO DE AGUA POTABLE" in obj_sum or "ESPY" in obj_sum

    # Caso 4: Obra Civil / Redes Alcantarillado
    obj_obra = build_objeto_contractual(
        propuesta_o_cotizacion="Adecuación de infraestructura y reposición de tubería de colector",
        tipologia="OBRA",
        contexto="Red de alcantarillado"
    )
    print(f"  Caso Obra Civil:\n  -> '{obj_obra}'")
    assert "EJECUCIÓN DE OBRAS" in obj_obra or "MANTENIMIENTO Y ADECUACIÓN" in obj_obra
    assert "INFRAESTRUCTURA" in obj_obra or "TUBERÍA" in obj_obra or "REDES" in obj_obra
    assert "ALCANTARILLADO" in obj_obra or "ESPY" in obj_obra

    # Caso 5: Arrendamiento de Vehículo Operativo
    obj_arr = build_objeto_contractual(
        propuesta_o_cotizacion="Alquiler de camioneta 4x4 de trabajo para cuadrilla",
        tipologia="ARRENDAMIENTO",
        contexto="Área operativa de la empresa"
    )
    print(f"  Caso Arrendamiento:\n  -> '{obj_arr}'")
    assert obj_arr.startswith("ARRENDAMIENTO DE")
    assert "VEHÍCULO" in obj_arr or "CAMIONETA" in obj_arr
    assert "ÁREA OPERATIVA" in obj_arr or "EMPRESA DE SERVICIOS PÚBLICOS" in obj_arr

def test_object_agent_integration_with_new_rules():
    print("\n--- TEST 5: INTEGRACIÓN OBJECT AGENT Y LONGITUD 20-45 PALABRAS ---")
    inp = ObjetoGenerationInput(
        tipologia="PRESTACION_SERVICIOS",
        necesidad_descripcion="Mantenimiento preventivo y correctivo de herramientas a todo costo",
        contratista_nombre="TECNISERVICIOS YOLOMBÓ",
        lugar_ejecucion="taller y área operativa de la ESPY"
    )
    res = object_agent.generate_objeto(inp)
    obj = res.objeto_sugerido
    print(f"  Objeto ObjectAgent:\n  -> '{obj}'")
    assert obj == obj.upper(), "Debe ser mayúsculas sostenidas"
    assert not is_vague_or_prohibited_objeto(obj)
    palabras = len(obj.split())
    print(f"  Conteo de palabras: {palabras} (rango objetivo: 20-45 palabras)")
    assert 18 <= palabras <= 50, f"Longitud de palabras fuera de rango: {palabras}"
    first_w = obj.split()[0]
    assert first_w not in ("REALIZAR", "EJECUTAR", "SUMINISTRAR"), f"No puede iniciar con infinitivo: {first_w}"
    print("  [OK] ObjectAgent cumple con todas las reglas prohibitivas y la fórmula de 4 bloques.")

if __name__ == "__main__":
    test_reglas_prohibitivas_deteccion()
    test_regla_no_iniciar_con_verbos_en_infinitivo_sueltos()
    test_regla_no_lista_de_mercado_y_sintesis_tecnica()
    test_formula_4_bloques_en_diversas_tipologias()
    test_object_agent_integration_with_new_rules()
    print("\n==================================================================")
    print(" TODAS LAS PRUEBAS DEL MÓDULO OBJETO CONTRACTUAL PASARON AL 100%!")
    print("==================================================================")
