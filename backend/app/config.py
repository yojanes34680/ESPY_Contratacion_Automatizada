"""Application configuration settings."""
import os
from pathlib import Path
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BASE_DIR.parent

# Cargar backend/.env en os.environ si no estamos en pruebas (ESPY_TESTING != '1')
env_file = BASE_DIR / ".env"
if env_file.exists() and os.getenv("ESPY_TESTING") != "1":
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass

class Settings(BaseModel):
    BASE_DIR: Path = BASE_DIR
    WORKSPACE_ROOT: Path = WORKSPACE_ROOT

    APP_NAME: str = os.getenv("APP_NAME", "ESPY Contratación Automatizada")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{BASE_DIR / 'espy_contratacion.db'}"
    )

    # Storage paths
    STORAGE_DIR: Path = Path(os.getenv("STORAGE_DIR", BASE_DIR / "storage"))
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    GENERATED_DIR: Path = STORAGE_DIR / "generated"
    TEMPLATES_DIR: Path = Path(os.getenv("TEMPLATES_DIR", BASE_DIR / "templates"))
    CUSTOM_TEMPLATES_DIR: Path = Path(os.getenv("CUSTOM_TEMPLATES_DIR", BASE_DIR / "templates" / "custom"))
    MASTER_EXCEL_PATH: Path = Path(
        os.getenv("MASTER_EXCEL_PATH", BASE_DIR / "master_excel" / "Matriz_Contratacion_Maestra.xlsx")
    )

    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

    # Security & Auth (Sin valor por defecto inseguro en código)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ADMIN_INITIAL_PASSWORD: str = os.getenv("ADMIN_INITIAL_PASSWORD", "")
    GUEST_INITIAL_PASSWORD: str = os.getenv("GUEST_INITIAL_PASSWORD", "")

    # UNSPSC Engine Switch: "clasico" (default) or "nuevo"
    UNSPSC_MOTOR: str = os.getenv("UNSPSC_MOTOR", "clasico")

    def ensure_directories(self):
        """Create runtime storage directories if they do not exist."""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        self.CUSTOM_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        self.MASTER_EXCEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    def set_gemini_api_key(self, new_key: str):
        """Save GEMINI_API_KEY into local .env and update in-memory settings."""
        clean_key = new_key.strip()
        self.GEMINI_API_KEY = clean_key
        os.environ["GEMINI_API_KEY"] = clean_key
        env_path = self.BASE_DIR / ".env"
        lines = []
        if env_path.exists():
            try:
                lines = env_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                lines = []
        key_found = False
        new_lines = []
        for line in lines:
            if line.startswith("GEMINI_API_KEY="):
                new_lines.append(f"GEMINI_API_KEY={clean_key}")
                key_found = True
            else:
                new_lines.append(line)
        if not key_found:
            new_lines.append(f"GEMINI_API_KEY={clean_key}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

settings = Settings()
settings.ensure_directories()

