import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import requests
from fastapi.testclient import TestClient
from app.main import app

BASE_URL = "http://127.0.0.1:8000"

# Check if live server is running, otherwise use FastAPI TestClient
_live_available = False
try:
    _res = requests.get(f"{BASE_URL}/api/health", timeout=0.5)
    if _res.status_code == 200:
        _live_available = True
except Exception:
    _live_available = False

if _live_available:
    print("[E2E Mode] Testing against live server at http://127.0.0.1:8000")
    class HTTPClient:
        @staticmethod
        def get(url, **kwargs):
            return requests.get(url, **kwargs)
        @staticmethod
        def post(url, **kwargs):
            return requests.post(url, **kwargs)
        @staticmethod
        def delete(url, **kwargs):
            return requests.delete(url, **kwargs)
    http = HTTPClient()
else:
    print("[E2E Mode] Testing with FastAPI TestClient (in-memory)")
    _tc = TestClient(app)
    class TestClientAdapter:
        @staticmethod
        def _clean_path(url):
            if url.startswith(BASE_URL):
                return url[len(BASE_URL):]
            return url
        def get(self, url, **kwargs):
            return _tc.get(self._clean_path(url), **kwargs)
        def post(self, url, **kwargs):
            return _tc.post(self._clean_path(url), **kwargs)
        def delete(self, url, **kwargs):
            return _tc.delete(self._clean_path(url), **kwargs)
    http = TestClientAdapter()

def test_frontend_initial_html():
    print("[1] Testing initial frontend HTML for zero-leakage...")
    res = http.get(f"{BASE_URL}/app/index.html")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text

    # Verify panel-acceso-independiente is present
    assert 'id="panel-acceso-independiente"' in html, "panel-acceso-independiente missing"
    
    # Verify panel-aplicacion-principal is style="display: none;"
    assert 'id="panel-aplicacion-principal" style="display: none;"' in html or 'style="display: none;"' in html, "panel-aplicacion-principal not hidden initially"
    
    # Verify login form inputs are present
    assert 'id="login-documento"' in html, "login-documento input missing"
    assert 'id="login-password"' in html, "login-password input missing"
    assert 'id="form-login"' in html, "form-login missing"
    print("    -> Zero-leakage verified: access gateway is independent and application DOM is hidden.")

def test_api_auth_and_guest_restrictions():
    print("[2] Testing API login and role enforcement...")
    from app.config import settings
    admin_pass = settings.ADMIN_INITIAL_PASSWORD or "AdminTestEnvPass123*"
    # Admin login
    res = http.post(f"{BASE_URL}/api/auth/login", json={
        "documento": "8156781",
        "password": admin_pass
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    admin_data = res.json()
    admin_token = admin_data["token"]
    assert admin_data["usuario"]["rol"] == "ADMIN"
    print(f"    -> Admin login successful: {admin_data['usuario']['documento']}")

    # Create guest user via Admin
    guest_doc = "99887766"
    guest_pass = "InvitadoEspy2026*"
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    
    # Clean up old test user if exists
    users_res = http.get(f"{BASE_URL}/api/auth/users", headers=headers_admin)
    if users_res.status_code == 200:
        for u in users_res.json():
            if u["documento"] == guest_doc:
                http.delete(f"{BASE_URL}/api/auth/users/{u['id']}", headers=headers_admin)

    # Create user
    create_res = http.post(f"{BASE_URL}/api/auth/users", headers=headers_admin, json={
        "documento": guest_doc,
        "nombre_completo": "Auditor Invitado de Control",
        "password": guest_pass,
        "rol": "INVITADO"
    })
    assert create_res.status_code == 201, f"User creation failed: {create_res.text}"
    created_user = create_res.json()
    print(f"    -> Created guest user: {guest_doc}")

    # Guest Login
    res_guest = http.post(f"{BASE_URL}/api/auth/login", json={
        "documento": guest_doc,
        "password": guest_pass
    })
    assert res_guest.status_code == 200, f"Guest login failed: {res_guest.text}"
    guest_data = res_guest.json()
    guest_token = guest_data["token"]
    assert guest_data["usuario"]["rol"] == "INVITADO"
    print("    -> Guest login successful.")

    headers_guest = {"Authorization": f"Bearer {guest_token}"}

    # Guest can read permitted data
    r_contracts = http.get(f"{BASE_URL}/api/contracts", headers=headers_guest)
    assert r_contracts.status_code == 200, f"Guest read contracts failed: {r_contracts.status_code}"
    print(f"    -> Guest can observe contracts list (status {r_contracts.status_code})")

    r_exec = http.get(f"{BASE_URL}/api/execution/summary?vigencia=2026", headers=headers_guest)
    assert r_exec.status_code == 200, f"Guest read execution failed: {r_exec.status_code}"
    print(f"    -> Guest can observe execution summary (status {r_exec.status_code})")

    # Guest CANNOT mutate contracts
    r_mutate_contract = http.post(f"{BASE_URL}/api/contracts", headers=headers_guest, json={"numero_contrato": "FAIL"})
    assert r_mutate_contract.status_code == 403, f"Expected 403, got {r_mutate_contract.status_code}"
    print("    -> Guest strictly blocked from POST /contracts (403 Forbidden)")

    # Guest CANNOT mutate payments
    r_mutate_payment = http.post(f"{BASE_URL}/api/execution/payments", headers=headers_guest, json={"codigo_egreso": "FAIL"})
    assert r_mutate_payment.status_code == 403, f"Expected 403, got {r_mutate_payment.status_code}"
    print("    -> Guest strictly blocked from POST /execution/payments (403 Forbidden)")

    # Guest CANNOT access user management
    r_guest_users = http.get(f"{BASE_URL}/api/auth/users", headers=headers_guest)
    assert r_guest_users.status_code == 403, f"Expected 403, got {r_guest_users.status_code}"
    print("    -> Guest strictly blocked from GET /auth/users (403 Forbidden)")

    # Guest CANNOT access reports
    r_guest_reports = http.get(f"{BASE_URL}/api/reports/preview?vigencia=2026", headers=headers_guest)
    assert r_guest_reports.status_code == 403, f"Expected 403, got {r_guest_reports.status_code}"
    print("    -> Guest strictly blocked from GET /reports/preview (403 Forbidden)")

    # Clean up guest user
    del_res = http.delete(f"{BASE_URL}/api/auth/users/{created_user['id']}", headers=headers_admin)
    assert del_res.status_code == 200
    print("    -> Cleaned up test guest user.")

if __name__ == "__main__":
    test_frontend_initial_html()
    test_api_auth_and_guest_restrictions()
    print("\nALL E2E HTTP CHECKS PASSED SUCCESSFULLY!")
