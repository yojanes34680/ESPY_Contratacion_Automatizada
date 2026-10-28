"""
Pruebas de validación del Motor UNSPSC Nuevo (Prompt 11):
1. Respaldo sin Gemini devuelve 'sugerencia_sin_validar' y confianza 'media' o 'baja'.
2. Descarte de código fuera de candidatos.
3. El endpoint /api/unspsc/contracts/{id}/save solo guarda en feedback códigos con estado 'aprobado' y cita verificada (no sugerencias).
4. Endpoints sin token devuelven 401.
5. Usuario con rol INVITADO no puede guardar clasificación (403).
6. Con UNSPSC_MOTOR='nuevo', la respuesta incluye 'objeto_detectado' y 'fuente_cita'.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.models.user import Usuario, RolUsuario
from app.models.contract import Contrato
from app.models.contractor import Contratista
from app.models.unspsc import UnspscHistoricalFeedback
from app.schemas.unspsc import UnspscAnalysisInput, UnspscAnalysisResult, UnspscCodeItem
from app.services.agents.unspsc.selector import unspsc_selector_agent, UnspscSelectorAgent
from app.services.agents.unspsc.schemas import DocumentItem
from app.utils.security import create_access_token, get_password_hash

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(scope="module")
def setup_data():
    with SessionLocal() as db:
        # Contratista
        c = db.query(Contratista).first()
        if not c:
            c = Contratista(
                tipo_persona="NATURAL",
                tipo_documento="CC",
                numero_documento="71222333",
                nombre_o_razon_social="Contratista Prueba UNSPSC"
            )
            db.add(c)
            db.commit()
            db.refresh(c)

        # Contrato de prueba
        contract = db.query(Contrato).filter(Contrato.numero_contrato == "TEST-UNSPSC-001").first()
        if not contract:
            contract = Contrato(
                numero_contrato="TEST-UNSPSC-001",
                vigencia=2026,
                contratista_id=c.id,
                objeto="SUMINISTRO DE REACTIVOS Y QUÍMICOS PARA PLANTA DE TRATAMIENTO DE AGUA",
                valor_total=15000000.0
            )
            db.add(contract)
            db.commit()
            db.refresh(contract)
        contract_id = contract.id

        # Usuarios
        admin = db.query(Usuario).filter(Usuario.documento == "8156781").first()
        if not admin:
            admin = Usuario(
                documento="8156781",
                nombre_completo="Admin UNSPSC",
                password_hash=get_password_hash("AdminPass123*"),
                rol=RolUsuario.ADMIN,
                is_active=True
            )
            db.add(admin)

        editor = db.query(Usuario).filter(Usuario.documento == "88880001").first()
        if not editor:
            editor = Usuario(
                documento="88880001",
                nombre_completo="Editor UNSPSC",
                password_hash=get_password_hash("EditorPass123*"),
                rol=RolUsuario.EDITOR,
                is_active=True
            )
            db.add(editor)

        invitado = db.query(Usuario).filter(Usuario.documento == "88880002").first()
        if not invitado:
            invitado = Usuario(
                documento="88880002",
                nombre_completo="Invitado UNSPSC",
                password_hash=get_password_hash("InvitadoPass123*"),
                rol=RolUsuario.INVITADO,
                is_active=True
            )
            db.add(invitado)

        db.commit()

    return {
        "admin_token": create_access_token({"sub": "8156781", "documento": "8156781", "rol": "ADMIN"}),
        "editor_token": create_access_token({"sub": "88880001", "documento": "88880001", "rol": "EDITOR"}),
        "invitado_token": create_access_token({"sub": "88880002", "documento": "88880002", "rol": "INVITADO"}),
        "contract_id": contract_id
    }

def test_fallback_returns_sugerencia_sin_validar():
    """El respaldo determinístico sin Gemini debe retornar siempre 'sugerencia_sin_validar' y nunca 'aprobado'."""
    item = DocumentItem(
        descripcion="hipoclorito de sodio para potabilizacion",
        naturaleza="bien",
        cita_literal="suministro de hipoclorito de sodio al 13%"
    )
    cands = [
        {"codigo": "47101500", "jerarquia": "Tratamiento de agua | Segmento: Limpieza", "score": 10.5},
        {"codigo": "12163800", "jerarquia": "Químicos | Segmento: Químicos", "score": 8.2}
    ]
    doc_text = "Se requiere el suministro de hipoclorito de sodio al 13% en canecas."
    
    agent = UnspscSelectorAgent()
    results = agent._select_codes_deterministic_fallback(item, cands, doc_text)
    
    assert len(results) > 0
    for r in results:
        assert r.estado == "sugerencia_sin_validar"
        assert r.confianza in ("media", "baja")
        assert r.estado != "aprobado"

def test_discard_codes_outside_candidates():
    """Gemini no puede introducir códigos inexistentes en la lista de candidatos enviados."""
    item = DocumentItem(
        descripcion="taladro percutor industrial",
        naturaleza="bien",
        cita_literal="mantenimiento de taladro percutor"
    )
    cands = [
        {"codigo": "73152108", "jerarquia": "Mantenimiento de herramientas", "score": 9.0}
    ]
    doc_text = "mantenimiento de taladro percutor para campo"
    
    # Simular respuesta de Gemini devolviendo un código inventado o no listado
    mock_response = MagicMock()
    mock_response.text = '{"seleccionados": [{"codigo": "99999999", "justificacion": "inventado", "confianza": "alta"}]}'
    
    with patch("google.genai.Client") as mock_client_cls:
        mock_instance = MagicMock()
        mock_instance.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_instance
        
        agent = UnspscSelectorAgent()
        results = agent.select_codes_for_item_gemini(
            item=item,
            objeto="Mantenimiento",
            candidates=cands,
            document_text=doc_text,
            override_api_key="fake-key"
        )
        # El código inventado '99999999' debe ser descartado, recurriendo al fallback determinístico seguro
        for r in results:
            assert r.codigo_unspsc != "99999999"

def test_endpoint_no_token_returns_401(client):
    """Llamar a /api/unspsc/status sin token devuelve 401."""
    res = client.get("/api/unspsc/status")
    assert res.status_code == 401

def test_invitado_cannot_save_unspsc(client, setup_data):
    """Usuario INVITADO no tiene permisos para guardar códigos UNSPSC (403)."""
    headers = {"Authorization": f"Bearer {setup_data['invitado_token']}"}
    payload = {
        "resumen_analisis": "Resumen prueba",
        "actividades_propuesta_extraidas": ["act1"],
        "codigos_seleccionados": [
            {
                "codigo_unspsc": "47101500",
                "descripcion_codigo": "Tratamiento de agua",
                "justificacion_eleccion": "Justificación",
                "segmento": "47",
                "familia": "4710",
                "clase": "471015",
                "confianza": "alta",
                "cita_verificada": True,
                "estado": "aprobado"
            }
        ],
        "total_codigos": 1
    }
    res = client.post(f"/api/unspsc/contracts/{setup_data['contract_id']}/save", json=payload, headers=headers)
    assert res.status_code == 403

def test_save_does_not_save_unreviewed_suggestions(client, setup_data):
    """Solo se guardan en el historial feedback los códigos con estado 'aprobado' y cita verificada."""
    headers = {"Authorization": f"Bearer {setup_data['editor_token']}"}
    contract_id = setup_data['contract_id']
    
    payload = {
        "resumen_analisis": "Resumen prueba",
        "actividades_propuesta_extraidas": ["act1"],
        "codigos_seleccionados": [
            {
                "codigo_unspsc": "11111111",
                "descripcion_codigo": "Sugerencia no validada",
                "justificacion_eleccion": "Sugerencia",
                "segmento": "11",
                "familia": "1111",
                "clase": "111111",
                "confianza": "media",
                "cita_verificada": True,
                "estado": "sugerencia_sin_validar"
            },
            {
                "codigo_unspsc": "22222222",
                "descripcion_codigo": "Aprobado sin cita",
                "justificacion_eleccion": "Aprobado",
                "segmento": "22",
                "familia": "2222",
                "clase": "222222",
                "confianza": "alta",
                "cita_verificada": False,
                "estado": "aprobado"
            },
            {
                "codigo_unspsc": "47101500",
                "descripcion_codigo": "Tratamiento de agua purificada",
                "justificacion_eleccion": 'Adecuado. Cita: "hipoclorito de sodio al 13%"',
                "segmento": "47",
                "familia": "4710",
                "clase": "471015",
                "confianza": "alta",
                "cita_verificada": True,
                "estado": "aprobado"
            }
        ],
        "total_codigos": 3
    }
    res = client.post(f"/api/unspsc/contracts/{contract_id}/save", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    # Solo 1 código cumplía estado='aprobado' Y cita_verificada=True
    assert data["feedback_aprobados_guardados"] == 1

def test_motor_nuevo_includes_objeto_detectado_and_fuente_cita():
    """El motor nuevo debe generar 'objeto_detectado' y 'fuente_cita'."""
    inp = UnspscAnalysisInput(
        objeto="SUMINISTRO DE PAPELERÍA Y ÚTILES DE ESCRITORIO",
        estudio_previo="Adquisición de papelería e insumos institucionales...",
        propuesta_economica="Resmas de papel bond carta, bolígrafos y carpetas."
    )
    agent = UnspscSelectorAgent()
    res = agent.analyze_contract_unspsc(inp)
    
    assert res.objeto_detectado is not None
    assert len(res.objeto_detectado) > 5
    assert len(res.codigos_seleccionados) > 0
    for c in res.codigos_seleccionados:
        assert c.fuente_cita in ("propuesta", "estudio_previo")
