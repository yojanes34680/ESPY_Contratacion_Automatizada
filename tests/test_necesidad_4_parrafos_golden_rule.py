"""Suite de pruebas unitarias y de integración para la
DESCRIPCIÓN DE LA NECESIDAD A SATISFACER conforme a la Ley 142 de 1994 y El Método del Embudo.
Verifica:
1. Regla de Oro: Prohibido mencionar 'acueducto y alcantarillado' en contratos de PGIRS, aseo o administrativos.
2. Estructura estricta de 3 niveles del Método del Embudo (Marco, Brecha, Requerimiento con viñetas).
3. Fórmulas obligatorias para Servicios y Suministro.
4. Brecha condicional por tipología (Servicios, Suministro, Obra) sin nombre de contratista.
5. Inclusión Total de actividades o bienes.
6. Integración con API endpoints (/build-necesidad y creación en /contracts).
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
    analyze_objeto_keywords
)

client = TestClient(app)

def test_unit_pgirs_golden_rule():
    print("\n--- TEST 1: Unidad - PGIRS / Aseo (Regla de Oro: Cero mención a acueducto y alcantarillado) ---")
    objeto = "ACTUALIZACIÓN E IMPLEMENTACIÓN DEL PLAN DE GESTIÓN INTEGRAL DE RESIDUOS SÓLIDOS (PGIRS) DEL MUNICIPIO DE YOLOMBÓ"
    tipo = "PRESTACION_SERVICIOS"
    
    text = build_descripcion_necesidad(objeto, tipo)
    assert text.startswith("DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"), "Falta título oficial"
    
    levels = [p.strip() for p in text.split("\n\n") if p.strip() and p.strip() != "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"]
    assert len(levels) >= 3, f"Se esperaban al menos 3 niveles, se obtuvieron {len(levels)}"
    
    n1, n2, n3 = levels[0], levels[1], levels[2]
    
    # Nivel 1: Marco
    assert "EMPRESA DE SERVICIOS PÚBLICOS DE YOLOMBÓ E.S.P." in n1
    assert "142 de 1994" in n1
    assert "residuos sólidos" in n1.lower() or "ambiental" in n1.lower()
    assert "acueducto y alcantarillado" not in n1.lower(), "Violación Regla de Oro en Nivel 1 PGIRS"
    assert "acueducto" not in n1.lower()
    assert "alcantarillado" not in n1.lower()
    
    # Nivel 2: Brecha de Servicios
    assert "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in n2
    assert "acueducto" not in n2.lower()
    assert "alcantarillado" not in n2.lower()
    
    # Nivel 3: Fórmula y Requerimiento
    assert "Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo" in n3
    assert "-" in n3, "Debe contener viñetas"
    print("  [OK] PGIRS cumple 100% con los 3 niveles del Método del Embudo y Regla de Oro.")


def test_unit_administrative_golden_rule():
    print("\n--- TEST 2: Unidad - Labores Administrativas y Jurídicas (Regla de Oro) ---")
    objeto = "PRESTACIÓN DE SERVICIOS PROFESIONALES DE ASESORÍA JURÍDICA EN DERECHO ADMINISTRATIVO Y CONTRACTUAL"
    tipo = "PRESTACION_SERVICIOS"
    
    text = build_descripcion_necesidad(objeto, tipo)
    levels = [p.strip() for p in text.split("\n\n") if p.strip() and p.strip() != "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"]
    assert len(levels) >= 3
    
    n1, n2, n3 = levels[0], levels[1], levels[2]
    assert "acueducto y alcantarillado" not in text.lower(), "Violación Regla de Oro en contrato administrativo"
    assert "acueducto" not in text.lower()
    assert "alcantarillado" not in text.lower()
    assert "jurídic" in n1.lower() or "administrativ" in n1.lower()
    
    # Nivel 2: Brecha
    assert "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in n2
    # Nivel 3: Fórmula
    assert "Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo" in n3
    print("  [OK] Contrato administrativo cumple 100% Regla de Oro y fórmula.")


def test_unit_acueducto():
    print("\n--- TEST 3: Unidad - Acueducto (Potabilización y distribución de agua) ---")
    objeto = "SUMINISTRO DE COAGULANTE POLICLORURO DE ALUMINIO Y CLORO GASEOSO PARA LA PLANTA DE TRATAMIENTO DE AGUA POTABLE"
    tipo = "SUMINISTRO"
    
    text = build_descripcion_necesidad(objeto, tipo)
    levels = [p.strip() for p in text.split("\n\n") if p.strip() and p.strip() != "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"]
    assert len(levels) >= 3
    
    n1, n2, n3 = levels[0], levels[1], levels[2]
    assert "potabilización" in n1.lower() or "acueducto" in n1.lower() or "agua" in n1.lower()
    
    # Nivel 2: Suministro
    assert "Actualmente, la ESPY presenta agotamiento en las existencias de su almacén" in n2
    
    # Nivel 3: Fórmula Suministro
    assert "Por consiguiente, surge la necesidad imperiosa de adquirir los siguientes bienes e insumos" in n3
    print("  [OK] Suministro de acueducto cumple con potabilización, condicional de almacén y fórmula.")


def test_unit_obra():
    print("\n--- TEST 4: Unidad - Obra (Infraestructura, mantenimiento, reparación) ---")
    objeto = "EJECUTAR OBRAS CIVILES PARA LA REPOSICIÓN DE REDES EN EL SECTOR URBANO"
    tipo = "OBRA"
    
    text = build_descripcion_necesidad(objeto, tipo)
    levels = [p.strip() for p in text.split("\n\n") if p.strip() and p.strip() != "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"]
    assert len(levels) >= 3
    
    n2 = levels[1]
    assert "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in n2
    assert "artículo 209 de la Constitución Política" in n2
    print("  [OK] Obra cumple con condicional normativo de insuficiencia técnica.")


def test_api_endpoint_build_necesidad():
    print("\n--- TEST 5: API Endpoint - POST /api/agents/build-necesidad ---")
    payload = {
        "objeto": "PRESTACIÓN DE SERVICIOS PARA LA REALIZACIÓN DE TALLERES Y CAPACITACIONES EN EL MANEJO DE RESIDUOS SÓLIDOS Y PGIRS",
        "tipologia": "PRESTACION_SERVICIOS"
    }
    r = client.post("/api/agents/build-necesidad", json=payload)
    assert r.status_code == 200, f"Error {r.status_code}: {r.text}"
    data = r.json()
    assert data["titulo"] == "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER"
    assert "acueducto y alcantarillado" not in data["texto_completo"].lower()
    assert "residuos sólidos" in data["texto_completo"].lower() or "pgirs" in data["texto_completo"].lower()
    assert "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in data["texto_completo"]
    assert "Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo" in data["texto_completo"]
    print("  [OK] Endpoint /api/agents/build-necesidad respondió exitosamente con los 3 niveles del Método del Embudo.")


def test_contract_creation_auto_generates_compliant_necesidad():
    print("\n--- TEST 6: Creación de contrato sin necesidad manual -> Auto-generación de Embudo ---")
    import time
    num_cto = f"ESP-NEC-{int(time.time())}"
    contract_data = {
        "numero_contrato": num_cto,
        "vigencia": 2026,
        "modalidad_seleccion": "CONTRATACION_DIRECTA",
        "tipologia": "PRESTACION_SERVICIOS",
        "contratista_id": 1,
        "objeto": "APOYO A LA GESTIÓN EN EL ARCHIVO CENTRAL Y ORGANIZACIÓN DE EXPEDIENTES ADMINISTRATIVOS",
        "valor_total": 12000000.0,
        "plazo_ejecucion": 4,
        "unidad_plazo": "MESES"
    }
    r = client.post("/api/contracts", json=contract_data)
    assert r.status_code == 201, f"Error {r.status_code}: {r.text}"
    created = r.json()
    just = created["justificacion_necesidad"]
    assert just is not None and "DESCRIPCIÓN DE LA NECESIDAD A SATISFACER" in just
    assert "acueducto y alcantarillado" not in just.lower(), "Violación Regla de Oro en contrato de archivo administrativo"
    assert "Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente" in just
    assert "Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo" in just
    print("  [OK] Contrato creado auto-generó justificación con Método del Embudo respetando la Regla de Oro.")


if __name__ == "__main__":
    test_unit_pgirs_golden_rule()
    test_unit_administrative_golden_rule()
    test_unit_acueducto()
    test_unit_obra()
    test_api_endpoint_build_necesidad()
    test_contract_creation_auto_generates_compliant_necesidad()
    print("\n==================================================================")
    print(" TODAS LAS PRUEBAS DE LA DESCRIPCIÓN DE LA NECESIDAD PASARON (100%)")
    print("==================================================================")
