import pytest
from app.services.agents.unspsc_agent import unspsc_agent

def test_instalacion_pasamanos_madera_plastica_represa():
    """
    Test de verificación:
    - Objeto: INSTALACION DE PASAMANOS EN MADERA PLASTICA A TODO COSTO PARA LOS SITIOS DE TRANSITO PEATONAL DE LA REPRESA EL SERENO DEL MUNICIPIO DE YOLOMBÓ
    - Propuesta Económica: Parales estacón 8x8x115 (60), Baretas 4x13x230 (90), Tornillos 3/8 x 1/2 x4 (380), Parales 12x12x300 (6), Estibas 50x70 (10), Visita técnica (1), Mano de obra días (10)
    - Estudio Previo: Secciones de Diagnóstico (Ausencia de Dispositivos de Contención y Apoyo, Riesgo Inmediato de Accidentes Ocupacionales, Incumplimiento de Obligaciones Normativas en Seguridad Ocupacional).
    """
    objeto = "INSTALACION DE PASAMANOS EN MADERA PLASTICA A TODO COSTO PARA LOS SITIOS DE TRANSITO PEATONAL DE LA REPRESA EL SERENO DEL MUNICIPIO DE YOLOMBÓ"
    propuesta = """
    COTIZACIÓN COMERCIAL
    Ítem | Descripción | Cantidad | Valor unitario | Valor total
    1 | Parales estacón 8x8x115 | 60 | $63.700 | $3.822.000
    2 | Baretas 4x13x230 | 90 | $63.400 | $5.706.000
    3 | Tornillos 3/8 x 1/2 x4 | 380 | $1.500 | $570.000
    4 | Parales 12x12x300 | 6 | $210.000 | $1.260.000
    5 | Estibas 50x70 | 10 | $45.000 | $450.000
    6 | Visita técnica | 1 | $150.000 | $150.000
    7 | Mano de obra días | 10 | $120.000 | $1.200.000
    """
    estudio_previo = """
    ESTUDIOS PREVIOS
    OBJETO: INSTALACION DE PASAMANOS EN MADERA PLASTICA A TODO COSTO PARA LOS SITIOS DE TRANSITO PEATONAL DE LA REPRESA EL SERENO DEL MUNICIPIO DE YOLOMBÓ

    DIAGNÓSTICO DE LA SITUACIÓN ACTUAL:
    1. Ausencia de Dispositivos de Contención y Apoyo
    2. Riesgo Inmediato de Accidentes Ocupacionales
    3. Incumplimiento de Obligaciones Normativas en Seguridad Ocupacional

    OBJETIVOS ESPECÍFICOS:
    - Instalar pasamanos en madera plástica en las áreas peatonales de la represa.
    - Suministrar parales, baretas y tornillos de fijación estructural.
    - Realizar pruebas de carga y estabilidad de los pasamanos instalados.
    """

    from app.schemas.unspsc import UnspscAnalysisInput
    input_data = UnspscAnalysisInput(
        objeto=objeto,
        propuesta_economica=propuesta,
        estudio_previo=estudio_previo
    )
    res = unspsc_agent.analyze_contract_unspsc(input_data)

    # 1. actividades_propuesta_extraidas NO contenga frases de diagnóstico
    extracted_lower = " ".join(res.actividades_propuesta_extraidas).lower()
    assert "ausencia de" not in extracted_lower, f"Se filtró frase de diagnóstico: {res.actividades_propuesta_extraidas}"
    assert "riesgo inmediato" not in extracted_lower, f"Se filtró frase de diagnóstico: {res.actividades_propuesta_extraidas}"
    assert "incumplimiento de" not in extracted_lower, f"Se filtró frase de diagnóstico: {res.actividades_propuesta_extraidas}"

    # 2. codigos_seleccionados NO contenga 80141606, 84131510 ni 93141713
    codes = [getattr(item, 'codigo_unspsc', None) or getattr(item, 'codigo', '') for item in res.codigos_seleccionados]
    assert "80141606" not in codes, f"Código de marketing 80141606 detectado: {codes}"
    assert "84131510" not in codes, f"Código de seguro 84131510 detectado: {codes}"
    assert "93141713" not in codes, f"Código de monumentos 93141713 detectado: {codes}"
    for c in codes:
        assert not c.startswith("8413"), f"Código de seguros {c} indebidamente seleccionado en contrato de obra"

    # 3. codigos_seleccionados contenga códigos pertinentes de los Segmentos 72 y/o 30 y 31
    segments = {c[:2] for c in codes}
    valid_work_segments = {"72", "30", "31"}
    assert segments.intersection(valid_work_segments), f"No se seleccionaron códigos de los segmentos 72, 30 o 31: {codes}"
