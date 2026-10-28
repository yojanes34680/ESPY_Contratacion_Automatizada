"""
Test file for Prompt 3: Authentication and RBAC across all endpoints.
Verifies:
1. No token -> 401 on /api/contracts
2. Deactivated user with valid token -> 403
3. INVITADO cannot perform POST /api/contracts (403)
4. EDITOR cannot perform DELETE /api/contracts/{id} (403)
5. ADMIN can perform DELETE /api/contracts/{id} (succeeds)
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.routers.auth import seed_master_admin
from app.models.user import Usuario, RolUsuario
from app.models.contract import Contrato
from app.utils.security import create_access_token, get_password_hash

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(scope="module")
def setup_users_and_contract():
    with SessionLocal() as db:
        seed_master_admin(db)
        
        # Admin user
        admin = db.query(Usuario).filter(Usuario.documento == "8156781").first()
        
        # Test Editor user
        editor = db.query(Usuario).filter(Usuario.documento == "99990001").first()
        if not editor:
            editor = Usuario(
                documento="99990001",
                nombre_completo="Test Editor",
                password_hash=get_password_hash("EditorPass123*"),
                rol=RolUsuario.EDITOR,
                is_active=True
            )
            db.add(editor)
        else:
            editor.is_active = True
            editor.rol = RolUsuario.EDITOR

        # Test Invitado user
        invitado = db.query(Usuario).filter(Usuario.documento == "99990002").first()
        if not invitado:
            invitado = Usuario(
                documento="99990002",
                nombre_completo="Test Invitado",
                password_hash=get_password_hash("InvitadoPass123*"),
                rol=RolUsuario.INVITADO,
                is_active=True
            )
            db.add(invitado)
        else:
            invitado.is_active = True
            invitado.rol = RolUsuario.INVITADO

        # Test Deactivated user
        desactivado = db.query(Usuario).filter(Usuario.documento == "99990003").first()
        if not desactivado:
            desactivado = Usuario(
                documento="99990003",
                nombre_completo="Test Inactivo",
                password_hash=get_password_hash("InactivoPass123*"),
                rol=RolUsuario.EDITOR,
                is_active=False
            )
            db.add(desactivado)
        else:
            desactivado.is_active = False

        from app.models.contractor import Contratista
        c = db.query(Contratista).first()
        if not c:
            c = Contratista(
                tipo_persona="NATURAL",
                tipo_documento="CC",
                numero_documento="111222333",
                nombre_o_razon_social="Contratista Prueba Permisos"
            )
            db.add(c)
            db.commit()
            db.refresh(c)

        # Create temporary test contract to test DELETE
        temp_contract = db.query(Contrato).filter(Contrato.numero_contrato == "TEST-PERM-001").first()
        if not temp_contract:
            temp_contract = Contrato(
                numero_contrato="TEST-PERM-001",
                vigencia=2026,
                contratista_id=c.id,
                objeto="CONTRATO TEMPORAL DE PRUEBA PARA PERMISOS RBAC",
                valor_total=1000000.0
            )
            db.add(temp_contract)
            db.commit()
            db.refresh(temp_contract)
        
        temp_contract_id = temp_contract.id
        db.commit()

    return {
        "admin_token": create_access_token({"sub": "8156781", "documento": "8156781", "rol": "ADMIN"}),
        "editor_token": create_access_token({"sub": "99990001", "documento": "99990001", "rol": "EDITOR"}),
        "invitado_token": create_access_token({"sub": "99990002", "documento": "99990002", "rol": "INVITADO"}),
        "desactivado_token": create_access_token({"sub": "99990003", "documento": "99990003", "rol": "EDITOR"}),
        "test_contract_id": temp_contract_id
    }

def test_no_token_returns_401(client):
    """Sin token de autenticación debe devolver 401 en /api/contracts."""
    res = client.get("/api/contracts")
    assert res.status_code == 401
    detail = res.json().get("detail", "").lower()
    assert "no autorizado" in detail or "no autenticado" in detail or "not authenticated" in detail

def test_deactivated_user_returns_403(client, setup_users_and_contract):
    """Usuario desactivado con token válido debe devolver 403."""
    headers = {"Authorization": f"Bearer {setup_users_and_contract['desactivado_token']}"}
    res = client.get("/api/contracts", headers=headers)
    assert res.status_code == 403
    assert "desactivada" in res.json().get("detail", "").lower()

def test_invitado_cannot_post_contract(client, setup_users_and_contract):
    """Usuario INVITADO no puede hacer POST (debe retornar 403)."""
    headers = {"Authorization": f"Bearer {setup_users_and_contract['invitado_token']}"}
    payload = {
        "numero_contrato": "TEST-INV-001",
        "vigencia": 2026,
        "objeto": "OBJETO DE PRUEBA INVITADO",
        "valor_total": 500000.0
    }
    res = client.post("/api/contracts", json=payload, headers=headers)
    assert res.status_code == 403
    assert "no tiene permisos" in res.json().get("detail", "").lower() or "solo lectura" in res.json().get("detail", "").lower()

def test_editor_cannot_delete_contract(client, setup_users_and_contract):
    """Usuario con rol EDITOR no puede eliminar contratos (debe retornar 403)."""
    headers = {"Authorization": f"Bearer {setup_users_and_contract['editor_token']}"}
    contract_id = setup_users_and_contract["test_contract_id"]
    res = client.delete(f"/api/contracts/{contract_id}", headers=headers)
    assert res.status_code == 403
    assert "administrador" in res.json().get("detail", "").lower()

def test_admin_can_delete_contract(client, setup_users_and_contract):
    """Usuario con rol ADMIN sí puede eliminar contratos."""
    headers = {"Authorization": f"Bearer {setup_users_and_contract['admin_token']}"}
    contract_id = setup_users_and_contract["test_contract_id"]
    res = client.request(
        "DELETE",
        f"/api/contracts/{contract_id}",
        headers=headers,
        json={"motivo": "Anulación de contrato de prueba por administrador"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "success" or data.get("success") is True
