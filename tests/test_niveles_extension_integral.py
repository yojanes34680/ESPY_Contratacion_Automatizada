import sys
from pathlib import Path

# Añadir backend al PYTHONPATH
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from app.utils.necesidad_builder import build_descripcion_necesidad, build_necesidad_structured
from app.utils.objetivos_builder import build_objetivo_general, build_objetivos_especificos, build_objetivos_contrato
from app.utils.obligaciones_builder import build_obligaciones_contratista
from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa


def test_necesidad_tres_niveles_longitud_y_contenido():
    """Valida que len(CORTA) < len(MEDIA) < len(COMPLETA), que en los 3 se preserve
    el 100% de los items de la propuesta y el parrafo constitucional obligatorio del Art. 209."""
    objeto = "PRESTACION DE SERVICIOS PARA EL MANTENIMIENTO PREVENTIVO Y CORRECTIVO DE VEHICULOS DE LA ESPY"
    propuesta_items = [
        "Cambio de aceite de motor sintético y filtros",
        "Sincronización electrónica y limpieza de inyectores",
        "Revisión y calibración del sistema de frenos y pastillas",
        "Alineación, balanceo y rotación de llantas"
    ]
    instrucciones = "Enfatizar la urgencia de evitar la parálisis de la recolección de residuos"

    # 1. CORTA
    necesidad_corta = build_descripcion_necesidad(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        nivel_extension="CORTA",
        instrucciones_adicionales=instrucciones,
        propuesta_items=propuesta_items
    )

    # 2. MEDIA
    necesidad_media = build_descripcion_necesidad(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        nivel_extension="MEDIA",
        instrucciones_adicionales=instrucciones,
        propuesta_items=propuesta_items
    )

    # 3. COMPLETA
    necesidad_completa = build_descripcion_necesidad(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        nivel_extension="COMPLETA",
        instrucciones_adicionales=instrucciones,
        propuesta_items=propuesta_items
    )

    # Verificar jerarquía de longitudes
    assert len(necesidad_corta) < len(necesidad_media), f"Corta ({len(necesidad_corta)}) no es menor que Media ({len(necesidad_media)})"
    assert len(necesidad_media) < len(necesidad_completa), f"Media ({len(necesidad_media)}) no es menor que Completa ({len(necesidad_completa)})"

    # Verificar párrafo obligatorio del Art. 209 C.P. en los 3 niveles
    frase_art209 = "artículo 209 de la Constitución Política"
    assert frase_art209 in necesidad_corta, "Párrafo Art 209 ausente en CORTA"
    assert frase_art209 in necesidad_media, "Párrafo Art 209 ausente en MEDIA"
    assert frase_art209 in necesidad_completa, "Párrafo Art 209 ausente en COMPLETA"

    # En los 3 niveles debe estar el 100% de los ítems
    for item in propuesta_items:
        # Extraer una palabra o raíz clave
        palabra_clave = item.split()[0].lower()
        assert palabra_clave in necesidad_corta.lower(), f"Item '{item}' no incluido en CORTA"
        assert palabra_clave in necesidad_media.lower(), f"Item '{item}' no incluido en MEDIA"
        assert palabra_clave in necesidad_completa.lower(), f"Item '{item}' no incluido en COMPLETA"

    # Verificar que las instrucciones adicionales se integren
    assert "parálisis" in necesidad_corta.lower() or "urgencia" in necesidad_corta.lower()
    assert "parálisis" in necesidad_media.lower() or "urgencia" in necesidad_media.lower()
    assert "parálisis" in necesidad_completa.lower() or "urgencia" in necesidad_completa.lower()


def test_necesidad_variante_almacen_suministro():
    """Valida la variante de almacén en suministros en los 3 niveles."""
    objeto = "SUMINISTRO DE TUBERIAS Y ACCESORIOS PARA REDES DE ACUEDUCTO"
    propuesta_items = ["Tubería PVC 2 pulgadas", "Válvulas de compuerta", "Uniones universales"]

    for nivel in ["CORTA", "MEDIA", "COMPLETA"]:
        nec = build_descripcion_necesidad(
            objeto=objeto,
            tipologia="SUMINISTRO",
            nivel_extension=nivel,
            propuesta_items=propuesta_items
        )
        assert "agotamiento en las existencias de su almacén" in nec
        assert "artículo 209 de la Constitución Política" in nec


def test_objetivos_tres_niveles():
    """Valida Objetivo General y Específicos en CORTA, MEDIA y COMPLETA."""
    objeto = "PRESTACION DE SERVICIOS PARA EL MANTENIMIENTO PREVENTIVO Y CORRECTIVO DE VEHICULOS"
    propuesta_items = [
        "Cambio de aceite de motor sintético y filtros",
        "Sincronización electrónica y limpieza de inyectores",
        "Revisión y calibración del sistema de frenos y pastillas",
        "Alineación, balanceo y rotación de llantas"
    ]
    instrucciones = "Garantizar disponibilidad operativa permanente de la flota vehicular"

    # 1. CORTA: General conciso + 3 específicos
    res_corta = build_objetivos_contrato(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        propuesta_items=propuesta_items,
        nivel_extension="CORTA",
        instrucciones_adicionales=instrucciones
    )
    assert len(res_corta["objetivos_especificos"]) == 3
    # No debe contener el objeto en mayúsculas sostenidas
    assert objeto not in res_corta["objetivo_general"]
    for obj in res_corta["objetivos_especificos"]:
        assert obj[0].isupper()
        assert not obj.startswith(" ")
        # Prohibido trámites administrativos
        assert "presentar informes" not in obj.lower()
        assert "pasar cuenta" not in obj.lower()

    # 2. MEDIA: General estándar + 4 específicos
    res_media = build_objetivos_contrato(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        propuesta_items=propuesta_items,
        nivel_extension="MEDIA",
        instrucciones_adicionales=instrucciones
    )
    assert len(res_media["objetivos_especificos"]) == 4

    # 3. COMPLETA: General amplio + 5 a 6 específicos
    res_completa = build_objetivos_contrato(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        propuesta_items=propuesta_items,
        nivel_extension="COMPLETA",
        instrucciones_adicionales=instrucciones
    )
    assert len(res_completa["objetivos_especificos"]) >= 5
    assert len(res_completa["objetivo_general"]) > len(res_corta["objetivo_general"])


def test_obligaciones_contratista_tres_niveles():
    """Valida obligaciones del contratista en CORTA, MEDIA y COMPLETA."""
    objeto = "PRESTACION DE SERVICIOS PARA EL MANTENIMIENTO PREVENTIVO Y CORRECTIVO DE VEHICULOS"
    propuesta_items = [
        "Cambio de aceite de motor sintético y filtros",
        "Sincronización electrónica y limpieza de inyectores",
        "Revisión y calibración del sistema de frenos y pastillas",
        "Alineación, balanceo y rotación de llantas"
    ]

    # CORTA
    res_corta = build_obligaciones_contratista(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        propuesta_items=propuesta_items,
        nivel_extension="CORTA"
    )
    assert len(res_corta["obligaciones_especificas"]) == 4
    assert len(res_corta["obligaciones_generales"]) == 4

    # MEDIA
    res_media = build_obligaciones_contratista(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        propuesta_items=propuesta_items,
        nivel_extension="MEDIA"
    )
    assert len(res_media["obligaciones_especificas"]) == 4
    assert len(res_media["obligaciones_generales"]) == 5

    # COMPLETA
    res_completa = build_obligaciones_contratista(
        objeto=objeto,
        tipologia="PRESTACION_SERVICIOS",
        propuesta_items=propuesta_items,
        nivel_extension="COMPLETA"
    )
    assert len(res_completa["obligaciones_especificas"]) == 4
    assert len(res_completa["obligaciones_generales"]) == 7

    # En COMPLETA la redacción de cada obligación específica debe ser más profunda y detallada
    total_len_corta = sum(len(x) for x in res_corta["obligaciones_especificas"])
    total_len_completa = sum(len(x) for x in res_completa["obligaciones_especificas"])
    assert total_len_completa > total_len_corta


def test_obligaciones_empresa_tres_niveles():
    """Valida obligaciones de la ESPY en los 3 niveles y reglas prohibitivas."""
    objeto = "MANTENIMIENTO DE BOMBAS ELECTROMECANICAS DE LA ESPY"

    # Plazo <= 30 días, Mantenimiento, Persona Jurídica
    res_corta = build_obligaciones_empresa(objeto=objeto, tipologia="MANTENIMIENTO", plazo_dias=20, tipo_persona="JURIDICA", nivel_extension="CORTA")
    res_media = build_obligaciones_empresa(objeto=objeto, tipologia="MANTENIMIENTO", plazo_dias=20, tipo_persona="JURIDICA", nivel_extension="MEDIA")
    res_completa = build_obligaciones_empresa(objeto=objeto, tipologia="MANTENIMIENTO", plazo_dias=20, tipo_persona="JURIDICA", nivel_extension="COMPLETA")

    assert len(res_corta) == 4
    assert len(res_media) >= 6
    assert len(res_completa) >= len(res_media)
    for res in [res_corta, res_media, res_completa]:
        # Prohibido "honorarios"
        text_all = " ".join(res).lower()
        assert "honorarios" not in text_all
        # Plazo <= 30 días: prohibido "informes mensuales" o "pagos mensuales"
        assert "mensuales" not in text_all
        # Persona Jurídica: Artículo 50 de la Ley 789 de 2002
        assert "artículo 50 de la ley 789 de 2002" in text_all
