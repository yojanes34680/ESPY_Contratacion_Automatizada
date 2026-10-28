"""Comprehensive test suite for RiskMatrixAgent and endpoints."""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_path = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_path))

from app.schemas.agent import RiskMatrixInput, RiskMatrixResult
from app.services.agents.risk_agent import risk_agent, RiskMatrixAgent
from fastapi.testclient import TestClient
from app.main import app

def test_risk_matrix_generation_unit():
    print("\n--- 1. Testing RiskMatrixAgent Unit Logic ---")
    pgirs_text = """
    ESTUDIOS PREVIOS DE JUSTIFICACION Y CONVENIENCIA CONTRATO DE PRESTACIÓN DE SERVICIOS
    La Empresa municipal de servicios públicos de Yolombó E.S.P., realiza el presente estudio sobre la conveniencia y oportunidad de contratar el PRESTACION DE SERVICIOS PARA EL APOYO A LA GENTIÓN DE LAS ACTIVIDADES CONPLEMENTARIAS DEL PGIRS DEL MUNICIPIO DE YOLOMBO.
    OBJETO: Seleccionar a la persona natural o jurídica que ofrezca las mejores condiciones para el contrato de "PRESTACION DE SERVICIOS PARA EL APOYO A LA GENTIÓN DE LAS ACTIVIDADES CONPLEMENTARIAS DEL PGIRS DEL MUNICIPIO DE YOLOMBO".
    TIPO DE CONTRATO: El contrato a celebrar es de PRESTACIÓN DE SERVICIOS.
    CONVENIENCIA: por lo que la celebración de un contrato de suministro da cumplimiento a tales objetivos.
    REQUERIMIENTO DE PÓLIZAS: No se requerirá la constitución de pólizas y/o garantías para la celebración del presente contrato.
    VALOR: $4.800.000. PLAZO: 2 meses. LUGAR: Municipio de Yolombó.
    """
    
    inp = RiskMatrixInput(
        objeto="PRESTACION DE SERVICIOS PARA EL APOYO A LA GENTIÓN DE LAS ACTIVIDADES CONPLEMENTARIAS DEL PGIRS DEL MUNICIPIO DE YOLOMBO",
        tipologia="PRESTACION_SERVICIOS",
        contratista_nombre="ANYIE OCHOA URIBE",
        valor_estimado=4800000.0,
        plazo_texto="2 meses",
        lugar_ejecucion="Municipio de Yolombó, Antioquia",
        exige_polizas=False,
        estudio_previo_texto=pgirs_text
    )
    
    result = risk_agent.generate_risk_matrix(inp)
    
    assert isinstance(result, RiskMatrixResult)
    print(f"Agent Name: {result.agente_nombre}")
    print(f"Total Risks Generated: {result.total_riesgos}")
    assert result.total_riesgos >= 6, "Expected at least 6 risks"
    
    # 1. Objeto normalizado
    print(f"Objeto Normalizado: {result.objeto}")
    assert "GESTIÓN" in result.objeto
    assert "COMPLEMENTARIAS" in result.objeto
    
    # 2. Arithmetic & Category Validation
    for r in result.riesgos:
        # Check consecutive numbering
        assert r.numero > 0
        
        # Check Initial Evaluation
        assert 1 <= r.probabilidad_inicial <= 5
        assert 1 <= r.impacto_inicial <= 5
        assert r.valoracion_inicial == r.probabilidad_inicial + r.impacto_inicial
        
        if r.valoracion_inicial <= 4:
            expected_cat_ini = "Bajo"
        elif r.valoracion_inicial == 5:
            expected_cat_ini = "Medio"
        elif r.valoracion_inicial in (6, 7):
            expected_cat_ini = "Alto"
        else:
            expected_cat_ini = "Extremo"
        assert r.categoria_inicial == expected_cat_ini
        
        # Check Residual Evaluation
        assert 1 <= r.probabilidad_residual <= 5
        assert 1 <= r.impacto_residual <= 5
        assert r.valoracion_residual == r.probabilidad_residual + r.impacto_residual
        
        if r.valoracion_residual <= 4:
            expected_cat_res = "Bajo"
        elif r.valoracion_residual == 5:
            expected_cat_res = "Medio"
        elif r.valoracion_residual in (6, 7):
            expected_cat_res = "Alto"
        else:
            expected_cat_res = "Extremo"
        assert r.categoria_residual == expected_cat_res
        
        # Check SST
        if "sst" in r.descripcion.lower() or "salud" in r.descripcion.lower() or "accidente" in r.descripcion.lower():
            assert r.tipo in ("Operacional / SST", "Laboral"), f"SST must not be economic, got {r.tipo}"
            
        # Check realistic periodicity
        assert r.monitoreo_periodicidad.lower() != "diario", "Periodicidad no debe ser diaria"
    
    print("Arithmetic & Quality Criteria Passed 100%!")
    
    # 3. Observaciones del Estudio Previo
    print("Observaciones detectadas:")
    for obs in result.observaciones_estudio_previo:
        print(f"  • {obs}")
    assert len(result.observaciones_estudio_previo) > 0, "Expected observations on template gaps/typos"
    
    # 4. DOCX Generation Test
    test_docx_path = Path("scratch/test_matriz_riesgos_output.docx")
    risk_agent.generate_docx(result, test_docx_path)
    assert test_docx_path.exists()
    assert test_docx_path.stat().st_size > 10000
    print(f"DOCX Generated Successfully ({test_docx_path.stat().st_size} bytes)")

def test_risk_matrix_api_endpoints(auth_client):
    print("\n--- 2. Testing FastAPI Endpoints ---")
    client = auth_client
    
    payload = {
        "objeto": "PRESTACIÓN DE SERVICIOS PARA EL APOYO A LA GESTIÓN DE LAS ACTIVIDADES COMPLEMENTARIAS DEL PGIRS DEL MUNICIPIO DE YOLOMBÓ",
        "tipologia": "PRESTACION_SERVICIOS",
        "contratista_nombre": "ANYIE OCHOA URIBE",
        "valor_estimado": 4800000.0,
        "plazo_texto": "2 meses",
        "lugar_ejecucion": "Municipio de Yolombó, Antioquia",
        "exige_polizas": False,
        "estudio_previo_texto": "Estudio previo de servicios para apoyo al PGIRS Yolombó..."
    }
    
    # Endpoint 1: generate-risk-matrix
    res = client.post("/api/agents/generate-risk-matrix", json=payload)
    assert res.status_code == 200, f"Error {res.status_code}: {res.text}"
    data = res.json()
    assert "riesgos" in data
    assert len(data["riesgos"]) >= 6
    print(f"POST /api/agents/generate-risk-matrix returned {len(data['riesgos'])} risks.")
    
    # Endpoint 2: generate-risk-matrix-docx
    res_docx = client.post("/api/agents/generate-risk-matrix-docx", json=data)
    assert res_docx.status_code == 200, f"Error {res_docx.status_code}: {res_docx.text}"
    assert "wordprocessingml" in res_docx.headers.get("content-type", "")
    assert len(res_docx.content) > 10000
    print(f"POST /api/agents/generate-risk-matrix-docx returned binary docx ({len(res_docx.content)} bytes).")

if __name__ == "__main__":
    test_risk_matrix_generation_unit()
    test_risk_matrix_api_endpoints()
    print("\nALL TESTS PASSED SUCCESSFULLY! [OK]")

