"""Comprehensive automated tests for authentication and role-based access control."""
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.database import SessionLocal
from app.routers.auth import seed_master_admin
from app.models.user import Usuario

def test_auth_system():
    # 1. Seed master admin
    with SessionLocal() as db:
        seed_master_admin(db)

    client = TestClient(app)

    admin_pass = settings.ADMIN_INITIAL_PASSWORD or "AdminTestEnvPass123*"

    # 2. Login as Master Admin
    res = client.post("/api/auth/login", json={
        "documento": "8156781",
        "password": admin_pass
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    admin_data = res.json()
    assert admin_data["success"] is True
    assert admin_data["usuario"]["documento"] == "8156781"
    assert admin_data["usuario"]["rol"] == "ADMIN"
    assert "debe_cambiar_password" in admin_data
    admin_token = admin_data["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[OK] Master Admin login successful")

    # 3. Bad password rejected
    bad_res = client.post("/api/auth/login", json={
        "documento": "8156781",
        "password": "WrongPassword123"
    })
    assert bad_res.status_code == 401, f"Expected 401, got: {bad_res.status_code}"
    print("[OK] Invalid credentials rejected correctly (401)")

    # 4. /api/auth/me with Admin Token
    me_res = client.get("/api/auth/me", headers=admin_headers)
    assert me_res.status_code == 200, f"Me endpoint failed: {me_res.text}"
    assert me_res.json()["documento"] == "8156781"
    assert me_res.json()["rol"] == "ADMIN"
    print("[OK] /api/auth/me returns valid admin profile")

    # 5. Admin creates guest user
    GUEST_DOC = "1098765432"
    # Ensure guest doesn't already exist from previous runs
    with SessionLocal() as db:
        existing = db.query(Usuario).filter(Usuario.documento == GUEST_DOC).first()
        if existing:
            db.delete(existing)
            db.commit()

    create_guest_res = client.post("/api/auth/users", headers=admin_headers, json={
        "documento": GUEST_DOC,
        "nombre_completo": "Auditor Invitado ESPY",
        "password": "GuestSecret123*",
        "rol": "INVITADO"
    })
    assert create_guest_res.status_code == 201, f"Create user failed: {create_guest_res.text}"
    guest_user_data = create_guest_res.json()
    guest_user_id = guest_user_data["id"]
    assert guest_user_data["documento"] == GUEST_DOC
    assert guest_user_data["rol"] == "INVITADO"
    print("[OK] Admin successfully created guest user")

    # 6. Guest user logs in
    guest_login_res = client.post("/api/auth/login", json={
        "documento": GUEST_DOC,
        "password": "GuestSecret123*"
    })
    assert guest_login_res.status_code == 200
    guest_token = guest_login_res.json()["token"]
    guest_headers = {"Authorization": f"Bearer {guest_token}"}
    assert guest_login_res.json()["usuario"]["rol"] == "INVITADO"
    print("[OK] Guest user logged in successfully with INVITADO role")

    # 7. Guest user tries to access admin-only endpoint
    guest_forbidden = client.get("/api/auth/users", headers=guest_headers)
    assert guest_forbidden.status_code == 403, f"Expected 403, got: {guest_forbidden.status_code}"
    print("[OK] Guest forbidden (403) from accessing admin endpoints")

    guest_forbidden_create = client.post("/api/auth/users", headers=guest_headers, json={
        "documento": "99999999",
        "nombre_completo": "Hacker",
        "password": "pass",
        "rol": "ADMIN"
    })
    assert guest_forbidden_create.status_code == 403
    print("[OK] Guest forbidden (403) from creating users")

    # 7b. Guest user blocked from mutating contracts and payments (Middleware test)
    guest_payment_blocked = client.post("/api/execution/payments", headers=guest_headers, json={
        "codigo_contrato": "CPS-001-2026",
        "codigo_egreso": "CE-TEST-999",
        "total_orden": 1000000,
        "total_pagar": 1000000
    })
    assert guest_payment_blocked.status_code == 403
    assert "solo lectura" in guest_payment_blocked.json()["detail"].lower()
    print("[OK] Guest strictly blocked (403) from creating/mutating payments via middleware")

    guest_contract_blocked = client.post("/api/contracts", headers=guest_headers, json={
        "numero_contrato": "CPS-999-2026",
        "tipologia": "PRESTACION_SERVICIOS",
        "objeto": "Intento no autorizado",
        "valor_total": 1000000,
        "plazo_ejecucion": 1,
        "unidad_plazo": "MESES",
        "contratista_id": 1,
        "fecha_suscripcion": "2026-01-01"
    })
    assert guest_contract_blocked.status_code == 403
    assert "solo lectura" in guest_contract_blocked.json()["detail"].lower()
    print("[OK] Guest strictly blocked (403) from creating/mutating contracts via middleware")

    # 7c. Guest user blocked from accessing reports endpoints
    guest_reports_blocked = client.get("/api/reports/preview?vigencia=2026", headers=guest_headers)
    assert guest_reports_blocked.status_code == 403
    assert "reportes" in guest_reports_blocked.json()["detail"].lower()
    print("[OK] Guest strictly blocked (403) from accessing reports endpoints via middleware")

    # 8. Master admin protected against deletion
    master_user_id = admin_data["usuario"]["id"]
    del_master = client.delete(f"/api/auth/users/{master_user_id}", headers=admin_headers)
    assert del_master.status_code == 400
    print("[OK] Master admin protected from deletion")

    # 9. Admin deletes guest user
    del_guest = client.delete(f"/api/auth/users/{guest_user_id}", headers=admin_headers)
    assert del_guest.status_code == 200
    print("[OK] Admin successfully deleted guest user")

    # 10. Test change-password endpoint
    chg_res = client.post("/api/auth/change-password", headers=admin_headers, json={
        "password_actual": admin_pass,
        "password_nueva": "NuevaClaveAdmin2026*"
    })
    assert chg_res.status_code == 200, f"Change password failed: {chg_res.text}"
    assert chg_res.json()["debe_cambiar_password"] is False
    print("[OK] POST /api/auth/change-password updated password and cleared flag")

    # Revert password back so subsequent runs are predictable
    client.post("/api/auth/change-password", headers=admin_headers, json={
        "password_actual": "NuevaClaveAdmin2026*",
        "password_nueva": admin_pass
    })

    print("\nALL AUTH AND ROLE TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_auth_system()
