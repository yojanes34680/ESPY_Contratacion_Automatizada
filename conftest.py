"""Configuración global de fixtures y aislamiento para pruebas con pytest.
Garantiza que ninguna prueba toque la base de datos de producción (espy_contratacion.db)
ni la matriz de Excel real, ni realice llamadas externas accidentales a la API de Gemini.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# 1. Configurar variables de entorno críticas ANTES de importar app
TEST_DIR = Path(tempfile.mkdtemp(prefix="espy_test_session_"))
TEST_DB_PATH = TEST_DIR / "test_isolated.db"
TEST_STORAGE_DIR = TEST_DIR / "storage"
TEST_EXCEL_PATH = TEST_DIR / "master_excel" / "Matriz_Contratacion_Maestra.xlsx"

os.environ["ESPY_TESTING"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["STORAGE_DIR"] = str(TEST_STORAGE_DIR)
os.environ["MASTER_EXCEL_PATH"] = str(TEST_EXCEL_PATH)
os.environ["GEMINI_API_KEY"] = ""
os.environ["SECRET_KEY"] = "espy_test_secret_key_48_characters_long_isolated_safe"
os.environ["ADMIN_INITIAL_PASSWORD"] = "AdminTestEnvPass123*"
os.environ["GUEST_INITIAL_PASSWORD"] = "GuestTestEnvPass123*"

# 2. Agregar backend/ y raíz al sys.path
REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Copiar plantilla Excel de prueba si existe
orig_excel = BACKEND_DIR / "master_excel" / "Matriz_Contratacion_Maestra.xlsx"
TEST_EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)
if orig_excel.exists():
    shutil.copy2(orig_excel, TEST_EXCEL_PATH)

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models.user import Usuario, RolUsuario
from app.utils.security import hash_password
from app.services.gemini_client import gemini_service
from app.main import app

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Inicializa el esquema de tablas en la base SQLite temporal."""
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)
    try:
        from app.scripts.seed_consolidated_contracts import seed_contracts
        seed_contracts()
    except Exception as e:
        pass
    yield
    # Limpieza al finalizar la sesión de pruebas
    Base.metadata.drop_all(bind=engine)
    try:
        shutil.rmtree(TEST_DIR, ignore_errors=True)
    except Exception:
        pass

@pytest.fixture(autouse=True)
def gemini_falso(request, monkeypatch):
    """Reemplaza con monkeypatch gemini_service._get_client para que devuelva None,
    forzando siempre el uso de generadores deterministas locales en pruebas,
    salvo que la prueba pertenezca a test_regression_suite.py.
    """
    if any(k in request.node.nodeid for k in ["test_regression_suite", "test_apu"]):
        return
    monkeypatch.setattr(gemini_service, "_get_client", lambda *args, **kwargs: None)

@pytest.fixture
def client():
    """TestClient estándar para interactuar con la aplicación FastAPI."""
    return TestClient(app)

@pytest.fixture
def admin_token(client):
    """Crea un usuario ADMIN de prueba directamente en la base temporal e inicia sesión
    por /api/auth/login para obtener un token JWT válido.
    """
    db = SessionLocal()
    try:
        doc = "1000000001"
        pwd = "AdminTestPassword123*"
        existing = db.query(Usuario).filter(Usuario.documento == doc).first()
        if not existing:
            u = Usuario(
                nombre_completo="Administrador de Pruebas",
                documento=doc,
                password_hash=hash_password(pwd),
                rol=RolUsuario.ADMIN,
                is_active=True
            )
            db.add(u)
            db.commit()
    finally:
        db.close()

    # Login mediante endpoint oficial
    resp = client.post("/api/auth/login", json={"documento": doc, "password": pwd})
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    
    # Fallback generando token firmado directamente con la SECRET_KEY de pruebas
    from app.utils.security import create_access_token
    return create_access_token({"documento": doc, "rol": "ADMIN"})

@pytest.fixture
def auth_client(client, admin_token):
    """TestClient configurado con el encabezado de autenticación Authorization por defecto."""
    client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return client
