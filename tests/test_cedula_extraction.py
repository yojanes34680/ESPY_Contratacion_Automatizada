import sys
import pytest
sys.path.insert(0, 'backend')

from app.services.document_parser import extract_colombian_cedula_data

def test_extract_cedula_formato_a_digital_mrz():
    """
    Formato A: Cédula Digital / Policarbonato con MRZ en reverso.
    Ejemplo: Carlos Ivan Escobar Gonzalez con NUIP 71.262.859.
    """
    ocr_text_digital = """
    REPÚBLICA DE COLOMBIA
    IDENTIFICACIÓN PERSONAL
    CÉDULA DE CIUDADANÍA
    NUIP 71.262.859
    Apellidos
    ESCOBAR GONZALEZ
    Nombres
    CARLOS IVAN
    Nacionalidad COLOMBIANA
    Estatura 1.74 Sexo M
    Fecha de Nacimiento 26-JUN-1982
    Lugar de Nacimiento MEDELLIN (ANTIOQUIA)
    Fecha y Lugar de Expedición 14-FEB-2024 MEDELLIN
    
    === REVERSO ===
    ICCOL041537172401001<<<<<<<<<<
    8206266M3402144COL71262859<<<8
    ESCOBAR<GONZALEZ<<CARLOS<IVAN<
    """
    res = extract_colombian_cedula_data(ocr_text_digital)
    assert res["numero_documento"] == "71262859", f"Esperado 71262859, obtenido {res['numero_documento']}"
    assert res["nombre_completo"] == "CARLOS IVAN ESCOBAR GONZALEZ", f"Esperado CARLOS IVAN ESCOBAR GONZALEZ, obtenido {res['nombre_completo']}"
    assert res["tipo_documento"] == "CC"


def test_extract_cedula_formato_b_amarilla_hologramas():
    """
    Formato B: Cédula Amarilla Tradicional de Hologramas en fotocopia B/N.
    Ejemplo: Paula Andrea Monsalve Mejia con Cédula 43.593.616 y serial de código de barras.
    """
    ocr_text_amarilla = """
    REPUBLICA DE COLOMBIA
    IDENTIFICACION PERSONAL
    CEDULA DE CIUDADANIA
    NUMERO 43.593.616
    MONSALVE MEJIA
    APELLIDOS
    PAULA ANDREA
    NOMBRES
    FIRMA
    
    === REVERSO ===
    FECHA DE NACIMIENTO
    30-ABR-1993
    MEDELLIN (ANTIOQUIA)
    ESTATURA 1.62 G.S. RH O+ SEXO F
    30-ABR-1993 MEDELLIN FECHA Y LUGAR DE EXPEDICION
    INDICE DERECHO
    A-0100150-00531938-F-0043593616-20131227
    """
    res = extract_colombian_cedula_data(ocr_text_amarilla)
    assert res["numero_documento"] == "43593616", f"Esperado 43593616, obtenido {res['numero_documento']}"
    assert res["nombre_completo"] == "PAULA ANDREA MONSALVE MEJIA", f"Esperado PAULA ANDREA MONSALVE MEJIA, obtenido {res['nombre_completo']}"
    assert res["tipo_documento"] == "CC"


def test_extract_cedula_formato_b_fotocopia_ruido_sin_palabra_numero():
    """
    Formato B con ruido OCR donde la palabra NUMERO sale borrosa y solo se lee '43.593.616'.
    """
    ocr_text_ruidosa = """
    REPUBLICA DE COLOMBIA
    CEDULA DE CIUDADANIA
    43.593.616
    MONSALVE MEJIA
    APELLIDOS
    PAULA ANDREA
    NOMBRES
    FIRMA
    """
    res = extract_colombian_cedula_data(ocr_text_ruidosa)
    assert res["numero_documento"] == "43593616"
    assert res["nombre_completo"] == "PAULA ANDREA MONSALVE MEJIA"


def test_extract_cedula_formato_a_digital_sin_mrz():
    """
    Formato A digital sin MRZ (solo frente con etiquetas encima del valor).
    """
    ocr_text_frente_digital = """
    REPÚBLICA DE COLOMBIA
    CÉDULA DE CIUDADANÍA
    NUIP 71.262.859
    Apellidos
    ESCOBAR GONZALEZ
    Nombres
    CARLOS IVAN
    """
    res = extract_colombian_cedula_data(ocr_text_frente_digital)
    assert res["numero_documento"] == "71262859"
    assert res["nombre_completo"] == "CARLOS IVAN ESCOBAR GONZALEZ"


if __name__ == "__main__":
    test_extract_cedula_formato_a_digital_mrz()
    print("[OK] Test 1: Formato A Digital MRZ - 71262859 / CARLOS IVAN ESCOBAR GONZALEZ")
    test_extract_cedula_formato_b_amarilla_hologramas()
    print("[OK] Test 2: Formato B Amarilla Hologramas - 43593616 / PAULA ANDREA MONSALVE MEJIA")
    test_extract_cedula_formato_b_fotocopia_ruido_sin_palabra_numero()
    print("[OK] Test 3: Formato B con Ruido Fotocopia - 43593616 / PAULA ANDREA MONSALVE MEJIA")
    test_extract_cedula_formato_a_digital_sin_mrz()
    print("[OK] Test 4: Formato A Digital sin MRZ - 71262859 / CARLOS IVAN ESCOBAR GONZALEZ")
    print("\nTODAS LAS PRUEBAS DE EXTRACCIÓN DE CÉDULA PASARON CON 100% DE ÉXITO!")
