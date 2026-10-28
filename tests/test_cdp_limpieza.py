"""Tests para la limpieza, saneamiento y formateo de texto del CDP (Certificado de Disponibilidad Presupuestal).
Valida que el marcador {{CDP}} contenga únicamente:
1. Número del CDP
2. Fecha de expedición
3. Valor
4. Código del rubro
5. Nombre del rubro
Y elimine cualquier bloque de clasificadores CCPET, pies de página o valores en letras.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from app.utils.cdp_cleaner import limpiar_texto_cdp, construir_texto_cdp

def test_limpiar_texto_cdp_ejemplo_real():
    """Valida el texto largo real del ejemplo provisto en la instrucción."""
    texto_largo = (
        "0027/2, expedido el 23 de octubre de 2026, por valor de $4.489.112, con cargo al "
        "Rubro Presupuestal 2.1.2.01.01.003.03.02 – MAQUINARIA DE INFORMATICA Y "
        "SUS PARTES, PIEZAS Y ACCESORIOS, y respaldado en los clasificadores "
        "presupuestales CCPET: CCPET02 (UNIDAD 23.0 ENTIDADES TERRITORIALES - "
        "SERVICIOS 4.489.112,00): PUBLICOS Clasificador Valor Clasificador; CCPET05 "
        "(FUENTES DE FINANCIACION 1.2.3.2.27 VENTA DE BIENESYSERVICIOS CON "
        "4.489.112,00): DESTINACION ESPECIFICA LEGAL Clasificador Valor Clasificador; "
        "CCPET70 (SERVICIOS PUBLICOS 24302 Equipos de Comunicacion y "
        "Computacion - 4.489.112,00): Administrativo Clasificador Valor Clasificador; "
        "CCPET83 (ATRIBUTO EJECUCION CON/SIN Con Situacion de Fondos "
        "4.489.112,00): SITUACIONDEFONDOS Clasificador Valor Clasificador; CCPET84 "
        "(ATRIBUTO DESTINACION DE LA 120101 100% De La Renta 4.489.112,00): "
        "RENTA Valoren letras xxxxxxxxxxxxxxxx Objetado la Disponibilidad SUMINISTRO "
        "E INSTALACION DE 4 CAMARAS,Y 2 GPS PARA LOS VEHICULOS "
        "RECOLECTORES DE RESIDUOS ORDINARIOSYORGANICOSDELA "
        "EMPRESADESERVICIOSPUBLICOSDEYOLOMBO. Desarrollado por Sistemas "
        "Aries S.A.S. Reservad"
    )

    resultado = limpiar_texto_cdp(texto_largo)
    esperado = (
        "0027/2, expedido el 23 de octubre de 2026, por valor de $4.489.112, con cargo al "
        "Rubro Presupuestal 2.1.2.01.01.003.03.02 – MAQUINARIA DE INFORMATICA Y "
        "SUS PARTES, PIEZAS Y ACCESORIOS."
    )
    assert resultado == esperado

def test_texto_ya_limpio_no_cambia():
    """Verifica que un texto que ya está limpio no sufre modificaciones innecesarias."""
    texto_limpio = (
        "0027/2, expedido el 23 de octubre de 2026, por valor de $4.489.112, con cargo al "
        "Rubro Presupuestal 2.1.2.01.01.003.03.02 – MAQUINARIA DE INFORMATICA Y "
        "SUS PARTES, PIEZAS Y ACCESORIOS."
    )
    assert limpiar_texto_cdp(texto_limpio) == texto_limpio

def test_construir_texto_cdp_dos_rubros():
    """Verifica que con datos de dos rubros se generan ambos con código y nombre, sin CCPET."""
    rubros = [
        {"codigo": "2.1.2.01.01.003.03.02", "nombre": "MAQUINARIA DE INFORMATICA"},
        {"codigo": "2.1.2.02.02.008", "nombre": "SERVICIOS DE PRODUCCION"}
    ]
    resultado = construir_texto_cdp(
        numero="00099",
        fecha_texto="10 de noviembre de 2026",
        valor_fmt="$15.000.000",
        rubros=rubros
    )
    assert "00099" in resultado
    assert "10 de noviembre de 2026" in resultado
    assert "$15.000.000" in resultado
    assert "con cargo a los Rubros Presupuestales" in resultado
    assert "2.1.2.01.01.003.03.02 – MAQUINARIA DE INFORMATICA" in resultado
    assert "2.1.2.02.02.008 – SERVICIOS DE PRODUCCION" in resultado
    assert "CCPET" not in resultado
    assert "Clasificador" not in resultado
    assert resultado.endswith(".")

def test_construir_texto_cdp_00047():
    """
    Con la función que arma el texto, a partir de los datos del CDP 00047
    (fecha 23/01/2026, valor 20.000.000, rubro 2.1.2.02.01.002 – PRODUCTOS ALIMENTICIOS,
    BEBIDAS Y TABACO, TEXTILES, PRENDAS DE VESTIR Y PRODUCTOS DE CUERO),
    verifique que el texto no contiene 'CCPET', 'Clasificador', 'Aries',
    'Valor en letras' ni 'Objeto de la Disponibilidad'.
    """
    rubros = [{
        "codigo": "2.1.2.02.01.002",
        "nombre": "PRODUCTOS ALIMENTICIOS, BEBIDAS Y TABACO, TEXTILES, PRENDAS DE VESTIR Y PRODUCTOS DE CUERO"
    }]
    resultado = construir_texto_cdp(
        numero="00047",
        fecha_texto="23 de enero de 2026",
        valor_fmt="$20.000.000",
        rubros=rubros
    )

    for prohibida in ["CCPET", "Clasificador", "Aries", "Valor en letras", "Objeto de la Disponibilidad"]:
        assert prohibida.lower() not in resultado.lower(), f"Se encontró la palabra prohibida: {prohibida}"

    assert "00047, expedido el 23 de enero de 2026, por valor de $20.000.000, con cargo al Rubro Presupuestal 2.1.2.02.01.002 – PRODUCTOS ALIMENTICIOS, BEBIDAS Y TABACO, TEXTILES, PRENDAS DE VESTIR Y PRODUCTOS DE CUERO." == resultado

def test_rubro_con_palabra_clasificador_no_se_corta():
    """Verifica que un nombre de rubro que contiene la palabra 'clasificador' no se corte por error."""
    texto_con_clasificador = (
        "00123, expedido el 15 de marzo de 2026, por valor de $10.000.000, con cargo al "
        "Rubro Presupuestal 2.1.2.02.02.009 – SISTEMA CLASIFICADOR Y REGISTRO DE DATOS OPERATIVOS."
    )
    resultado = limpiar_texto_cdp(texto_con_clasificador)
    assert resultado == texto_con_clasificador
    assert "SISTEMA CLASIFICADOR Y REGISTRO DE DATOS OPERATIVOS" in resultado

    # Y si además tiene CCPET al final, sólo debe cortar a partir de CCPET preservando el rubro
    texto_con_ccpet_al_final = (
        "00123, expedido el 15 de marzo de 2026, por valor de $10.000.000, con cargo al "
        "Rubro Presupuestal 2.1.2.02.02.009 – SISTEMA CLASIFICADOR Y REGISTRO DE DATOS OPERATIVOS, "
        "y respaldado en los clasificadores presupuestales CCPET: CCPET02 Clasificador Valor Clasificador"
    )
    res_ccpet = limpiar_texto_cdp(texto_con_ccpet_al_final)
    assert res_ccpet == texto_con_clasificador

