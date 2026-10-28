"""Test script to verify Escenario A and Escenario B in necesidad_builder."""
import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.utils.necesidad_builder import build_descripcion_necesidad

def test_escenario_b_deductive_breakdown():
    print("\n--- TEST: Escenario B - Cotización Escueta de Una Sola Línea ---")
    objeto = "MANTENIMIENTO A TODO COSTO DE HERRAMIENTAS Y EQUIPOS ELÉCTRICOS"
    tipo = "PRESTACION_SERVICIOS"
    # Cotización con un único ítem escueto
    items_escuetos = ["Mantenimiento a todo costo de herramientas"]

    res = build_descripcion_necesidad(
        objeto=objeto,
        tipologia=tipo,
        items_o_actividades=items_escuetos
    )

    # Verificar que NO quedó con una sola viñeta
    viñetas = [line for line in res.split("\n") if line.strip().startswith("-")]
    print(f"Viñetas generadas en Escenario B: {len(viñetas)}")
    for v in viñetas:
        print(f"  {v}")

    assert len(viñetas) >= 5, f"Se esperaban al menos 5 viñetas con desglose deductivo, se obtuvieron {len(viñetas)}"
    assert any("diagnóstico" in v.lower() for v in viñetas), "Falta labor de diagnóstico"
    assert any("preventivo" in v.lower() for v in viñetas), "Falta labor de preventivo"
    assert any("correctivo" in v.lower() or "repuestos" in v.lower() for v in viñetas), "Falta correctivo o repuestos"
    assert any("pruebas" in v.lower() or "calibración" in v.lower() for v in viñetas), "Falta pruebas o calibración"
    assert any("entrega" in v.lower() or "satisfacción" in v.lower() for v in viñetas), "Falta entrega"
    print("  [OK] Escenario B activa exitosamente el Desglose Técnico Deductivo con 6 labores operativas inherentes.")

def test_escenario_a_detailed_quote():
    print("\n--- TEST: Escenario A - Propuesta Detallada (Inclusión Total) ---")
    objeto = "PRESTACIÓN DE SERVICIOS PARA LA GESTIÓN INTEGRAL DE RESIDUOS SÓLIDOS"
    tipo = "PRESTACION_SERVICIOS"
    items_detallados = [
        "Capacitación en separación en la fuente a líderes barriales",
        "Rutas de recolección selectiva de material reciclable",
        "Pesaje y consolidación de estadísticas en centro de acopio",
        "Mantenimiento básico de puntos limpios comunitarios"
    ]

    res = build_descripcion_necesidad(
        objeto=objeto,
        tipologia=tipo,
        items_o_actividades=items_detallados
    )

    viñetas = [line for line in res.split("\n") if line.strip().startswith("-")]
    print(f"Viñetas en Escenario A: {len(viñetas)}")
    assert len(viñetas) == 4, f"Se esperaban exactamente 4 viñetas (100%), se obtuvieron {len(viñetas)}"
    for it in items_detallados:
        assert any(it.lower() in v.lower() for v in viñetas), f"Ítem {it} no encontrado en viñetas"
    print("  [OK] Escenario A mantiene la Inclusión Total del 100% de actividades sin resumir.")

if __name__ == "__main__":
    test_escenario_b_deductive_breakdown()
    test_escenario_a_detailed_quote()
    print("\n=======================================================")
    print(" TODAS LAS PRUEBAS DE ESCENARIO A Y B PASARON AL 100%!")
    print("=======================================================")
