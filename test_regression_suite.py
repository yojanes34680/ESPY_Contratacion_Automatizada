"""
SUITE DE PRUEBAS DE REGRESIÓN OBLIGATORIA (BLINDAJE DE CÓDIGO - ESPY)
=====================================================================
Directriz de Seguridad Contractual y Regla de Cero Regresiones:
Ninguna mejora, corrección o adición a un contrato específico o módulo
debe alterar, desconfigurar o romper el comportamiento de los contratos
y módulos ya consolidados y aprobados.

Casos de éxito consolidados evaluados:
1. Test A: Mantenimiento Herramientas CPS-055-2026 (CPS-001/055-2026).
   - Objeto limpio sin bucles ni cadenas espurias ("DISPONIBILIDAD", fallbacks inventados).
   - Persona jurídica con su Representante Legal y formato formal (3 líneas en minuta).
   - Clasificación temática y asignación de códigos UNSPSC en Segmento 73.
2. Test B: Suministro PGIRS ASOCOMUNAL ($50.076.264 COP).
   - Selección estricta de códigos UNSPSC de bienes (Segmentos 10, 46, 47, 52, 55).
   - Prohibición absoluta de códigos de servicios (>= 70) en Suministro.
   - Relación código-cita semántica 1:1 verificada sin desfase ni duplicación.
3. Test C: Obra Válvula Las Camelias.
   - Clasificación en Categoría D (Obras Civiles / Infraestructura Hidrosanitaria).
   - Códigos de acueducto y obras civiles en Segmento 72 (Acueducto, Excavación, Pavimento).
   - Prohibición de códigos de alcantarillado/drenaje incompatible o parques.
4. Test D: Servicios Apoyo PGIRS (Mauricio Carmona).
   - Clasificación en Categoría A (Gestión Ambiental, PGIRS y Sensibilización).
   - Asignación de códigos en Segmentos 76, 77 y 93.
   - Exclusión de códigos de taller o electromecánicos (72 y 73).
"""

import sys
import os
import re
from pathlib import Path

# Añadir backend al PYTHONPATH
BACKEND_DIR = Path(__file__).parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from app.models.contract import Contrato
from app.models.contractor import Contratista, TipoPersona
from app.services.docx_engine import generate_docx_for_contract
from app.services.gemini_client import gemini_service
from app.services.agents.object_agent import object_agent
from app.services.agents.unspsc_agent import unspsc_agent
from app.schemas.agent import ObjetoGenerationInput
from app.schemas.unspsc import UnspscAnalysisInput
import docx


# =====================================================================
# TEST A: MANTENIMIENTO HERRAMIENTAS (CPS-055-2026 / CPS-001-2026)
# =====================================================================
def test_a_mantenimiento_herramientas_cps055():
    """
    Test A: Mantenimiento Herramientas
    - Objeto limpio sin bucles ni cadenas espurias ("DISPONIBILIDAD", fallbacks inventados).
    - Persona jurídica con su Representante Legal verificado.
    - Códigos UNSPSC en Segmento 73 (Mantenimiento electromecánico/herramientas).
    """
    print("\n--- EJECUTANDO TEST A: Mantenimiento Herramientas CPS-055-2026 ---")
    
    # 1. Validación de extracción y objeto limpio (sin disponibilidad ni fallbacks)
    ocr_file = Path("backend/storage/uploads/19c1f42fcf_PROPUESTA.ocr.txt")
    assert ocr_file.exists(), f"Archivo de propuesta no encontrado: {ocr_file}"
    raw_ocr = ocr_file.read_text(encoding="utf-8")
    
    extracted = gemini_service.extract_contractor_data(raw_ocr)
    assert extracted.objeto_propuesto, "Debe extraer el objeto de la propuesta de herramientas"
    assert "HERRAMIENTAS" in extracted.objeto_propuesto.upper()
    assert "ELECTRICAS" in extracted.objeto_propuesto.upper()
    assert "DISPONIBILIDAD" not in extracted.objeto_propuesto.upper(), "No debe incluir bucles de 'DISPONIBILIDAD'"
    assert "INFRAESTRUCTURA Y EQUIPOS" not in extracted.objeto_propuesto.upper(), "No debe incluir fallbacks inventados"
    
    # Formulación con ObjectAgent
    inp_obj = ObjetoGenerationInput(
        tipologia="PRESTACION_SERVICIOS",
        texto_propuesta_o_estudio=raw_ocr,
        contratista_nombre="ASOCOMUNAL YOLOMBO"
    )
    res_obj = object_agent.generate_objeto(inp_obj)
    objeto_final = res_obj.objeto_sugerido
    assert "HERRAMIENTAS" in objeto_final
    assert "ELECTRICAS" in objeto_final
    assert "DISPONIBILIDAD" not in objeto_final
    assert "INFRAESTRUCTURA Y EQUIPOS" not in objeto_final
    assert objeto_final == objeto_final.upper()

    # 2. Validación Persona Jurídica y Representante Legal en Minuta
    contratista_pj = Contratista(
        id=55,
        tipo_persona=TipoPersona.JURIDICA,
        nombre_o_razon_social="ASOCIACION DE JUNTAS DE ACCION COMUNAL Y VIVIENDA COMUNITARIA",
        tipo_documento="NIT",
        numero_documento="800.254.070-8",
        representante_legal_nombre="PAULA ANDREA MONSALVE MEJIA",
        representante_legal_documento="43.593.616"
    )
    contrato = Contrato(
        id=55,
        numero_contrato="CPS-055-2026",
        vigencia=2026,
        objeto=objeto_final,
        contratista_id=55,
        valor_total=3000000
    )
    contrato.contratista = contratista_pj
    
    doc_path = generate_docx_for_contract(contrato, template_type="MINUTA")
    doc_m = docx.Document(str(doc_path))
    
    # Verificar comparecencia
    preamble_m = ""
    for p in doc_m.paragraphs:
        if "por la otra" in p.text.lower():
            preamble_m = p.text
            break
    assert preamble_m, "Debe existir párrafo de comparecencia en minuta"
    assert "el señor ASOCIACION" not in preamble_m, "No debe incluir 'el señor' antes de persona jurídica"
    assert "NIT 800.254.070-8" in preamble_m
    assert "PAULA ANDREA MONSALVE MEJIA" in preamble_m
    
    # 3. Validación UNSPSC en Segmento 73
    payload_unspsc = UnspscAnalysisInput(
        objeto=objeto_final,
        estudio_previo="Mantenimiento preventivo y correctivo a todo costo de herramientas eléctricas y equipos de taller de la ESPY.",
        propuesta_economica=raw_ocr
    )
    result_unspsc = unspsc_agent.analyze_contract_unspsc(payload_unspsc)
    cat_id, cat_nombre = unspsc_agent.classify_contract_thematic_category(payload_unspsc.objeto, payload_unspsc.propuesta_economica)
    assert cat_id == "B", f"Se esperaba Categoría B (Mantenimiento/Taller), obtenido {cat_id}"
    
    codigos = [c.codigo_unspsc for c in result_unspsc.codigos_seleccionados]
    assert len(codigos) > 0, "Debe seleccionar códigos UNSPSC"
    for c in codigos:
        assert c.startswith("73"), f"El código {c} debe pertenecer obligatoriamente al Segmento 73"
    print("✓ Test A superado: Objeto limpio, persona jurídica con RL y códigos 100% en Segmento 73.")


# =====================================================================
# TEST B: SUMINISTRO PGIRS ASOCOMUNAL ($50.076.264)
# =====================================================================
def test_b_suministro_pgirs_asocomunal():
    """
    Test B: Suministro PGIRS ASOCOMUNAL ($50.076.264 COP)
    - Selecciona códigos de bienes manufacturados (Segmentos 10, 46, 47, 52, 55).
    - Prohíbe estrictamente códigos de servicios (>= 70).
    - La relación código-cita semántica es 1:1 sin duplicaciones.
    """
    print("\n--- EJECUTANDO TEST B: Suministro PGIRS ASOCOMUNAL $50.076.264 ---")
    
    payload = UnspscAnalysisInput(
        objeto="SUMINISTRO DE INSUMOS, MATERIALES, DOTACIONES, EQUIPOS Y LOGISTICA PARA EL PGIRS DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBO",
        estudio_previo="Se requiere la adquisición de bienes e insumos para el desarrollo de actividades ambientales del PGIRS por valor de $50.076.264.",
        propuesta_economica="""ASOCOMUNAL YOLOMBO - NIT 800.254.070-8
1. Canecas plasticas de 53 galones con tapa y baldes de basura para recoleccion
2. Dotaciones completas para recicladores (overoles de proteccion, guantes de carnaza y botas de seguridad con puntera)
3. Vallas publicitarias de zinc y volantes informativos de separacion en la fuente
4. Plantulas ornamentales y especies vivas para jornadas ambientales
5. Equipos de sonido portatil, bafles y altoparlantes para socializacion
VALOR TOTAL: $50.076.264 COP"""
    )
    
    result = unspsc_agent.analyze_contract_unspsc(payload)
    cat_id, _ = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "C", f"Se esperaba Categoría C (Suministro), obtenido {cat_id}"
    
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    
    # 1. Prohibición absoluta de códigos de servicio (>= 70) en suministro
    for c in codigos:
        seg = int(c[:2])
        assert seg < 70, f"Violación de tipología primaria en Suministro: se asignó código de servicio {c} (Segmento {seg})"

    # 2. Presencia de los segmentos de bienes correspondientes
    segmentos = {c[:2] for c in codigos}
    assert any(s in ["47", "24"] for s in segmentos), "Falta código de canecas/residuos (Segmento 47)"
    assert "46" in segmentos, "Falta código de dotaciones/EPI (Segmento 46)"
    assert any(s in ["55", "56"] for s in segmentos), "Falta código de vallas/señalización (Segmento 55 o 56)"
    assert "10" in segmentos, "Falta código de plántulas (Segmento 10)"
    assert any(s in ["52", "45"] for s in segmentos), "Falta código de sonido/bafles (Segmento 52 o 45)"

    # 3. Relación código-cita semántica 1:1 sin duplicaciones
    codigos_set = set()
    for item in result.codigos_seleccionados:
        assert item.codigo_unspsc not in codigos_set, f"Código UNSPSC duplicado en resultado: {item.codigo_unspsc}"
        codigos_set.add(item.codigo_unspsc)
        
        c = item.codigo_unspsc
        just = item.justificacion_eleccion.lower()
        if c.startswith("47") or c.startswith("24"):
            assert any(w in just for w in ["caneca", "balde", "recipiente", "contenedor", "desperdicio", "residuo"])
        elif c.startswith("46"):
            assert any(w in just for w in ["dotacion", "overol", "guante", "bota", "seguridad", "proteccion"])
        elif c.startswith("55") or c.startswith("56"):
            assert any(w in just for w in ["valla", "senalamiento", "senal", "volante", "informativo"])
        elif c.startswith("10"):
            assert any(w in just for w in ["plantula", "planta", "especies vivas", "ornamental", "vivero"])
        elif c.startswith("52") or c.startswith("45"):
            assert any(w in just for w in ["sonido", "audio", "bafle", "altavoz", "altoparlante"])
            
    print("✓ Test B superado: Suministro clasificado en bienes (10, 46, 47, 52, 55) con correspondencia 1:1 y sin servicios.")


# =====================================================================
# TEST C: OBRA VÁLVULA LAS CAMELIAS
# =====================================================================
def test_c_obra_valvula_las_camelias():
    """
    Test C: Obra Válvula Las Camelias
    - Valida códigos de acueducto y obras civiles (Segmento 72).
    - Cubre los componentes de APU: Hidrosanitario, Movimiento de tierras y Pavimentos.
    - Prohíbe códigos de alcantarillado incompatible y canchas o parques.
    """
    print("\n--- EJECUTANDO TEST C: Obra Válvula Las Camelias ---")
    
    payload = UnspscAnalysisInput(
        objeto="INSTALACION DE VALVULA DE SECTORIZACION EN LA RED DE DISTRIBUCION DE ACUEDUCTO DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO",
        estudio_previo="Se requiere excavación a cielo abierto, empalme de tubería a presión RDE 21, válvula de sectorización y reposición de pavimento en concreto hidráulico.",
        propuesta_economica="""CONSTRUCTORA E INGENIERIA HIDRAULICA S.A.S. - NIT 901.234.567-8
1. LOCALIZACION Y REPLANTEO, EXCAVACION MANUAL EN MATERIAL COMUN
2. SUMINISTRO E INSTALACION DE VALVULA DE SECTORIZACION Y TUBERIA A PRESION RDE 21
3. ROTURA Y REPOSICION DE PAVIMENTO EN CONCRETO"""
    )
    
    result = unspsc_agent.analyze_contract_unspsc(payload)
    cat_id, _ = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "D", f"Se esperaba Categoría D (Obras Civiles/Acueducto), obtenido {cat_id}"
    
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    
    # 1. Todos los códigos deben pertenecer al Segmento 72 (Servicios de Construcción)
    for c in codigos:
        assert c.startswith("72"), f"El código {c} debe pertenecer al Segmento 72"

    # 2. Componentes obligatorios del APU
    has_hidro = any(c in ["72141119", "72141121", "72141124", "72151100"] for c in codigos)
    assert has_hidro, "Falta componente hidrosanitario de acueducto (72141119/72141121/72141124/72151100)"
    
    has_tierras = any(c in ["72141511", "72141505", "72141510"] for c in codigos)
    assert has_tierras, "Falta componente de excavación / movimiento de tierras (72141511/72141505)"
    
    has_pav = any(c in ["72141103", "72141104", "72141105"] for c in codigos)
    assert has_pav, "Falta componente de pavimento / vías (72141103/72141104/72141105)"
    
    # 3. Prohibición de drenajes o alcantarillado incompatibles
    prohibidos = {"72153103", "72152303", "72151906", "72141120", "72141205"}
    for bp in prohibidos:
        assert bp not in codigos, f"Código incompatible detectado en acueducto: {bp}"
        
    print("✓ Test C superado: Obra civil Las Camelias clasificada en Segmento 72 con los 3 componentes APU balanceados.")


# =====================================================================
# TEST D: SERVICIOS APOYO PGIRS - MAURICIO CARMONA
# =====================================================================
def test_d_servicios_apoyo_pgirs_mauricio_carmona():
    """
    Test D: Servicios Apoyo PGIRS (Mauricio Carmona)
    - Valida códigos de educación y gestión ambiental (Segmentos 76, 77, 93).
    - Prohíbe códigos de mantenimiento y taller mecánico (Segmentos 72 y 73).
    """
    print("\n--- EJECUTANDO TEST D: Servicios Apoyo PGIRS (Mauricio Carmona) ---")
    
    ocr_file = Path("backend/storage/uploads/8ea00ab7aa_propuesta economica.ocr.txt")
    if ocr_file.exists():
        raw_propuesta = ocr_file.read_text(encoding="utf-8")
    else:
        raw_propuesta = """Mauricio Antonio Carmona Rivera - C.C. 1045107945
OBJETO: Prestar servicios de apoyo a la gestion de las actividades contempladas en el Plan de Gestion Integral de Residuos Solidos - PGIRS del municipio de Yolombo, mediante el desarrollo de jornadas de sensibilizacion y educacion ambiental dirigidas a la comunidad, especialmente relacionadas con la adecuada separacion de residuos en la fuente y la socializacion de los cambios en la operacion de la ruta selectiva."""

    payload = UnspscAnalysisInput(
        objeto="PRESTACION DE SERVICIOS DE APOYO A LA GESTION EN LA IMPLEMENTACION Y SENSIBILIZACION DEL PGIRS EN EL MUNICIPIO DE YOLOMBO",
        estudio_previo="Se requiere apoyo a la gestión comunitaria para socialización puerta a puerta de la ruta selectiva, educación ambiental en separación en la fuente y gestión integral de residuos sólidos.",
        propuesta_economica=raw_propuesta
    )
    
    result = unspsc_agent.analyze_contract_unspsc(payload)
    cat_id, _ = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "A", f"Se esperaba Categoría A (Gestión Ambiental / PGIRS), obtenido {cat_id}"
    
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    assert len(codigos) > 0, "Debe seleccionar códigos UNSPSC"
    
    # 1. Deben pertenecer a Segmentos de gestión ambiental, residuos o comunitarios (77, 76, 93 o conexo educativo 86)
    valid_segs = {"76", "77", "93", "86"}
    for c in codigos:
        seg = c[:2]
        assert seg in valid_segs, f"Código {c} (Segmento {seg}) fuera de los segmentos permitidos de PGIRS/Educación Ambiental"

    # 2. Prohibición estricta de códigos de taller o electromecánicos (72 y 73)
    for c in codigos:
        seg = c[:2]
        assert seg not in ["72", "73"], f"Violación temática: Se seleccionó código de obra/taller ({c}) en servicios PGIRS"
        
    print("✓ Test D superado: Servicios PGIRS clasificados en Segmentos 76, 77 y 93 sin códigos de taller ni obra.")


# =====================================================================
# TEST E: EXÁMENES OCUPACIONALES ASISTYMED IPS S.A.S. (MEDICINA LABORAL)
# =====================================================================
def test_e_examenes_ocupacionales_asistymed():
    """
    Test E: Exámenes Ocupacionales ASISTYMED IPS S.A.S.
    - Reconoce automáticamente la categoría especializada E_HEALTH (Salud Ocupacional / Medicina Laboral).
    - Asigna obligatoriamente códigos del Segmento 85 (Servicios de Salud).
    - Prohíbe terminantemente códigos de aduanas o consultoría general del Segmento 80.
    - Filtro anti-saludos: No extrae 'Dando respuesta a la solicitud...' ni firmas.
    - Emparejamiento estricto 1:1: Cada código corresponde a su examen de la tabla
      (Osteomuscular/Snellen, Psicosensométrico, Audiometría, Espirometría).
    """
    print("\n--- EJECUTANDO TEST E: Exámenes Ocupacionales ASISTYMED IPS S.A.S. ---")
    ocr_file = Path("backend/storage/uploads/17ad64cb1e_PROPUESTA ECONOMICA.ocr.txt")
    if ocr_file.exists():
        raw_propuesta = ocr_file.read_text(encoding="utf-8")
    else:
        raw_propuesta = """ASISTYMED IPS S.A.S.
Dando respuesta a la solicitud realizada, le envío el valor de los exámenes ocupacionales:
CONCEPTO | TOTAL
Examen ocupacional con enfasis Osteo-muscular. Tamizaje Visual (carta Snellen) | $1.680.000
Psicosensometrico | $230.000
Audiometria | $525.000
Espirometria | $588.000
Atentamente, Dr. Jorge Nelson Molina"""

    payload = UnspscAnalysisInput(
        objeto="PRESTACION DE SERVICIOS PROFESIONALES PARA LA REALIZACION DE EXAMENES OCUPACIONALES",
        estudio_previo="Se requiere contratar la realización de los exámenes médicos ocupacionales periódicos para los trabajadores de la ESPY.",
        propuesta_economica=raw_propuesta
    )

    cat_id, cat_nombre = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "E_HEALTH", f"Se esperaba Categoría E_HEALTH, obtenido {cat_id}"

    result = unspsc_agent.analyze_contract_unspsc(payload)
    
    # 1. Filtro anti-saludos: Ninguna actividad extraída puede ser saludo o firma
    for act in result.actividades_propuesta_extraidas:
        act_lower = act.lower()
        assert "dando respuesta" not in act_lower, f"Saludo conversacional filtrado incorrectamente: {act}"
        assert "le envio" not in act_lower and "le envío" not in act_lower, f"Saludo filtrado incorrectamente: {act}"
        assert "nelson molina" not in act_lower, f"Nombre de persona/firma extraído incorrectamente: {act}"

    # 2. Las 4 actividades reales de la tabla deben estar presentes
    acts_joined = " ".join(result.actividades_propuesta_extraidas).lower()
    assert "osteo" in acts_joined or "snellen" in acts_joined, "Falta examen osteomuscular/tamizaje visual"
    assert "psicosensometrico" in acts_joined or "psico" in acts_joined, "Falta examen psicosensométrico"
    assert "audiometria" in acts_joined, "Falta audiometría"
    assert "espirometria" in acts_joined, "Falta espirometría"

    # 3. Todos los códigos seleccionados deben pertenecer al Segmento 85
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    assert len(codigos) >= 4, f"Se esperaban al menos 4 códigos para los 4 exámenes, obtenidos {len(codigos)}"
    for c in codigos:
        assert c.startswith("85"), f"El código {c} debe pertenecer obligatoriamente al Segmento 85 (Salud)"
        assert not c.startswith("80"), f"Violación grave: Se seleccionó código genérico del Segmento 80 ({c}) en salud ocupacional"

    # 4. Emparejamiento 1:1: Las citas en las justificaciones deben ser diversas (prohibido repetir items[0])
    citations = []
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"La justificación debe contener cita entre comillas: {item.justificacion_eleccion}"
        citations.append(quotes[0].strip())

    unique_citations = set(citations)
    assert len(unique_citations) >= 3, f"Emparejamiento estricto 1:1 falló, citas duplicadas o repetidas: {citations}"
    print("✓ Test E superado: Salud ocupacional clasificada en Segmento 85 con filtro anti-saludos y emparejamiento 1:1.")


# =====================================================================
# TEST F: BIENESTAR LABORAL Y SALIDA RECREATIVA (CPS-046-2026)
# =====================================================================
def test_f_bienestar_laboral_salida_recreativa_asocomunal():
    """
    Test F: Bienestar Laboral y Salida Recreativa (CPS-046-2026 - ASOCOMUNAL)
    - Clasifica en E_WELLBEING (Servicios de Bienestar Social, Recreación y Eventos).
    - Extrae el ítem real de la tabla de PROPUESTA.pdf y desglosa operativamente
      los componentes del Estudio Previo (salida recreativa, transporte de personas,
      instalaciones recreativas/hospedaje, alimentación/banquetes y obsequios).
    - CERO texto fantasma 'Actividad operativa complementaria del alcance en campo'.
    - CERO códigos quemados de consultoría genérica (80121609, 80121900, 84121700, 80151504).
    - Selección coherente de códigos oficiales de Segmentos 90, 78 y 80.
    - Citas 1:1 en las justificaciones sin repetir la primera cita.
    """
    print("\n--- EJECUTANDO TEST F: Salida Recreativa y Bienestar Laboral ---")
    ocr_file = Path("backend/storage/temp_unspsc/propuesta_1792249660486_PROPUESTA.ocr.txt")
    if ocr_file.exists():
        raw_propuesta = ocr_file.read_text(encoding="utf-8")
    else:
        raw_propuesta = """ASOCOMUNAL YOLOMBO - NIT 800254070-8
Producto: ACTIVIDADES DE BIENESTAR LABORAL E INTEGRACION DE LOS EMPLEADOS DE LA ESPY, INCLUYENDO CELEBRACIONES, OBSEQUIOS Y ACTIVIDADES DE FIN DE ANO
Cantidad: 1 | VALOR TOTAL: $18.000.000"""

    payload = UnspscAnalysisInput(
        objeto="PRESTACIÓN DE SERVICIOS PARA REALIZACIÓN DE UNA SALIDA RECREATIVA, EDUCATIVA Y DE INTEGRACIÓN EN EL MARCO DE LAS ACTIVIDADES DE BIENESTAR LABORAL PROGRAMADAS POR LA EMPRESA PARA LA VIGENCIA 2026",
        estudio_previo="Se requiere contratar la salida recreativa de integración laboral de los empleados de la ESPY, que incluye transporte de personas, instalaciones de recreación y hospedaje, y celebraciones y obsequios de fin de año.",
        propuesta_economica=raw_propuesta
    )

    cat_id, cat_nombre = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "E_WELLBEING", f"Se esperaba Categoría E_WELLBEING, obtenido {cat_id}"

    result = unspsc_agent.analyze_contract_unspsc(payload)

    # 1. Cero texto fantasma
    for act in result.actividades_propuesta_extraidas:
        assert "actividad operativa complementaria" not in act.lower(), f"Texto fantasma detectado: {act}"

    # 2. Componentes operativos identificados
    acts_joined = " ".join(result.actividades_propuesta_extraidas).lower()
    assert any(k in acts_joined for k in ["bienestar", "integracion", "salida"]), "Falta núcleo de bienestar o integración"
    assert any(k in acts_joined for k in ["celebraciones", "obsequios", "transporte", "hospedaje"]), "Faltan componentes operativos del desglose"

    # 3. Códigos seleccionados
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    assert len(codigos) >= 4, f"Se esperaban al menos 4 códigos representativos, obtenidos {len(codigos)}"

    # Códigos quemados prohibidos
    banned_fallbacks = {"80121609", "80121900", "84121700", "80151504"}
    for bf in banned_fallbacks:
        assert bf not in codigos, f"Código quemado fallback detectado: {bf}"

    # Validar que los códigos pertenezcan a los segmentos de bienestar / recreación / transporte / eventos
    for c in codigos:
        seg = c[:2]
        assert seg in ["90", "78", "80", "93"], f"Código {c} pertenece a segmento incompatible {seg}"

    # Debe cubrir recreación/deporte (90141700), transporte (78111800), hospedaje (90111500) o banquetes (90101600)
    has_recreacion = any(c.startswith("9014") or c.startswith("9015") for c in codigos)
    has_transporte = any(c.startswith("7811") for c in codigos)
    has_banquetes_o_hotel = any(c.startswith("9010") or c.startswith("9011") for c in codigos)
    assert has_recreacion, "Debe incluir código de recreación / deportes aficionados"
    assert has_transporte, "Debe incluir código de transporte de pasajeros por carretera"
    assert has_banquetes_o_hotel, "Debe incluir código de hospedaje o banquetes/catering"

    # 4. Emparejamiento de citas en justificaciones: Prohibido repetir la misma cita en todas las filas
    citations = []
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual: {item.justificacion_eleccion}"
        citations.append(quotes[0].strip())

    unique_citations = set(citations)
    assert len(unique_citations) >= 3, f"Falta diversidad en citas 1:1, encontradas: {citations}"
    print("✓ Test F superado: Salida recreativa y bienestar laboral clasificado en Segmentos 90, 78 y 80 sin códigos quemados ni texto fantasma.")


# =====================================================================
# TEST G: TRANSPORTE EN VOLQUETA Y APOYO A RECOLECCIÓN DE RESIDUOS (WILSON MUÑOZ)
# =====================================================================
def test_g_transporte_volqueta_residuos_wilson_munoz():
    """
    Test G: Transporte en Volqueta / Residuos Sólidos (Wilson Muñoz - 23 viajes de 6 m³)
    - Regla de Prioridad Operativa: Clasifica en E_FREIGHT_TRANSPORT (Segmentos 78 y 76).
    - Prohibido paquetes de educación ambiental o pedagogía (8610...), consultoría de
      informes (7710...) o trabajo comunitario (9314...) por el simple término "residuos" o "aseo".
    - Quota estricta: Devuelve entre 2 y 3 códigos representativos (no inflar a 5 códigos).
    - Códigos pertinentes: 78101801 / 78101800 (transporte de carga en camión/volqueta),
      76121500 / 76121501 (recolección y disposición de basuras/residuos), 78111808 (alquiler vehículos).
    - Limpieza de OCR: CERO filtración de 'RUT_CONTACTO_UBICACION_BLOQUE' ni texto pegado sin espacios.
    - Citas 1:1 en justificaciones: Prohibido repetir items[0] en todas las filas.
    """
    print("\n--- EJECUTANDO TEST G: Transporte en Volqueta Residuos Wilson Muñoz ---")
    ocr_file = Path("backend/storage/temp_unspsc/propuesta_1792255596650_PROPUESTA_ECONOMICA.ocr.txt")
    if ocr_file.exists():
        raw_propuesta = ocr_file.read_text(encoding="utf-8")
    else:
        raw_propuesta = """Asunto: Cotizacion de servicio de transporte en volqueta para apoyo a la prestacion del servicio de aseo
El servicio comprende la realizacion de veintitres (23) viajes en volqueta, con una capacidad aproximada de seis metros cubicos (6 m3) por viaje.
1. Servicio de transporte en volqueta para apoyo a la prestacion del servicio de aseo | 23 viajes | 6 m3
VALOR TOTAL: $17.083.000 COP"""

    payload = UnspscAnalysisInput(
        objeto="PRESTACIÓN DEL SERVICIO DE TRANSPORTE EN VOLQUETA PARA APOYO A LA RECOLECCIÓN Y TRANSPORTE DE RESIDUOS SÓLIDOS EN EL MUNICIPIO DE YOLOMBÓ",
        estudio_previo="Se requiere contratar el servicio de transporte en volqueta para apoyo a la recolección y transporte de residuos sólidos en el municipio de Yolombó, consistente en 23 viajes de 6 m3.",
        propuesta_economica=raw_propuesta
    )

    # 1. Clasificación Temática con Prioridad Operativa
    cat_id, cat_nombre = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "E_FREIGHT_TRANSPORT", f"Se esperaba Categoría E_FREIGHT_TRANSPORT, obtenido {cat_id}"

    result = unspsc_agent.analyze_contract_unspsc(payload)

    # 2. Limpieza de texto en Paso 1 (Actividades extraídas)
    assert len(result.actividades_propuesta_extraidas) >= 3, "Debe extraer al menos 3 actividades"
    for act in result.actividades_propuesta_extraidas:
        assert "rut_" not in act.lower(), f"Fuga de etiqueta interna de RUT en Paso 1: {act}"
        assert "ubicacion_bloque" not in act.lower(), f"Fuga de bloque de ubicación en Paso 1: {act}"
        assert "elserviciocomprendela" not in act.lower(), f"Texto pegado sin corregir: {act}"

    # 3. Quota de códigos: Entre 2 y 3 códigos para contrato de ítem unitario
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    assert 2 <= len(codigos) <= 3, f"Se esperaban entre 2 y 3 códigos, obtenidos {len(codigos)}"

    # 4. Prohibición estricta de códigos de pedagogía, informes o trabajo comunitario
    banned_segments = {"86", "77", "93", "80", "27"}
    for c in codigos:
        seg = c[:2]
        assert seg not in banned_segments, f"Código incompatible {c} de segmento {seg} asignado a transporte en volqueta"
        assert seg in ["78", "76", "72"], f"Código {c} no pertenece a los segmentos autorizados (78, 76, 72)"

    # 5. Cobertura del núcleo de transporte de carga y disposición de residuos
    has_transporte_carga = any(c.startswith("781018") for c in codigos)
    has_residuos_disposicion = any(c.startswith("761215") for c in codigos)
    assert has_transporte_carga, "Debe incluir código de transporte de carga por carretera (78101801 o 78101800)"
    assert has_residuos_disposicion, "Debe incluir código de recolección y disposición de basuras (76121500 o 76121501)"

    # 6. Emparejamiento 1:1 en justificaciones: Prohibido repetir exactamente la misma cita en todas las filas
    citations = []
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual entre comillas: {item.justificacion_eleccion}"
        citations.append(quotes[0].strip())

    unique_citations = set(citations)
    assert len(unique_citations) >= 2, f"Falta diversidad en citas 1:1, se detectó repetición monótona de items[0]: {citations}"
    print("✓ Test G superado: Transporte en volqueta Wilson Muñoz clasificado en E_FREIGHT_TRANSPORT (Segmentos 78 y 76) con 2-3 códigos y citas 1:1.")


# =====================================================================
# TEST H: MARKETING DIGITAL, COMUNICACIONES Y REDES SOCIALES (MANUELA GALLEGO)
# =====================================================================
def test_h_marketing_digital_comunicaciones():
    """
    Test H: Marketing Digital y Comunicaciones (Manuela Gallego)
    - Prioridad exclusiva del Objeto Contractual: Clasifica en E_MARKETING (Segmentos 80, 81, 82).
    - Prohibido clasificar en Categoría A (PGIRS/residuos) por menciones institucionales en el Estudio Previo.
    - Extracción de viñetas operativas reales en Paso 1 (ALCANCE DEL SERVICIO / ENTREGABLES).
    - Cero filtración de frases de relleno institucionales del Estudio Previo.
    - Asignación de códigos de los Segmentos 80 (Marketing/Redes), 82 (Diseño/Audiovisual) y 81 (Hosting/Internet).
    - Citas 1:1 verificadas con la propuesta.
    """
    print("\n--- EJECUTANDO TEST H: Marketing Digital y Comunicaciones ---")
    ocr_file = Path("backend/storage/uploads/32920721a2_PROPUESTA ECONOMICA.ocr.txt")
    assert ocr_file.exists(), f"Archivo de propuesta no encontrado: {ocr_file}"
    raw_ocr = ocr_file.read_text(encoding="utf-8")

    payload = UnspscAnalysisInput(
        objeto="PRESTACION DE SERVICIOS PARA DISEÑAR E IMPLEMENTAR ESTRATEGIAS DE MARKETING DIGITAL Y COMUNICACIÓN DE LA EMPRESA DE SERVICIOS PUBLICOS DE YOLOMBÓ",
        estudio_previo="La Empresa de Servicios Públicos de Yolombó E.S.P. realiza el presente estudio sobre la necesidad de contar con estrategias de comunicación en los ámbitos de Acueducto, Alcantarillado y Aseo, con el fin de llegar a la comunidad usuaria.",
        propuesta_economica=raw_ocr
    )

    # 1. Clasificación Temática en Eje de Marketing Digital
    cat_id, cat_nombre = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "E_MARKETING", f"Se esperaba Categoría E_MARKETING, obtenido {cat_id}"
    assert cat_id != "A", "PROHIBIDO clasificar en Categoría A (PGIRS/Aseo) un contrato de marketing digital"

    result = unspsc_agent.analyze_contract_unspsc(payload)

    # 2. Extracción de actividades en Paso 1
    assert len(result.actividades_propuesta_extraidas) >= 3, "Debe extraer al menos 3 actividades"
    for act in result.actividades_propuesta_extraidas:
        lower_a = act.lower()
        assert "realiza el presente estudio" not in lower_a, f"Se filtró frase institucional del EP: {act}"
        assert "ambitos de acueducto" not in lower_a, f"Se filtró frase institucional del EP: {act}"
        assert "alcantarillado y aseo" not in lower_a, f"Se filtró frase institucional del EP: {act}"

    # 3. Códigos asignados deben pertenecer a los Segmentos 80, 81 o 82
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    assert len(codigos) >= 3, f"Se esperaban al menos 3 códigos, obtenidos {len(codigos)}"

    banned_in_marketing = {"72", "73", "76", "77", "86", "93", "27"}
    for c in codigos:
        seg = c[:2]
        assert seg not in banned_in_marketing, f"Código incompatible {c} de segmento {seg} asignado a marketing digital"
        assert seg in ["80", "81", "82"], f"Código {c} no pertenece a los segmentos autorizados (80, 81, 82)"

    # 4. Verificar cobertura de los ejes de la propuesta (Marketing/Redes, Diseño/Audiovisual, Hosting/Internet)
    has_marketing_redes = any(c.startswith("8014") or c.startswith("8017") for c in codigos)
    has_audiovisual_diseno = any(c.startswith("8214") or c.startswith("8213") or c.startswith("8210") for c in codigos)
    has_hosting_internet = any(c.startswith("8111") for c in codigos)
    assert has_marketing_redes, "Debe incluir código de marketing digital / gestión de redes sociales (Segmento 80)"
    assert has_audiovisual_diseno, "Debe incluir código de diseño gráfico o producción audiovisual/fotografía (Segmento 82)"
    assert has_hosting_internet, "Debe incluir código de hosting web / servicios de internet (Segmento 81)"

    # 5. Verificación de citas 1:1
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual entre comillas: {item.justificacion_eleccion}"

    print("✓ Test H superado: Marketing Digital y Comunicaciones clasificado en E_MARKETING (Segmentos 80, 81, 82) con viñetas reales y citas 1:1.")


# =====================================================================
# TEST I: SUMINISTRO DE ALMUERZOS, REFRIGERIOS, ANCHETAS Y RECONOCIMIENTOS (ASOCOMUNAL)
# =====================================================================
def test_i_suministro_catering_almuerzos_asocomunal():
    """
    Test I: Suministro de Alimentación, Catering, Anchetas y Reconocimientos (ASOCOMUNAL)
    - Extracción de tabla (Paso 1): Extrae íntegros los 6 ítems sin cortarlos por comas ni romper filas:
      1. Almuerzos (arroz, proteína, guarnición y jugo)
      2. Refrigerios (pastel de queso, jugo, hidratación, fruta)
      3. Bolsas de crispetas
      4. Anchetas con productos yolombinos
      5. Reconocimientos
      6. Bolsas en algodón contramarcadas
      Cero frases de relleno institucionales ("realiza el presente", "CONTRATO DE SUMINISTRO").
    - Excepción de Catering en Suministro: Asigna Segmento 90 (90101600), Segmento 50 (50161800), Segmento 80 (80141611).
    - Prohibición estricta de Ferretería (Segmento 40), Tuberías, Válvulas o Herramientas (27) para alimentación.
    - Citas 1:1 sincronizadas y sin duplicación de la misma cita en todas las filas.
    """
    print("\n--- EJECUTANDO TEST I: Suministro de Almuerzos, Refrigerios, Anchetas y Reconocimientos ---")
    ocr_file = Path("backend/storage/temp_unspsc/propuesta_1792417833138_PROPUESTA_ECONOMICA.ocr.txt")
    assert ocr_file.exists(), f"Archivo de propuesta no encontrado: {ocr_file}"
    raw_ocr = ocr_file.read_text(encoding="utf-8")

    payload = UnspscAnalysisInput(
        objeto="SUMINISTRO DE ALMUERZOS, REFRIGERIOS, ANCHETAS, RECONOCIMIENTOS Y BOLSAS ECOLÓGICAS PARA ACTIVIDADES DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ",
        estudio_previo="La Empresa de Servicios Públicos de Yolombó E.S.P. realiza el presente CONTRATO DE SUMINISTRO con el fin de adquirir la alimentación y elementos requeridos para eventos institucionales.",
        propuesta_economica=raw_ocr
    )

    # 1. Clasificación Temática en Categoría C
    cat_id, cat_nombre = unspsc_agent.classify_contract_thematic_category(payload.objeto, payload.propuesta_economica)
    assert cat_id == "C", f"Se esperaba Categoría C, obtenido {cat_id}"

    result = unspsc_agent.analyze_contract_unspsc(payload)

    # 2. Validación de Extracción de Tablas (Paso 1)
    extracted = result.actividades_propuesta_extraidas
    assert len(extracted) >= 5, f"Se esperaban al menos 5 o 6 ítems extraídos, obtenidos {len(extracted)}: {extracted}"

    joined_extracted = " ".join(extracted).lower()
    # Verificar los 6 ítems nucleares
    assert "almuerzo" in joined_extracted, "Debe extraer Almuerzos"
    assert "refrigerio" in joined_extracted, "Debe extraer Refrigerios"
    assert "crispeta" in joined_extracted, "Debe extraer Bolsas de crispetas"
    assert "ancheta" in joined_extracted, "Debe extraer Anchetas"
    assert "reconocimiento" in joined_extracted, "Debe extraer Reconocimientos"
    assert "bolsa" in joined_extracted and "algodon" in joined_extracted, "Debe extraer Bolsas en algodón"

    # Verificar que no contenga frases basura institucionales
    for act in extracted:
        lower_a = act.lower()
        assert "realiza el presente" not in lower_a, f"Se filtró frase institucional: {act}"
        assert "contrato de suministro" not in lower_a, f"Se filtró frase institucional: {act}"

    # 3. Validación de Códigos UNSPSC
    codigos = [c.codigo_unspsc for c in result.codigos_seleccionados]
    assert len(codigos) >= 3, f"Se esperaban al menos 3 códigos, obtenidos {len(codigos)}: {codigos}"

    # Prohibición terminante de Ferretería (Segmento 40: válvulas, tuberías) o Herramientas (27)
    banned_segs = {"40", "27", "72", "73"}
    for c in codigos:
        seg = c[:2]
        assert seg not in banned_segs, f"Código absurdo {c} del segmento {seg} (ferretería/obra/taller) asignado a contrato de catering"

    # Presencia obligatoria de los 3 segmentos/códigos nucleares
    has_catering = any(c.startswith("901016") for c in codigos)
    has_alimentos = any(c.startswith("501618") or c.startswith("501921") or c[:2] == "50" for c in codigos)
    has_obsequios_bolsas = any(c.startswith("801416") or c[:2] == "80" for c in codigos)

    assert has_catering, f"Debe incluir código 90101600 (Servicios de banquetes y catering), obtenidos: {codigos}"
    assert has_alimentos, f"Debe incluir código 50161800 (Confitería / Alimentos), obtenidos: {codigos}"
    assert has_obsequios_bolsas, f"Debe incluir código 80141611 (Personalización de obsequios / Bolsas / Reconocimientos), obtenidos: {codigos}"

    # 4. Sincronización de Citas 1:1 y Eliminación de Duplicación
    cited_activities = []
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual entre comillas: {item.justificacion_eleccion}"
        quote_text = quotes[0].lower().strip()
        cited_activities.append(quote_text)

        # Regla de simetría de cita por código
        if item.codigo_unspsc.startswith("901016"):
            assert any(w in quote_text for w in ["almuerzo", "refrigerio", "pastel", "queso", "arroz"]), (
                f"Código de catering {item.codigo_unspsc} debe citar almuerzos o refrigerios, cita actual: {quote_text}"
            )
        elif item.codigo_unspsc.startswith("501618"):
            assert any(w in quote_text for w in ["ancheta", "crispeta", "yolombino"]), (
                f"Código de alimentos {item.codigo_unspsc} debe citar anchetas o crispetas, cita actual: {quote_text}"
            )
        elif item.codigo_unspsc.startswith("801416"):
            assert any(w in quote_text for w in ["bolsa", "algodon", "reconocimiento"]), (
                f"Código de artículos publicitarios {item.codigo_unspsc} debe citar bolsas o reconocimientos, cita actual: {quote_text}"
            )

    # Regla: NO repetir la misma cita en todas las filas
    unique_cites = set(cited_activities)
    assert len(unique_cites) >= 3, f"Las citas están duplicadas o repetitivas: {cited_activities}"

    print("✓ Test I superado: Suministro de catering y alimentación con extracción íntegra de tabla, códigos 90/50/80, cero ferretería y citas 1:1.")


def test_j_suministro_vehiculo_camion_pequeno():
    """
    Test J: Suministro / Adquisición de Vehículo Tipo Camión Pequeño (Categoría C - Segmento 25).
    Valida:
    1. Búsqueda en Segmento 25 (Bienes Manufacturados del 10 al 60).
    2. Selección de códigos pertinentes (25101507 Camiones ligeros / 25181604 Carrocería de camión de carga / 25101917 Camabaja).
    3. Cero códigos absurdos o desconectados (Prohibido Isótopos 12142200, Gas natural, Alimentos o Almuerzos).
    4. Cuota ajustada y de alta fidelidad: Máximo 2 códigos de alta precisión en lugar de rellenar con 5 códigos falsos.
    """
    agent = unspsc_agent
    inp = UnspscAnalysisInput(
        objeto="ADQUISICIÓN DE UN VEHÍCULO TIPO CAMIÓN PEQUEÑO CON CARROCERÍA DE ESTACAS O PLATAFORMA",
        estudio_previo="La ESPY requiere adquirir un vehículo tipo camión pequeño para el apoyo operativo del municipio de Yolombó.",
        propuesta_economica="Item 1: Suministro de un (1) vehículo tipo camión pequeño con carrocería de carga."
    )
    result = agent.analyze_contract_unspsc(inp)

    assert result.total_codigos > 0, "Debe retornar al menos 1 código de vehículo"
    assert result.total_codigos <= 2, f"En vehículos se prefieren 1 o 2 códigos exactos sin rellenar, obtenidos: {result.total_codigos}"

    codigos = [item.codigo_unspsc for item in result.codigos_seleccionados]
    for c in codigos:
        assert c[:2] == "25", f"Todos los códigos de suministro de vehículos deben pertenecer al Segmento 25, código obtenido: {c}"
        assert not c.startswith("121422"), "Prohibido terminantemente seleccionar códigos de Isótopos"
        assert not c.startswith("901016"), "Prohibido terminantemente seleccionar códigos de almuerzos/catering en vehículos"
        assert not c.startswith("501618"), "Prohibido terminantemente seleccionar códigos de alimentos en vehículos"

    has_camion_or_carroceria = any(c in ("25101507", "25181604", "25101917", "25101611") for c in codigos)
    assert has_camion_or_carroceria, f"Debe seleccionar código de camión o carrocería (25101507, 25181604, 25101917), obtenidos: {codigos}"

    print("✓ Test J superado: Suministro de vehículo/camión con apertura al Segmento 25, cero isótopos/alimentos y cuota de precisión.")


def test_k_suministro_tecnologia_impresion_toner():
    """
    Test K: Suministro de Equipo Tecnológico de Impresión y Elementos de Consumo (Categoría C - Segmentos 43 y 44).
    Valida:
    1. Enrutamiento obligatorio a Segmentos 43 y 44.
    2. Prohibición estricta de códigos de publicidad/señalización (Segmento 55), alimentos (Segmento 50) o ferretería (Segmento 40).
    3. Selección de códigos prioritarios de impresora (43212104 / 43212105) y consumibles/tóner (44101703 / 44103103).
    4. Correspondencia y citas 1:1 limpias sin arrastrar textos generales del estudio previo.
    """
    agent = unspsc_agent
    inp = UnspscAnalysisInput(
        objeto="ADQUISICIÓN DE EQUIPO TECNOLÓGICO DE IMPRESIÓN Y ELEMENTOS DE CONSUMO (Impresora de trabajo pesado y Tóners)",
        estudio_previo="La ESPY requiere adquirir equipo tecnológico de impresión y elementos de consumo para el desarrollo de las actividades operativas de la entidad.",
        propuesta_economica="""
Item | Descripción | Cantidad
1 | Impresora de trabajo pesado monocromática láser de 65ppm | 1
2 | Tóner para impresora con capacidad de 15.000 copias | 4
"""
    )
    result = agent.analyze_contract_unspsc(inp)

    assert result.total_codigos > 0, "Debe retornar al menos 1 código"
    assert result.total_codigos <= 2, f"Máximo 2 códigos de alta precisión en tecnología de impresión, obtenidos: {result.total_codigos}"

    codigos = [item.codigo_unspsc for item in result.codigos_seleccionados]
    for c in codigos:
        assert c[:2] in ("43", "44"), f"Los códigos deben pertenecer a Segmentos 43 o 44, obtenido: {c}"
        assert not c.startswith("55"), f"Prohibido terminantemente seleccionar códigos de señalización/publicidad (Segmento 55): {c}"
        assert not c.startswith("50"), f"Prohibido terminantemente seleccionar códigos de alimentos (Segmento 50): {c}"
        assert not c.startswith("40"), f"Prohibido terminantemente seleccionar códigos de ferretería (Segmento 40): {c}"

    has_impresora = any(c.startswith("432121") for c in codigos)
    has_toner = any(c.startswith("441031") or c.startswith("441017") for c in codigos)

    assert has_impresora, f"Debe incluir código de impresora (Segmento 43, ej. 43212104 o 43212105), obtenidos: {codigos}"
    assert has_toner, f"Debe incluir código de consumible/tóner (Segmento 44, ej. 44101703 o 44103103), obtenidos: {codigos}"

    # Validar correspondencia de citas 1:1
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita: {item.justificacion_eleccion}"
        quote = quotes[0].lower().strip()
        if item.codigo_unspsc.startswith("43"):
            assert any(w in quote for w in ["impresora", "pesado", "65ppm", "ppm", "maquina"]), f"Código 43 debe citar impresora, cita actual: {quote}"
        elif item.codigo_unspsc.startswith("44"):
            assert any(w in quote for w in ["toner", "tóner", "copias", "15.000", "cartucho"]), f"Código 44 debe citar tóner, cita actual: {quote}"

    print("✓ Test K superado: Enrutamiento a Segmentos 43/44, cero publicidad/ferretería, citas 1:1 limpias.")


# =====================================================================
# TEST L: OBRA REPOSICIÓN TUBERÍA DE ACUEDUCTO LA ESPIGA
# =====================================================================
def test_l_obra_acueducto_la_espiga():
    """
    Test L: Obra Reposición de Tubería de Acueducto en el Sector La Espiga
    - Contrato de Obra / Infraestructura Hidrosanitaria por $85.747.811 COP.
    - Clasificación ineludible en Categoría D.
    - Búsqueda exclusivamente en Segmento 72 (Servicios de Construcción).
    - Prohibición estricta de códigos de señalización/publicidad (Segmento 55),
      equipos médicos (Segmento 42) o materiales sueltos del Segmento 48.
    - Priorización de códigos: 72141119 (Construcción de acueductos),
      72141510/72141511 (Movimiento de tierras/Excavación/Demolición),
      72141124 (Tendido de tubería) y 72141103 (Pavimentación/Concretos).
    - Emparejamiento semántico 1:1 con los ítems del presupuesto.
    """
    print("\n--- EJECUTANDO TEST L: Obra Reposición Tubería La Espiga ---")
    agent = unspsc_agent

    inp = UnspscAnalysisInput(
        objeto="REPOSICIÓN DE LA TUBERÍA DE DISTRIBUCIÓN DEL SERVICIO DE ACUEDUCTO EN EL SECTOR LA ESPIGA",
        estudio_previo="Contrato de Obra para la reposición de la tubería de distribución del servicio de acueducto en el sector La Espiga del municipio de Yolombó por valor de $85.747.811.",
        propuesta_economica="""
Item | Descripción | Unidad | Cantidad
1 | Demolición y excavación manual en material común para zanja | M3 | 120.0
2 | Suministro e instalación y tendido de tubería de 8 pulgadas para acueducto | ML | 350.0
3 | Reposición de pavimento y obras en concreto hidráulico | M2 | 85.0
"""
    )
    cat_id, cat_nombre = agent.classify_contract_thematic_category(inp.objeto, inp.propuesta_economica)
    assert cat_id == "D", f"Debe clasificar en Categoría D (Obras Civiles), obtenido: {cat_id}"

    result = agent.analyze_contract_unspsc(inp)

    assert result.total_codigos > 0, "Debe retornar códigos seleccionados"
    codigos = [item.codigo_unspsc for item in result.codigos_seleccionados]

    # 1. Regla de Segmento Exclusivo 72 y Prohibición Estricta de 55, 42, 48
    for c in codigos:
        assert c.startswith("72"), f"Todos los códigos deben pertenecer al Segmento 72 (Construcción), obtenido: {c}"
        assert not c.startswith("55"), f"Prohibido terminantemente códigos de publicidad/señalización (Segmento 55): {c}"
        assert not c.startswith("42"), f"Prohibido terminantemente códigos médicos/camillas (Segmento 42): {c}"
        assert not c.startswith("48"), f"Prohibido terminantemente códigos de tubería suelta del Segmento 48: {c}"

    # 2. Componentes obligatorios del APU
    has_hidro = any(c in ["72141119", "72141124", "72141121", "72151100"] for c in codigos)
    assert has_hidro, f"Debe incluir código de acueductos o tendido de tubería (72141119/72141124), obtenidos: {codigos}"

    has_tierras = any(c in ["72141510", "72141511", "72141505"] for c in codigos)
    assert has_tierras, f"Debe incluir código de excavación o demolición/movimiento de tierras (72141510/72141511), obtenidos: {codigos}"

    has_pav = any(c in ["72141103", "72141104", "72141105"] for c in codigos)
    assert has_pav, f"Debe incluir código de pavimentos/concretos (72141103/72141105), obtenidos: {codigos}"

    # 3. Emparejamiento 1:1 con los ítems del presupuesto
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual: {item.justificacion_eleccion}"
        quote = quotes[0].lower().strip()
        if item.codigo_unspsc in ["72141510", "72141511", "72141505"]:
            assert any(w in quote for w in ["excavacion", "excavación", "demolicion", "demolición", "zanja", "tierra"]), f"Código de tierras debe citar excavación/demolición, cita actual: {quote}"
        elif item.codigo_unspsc in ["72141119", "72141124", "72141121", "72151100"]:
            assert any(w in quote for w in ["tuberia", "tubería", "8", "pulgadas", "acueducto", "tendido"]), f"Código de agua debe citar tubería/acueducto, cita actual: {quote}"
        elif item.codigo_unspsc in ["72141103", "72141104", "72141105"]:
            assert any(w in quote for w in ["pavimento", "concreto", "hidraulico", "hidráulico"]), f"Código de obras civiles debe citar concreto/pavimento, cita actual: {quote}"

    print("✓ Test L superado: Obra La Espiga clasificada en Categoría D, Segmento 72 exclusivo, cero 55/42/48 y correspondencia 1:1.")


# =====================================================================
# TEST M: OBRA CUNETA, MURO DE CONTENCIÓN Y ESTABILIZACIÓN TALUD PTAP
# =====================================================================
def test_m_obra_estabilizacion_talud_ptap():
    """
    Test M: Obra Estabilización de Taludes, Cuneta Perimetral, Muro de Contención y Reforestación PTAP
    - Contrato de Obra / Infraestructura (Categoría D).
    - Sub-enrutador inteligente de Obras Civiles (Segmentos 72 y 70).
    - No devolver combo estático de tubería o aceras.
    - Selecciona códigos de:
      1. Cuneta de coronación / Drenaje hidráulico superficial (72141205 / 72141100).
      2. Muro de contención en llantas / Estabilización de tierras (72152707 / 72141502).
      3. Retiro de derrumbes / Movimiento de tierras / Llenos compactados (72141505 / 72141511).
      4. Reforestación de talud / Maní forrajero / Cobertura vegetal (70111501 / 72102902 / 70111709).
    - Emparejamiento 1:1 estricto en la justificación con cada ítem textual del presupuesto.
    """
    print("\n--- EJECUTANDO TEST M: Obra Estabilización Talud PTAP ---")
    agent = unspsc_agent

    inp = UnspscAnalysisInput(
        objeto="CONSTRUCCIÓN DE UNA CUNETA PERIMETRAL DE CORONACIÓN, MURO DE CONTENCIÓN EN LLANTAS RECICLADAS Y OBRAS COMPLEMENTARIAS PARA LA ESTABILIZACIÓN DE TALUDES EN LA PTAP",
        estudio_previo="La ESPY requiere la estabilización de taludes en la Planta de Tratamiento de Agua Potable (PTAP) mediante obras de drenaje superficial, muros de contención en llantas y reforestación.",
        propuesta_economica="""
Item | Descripción | Unidad | Cantidad
1 | construcion de cuneta de coronocacion de 0.60 de desarrollo con esp=0.10 ml y cajas disipadoras de energia | ML | 80.0
2 | Suministro, Trasporte y fabricación de muro de contención conformado por Llantas recicladas | M2 | 45.0
3 | retiro de derrumbe m2 20,00 y llenos compatados con material de cantera m3 12,00 | GLOBAL | 1.0
4 | reforestacion de talud con mani forrajero o similar m2 100,00 | M2 | 100.0
"""
    )
    cat_id, cat_nombre = agent.classify_contract_thematic_category(inp.objeto, inp.propuesta_economica)
    assert cat_id == "D", f"Debe clasificar en Categoría D (Obras Civiles), obtenido: {cat_id}"

    result = agent.analyze_contract_unspsc(inp)

    assert result.total_codigos >= 4, f"Debe retornar al menos 4 códigos para los 4 ítems del APU, obtenidos: {result.total_codigos}"
    codigos = [item.codigo_unspsc for item in result.codigos_seleccionados]

    # 1. Validación de códigos esperados (Sub-clasificación inteligente de obra)
    has_drenaje = any(c in ["72141205", "72141100"] for c in codigos)
    assert has_drenaje, f"Falta código de drenaje superficial / cuneta (72141205 / 72141100), obtenidos: {codigos}"

    has_muro = any(c in ["72152707", "72141502"] for c in codigos)
    assert has_muro, f"Falta código de muro de contención / retención (72152707 / 72141502), obtenidos: {codigos}"

    has_tierras = any(c in ["72141505", "72141511"] for c in codigos)
    assert has_tierras, f"Falta código de movimiento de tierras / derrumbes / llenos (72141505 / 72141511), obtenidos: {codigos}"

    has_reforest = any(c in ["70111501", "72102902", "70111709", "72102905", "70111700"] for c in codigos)
    assert has_reforest, f"Falta código de reforestación / siembra / maní forrajero (70111501 / 72102902 / 70111709), obtenidos: {codigos}"

    # Prohibido devolver aceras o plomería cuando es estabilización de taludes
    assert "72151100" not in codigos, "No debe incluir plomería en estabilización de taludes"
    assert "72141105" not in codigos, "No debe incluir aceras peatonales en cunetas de talud"

    # 2. Emparejamiento estricto 1:1 en justificaciones (Citas no repetidas)
    quotes_seen = []
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual: {item.justificacion_eleccion}"
        quote = quotes[0].lower().strip()
        quotes_seen.append(quote)

        if item.codigo_unspsc in ["72141205", "72141100"]:
            assert any(w in quote for w in ["cuneta", "coronocacion", "coronacion", "disipadora"]), f"Fila de drenaje debe citar cuneta/coronación, cita: {quote}"
        elif item.codigo_unspsc in ["72152707", "72141502"]:
            assert any(w in quote for w in ["muro", "llantas", "contencion", "contención"]), f"Fila de muro debe citar muro de contención en llantas, cita: {quote}"
        elif item.codigo_unspsc in ["72141505", "72141511"]:
            assert any(w in quote for w in ["derrumbe", "llenos", "cantera", "compatados", "compactados", "excavacion", "tierra"]), f"Fila de tierras debe citar retiro de derrumbe/llenos, cita: {quote}"
        elif item.codigo_unspsc in ["70111501", "72102902", "70111709", "72102905", "70111700"]:
            assert any(w in quote for w in ["reforestacion", "reforestación", "mani", "maní", "forrajero", "siembra"]), f"Fila de reforestación debe citar maní forrajero, cita: {quote}"

    # Validar que NO todas las filas repitan la misma cita
    assert len(set(quotes_seen)) >= 3, f"Las citas no deben repetirse entre filas. Citas obtenidas: {quotes_seen}"

    print("✓ Test M superado: Sub-enrutador de estabilización de taludes funcional con códigos de drenaje, muro, tierras y reforestación 1:1.")


# =====================================================================
# TEST N: EXTRACCIÓN PERSONA JURÍDICA CON CÉDULA DE REP LEGAL Y RUT (MONITOREO INTELIGENTE)
# =====================================================================
def test_n_extraccion_persona_juridica_con_cedula():
    """
    Test N: Extracción simultánea de Persona Jurídica (RUT) y Representante Legal (Cédula)
    - Prioridad absoluta del documento CEDULA para el representante legal cuando tipo_persona == 'JURIDICA'.
    - Filtrado estricto con is_valid_person_name: PROHIBIDO asignar 'CERTIFICADO' u otros nombres inválidos.
    - No clonación del NIT en la cédula del representante legal.
    - NIT íntegro de 9 dígitos en RUT (830513067) con su DV oficial (6) sin truncar a 8 dígitos.
    """
    print("\n--- EJECUTANDO TEST N: Extracción Persona Jurídica con Cédula (MONITOREO INTELIGENTE) ---")
    from app.services.rut_parser import parse_dian_rut, calculate_dian_dv
    from app.services.document_parser import is_valid_person_name, extract_colombian_cedula_data

    # 1. Simulación texto RUT oficial de MONITOREO INTELIGENTE S.A.S.
    rut_text = """
    2. Concepto 0 2 Actualización
    4. Número de formulario 14993267911
    5. Número de Identificación Tributaria (NIT) 6. DV 12. Dirección seccional 14. Buzón electrónico
    8 3 0 5 1 3 0 6 7 6 Impuestos de Medellín 1 1
    IDENTIFICACIÓN
    24. Tipo de contribuyente 25. Tipo de documento 26. Número de Identificación
    Persona jurídica 1
    35. Razón social
    MONITOREO INTELIGENTE S. A. S.
    38. País 39. Departamento 40. Ciudad/Municipio
    COLOMBIA 1 6 9 Antioquia 0 5 Medellín 0 0 1
    41. Dirección principal
    C L 8 B 65 191 O F 314
    42. Correo electrónico administracion@monitoreointeligente.com
    53. Código 48 - Impuesto sobre las ventas - IVA
    Firma autorizada:
    984. Nombre ESCOBAR GONZALEZ CARLOS IVAN
    Firma del solicitante:
    985. Cargo Representante legal Certificado
    === PÁGINA 3 ===
    Representación
    98. Representación 99. Fecha inicio ejercicio representación
    REPRS LEGAL PRIN 1 8 2 0 0 5 0 1 1 4
    100. Tipo de documento 101. Número de identificación 102. DV 103. Número de tarjeta profesional
    Cédula de Ciudadanía 1 3 7 1 2 6 2 8 5 9
    1
    104. Primer apellido 105. Segundo apellido 106. Primer nombre 107. Otros nombres
    ESCOBAR GONZALEZ CARLOS IVAN
    """

    # 2. Simulación texto de Cédula de Ciudadanía
    cedula_text = """
    === PÁGINA 1 ===
    CEDULA DE CIUDADANIA
    REPUBLICA DE COLOMBIA
    NUIP 71.262.859
    APELLIDOS: ESCOBAR GONZALEZ
    NOMBRES: CARLOS IVAN
    ICC0L041537172401001<<<<<<<<<<
    8206266M3402144COL71262859<<<8
    ESCOBAR<GONZALEZ<<CARLOS<IVAN<<<
    """

    # Validar RUT Parser
    rut_parsed = parse_dian_rut(rut_text)
    assert rut_parsed.get("tipo_persona") == "JURIDICA"
    assert rut_parsed.get("numero_documento") == "830513067", f"NIT truncado o incorrecto: {rut_parsed.get('numero_documento')}"
    assert rut_parsed.get("digito_verificacion") == "6", f"DV incorrecto: {rut_parsed.get('digito_verificacion')}"
    assert rut_parsed.get("nombre_o_razon_social") == "MONITOREO INTELIGENTE S. A. S."
    assert rut_parsed.get("representante_legal_nombre") != "CERTIFICADO", "No debe asignar CERTIFICADO como representante legal"
    assert "CARLOS IVAN" in (rut_parsed.get("representante_legal_nombre") or "")
    assert rut_parsed.get("representante_legal_documento") == "71262859"

    # Validar validador de nombres
    assert not is_valid_person_name("CERTIFICADO")
    assert not is_valid_person_name("DISPONIBILIDAD PRESUPUESTAL")
    assert is_valid_person_name("CARLOS IVAN ESCOBAR GONZALEZ")

    # Validar extractor de cédula
    ced_parsed = extract_colombian_cedula_data(cedula_text)
    assert ced_parsed.get("numero_documento") == "71262859"
    assert ced_parsed.get("nombre_completo") == "CARLOS IVAN ESCOBAR GONZALEZ"

    # Validar que calculate_dian_dv sea exacto
    assert calculate_dian_dv("830513067") == "6"

    print("✓ Test N superado: Extracción de Persona Jurídica, Cédula de Representante Legal y RUT de 9 dígitos validada con éxito.")


# =====================================================================
# TEST O: SUMINISTRO Y PLATAFORMA GPS / CÁMARAS ADAS-DMS (CS-056-2026)
# =====================================================================
def test_o_suministro_gps_camaras_vehiculares_cs056():
    """
    Test O: Suministro, Instalación y Puesta en Funcionamiento de Unidades de Rastreo Satelital GPS,
    Cámaras de Videovigilancia Vehicular ADAS/DMS, Tarjetas MicroSD 128GB y Monitoreo en Plataforma (CS-056-2026).
    Valida:
    1. Cero códigos de banquetes/catering (90101603) o alimentos (Segmento 50).
    2. Cero códigos de compra de vehículos automotores (25101507, 25101917, 25101601, 25101611).
    3. Cero códigos de altoparlantes domésticos (52161512).
    4. Selección de códigos tecnológicos y de seguridad de catálogo oficial (2517, 4512/4617, 4320, 8111).
    5. Citas 1:1 verificables de la propuesta económica sin citas falsas de otros contratos.
    """
    agent = unspsc_agent
    inp = UnspscAnalysisInput(
        objeto="SUMINISTRO, INSTALACIÓN Y PUESTA EN FUNCIONAMIENTO DE UNIDADES DE RASTREO SATELITAL GPS, CÁMARAS DE VIDEOVIGILANCIA VEHICULAR CON TECNOLOGÍA ADAS/DMS, TARJETAS MICROSD 128GB Y SERVICIO CONEXO DE MONITOREO EN PLATAFORMA PARA EL PARQUE AUTOMOTOR DE LA EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P.",
        estudio_previo="La ESPY requiere la adquisición de unidades de rastreo satelital GPS, cámaras de videovigilancia vehicular con tecnología ADAS/DMS, tarjetas MicroSD de 128GB y servicio conexo de monitoreo en plataforma web 24/7 para el parque automotor de la entidad.",
        propuesta_economica="""
Item | Descripción | Cantidad
1 | UNIDAD GPS LC | 4
2 | UNIDAD DE Video Ref. JC371 Incluye cámara frontal ADAS | 4
3 | CI05F Cabin-View Full AHD Camera DMS | 4
4 | MicroSD 128GB | 4
5 | Monitoreo de PLATAFORMA GPS Y VIDEO Advanced 24/7 | 4
6 | Instalación y accesorios de seguridad en cabina (botón de pánico, apagado remoto) | 4
"""
    )
    result = agent.analyze_contract_unspsc(inp)

    assert result.total_codigos >= 4, f"Debe seleccionar al menos 4 códigos para cubrir los componentes del contrato, obtenidos: {result.total_codigos}"

    codigos = [item.codigo_unspsc for item in result.codigos_seleccionados]

    # 1. Prohibiciones estrictas
    assert "90101603" not in codigos, "Prohibido terminantemente seleccionar banquetes/catering en GPS"
    assert not any(c.startswith("90") for c in codigos), f"Prohibido Segmento 90 en GPS, obtenidos: {codigos}"
    assert not any(c.startswith("50") for c in codigos), f"Prohibido Segmento 50 en GPS, obtenidos: {codigos}"
    assert not any(c.startswith("2510") for c in codigos), f"Prohibido compra de vehículos (Familia 2510: camiones, camabajas): {codigos}"
    assert "52161512" not in codigos, f"Prohibido altoparlantes domésticos (52161512) en GPS: {codigos}"

    # 2. Selección de códigos tecnológicos oficiales
    has_gps = any(c in ("25173107", "43221722", "25173108") or c.startswith("251731") for c in codigos)
    has_camara = any(c in ("46171610", "45121516", "45121500", "46171611") or c.startswith("461716") or c.startswith("451215") for c in codigos)
    has_memoria = any(c in ("43202005", "43201800", "43202000") or c.startswith("432020") for c in codigos)
    has_seguridad_o_plataforma = any(c in ("25172100", "81112200", "43232504", "81111809", "72151608") for c in codigos)

    assert has_gps, f"Debe seleccionar código de GPS vehicular (25173107): {codigos}"
    assert has_camara, f"Debe seleccionar código de cámara vehicular ADAS/DMS (45121516 o 46171610): {codigos}"
    assert has_memoria, f"Debe seleccionar código de memoria MicroSD (43202005): {codigos}"
    assert has_seguridad_o_plataforma, f"Debe seleccionar código de seguridad vehicular o plataforma/instalación: {codigos}"

    # 3. Validación de citas 1:1 verificables
    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita: {item.justificacion_eleccion}"
        quote = quotes[0].lower().strip()
        # Verificar que no contenga frases de otros contratos
        assert "almuerz" not in quote, f"Cita contaminada con almuerzos: {quote}"
        assert "pastel de carne" not in quote, f"Cita contaminada con pastel de carne: {quote}"
        assert "ancheta" not in quote, f"Cita contaminada con anchetas: {quote}"
        assert "impresora de trabajo pesado" not in quote, f"Cita contaminada con impresora: {quote}"
        assert "23 viajes" not in quote, f"Cita contaminada con viajes: {quote}"

    print("✓ Test O superado: Suministro de GPS/Cámaras/MicroSD/Plataforma (CS-056-2026) clasificado con 100% de precisión y cero códigos espurios.")


# =====================================================================
# TEST P: INSTALACIÓN DE PASAMANOS Y CARPINTERÍA EN MADERA PLÁSTICA A TODO COSTO
# =====================================================================
def test_p_instalacion_pasamanos_madera_plastica_todo_costo():
    """
    Test P: Instalación de Pasamanos, Parales y Carpintería en Madera Plástica A Todo Costo
    - Clasificación en Categoría D (Obras/Mantenimiento/Instalaciones) en lugar de Categoría E.
    - Apertura de Segmentos 72 (Servicios de construcción/instalación), 30 (Materiales de construcción) y 31 (Ferretería/Tornillería).
    - Prohibición absoluta de códigos desconectados como cafeterías (Segmento 90) o cooperación técnica (Segmento 80).
    - Asignación precisa de códigos correspondientes a pasamanos, postes/madera, tornillos y acabados.
    """
    print("\n--- EJECUTANDO TEST P: Instalación Pasamanos en Madera Plástica A Todo Costo ---")
    agent = unspsc_agent

    ep = """ESTUDIOS PREVIOS DE JUSTIFICACION Y CONVENIENCIA
INSTALACION DE PASAMANOS EN MADERA PLASTICA A TODO COSTO PARA LOS SITIOS DE TRANSITO PEATONAL DE LA REPRESA EL SERENO DEL MUNICIPIO DE YOLOMBÓ

OBJETO: Seleccionar a la persona natural o jurídica que ofrezca las mejores condiciones
para el contrato de "INSTALACION DE PASAMANOS EN MADERA PLASTICA A TODO COSTO PARA LOS SITIOS DE TRANSITO PEATONAL DE LA REPRESA EL SERENO DEL MUNICIPIO DE YOLOMBÓ".
PLAZO DE EJECUCION: 30 días
VALOR: $15.000.000
"""

    prop = """COTIZACION PARA INSTALACION DE PASAMANOS EN MADERA PLASTICA A TODO COSTO
Item | Descripción | Cantidad
1 | Parales estacón 8x8x115 | 60
2 | Baretas 4x13x230 | 90
3 | Tornillos 3/8 x 1/2 x4 | 380
4 | Parales 12x12x300 | 6
5 | Estibas 50x70 | 10
6 | visita técnica | 1
7 | Mano de obra, dias | 10
"""

    inp = UnspscAnalysisInput(
        objeto="Seleccionar a la persona natural o jurídica que ofrezca las mejores condiciones",
        estudio_previo=ep,
        propuesta_economica=prop
    )

    result = agent.analyze_contract_unspsc(inp)
    assert result.total_codigos > 0, "Debe retornar códigos seleccionados"

    # 1. Objeto detectado no debe estar truncado ni ser sólo la fórmula preambular
    assert result.objeto_detectado is not None
    assert "PASAMANOS" in result.objeto_detectado.upper(), f"Objeto detectado debe contener PASAMANOS, obtenido: {result.objeto_detectado}"
    assert "MADERA PLASTICA" in result.objeto_detectado.upper() or "MADERA PLÁSTICA" in result.objeto_detectado.upper(), f"Objeto debe contener MADERA PLASTICA, obtenido: {result.objeto_detectado}"

    # 2. Las actividades extraídas deben estar limpias
    acts = result.actividades_propuesta_extraidas
    assert len(acts) >= 4, f"Se esperaban al menos 4 actividades extraídas, obtenidas: {len(acts)}"
    acts_lower = [a.lower() for a in acts]
    assert any("parales" in a for a in acts_lower), "Falta actividad de parales"
    assert any("tornillos" in a for a in acts_lower), "Falta actividad de tornillos"
    assert any("baretas" in a for a in acts_lower), "Falta actividad de baretas"
    for a in acts:
        assert "11560" not in a, f"Error: 115 y 60 pegados en actividad: {a}"

    # 3. Categoría D clasificada y segmentos
    codigos = [item.codigo_unspsc for item in result.codigos_seleccionados]
    for c in codigos:
        assert not c.startswith("90"), f"Prohibido código de cafetería/catering en pasamanos: {c}"
        assert not c.startswith("93"), f"Prohibido código de cooperación técnica en pasamanos: {c}"
        assert not c.startswith("80"), f"Prohibido código de asistencia técnica/cooperación en pasamanos: {c}"
        assert not c.startswith("50"), f"Prohibido código de alimentos en pasamanos: {c}"
        assert c[:2] in ("72", "30", "31", "24"), f"Código {c} fuera de los segmentos permitidos (72, 30, 31, 24)"

    has_seg72 = any(c.startswith("72") for c in codigos)
    has_mat30_or_31_or_24 = any(c.startswith(("30", "31", "24")) for c in codigos)
    assert has_seg72, f"Debe incluir al menos un código de servicios de instalación/construcción/carpintería (Segmento 72), obtenidos: {codigos}"
    assert has_mat30_or_31_or_24, f"Debe incluir al menos un código de materiales/tornillería/estructuras (Segmento 30, 31 o 24), obtenidos: {codigos}"

    for item in result.codigos_seleccionados:
        quotes = re.findall(r'["“]([^"”]+)["”]', item.justificacion_eleccion)
        assert len(quotes) > 0, f"Justificación sin cita textual: {item.justificacion_eleccion}"

    print("✓ Test P superado: Pasamanos y carpintería en madera plástica clasificado en Categoría D con códigos de Segmentos 72, 30 y 31.")


if __name__ == "__main__":
    test_a_mantenimiento_herramientas_cps055()
    test_b_suministro_pgirs_asocomunal()
    test_c_obra_valvula_las_camelias()
    test_d_servicios_apoyo_pgirs_mauricio_carmona()
    test_e_examenes_ocupacionales_asistymed()
    test_f_bienestar_laboral_salida_recreativa_asocomunal()
    test_g_transporte_volqueta_residuos_wilson_munoz()
    test_h_marketing_digital_comunicaciones()
    test_i_suministro_catering_almuerzos_asocomunal()
    test_j_suministro_vehiculo_camion_pequeno()
    test_k_suministro_tecnologia_impresion_toner()
    test_l_obra_acueducto_la_espiga()
    test_m_obra_estabilizacion_talud_ptap()
    test_n_extraccion_persona_juridica_con_cedula()
    test_o_suministro_gps_camaras_vehiculares_cs056()
    test_p_instalacion_pasamanos_madera_plastica_todo_costo()
    print("\n=======================================================")
    print(" ¡SUITE DE REGRESIÓN OBLIGATORIA SUPERADA AL 100%! ")
    print("=======================================================")

