"""Test unitario y de integración para validar la normalización del Objeto Contractual en MAYÚSCULAS
y la estructura institucional requerida por la ESP Yolombó:
'PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO'
"""
import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path("backend").resolve()))

from app.utils.object_normalizer import normalize_objeto_contractual
from app.services.gemini_client import gemini_service
from app.services.agents.object_agent import object_agent
from app.services.agents.dispatcher import dispatcher
from app.schemas.agent import ObjetoGenerationInput, ContractDraftingInput

def test_objeto_exacto_solicitado_por_usuario():
    print("\n=== PRUEBA 1: VALIDACIÓN DEL OBJETO SOLICITADO POR EL USUARIO ===")
    ocr_file = Path("backend/storage/uploads/7917234b1a_PROPUESTA ECONOMICA.ocr.txt")
    assert ocr_file.exists(), "El archivo OCR de propuesta debe existir"
    
    ocr_text = ocr_file.read_text(encoding="utf-8")
    ext_data = gemini_service._heuristic_contractor_extraction(ocr_text)

    expected = "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO"
    print(f"Objeto extraído de propuesta: {ext_data.objeto_propuesto}")
    assert ext_data.objeto_propuesto == expected, f"Objeto extraído no coincide.\nEsperado: {expected}\nObtenido: {ext_data.objeto_propuesto}"
    print("[OK] Objeto propuesto extraído coincide exactamente con el formato en mayúsculas.")

def test_variaciones_entrada_objeto_valvula():
    print("\n=== PRUEBA 2: TODAS LAS VARIACIONES DEL CASO VÁLVULA SECTORIZACIÓN ===")
    expected = "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO"
    casos = [
        "Instalar válvula de sectorización sector las camelias en el municipio de Yolombó para la Empresa de Servicios Públicos.",
        "INSTALACION DE VALVULADE SECTORIZACION SECTOR LA CAMELIAS",
        "INSTALACION DE VALVULA DE SECTORIZACION SECTOR LAS CAMELIAS",
        "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO",
        "Instalacion de valvula de sectorizacion sector las camelias municipio de yolombo"
    ]
    for c in casos:
        res = normalize_objeto_contractual(c)
        print(f"  Entrada: {c[:60]}... -> Salida: {res}")
        assert res == expected, f"Fallo al normalizar: '{c}' -> '{res}'"
    print("[OK] Todas las variaciones normalizan al objeto exacto solicitado.")

def test_object_agent_generates_uppercase():
    print("\n=== PRUEBA 3: OBJECT AGENT GENERA OBJETO EN MAYÚSCULAS SOSTENIDAS ===")
    inp = ObjetoGenerationInput(
        tipologia="PRESTACION_SERVICIOS",
        necesidad_descripcion="INSTALACION DE VALVULADE SECTORIZACION SECTOR LA CAMELIAS",
        contratista_nombre="CONTRATISTA DE PRUEBA"
    )
    result = object_agent.generate_objeto(inp)
    print(f"Objeto sugerido por ObjectAgent: {result.objeto_sugerido}")
    expected = "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO"
    assert result.objeto_sugerido == expected, f"Objeto sugerido no coincide con esperado: {result.objeto_sugerido}"
    assert result.objeto_sugerido == result.objeto_sugerido.upper(), "El objeto no está en mayúsculas sostenidas"
    print("[OK] ObjectAgent formula correctamente en mayúsculas sostenidas.")

def test_multi_agent_dispatcher_objeto_uppercase():
    print("\n=== PRUEBA 4: DISPATCHER MULTI-AGENTE Y NORMALIZACIÓN DE OBJETO ===")
    inp = ContractDraftingInput(
        tipologia="PRESTACION_SERVICIOS",
        necesidad_descripcion="INSTALACION DE VALVULADE SECTORIZACION SECTOR LA CAMELIAS",
        alcance_esperado="Instalación de válvula y accesorios en red matriz",
        valor_estimado=4153408.0,
        plazo=3,
        unidad_plazo="DIAS"
    )
    draft = dispatcher.dispatch_drafting(inp)
    print(f"Objeto en draft: {draft.objeto}")
    expected = "PRESTACION DE SERVICIOS PARA LA INSTALACION DE VALVULA DE SECTORIZACION DEL SECTOR LAS CAMELIAS DEL MUNICIPIO DE YOLOMBO"
    assert draft.objeto == expected, f"Objeto en draft no coincide: {draft.objeto}"
    assert draft.objeto == draft.objeto.upper(), "El objeto en draft debe estar en mayúsculas sostenidas"
    print("[OK] Dispatcher Multi-Agente garantiza objeto en mayúsculas.")

if __name__ == "__main__":
    test_objeto_exacto_solicitado_por_usuario()
    test_variaciones_entrada_objeto_valvula()
    test_object_agent_generates_uppercase()
    test_multi_agent_dispatcher_objeto_uppercase()
    print("\n=== TODAS LAS PRUEBAS DE OBJETO EN MAYÚSCULAS PASARON EXITOSAMENTE (100%) ===")
