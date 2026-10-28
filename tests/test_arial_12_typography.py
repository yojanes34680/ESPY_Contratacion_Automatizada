"""Test suite para verificar que todo el contenido generado en:
- Acta de Inicio
- Estudios Previos (Servicios y Suministro)
- Minuta Contractual (Servicios y Suministro)
- Adición Contractual
tenga rigurosamente letra tipo 'Arial' tamaño 12 (12pt).
"""
import sys
from pathlib import Path
import docx

sys.path.insert(0, str(Path("backend").resolve()))

from app.models.contract import Contrato, TipologiaContrato, ModalidadSeleccion, EstadoContrato
from app.models.contractor import Contratista, TipoPersona
from app.services.docx_engine import generate_docx_for_contract, generate_adicion_docx

def create_mock_contrato():
    c = Contratista(
        id=1,
        nombre_o_razon_social="INGENIERÍA Y SERVICIOS DE OCCIDENTE S.A.S.",
        tipo_persona=TipoPersona.JURIDICA,
        numero_documento="901234567",
        digito_verificacion="1",
        representante_legal_nombre="JUAN CARLOS PÉREZ GÓMEZ",
        representante_legal_documento="71234567",
        direccion="Calle 50 # 45-20, Yolombó",
        municipio="Yolombó",
        departamento="Antioquia",
        correo_electronico="contacto@ingenieriaoccidente.com",
        telefono="3119876543",
        regimen_tributario="Responsable de IVA"
    )

    contrato = Contrato(
        id=101,
        numero_contrato="CPS-025-2026",
        vigencia=2026,
        modalidad_seleccion=ModalidadSeleccion.CONTRATACION_DIRECTA,
        tipologia=TipologiaContrato.PRESTACION_SERVICIOS,
        estado=EstadoContrato.EN_EJECUCION,
        objeto="PRESTACIÓN DE SERVICIOS DE APOYO A LA GESTIÓN PARA EL MANTENIMIENTO DE HERRAMIENTAS ELÉCTRICAS Y EQUIPOS ELECTROMECÁNICOS A TODO COSTO ADSCRITOS AL ÁREA OPERATIVA DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P.",
        justificacion_necesidad="En materia técnico-operativa, resulta esencial el mantenimiento preventivo y correctivo de las herramientas eléctricas para evitar contingencias en la prestación del servicio de acueducto y alcantarillado.",
        objetivo_general="Optimizar la confiabilidad y operatividad de los equipos de campo de la ESPY.",
        objetivos_especificos=[
            "Diagnosticar el estado electromecánico inicial de los equipos y herramientas de campo.",
            "Ejecutar los mantenimientos preventivos y correctivos requeridos con repuestos originales.",
            "Realizar pruebas de aislamiento dieléctrico y funcionamiento bajo carga técnica.",
            "Consolidar la trazabilidad técnica mediante fichas técnicas detalladas por equipo."
        ],
        obligaciones_minuta=[
            "Ejecutar el diagnóstico electromecánico previo de las herramientas.",
            "Suministrar repuestos nuevos y originales a todo costo.",
            "Realizar pruebas técnicas de aislamiento y seguridad operativa.",
            "Acreditar el pago mensual de aportes al Sistema de Seguridad Social Integral y ARL."
        ],
        obligaciones_estudio_previo=[
            "Efectuar el levantamiento técnico inicial del estado de herramientas.",
            "Garantizar la disponibilidad de taller especializado y personal calificado.",
            "Entregar los informes mensuales con registro fotográfico del antes y después.",
            "Presentar constancia de cumplimiento de normas de Seguridad y Salud en el Trabajo (SST)."
        ],
        valor_total=24000000.0,
        valor_inicial=24000000.0,
        plazo_ejecucion=6,
        unidad_plazo="MESES",
        contratista=c,
        contratista_id=1,
        fecha_suscripcion="2026-02-01",
        fecha_estudio_previo="2026-01-20",
        fecha_acta_inicio="2026-02-05",
        fecha_terminacion="2026-08-05",
        supervisor_nombre="ING. CARLOS ANDRÉS HENAO",
        supervisor_cargo="Director Técnico y Operativo",
        supervisor_dependencia="Dirección Operativa de la ESPY"
    )
    return contrato

def test_documentos_generados_letra_arial_12():
    contrato = create_mock_contrato()
    tipos_a_probar = [
        ("ACTA_INICIO", "Acta de Inicio"),
        ("ESTUDIO_PREVIO_SERVICIOS", "Estudio Previo"),
        ("MINUTA_SERVICIOS", "Minuta Contractual"),
    ]

    for t_key, t_desc in tipos_a_probar:
        print(f"\n--- PROBANDO {t_desc.upper()} ({t_key}) ---")
        out_path = generate_docx_for_contract(contrato, t_key)
        assert out_path.exists(), f"El archivo debe existir: {out_path}"
        doc = docx.Document(out_path)

        non_compliant_runs = []
        # Revisar párrafos del documento
        for p_idx, p in enumerate(doc.paragraphs):
            t_txt = p.text.strip()
            if not t_txt:
                continue
            for r_idx, r in enumerate(p.runs):
                if not r.text.strip():
                    continue
                # Validar Arial y 12pt
                font_name = r.font.name
                font_size = r.font.size.pt if r.font.size else None
                if font_name != "Arial" or font_size != 12.0:
                    non_compliant_runs.append((f"P{p_idx+1}: '{r.text[:35]}'", font_name, font_size))

        # Revisar tablas del documento
        for t_idx, tbl in enumerate(doc.tables):
            for row_idx, row in enumerate(tbl.rows):
                for cell_idx, cell in enumerate(row.cells):
                    for p_cell in cell.paragraphs:
                        for r in p_cell.runs:
                            if not r.text.strip():
                                continue
                            font_name = r.font.name
                            font_size = r.font.size.pt if r.font.size else None
                            if font_name != "Arial" or font_size != 12.0:
                                non_compliant_runs.append((f"T{t_idx+1}R{row_idx+1}C{cell_idx+1}: '{r.text[:35]}'", font_name, font_size))

        print(f"  [RESULTADO] Total fragmentos no conformes: {len(non_compliant_runs)}")
        if non_compliant_runs:
            print(f"  Ejemplos no conformes: {non_compliant_runs[:5]}")
        assert len(non_compliant_runs) == 0, f"Se encontraron runs que no son Arial 12 en {t_desc}"
        print(f"  [OK] 100% del contenido de {t_desc} está en Arial tamaño 12.")

def test_adicion_letra_arial_12():
    print("\n--- PROBANDO MINUTA DE ADICIÓN CONTRACTUAL ---")
    contrato = create_mock_contrato()
    adicion_data = {
        "numero_adicion": 1,
        "valor_adicion": 6000000.0,
        "cdp_numero": "CDP-2026-089",
        "cdp_fecha": "2026-05-10",
        "cdp_rubro": "2.1.2.02.02",
        "cdp_rubro_nombre": "Mantenimiento y Reparaciones Técnicas",
        "fecha_adicion": "2026-05-15"
    }
    out_path = generate_adicion_docx(contrato, adicion_data)
    assert out_path.exists(), f"El archivo debe existir: {out_path}"
    doc = docx.Document(out_path)

    non_compliant_runs = []
    for p_idx, p in enumerate(doc.paragraphs):
        if not p.text.strip():
            continue
        for r in p.runs:
            if not r.text.strip():
                continue
            font_name = r.font.name
            font_size = r.font.size.pt if r.font.size else None
            if font_name != "Arial" or font_size != 12.0:
                non_compliant_runs.append((f"P{p_idx+1}: '{r.text[:35]}'", font_name, font_size))

    for t_idx, tbl in enumerate(doc.tables):
        for row_idx, row in enumerate(tbl.rows):
            for cell_idx, cell in enumerate(row.cells):
                for p_cell in cell.paragraphs:
                    for r in p_cell.runs:
                        if not r.text.strip():
                            continue
                        font_name = r.font.name
                        font_size = r.font.size.pt if r.font.size else None
                        if font_name != "Arial" or font_size != 12.0:
                            non_compliant_runs.append((f"T{t_idx+1}R{row_idx+1}C{cell_idx+1}: '{r.text[:35]}'", font_name, font_size))

    print(f"  [RESULTADO] Total fragmentos no conformes: {len(non_compliant_runs)}")
    assert len(non_compliant_runs) == 0, "Se encontraron runs que no son Arial 12 en la adición"
    print("  [OK] 100% del contenido de la Minuta de Adición está en Arial tamaño 12.")

if __name__ == "__main__":
    test_documentos_generados_letra_arial_12()
    test_adicion_letra_arial_12()
    print("\n==========================================================================")
    print(" TODAS LAS PRUEBAS DE TIPOGRAFÍA ARIAL TAMAÑO 12 PASARON EXITOSAMENTE (100%)!")
    print("==========================================================================")
