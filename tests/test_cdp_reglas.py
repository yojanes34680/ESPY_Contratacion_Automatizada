"""Tests para las reglas y endpoints de saneamiento del texto de CDP (Certificado de Disponibilidad Presupuestal).
Valida:
1. El endpoint GET /api/cdp/marcas-corte requiere usuario autenticado y devuelve exactamente
   las mismas marcas que utiliza cdp_cleaner.py.
2. Al guardar o actualizar un contrato con texto de CDP que incluya clasificadores CCPET,
   el servidor higieniza y guarda la versión limpia en la base de datos.
"""
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.contract import Contrato, TipologiaContrato, ModalidadSeleccion, EstadoContrato
from app.models.contractor import Contratista, TipoPersona
from app.models.user import Usuario, RolUsuario
from app.routers.auth import create_access_token
from app.utils.cdp_cleaner import get_marcas_de_corte_cdp, limpiar_texto_cdp

# Base de datos en memoria para pruebas aisladas
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Crear usuario de prueba
        test_user = Usuario(
            nombre_completo="Usuario Auditor CDP",
            documento="999888777",
            password_hash="test_hash",
            rol=RolUsuario.ADMIN,
            is_active=True
        )

        db.add(test_user)

        # Crear contratista de prueba
        test_contractor = Contratista(
            nombre_o_razon_social="OPERADORA DE PRUEBAS S.A.S.",
            tipo_persona=TipoPersona.JURIDICA,
            numero_documento="901234567-8",
            departamento="Antioquia",
            municipio="Yolombó"
        )
        db.add(test_contractor)
        db.commit()
    finally:
        db.close()
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def auth_token():
    return create_access_token({"documento": "999888777", "rol": "ADMIN"})


def test_endpoint_cdp_marcas_corte_requiere_auth(client):
    """Verifica que el endpoint /api/cdp/marcas-corte rechaza peticiones sin autenticación."""
    resp = client.get("/api/cdp/marcas-corte")
    assert resp.status_code in (401, 403), f"Esperado 401/403 sin token, recibido {resp.status_code}"

def test_endpoint_cdp_marcas_corte_devuelve_mismas_marcas_que_cdp_cleaner(client, auth_token):
    """Verifica que el endpoint devuelve las mismas marcas de corte que tiene cdp_cleaner.py."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    resp = client.get("/api/cdp/marcas-corte", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Comparar con cdp_cleaner
    marcas_oficiales = get_marcas_de_corte_cdp()
    assert data == marcas_oficiales
    assert "\\bCCPET\\b" in data
    assert any("clasificadores" in m.lower() for m in data)

def test_crear_contrato_con_ccpet_guarda_cdp_limpio(client, auth_token):
    """Verifica que al crear un contrato con texto de CDP largo y clasificadores CCPET, se guarda limpio."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    texto_con_ccpet = (
        "00150, expedido el 10 de octubre de 2026, por valor de $5.000.000, con cargo al "
        "Rubro Presupuestal 2.1.2.02.02.008 – SERVICIOS PRESTADOS A LAS EMPRESAS, "
        "y respaldado en los clasificadores presupuestales CCPET: CCPET02 Clasificador Valor Clasificador"
    )

    payload = {
        "numero_contrato": "CPS-099-2026",
        "vigencia": 2026,
        "tipologia": "PRESTACION_SERVICIOS",
        "modalidad": "CONTRATACION_DIRECTA",
        "contratista_id": 1,
        "objeto": "PRESTACIÓN DE SERVICIOS TÉCNICOS PARA PRUEBAS DE AUDITORÍA",
        "valor_total": 5000000.0,
        "plazo_ejecucion": 1,
        "unidad_plazo": "MESES",
        "metadatos_agente": {
            "cdp_numero": "00150",
            "cdp_fecha": "2026-10-10",
            "cdp_valor": 5000000.0,
            "cdp_rubro": "2.1.2.02.02.008",
            "cdp_rubro_nombre": "SERVICIOS PRESTADOS A LAS EMPRESAS",
            "cdp_texto_completo": texto_con_ccpet
        }
    }

    resp = client.post("/api/contracts", json=payload, headers=headers)
    assert resp.status_code == 201, f"Error al crear contrato: {resp.text}"
    created = resp.json()

    meta = created.get("metadatos_agente") or {}
    cdp_saved = meta.get("cdp_texto_completo")
    assert cdp_saved is not None
    assert "CCPET" not in cdp_saved
    assert "clasificadores" not in cdp_saved.lower()
    assert "00150, expedido el 10 de octubre de 2026, por valor de $5.000.000, con cargo al Rubro Presupuestal 2.1.2.02.02.008 – SERVICIOS PRESTADOS A LAS EMPRESAS." == cdp_saved

def test_actualizar_contrato_con_ccpet_guarda_cdp_limpio(client, auth_token):
    """Verifica que al actualizar metadatos_agente de un contrato existente, el texto del CDP se sanea."""
    headers = {"Authorization": f"Bearer {auth_token}"}

    update_payload = {
        "metadatos_agente": {
            "cdp_texto_completo": "00200, expedido el 20 de octubre de 2026, con cargo al Rubro 2.1.2.01.01 – INFORMATICA CCPET01 Clasificador Valor Clasificador"
        }
    }

    resp = client.put("/api/contracts/1", json=update_payload, headers=headers)
    assert resp.status_code == 200, f"Error actualizando contrato: {resp.text}"
    updated = resp.json()

    meta = updated.get("metadatos_agente") or {}
    cdp_saved = meta.get("cdp_texto_completo")
    assert "CCPET" not in cdp_saved
    assert "00200, expedido el 20 de octubre de 2026, con cargo al Rubro 2.1.2.01.01 – INFORMATICA." == cdp_saved
