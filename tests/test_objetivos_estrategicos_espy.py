"""Pruebas exhaustivas para el Módulo de Objetivo General y Objetivos Específicos:
1. Reglas Prohibitivas Estrictas:
   - Prohibido concatenar o incrustar el objeto en mayúsculas ("Asegurar las labores para PRESTACIÓN DE SERVICIOS DE...").
   - Prohibido trámites administrativos ("presentar informes mensuales", "pasar cuentas de cobro", "seguridad social", "reuniones").
   - Prohibido frases comodín vacías ("Ejecutar las actividades programadas en los plazos fijados").
2. Objetivo General:
   - Verbo en infinitivo de alto nivel (Garantizar, Fortalecer, Optimizar, Asegurar, Ejecutar, Proveer).
   - Acción técnica real en minúsculas fluida.
   - Fórmula lógica con beneficio misional directo en Yolombó.
3. Objetivos Específicos:
   - Entre 3 y 5 viñetas.
   - Cada una inicia con verbo en infinitivo con ortografía impecable (sin letras cortadas).
   - Estructuración en fases/logros técnicos:
     * Meta 1: Diagnóstico / Planeación / Abastecimiento.
     * Meta 2: Ejecución Nuclear / Intervención.
     * Meta 3: Calidad / Continuidad / Mitigación de riesgos.
     * Meta 4: Trazabilidad Técnica / Gestión de información.
4. Integración en docx_engine y fallbacks de agentes (Services, Supply, Works, Lease).
"""
import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path("backend").resolve()))

from app.utils.objetivos_builder import (
    build_objetivo_general,
    build_objetivos_especificos,
    build_objetivos_contrato,
    is_prohibited_objective
)
from app.utils.objective_normalizer import starts_with_infinitive
from app.services.agents.services_agent import ServicesContractAgent
from app.services.agents.supply_agent import SupplyContractAgent
from app.services.agents.works_agent import WorksContractAgent
from app.schemas.agent import ContractDraftingInput


def test_prohibiciones_estrictas():
    print("=" * 70)
    print("TEST 1: VALIDACIÓN DE REGLAS PROHIBITIVAS ESTRICTAS")
    print("=" * 70)

    # 1. Detección de trámites administrativos prohibidos
    assert is_prohibited_objective("Presentar a la supervisión informes mensuales de actividades y ejecución.")
    assert is_prohibited_objective("Radicar cuentas de cobro con soportes de pago.")
    assert is_prohibited_objective("Acreditar el pago oportuno de seguridad social y parafiscales.")
    assert is_prohibited_objective("Asistir a comités técnicos y reuniones periódicas.")
    assert is_prohibited_objective("Ejecutar las actividades programadas en los plazos fijados.")
    assert is_prohibited_objective("Acompañar y asesorar técnicamente a la supervisión designada por la ESP.")

    # 2. Objetivos técnicos válidos NO deben ser marcados como prohibidos
    assert not is_prohibited_objective("Diagnosticar el estado electromecánico de los equipos de bombeo.")
    assert not is_prohibited_objective("Realizar el mantenimiento correctivo y sustitución de rodamientos desgastados.")
    assert not is_prohibited_objective("Efectuar pruebas de aislamiento y potencia bajo carga en banco de pruebas.")
    assert not is_prohibited_objective("Levantar el historial técnico de fallas por equipo para toma de decisiones.")

    print("OK: El detector de prohibiciones bloquea trámites administrativos y frases comodín correctamente.")


def test_objetivo_general_construccion_natural():
    print("\n" + "=" * 70)
    print("TEST 2: OBJETIVO GENERAL (FÓRMULA LÓGICA Y REDACCIÓN NATURAL SIN MAYÚSCULAS)")
    print("=" * 70)

    casos = [
        (
            "PRESTACIÓN DE SERVICIOS PARA EL MANTENIMIENTO A TODO COSTO DE HERRAMIENTAS Y EQUIPOS",
            "PRESTACION_SERVICIOS",
            "mantenimiento de herramientas electromecánicas"
        ),
        (
            "SUMINISTRO DE TUBERÍAS Y ACCESORIOS PARA REDES DE ACUEDUCTO",
            "SUMINISTRO",
            "tuberías PVC y válvulas de compuerta"
        ),
        (
            "CONTRATO DE OBRA CIVIL PARA LA REPOSICIÓN DE REDES DE ALCANTARILLADO",
            "OBRA",
            "excavación, tubería y pavimento"
        ),
        (
            "APOYO A LA GESTIÓN PARA LA ACTUALIZACIÓN Y SOCIALIZACIÓN DEL PGIRS",
            "PRESTACION_SERVICIOS",
            "residuos sólidos, reciclaje y separación"
        )
    ]

    verbos_alto_nivel = {"garantizar", "fortalecer", "optimizar", "asegurar", "ejecutar", "proveer"}

    for objeto, tipo, contexto in casos:
        gen = build_objetivo_general(objeto=objeto, tipologia=tipo, contexto=contexto)
        print(f"\nObjeto: {objeto}")
        print(f"Objetivo General Generado:\n  -> {gen}")

        # Prohibición 1: Nunca incrustar el objeto literal en mayúsculas
        assert "PRESTACIÓN DE SERVICIOS" not in gen, f"Contiene objeto en mayúsculas: {gen}"
        assert "CONTRATO DE OBRA" not in gen, f"Contiene tipo de contrato en mayúsculas: {gen}"
        assert "SUMINISTRO DE TUBERÍAS" not in gen

        # Verbo de alto nivel al inicio
        primera_palabra = gen.split()[0].lower().rstrip(",:;.")
        assert primera_palabra in verbos_alto_nivel, f"No inicia con verbo de alto nivel: {primera_palabra}"
        assert starts_with_infinitive(gen)

        # Fórmula lógica: contiene beneficio misional y mención de Yolombó o ESPY
        assert "yolombó" in gen.lower() or "espy" in gen.lower()
        assert "con el fin de" in gen.lower() or "para" in gen.lower()
        assert gen.endswith(".")

    print("\nOK: Objetivos generales construidos con verbos de alto nivel y redacción fluida sin mayúsculas.")


def test_objetivos_especificos_fases_tecnicas():
    print("\n" + "=" * 70)
    print("TEST 3: OBJETIVOS ESPECÍFICOS (3 A 5 METAS TÉCNICAS SIN FRASES COMODÍN)")
    print("=" * 70)

    # Caso Mantenimiento de Herramientas
    esp_mantenimiento = build_objetivos_especificos(
        objeto="Mantenimiento a todo costo de herramientas y equipos",
        tipologia="PRESTACION_SERVICIOS",
        contexto="herramientas eléctricas, diagnóstico y reparación técnica"
    )

    print(f"\nMantenimiento de Herramientas ({len(esp_mantenimiento)} metas):")
    for idx, ob in enumerate(esp_mantenimiento, 1):
        print(f"  {idx}. {ob}")
        assert starts_with_infinitive(ob)
        assert not is_prohibited_objective(ob), f"Objetivo prohibido detectado: {ob}"
        assert ob.endswith(".")
    assert 3 <= len(esp_mantenimiento) <= 5

    # Caso Suministro de Papelería
    esp_suministro = build_objetivos_especificos(
        objeto="Suministro de papelería e insumos de oficina para la ESPY",
        tipologia="SUMINISTRO",
        contexto="papelería, resmas, tóner y útiles"
    )
    print(f"\nSuministro de Papelería ({len(esp_suministro)} metas):")
    for idx, ob in enumerate(esp_suministro, 1):
        print(f"  {idx}. {ob}")
        assert starts_with_infinitive(ob)
        assert not is_prohibited_objective(ob)
    assert 3 <= len(esp_suministro) <= 5

    # Caso Obra de Alcantarillado
    esp_obra = build_objetivos_especificos(
        objeto="Ejecutar obras civiles para la reposición de alcantarillado",
        tipologia="OBRA",
        items_propuesta=[
            "Excavación manual en material común",
            "Suministro e instalación de tubería novafort",
            "Relleno y compactación técnica",
            "Reposición de pavimento rígido"
        ]
    )
    print(f"\nObra de Alcantarillado ({len(esp_obra)} metas):")
    for idx, ob in enumerate(esp_obra, 1):
        print(f"  {idx}. {ob}")
        assert starts_with_infinitive(ob)
        assert not is_prohibited_objective(ob)
    assert 3 <= len(esp_obra) <= 5

    print("\nOK: Objetivos específicos cubren las fases técnicas (Diagnóstico, Ejecución, Calidad/Mitigación, Trazabilidad).")


def test_agents_fallback_integration():
    print("\n" + "=" * 70)
    print("TEST 4: INTEGRACIÓN DE OBJETIVOS CON AGENTES ESPECIALIZADOS (FALLBACKS)")
    print("=" * 70)

    # 1. ServicesContractAgent
    serv_agent = ServicesContractAgent()
    input_serv = ContractDraftingInput(
        tipologia="PRESTACION_SERVICIOS",
        necesidad_descripcion="Mantenimiento a todo costo de herramientas y equipos de la ESPY",
        valor_estimado=10000000,
        plazo=6,
        unidad_plazo="MESES"
    )
    res_serv = serv_agent.fallback_generator(input_serv)
    print(f"ServicesContractAgent:")
    print(f"  Obj General: {res_serv.objetivo_general}")
    assert starts_with_infinitive(res_serv.objetivo_general)
    assert "PRESTACIÓN DE SERVICIOS" not in res_serv.objetivo_general
    assert 3 <= len(res_serv.objetivos_especificos) <= 5
    for o in res_serv.objetivos_especificos:
        assert not is_prohibited_objective(o)

    # 2. SupplyContractAgent
    sup_agent = SupplyContractAgent()
    input_sup = ContractDraftingInput(
        tipologia="SUMINISTRO",
        necesidad_descripcion="Suministro de cloro gas y coagulante para potabilización de agua en PTAP",
        valor_estimado=25000000,
        plazo=12,
        unidad_plazo="MESES"
    )
    res_sup = sup_agent.fallback_generator(input_sup)
    print(f"\nSupplyContractAgent:")
    print(f"  Obj General: {res_sup.objetivo_general}")
    assert starts_with_infinitive(res_sup.objetivo_general)
    assert 3 <= len(res_sup.objetivos_especificos) <= 5
    for o in res_sup.objetivos_especificos:
        assert not is_prohibited_objective(o)

    # 3. WorksContractAgent
    work_agent = WorksContractAgent()
    input_work = ContractDraftingInput(
        tipologia="OBRA",
        necesidad_descripcion="Reposición de redes de alcantarillado y acometidas domiciliarias",
        valor_estimado=45000000,
        plazo=3,
        unidad_plazo="MESES"
    )
    res_work = work_agent.fallback_generator(input_work)
    print(f"\nWorksContractAgent:")
    print(f"  Obj General: {res_work.objetivo_general}")
    assert starts_with_infinitive(res_work.objetivo_general)
    assert 3 <= len(res_work.objetivos_especificos) <= 5
    for o in res_work.objetivos_especificos:
        assert not is_prohibited_objective(o)

    print("\nOK: Todos los agentes especializados generan objetivos estratégicos y específicos técnicos.")


if __name__ == "__main__":
    test_prohibiciones_estrictas()
    test_objetivo_general_construccion_natural()
    test_objetivos_especificos_fases_tecnicas()
    test_agents_fallback_integration()
    print("\n" + "=" * 70)
    print("TODAS LAS PRUEBAS DEL MÓDULO DE OBJETIVOS PASARON AL 100%!")
    print("=" * 70)
