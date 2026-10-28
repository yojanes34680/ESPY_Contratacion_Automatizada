"""FastAPI Application Main Entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import engine, Base
import app.models  # Ensure all models are registered with Base metadata
from app.routers import (
    contractors_router, 
    contracts_router, 
    documents_router,
    agents_router,
    templates_router,
    excel_router,
    additions_router,
    execution_router,
    auth_router,
    reports_router,
    apu_router,
    unspsc_router,
    cdp_router
)

from app.routers.auth import seed_master_admin
from app.database import SessionLocal
from app.scripts.seed_payments import seed_payments_table
from app.utils.logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Validación estricta de SECRET_KEY
    if not settings.SECRET_KEY or len(settings.SECRET_KEY.strip()) < 32:
        error_msg = (
            "\n" + "=" * 80 + "\n"
            "ERROR CRÍTICO DE SEGURIDAD: SECRET_KEY no está configurada o tiene menos de 32 caracteres.\n"
            "Para proteger la generación y validación de tokens de sesión, debe definir una SECRET_KEY segura.\n"
            "Puede generarla ejecutando en su terminal:\n"
            "    python -c \"import secrets; print(secrets.token_urlsafe(48))\"\n"
            "y agregarla a su archivo backend/.env como:\n"
            "    SECRET_KEY=<clave_generada>\n"
            + "=" * 80 + "\n"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info("Inicializando base de datos y esquemas...")
    settings.ensure_directories()
    Base.metadata.create_all(bind=engine)
    # Migración ligera e idempotente para columnas nuevas en contratos y usuarios
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN supervisor_tipo_documento VARCHAR(20) DEFAULT 'CC'"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN supervisor_documento VARCHAR(50)"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN marco_juridico TEXT"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN valor_inicial FLOAT"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN adicion_1 FLOAT DEFAULT 0.0"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN prorroga_1 VARCHAR(100)"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN plazo_texto VARCHAR(50)"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN estudio_mercado JSON"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN codigos_unspsc JSON"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN obligaciones_empresa JSON"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE usuarios ADD COLUMN debe_cambiar_password BOOLEAN DEFAULT 0"))
                conn.commit()
            except Exception:
                pass
            # Migraciones Prompt 4: Anulación y Trazabilidad de Auditoría
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN motivo_anulacion TEXT"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN anulado_por VARCHAR(200)"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratos ADD COLUMN fecha_anulacion DATETIME"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE contratistas ADD COLUMN activo BOOLEAN DEFAULT 1"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE auditoria ADD COLUMN usuario_documento VARCHAR(50)"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text("ALTER TABLE auditoria ADD COLUMN usuario_nombre VARCHAR(200)"))
                conn.commit()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Aviso en verificación de columnas contratos/usuarios/auditoria: {e}")
    try:
        from app.services.agents.unspsc_agent import unspsc_agent
        unspsc_agent._load_catalog_cache()
    except Exception as e:
        logger.warning(f"Aviso al precalentar catálogo UNSPSC: {e}")
    try:
        seed_payments_table()
    except Exception as e:
        logger.warning(f"Aviso en verificación/seed de pagos de ejecución: {e}")
    try:
        with SessionLocal() as db_session:
            seed_master_admin(db_session)
    except Exception as e:
        logger.warning(f"Aviso al sembrar usuario administrador maestro: {e}")
    logger.info("Esquemas de base de datos creados/verificados exitosamente.")
    yield
    logger.info("Finalizando aplicación ESPY Contratación Automatizada...")

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Sistema integral de administración, gestión y automatización de la contratación pública "
        "para una Empresa de Servicios Públicos (ESP), bajo la Ley 142 de 1994 y principios constitucionales."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_static_middleware(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/app"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.middleware("http")
async def guest_mutation_guard_middleware(request, call_next):
    """
    Middleware de seguridad y control de acceso para red local:
    1. Rutas públicas: /, /app/*, /assets/*, /docs, /openapi.json, /api/auth/login, /api/health
    2. Rutas protegidas: /api/* y /storage/* requieren token JWT válido en header (Authorization, X-Auth-Token) o query param (?token=)
    3. Rol INVITADO: Modo solo lectura (bloquea POST/PUT/PATCH/DELETE y /api/reports)
    """
    path = request.url.path

    # Rutas públicas siempre permitidas sin token
    is_public = (
        path == "/"
        or path.startswith("/app")
        or path.startswith("/assets")
        or path in ("/docs", "/openapi.json", "/redoc")
        or path.endswith("/auth/login")
        or path == "/api/health"
    )

    # Permitir peticiones OPTIONS (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)

    # Si es ruta de API o Storage y no es pública, verificar autenticación
    if not is_public and (path.startswith("/api/") or path.startswith("/storage")):
        # Extraer token de headers o query param
        auth_header = request.headers.get("Authorization") or request.headers.get("X-Auth-Token")
        raw_token = None
        if auth_header:
            raw_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else auth_header.strip()
        elif "token" in request.query_params:
            raw_token = request.query_params.get("token", "").strip()

        # Eliminada por completo la excepción del cliente de pruebas en el middleware
        if not raw_token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Acceso no autorizado: Debe iniciar sesión con una cuenta autorizada para acceder desde la red."}
            )

        from app.utils.security import decode_access_token
        payload = decode_access_token(raw_token)
        if not payload or "documento" not in payload:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token inválido o expirado. Inicie sesión nuevamente."}
            )

        rol = str(payload.get("rol", "")).upper()
        if "INVITADO" in rol:
            # Bloquear acceso al módulo de reportes e informes oficiales
            if path.startswith("/api/reports"):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Acceso denegado: El Centro de Reportes e Informes Contractuales es de uso exclusivo para Administradores."
                    }
                )
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Acceso denegado: El usuario con rol Invitado se encuentra en modo de solo lectura y no tiene permisos para crear, editar, diligenciar, modificar o eliminar información en el sistema."
                    }
                )

    return await call_next(request)

from app.routers.auth import get_current_user

# Registrar routers principales (con get_current_user obligatorio, excepto auth_router cuyo login es público)
app.include_router(contractors_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(contracts_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(documents_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(agents_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(templates_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(excel_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(additions_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(execution_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(auth_router, prefix="/api")
app.include_router(reports_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(apu_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(unspsc_router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(cdp_router, prefix="/api", dependencies=[Depends(get_current_user)])



from fastapi.responses import JSONResponse, RedirectResponse

# Montar storage para archivos estáticos
if settings.STORAGE_DIR.exists():
    app.mount("/storage", StaticFiles(directory=str(settings.STORAGE_DIR)), name="storage")

# Montar frontend si la carpeta existe
frontend_path = settings.WORKSPACE_ROOT / "frontend"
if frontend_path.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    assets_path = frontend_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

@app.get("/", tags=["General"])
def root():
    if frontend_path.exists():
        return RedirectResponse(url="/app/")
    return {
        "sistema": settings.APP_NAME,
        "version": "1.0.0",
        "regimen": "Ley 142 de 1994 - Régimen Contractual de Empresas de Servicios Públicos (ESP)",
        "estado": "Operacional",
        "docs_url": "/docs",
        "app_ui_url": "/app/" if frontend_path.exists() else None
    }

@app.get("/api/health", tags=["General"])
def health_check():
    """Health check endpoint para monitoreo de la infraestructura."""
    return {
        "status": "healthy",
        "database": "connected",
        "storage_dirs": {
            "uploads": settings.UPLOADS_DIR.exists(),
            "generated": settings.GENERATED_DIR.exists(),
            "templates": settings.TEMPLATES_DIR.exists(),
            "master_excel": settings.MASTER_EXCEL_PATH.exists()
        },
        "modules_active": {
            "fase_1_estructura_backend": True,
            "fase_2_multi_agent_llm": True,
            "fase_3_docx_excel": True,
            "fase_4_frontend_ui": frontend_path.exists()
        }
    }

@app.get("/api/system/network-info", tags=["General"])
def get_network_info(current_user: Usuario = Depends(get_current_user)):
    """Retorna las URLs de acceso local y de red para invitados."""
    import socket
    def _detect_lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    lan_ip = _detect_lan_ip()
    hostname = socket.gethostname()
    port = 8000

    return {
        "local_ip": lan_ip,
        "hostname": hostname,
        "port": port,
        "local_url": f"http://127.0.0.1:{port}/app/",
        "guest_url": f"http://{lan_ip}:{port}/app/",
        "hostname_url": f"http://{hostname}:{port}/app/",
        "instructions": "Los invitados en celulares o computadores deben estar conectados a la misma red Wi-Fi y abrir guest_url"
    }

from pydantic import BaseModel, Field
from app.routers.auth import require_admin
from app.models.user import Usuario

class ApiKeyConfigInput(BaseModel):
    api_key: str = Field(..., description="Clave de API de Google Gemini")

@app.get("/api/system/config-status", tags=["General"])
def get_config_status(current_user: Usuario = Depends(require_admin)):
    """Retorna el estado de configuración de Gemini sin exponer la clave completa."""
    key = settings.GEMINI_API_KEY or ""
    is_configured = bool(key.strip())
    masked_key = ""
    if is_configured:
        clean = key.strip()
        if len(clean) > 8:
            masked_key = f"{clean[:4]}...{clean[-4:]}"
        else:
            masked_key = "Configurada"
    return {
        "gemini_configured": is_configured,
        "masked_key": masked_key
    }

@app.post("/api/system/config-api-key", tags=["General"])
def configure_api_key(
    payload: ApiKeyConfigInput,
    current_user: Usuario = Depends(require_admin)
):
    """Guarda la API Key de Gemini en el servidor (.env y settings). Solo ADMIN."""
    new_key = payload.api_key.strip()
    if not new_key:
        raise HTTPException(status_code=400, detail="La API Key no puede estar vacía")
    settings.set_gemini_api_key(new_key)
    # Actualizar instancia de gemini_service si está cargada
    try:
        from app.services.gemini_client import gemini_service
        gemini_service.api_key = new_key
    except Exception:
        pass
    masked = f"{new_key[:4]}...{new_key[-4:]}" if len(new_key) > 8 else "Configurada"
    return {
        "success": True,
        "message": "Clave API de Gemini configurada exitosamente en el servidor.",
        "masked_key": masked
    }

