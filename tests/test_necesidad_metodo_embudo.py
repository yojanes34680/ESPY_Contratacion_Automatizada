"""Suite de pruebas para la DESCRIPCIÓN DE LA NECESIDAD A SATISFACER
conforme a las Instrucciones Definitivas del Agente:
1. El Método del Embudo en 3 niveles (Nivel 1 Marco, Nivel 2 Brecha, Nivel 3 Requerimiento).
2. Regla de Inclusión Total (100% de actividades o bienes sin resumir ni agrupar).
3. Fórmulas obligatorias para Servicios y Suministro.
4. Regla de Oro (Prohibido mencionar acueducto y alcantarillado en PGIRS/aseo/administrativo).
5. Regla de Tono (Perspectiva institucional de la ESPY, sin primera persona ni contratista propone).
6. Endpoint API /api/agents/build-necesidad.
"""
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app
from app.utils.necesidad_builder import (
    build_descripcion_necesidad,
    build_necesidad_structured,
    extract_items_from_text,
    build_nivel_1_marco,
    build_nivel_2_brecha,
    build_nivel_3_requerimiento
)

client = TestClient(app)

def test_metodo_embudo_servicios_inclusion_total():
    print("\n--- TEST 1: Método del Embudo en Servicios + Regla de Inclusión Total ---")
    objeto = "PRESTACIÓN DE SERVICIOS DE APOYO TÉCNICO EN EL MANEJO DEL PGIRS Y RECICLAJE"
    tipo = "PRESTACION_SERVICIOS"
    actividades = [
        "Realizar talleres comunitarios de separación en la fuente en 8 veredas",
        "Efectuar caracterización física de residuos sólidos domiciliarios",
        "Consolidar la base de datos de rutas de recolección selectiva",
        "Elaborar reportes mensuales de aprovechamiento para la autoridad ambiental",
        "Apoyar campañas educativas en instituciones educativas del municipio"
    ]

    res = build_descripcion_necesidad(
        objeto=objeto,
        tipologia=tipo,
        items_o_actividades=actividades
    )

    # Verificar título oficial
    assert res.startswith("DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"), "Falta título oficial"
    
    # Nivel 1: Marco Institucional
    assert "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P." in res
    assert "PGIRS" in res or "residuos sólidos" in res
    # Regla de Oro: Prohibido mencionar acueducto y alcantarillado en PGIRS
    assert "acueducto y alcantarillado" not in res.lower()
    assert "acueducto" not in res.lower()
    assert "alcantarillado" not in res.lower()

    # Nivel 2: Brecha Operativa en Servicios (Insuficiencia Interna Jurídica)
    assert "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in res
    assert "experticia técnica específica" in res or "disponibilidad de tiempo exclusivo" in res

    # Nivel 3: Fórmula exacta para Servicios
    formula_esperada = "Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo para que se ejecuten en su totalidad las siguientes labores puntuales:"
    assert formula_esperada in res, f"Fórmula de servicios no encontrada: {res}"

    # Regla de Inclusión Total: 100% de las 5 actividades deben estar presentes
    for act in actividades:
        assert f"- {act}" in res, f"Actividad omitida o modificada: {act}"

    # Regla de Tono: Sin primera persona ni menciones al contratista
    assert "propongo" not in res.lower()
    assert "el contratista propone" not in res.lower()
    assert "la propuesta indica" not in res.lower()
    print("  [OK] Servicios cumple con los 3 niveles, fórmula exacta y 100% de actividades en viñetas.")


def test_metodo_embudo_suministro_inclusion_total():
    print("\n--- TEST 2: Método del Embudo en Suministro + Regla de Inclusión Total ---")
    objeto = "SUMINISTRO DE MATERIALES Y ACCESORIOS PARA REDES DE ACUEDUCTO"
    tipo = "SUMINISTRO"
    bienes = [
        "50 Micromedidores volumétricos de 1/2 pulgada R160",
        "30 Válvulas de compuerta elástica de 2 pulgadas",
        "200 Metros de tubería de polietileno de alta densidad PE-100 PN-16",
        "15 Cajas para medidor en concreto polimérico con tapa de seguridad",
        "40 Uniones universales de 1/2 pulgada en bronce"
    ]

    res = build_descripcion_necesidad(
        objeto=objeto,
        tipologia=tipo,
        items_o_actividades=bienes
    )

    # Nivel 1: Marco Institucional
    assert "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P." in res
    assert "acueducto" in res.lower() or "agua" in res.lower()

    # Nivel 2: Brecha de Inventario en Suministro (Insuficiencia Interna Jurídica)
    assert "Actualmente, la ESPY presenta agotamiento en las existencias de su almacén" in res
    assert "no produce por sí misma los bienes, materiales e insumos" in res

    # Nivel 3: Fórmula exacta para Suministro
    formula_esperada = "Por consiguiente, surge la necesidad imperiosa de adquirir los siguientes bienes e insumos para garantizar la continuidad operativa:"
    assert formula_esperada in res, f"Fórmula de suministro no encontrada: {res}"

    # Regla de Inclusión Total: 100% de los bienes deben estar presentes
    for b in bienes:
        assert f"- {b}" in res, f"Bien omitido o modificado: {b}"

    print("  [OK] Suministro cumple con los 3 niveles, fórmula exacta y 100% de bienes en viñetas.")


def test_extract_items_from_text_rule():
    print("\n--- TEST 3: Extractor de ítems desde texto (Regla de Inclusión Total) ---")
    propuesta_texto = """
    PROPUESTA TÉCNICA
    Actividades a desarrollar:
    1. Diagnóstico del sistema de recolección de aguas residuales.
    2. Sondeo y desobstrucción hidrostática de 500 metros de colectores.
    3. Limpieza profunda y desinfección de 25 pozos de inspección.
    4. Entrega de informe técnico con registro fotográfico y recomendaciones.
    """
    items = extract_items_from_text(propuesta_texto)
    assert len(items) == 4, f"Se esperaban 4 ítems extraídos, se obtuvieron {len(items)}: {items}"
    assert "Diagnóstico del sistema" in items[0]
    assert "Sondeo y desobstrucción" in items[1]
    assert "Limpieza profunda" in items[2]
    assert "Entrega de informe técnico" in items[3]
    print(f"  [OK] Extracción del 100% de ítems validada: {len(items)} actividades.")


def test_api_endpoint_build_necesidad():
    print("\n--- TEST 4: Endpoint API POST /api/agents/build-necesidad ---")
    actividades = [
        "Revisión de expedientes contractuales de la vigencia 2025 y 2026",
        "Proyección de minutas y actos administrativos de contratación",
        "Atención y respuesta de derechos de petición institucionales"
    ]
    payload = {
        "objeto": "PRESTACIÓN DE SERVICIOS PROFESIONALES DE ASESORÍA JURÍDICA",
        "tipologia": "PRESTACION_SERVICIOS",
        "items_o_actividades": actividades
    }
    r = client.post("/api/agents/build-necesidad", json=payload)
    assert r.status_code == 200, f"Error {r.status_code}: {r.text}"
    data = r.json()

    assert data["titulo"] == "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"
    assert "nivel_1" in data and "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P." in data["nivel_1"]
    assert "nivel_2" in data and "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in data["nivel_2"]
    assert "nivel_3" in data and "Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo" in data["nivel_3"]

    # Verificar 100% de actividades en el texto unificado
    for act in actividades:
        assert f"- {act}" in data["texto_completo"]

    # Regla de Oro en contrato jurídico
    assert "acueducto y alcantarillado" not in data["texto_completo"].lower()
    print("  [OK] API Endpoint responde con los 3 niveles del Método del Embudo y 100% de ítems.")


if __name__ == "__main__":
    test_metodo_embudo_servicios_inclusion_total()
    test_metodo_embudo_suministro_inclusion_total()
    test_extract_items_from_text_rule()
    test_api_endpoint_build_necesidad()
    print("\n==================================================================")
    print(" TODAS LAS PRUEBAS DEL MÉTODO DEL EMBUDO PASARON EXITOSAMENTE (100%)")
    print("==================================================================")
