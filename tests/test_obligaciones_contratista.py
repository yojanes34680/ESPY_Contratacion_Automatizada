"""Prueba integral de validación para el Módulo de Obligaciones del Contratista:
1. Regla de Simetría y Verbos Rectores en infinitivo (Ejecutar, Suministrar, Realizar, Garantizar, Entregar, Presentar...).
2. Escenario A (Propuesta Detallada >= 3 ítems): Regla de Inclusión Total (100% de actividades convertidas).
3. Escenario B (Cotización Escueta de una sola línea - ej: 'Mantenimiento a todo costo'): Desglose en mínimo 6 a 8 obligaciones específicas técnicas y de control:
   - Obligación principal literal.
   - Diagnóstico / levantamiento inicial.
   - Ejecución técnica preventiva/correctiva o entrega.
   - Cláusula de Todo Costo / calidad de repuestos nuevos u originales.
   - Pruebas de funcionamiento y entrega a satisfacción.
   - Soportes técnicos detallados (fichas, fotos antes/después, relación de repuestos) como requisito indispensable para pago.
   - Garantía técnica sobre trabajo/bienes.
4. Paso 2: Inclusión de Obligaciones Generales y Administrativas (Acta de inicio/liquidación, informes con evidencias, Ley 789/2002 seguridad social, SST/EPP, supervisor).
5. Compatibilidad e integración con docx_engine y agentes de tipología.
"""
import sys
import re
from pathlib import Path

# Agregar backend al PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.utils.obligaciones_builder import (
    build_obligaciones_contratista,
    format_obligation_infinitive,
    get_obligaciones_generales_administrativas,
    generate_escenario_b_obligaciones_especificas,
    INFINITIVE_VERBS_RE
)


def test_escenario_a_inclusion_total():
    print("=" * 70)
    print("TEST 1: ESCENARIO A - PROPUESTA DETALLADA (REGLA DE INCLUSIÓN TOTAL)")
    print("=" * 70)

    items_propuesta = [
        "Excavación manual en material común hasta 1.5 m",
        "Suministro e instalación de tubería PVC de 3 pulgadas RDE 21",
        "Instalación de válvula de compuerta elástica de 3 pulgadas",
        "Relleno y compactación con material de afirmado",
        "Reposición de pavimento en concreto rígido de 3000 PSI"
    ]

    res = build_obligaciones_contratista(
        objeto="Ejecutar las obras civiles para la reposición de redes de acueducto",
        tipologia="OBRA",
        items_propuesta=items_propuesta
    )

    assert res["escenario_detectado"] == "ESCENARIO_A", f"Esperado ESCENARIO_A, obtenido {res['escenario_detectado']}"
    especificas = res["obligaciones_especificas"]
    generales = res["obligaciones_generales"]

    # 1. Inclusión total: exactamente 5 obligaciones específicas
    assert len(especificas) == len(items_propuesta), f"Esperadas {len(items_propuesta)} específicas, obtenidas {len(especificas)}"

    # 2. Todas deben iniciar con verbo en infinitivo
    for ob in especificas + generales:
        first_word = ob.split()[0].lower().rstrip(",:;.")
        assert INFINITIVE_VERBS_RE.match(ob), f"La obligación no inicia con verbo en infinitivo: '{ob[:40]}...'"
        assert ob.endswith("."), f"La obligación no termina en punto: '{ob}'"

    # 3. Validar presencia de conceptos de la propuesta
    assert any("excavación" in ob.lower() for ob in especificas)
    assert any("tubería pvc" in ob.lower() for ob in especificas)
    assert any("válvula" in ob.lower() for ob in especificas)
    assert any("relleno" in ob.lower() or "llenado" in ob.lower() for ob in especificas)
    assert any("pavimento" in ob.lower() for ob in especificas)

    print(f"OK: Escenario A procesó {len(especificas)} obligaciones específicas con 100% de inclusión y verbos rectores.")


def test_escenario_b_cotizacion_escueta_mantenimiento():
    print("\n" + "=" * 70)
    print("TEST 2: ESCENARIO B - COTIZACIÓN ESCUETA (MANTENIMIENTO A TODO COSTO)")
    print("=" * 70)

    # Insumo de una sola línea
    items_propuesta = ["Mantenimiento a todo costo de herramientas y equipos electromecánicos"]

    res = build_obligaciones_contratista(
        objeto="Mantenimiento preventivo y correctivo de herramientas de la ESPY",
        tipologia="PRESTACION_SERVICIOS",
        items_propuesta=items_propuesta
    )

    assert res["escenario_detectado"] == "ESCENARIO_B", f"Esperado ESCENARIO_B, obtenido {res['escenario_detectado']}"
    especificas = res["obligaciones_especificas"]
    generales = res["obligaciones_generales"]

    # 1. Prohibido dejar una sola obligación: Mínimo 6 a 8 obligaciones específicas
    assert 6 <= len(especificas) <= 8, f"Esperadas entre 6 y 8 específicas, obtenidas {len(especificas)}"

    # 2. Validar los 7 componentes técnicos obligatorios de protección a la ESPY:
    texto_especificas = " ".join(especificas).lower()

    # Componente 1: Obligación principal literal
    assert any("mantenimiento" in ob.lower() and "herramientas" in ob.lower() for ob in especificas)
    # Componente 2: Diagnóstico o levantamiento de estado inicial
    assert "diagnóstico" in texto_especificas or "diagnostico" in texto_especificas or "estado inicial" in texto_especificas
    # Componente 3: Ejecución técnica detallada (preventiva/correctiva)
    assert "preventivo" in texto_especificas and "correctivo" in texto_especificas
    # Componente 4: Cláusula de Todo Costo e insumos nuevos u originales
    assert "todo costo" in texto_especificas and ("repuestos" in texto_especificas or "originales" in texto_especificas)
    # Componente 5: Pruebas de funcionamiento y entrega a satisfacción
    assert "pruebas" in texto_especificas and "entrega" in texto_especificas
    # Componente 6: Soportes técnicos detallados (fichas, fotos antes/después, repuestos) para pago
    assert ("fotográfico" in texto_especificas or "fotografico" in texto_especificas or "fichas técnicas" in texto_especificas or "fichas tecnicas" in texto_especificas) and "pago" in texto_especificas
    # Componente 7: Garantía técnica
    assert "garantizar" in texto_especificas and ("garantía" in texto_especificas or "garantia" in texto_especificas or "garantizar técnicamente" in texto_especificas)


    # 3. Todas deben iniciar con verbo en infinitivo
    for ob in especificas + generales:
        assert INFINITIVE_VERBS_RE.match(ob), f"No inicia en infinitivo: '{ob[:40]}...'"
        assert ob.endswith("."), f"No finaliza en punto: '{ob}'"

    print(f"OK: Escenario B desglosó el renglón único en {len(especificas)} obligaciones específicas con todos los blindajes técnicos.")


def test_escenario_b_suministro_escueto():
    print("\n" + "=" * 70)
    print("TEST 3: ESCENARIO B - SUMINISTRO GLOBAL ESCUETO")
    print("=" * 70)

    res = build_obligaciones_contratista(
        objeto="Suministro de papelería e insumos de oficina para la ESPY",
        tipologia="SUMINISTRO",
        items_propuesta=["Suministro de papelería y útiles de oficina"]
    )

    assert res["escenario_detectado"] == "ESCENARIO_B"
    especificas = res["obligaciones_especificas"]
    assert 6 <= len(especificas) <= 8

    texto_esp = " ".join(especificas).lower()
    assert "primera calidad" in texto_esp or "especificaciones" in texto_esp
    assert "almacén" in texto_esp or "almacen" in texto_esp or "entrega" in texto_esp
    assert "remisiones" in texto_esp or "pago" in texto_esp
    assert "garantía" in texto_esp or "garantia" in texto_esp or "reponer" in texto_esp

    print(f"OK: Suministro escueto desglosado en {len(especificas)} obligaciones de control y almacén.")


def test_obligaciones_generales_administrativas_blindaje():
    print("\n" + "=" * 70)
    print("TEST 4: BLOQUE DE OBLIGACIONES GENERALES Y ADMINISTRATIVAS (SUPERVISIÓN)")
    print("=" * 70)

    for tipo in ["PRESTACION_SERVICIOS", "SUMINISTRO", "OBRA"]:
        generales = get_obligaciones_generales_administrativas(tipo)
        texto_gen = " ".join(generales).lower()

        # Validar los 5 mandatos del usuario:
        # 1. Suscripción oportuna Acta Inicio, Parciales, Liquidación/Recibo final
        assert "acta de inicio" in texto_gen and ("liquidación" in texto_gen or "liquidacion" in texto_gen)
        # 2. Informes de ejecución detallados con evidencias verificables
        assert "informes" in texto_gen and ("evidencias" in texto_gen or "soportes" in texto_gen)
        # 3. Seguridad Social mensual (Salud, Pensión, ARL) y Parafiscales (Ley 789 de 2002 / Ley 1150 de 2007)
        assert "seguridad social" in texto_gen and "ley 789 de 2002" in texto_gen
        # 4. SG-SST y uso de EPP
        assert "sst" in texto_gen and ("epp" in texto_gen or "protección personal" in texto_gen or "proteccion personal" in texto_gen)
        # 5. Atención al supervisor del contrato
        assert "supervisor" in texto_gen

        # Verbos en infinitivo
        for ob in generales:
            assert INFINITIVE_VERBS_RE.match(ob), f"General no inicia en infinitivo: '{ob[:35]}...'"
            assert ob.endswith(".")

        print(f"OK: Obligaciones generales para {tipo} ({len(generales)} ítems) cumplen con todos los blindajes de supervisión.")


def test_services_agent_fallback():
    print("\n" + "=" * 70)
    print("TEST 5: INTEGRACIÓN CON SERVICES CONTRACT AGENT (FALLBACK)")
    print("=" * 70)

    from app.services.agents.services_agent import ServicesContractAgent
    from app.schemas.agent import ContractDraftingInput

    agent = ServicesContractAgent()
    input_data = ContractDraftingInput(
        tipologia="PRESTACION_SERVICIOS",
        necesidad_descripcion="Mantenimiento a todo costo de herramientas y equipos",
        alcance_esperado="Diagnóstico y reparación técnica",
        valor_estimado=15000000,
        plazo=6,
        unidad_plazo="MESES"
    )

    draft = agent.fallback_generator(input_data)
    assert len(draft.obligaciones_minuta) >= 10, f"Se esperaban al menos 10 obligaciones en minuta, obtenidas {len(draft.obligaciones_minuta)}"
    assert len(draft.obligaciones_estudio_previo) >= 8

    # Verificar que todas inicien en infinitivo
    for ob in draft.obligaciones_minuta:
        assert INFINITIVE_VERBS_RE.match(ob), f"Minuta no inicia en infinitivo: '{ob[:35]}...'"

    print(f"OK: ServicesContractAgent generó {len(draft.obligaciones_minuta)} obligaciones en minuta y {len(draft.obligaciones_estudio_previo)} en estudio previo.")


if __name__ == "__main__":
    test_escenario_a_inclusion_total()
    test_escenario_b_cotizacion_escueta_mantenimiento()
    test_escenario_b_suministro_escueto()
    test_obligaciones_generales_administrativas_blindaje()
    test_services_agent_fallback()
    print("\n" + "=" * 70)
    print("TODAS LAS PRUEBAS DE OBLIGACIONES DEL CONTRATISTA PASARON EXITOSAMENTE (100%)")
    print("=" * 70)
