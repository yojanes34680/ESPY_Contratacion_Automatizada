"""Usuario (User) ORM Model for Authentication and Role-Based Access Control."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
import enum

from app.database import Base

class RolUsuario(str, enum.Enum):
    ADMIN = "ADMIN"
    EDITOR = "EDITOR"
    INVITADO = "INVITADO"

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    documento = Column(String(50), unique=True, index=True, nullable=False)
    nombre_completo = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(SQLEnum(RolUsuario), default=RolUsuario.INVITADO, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    debe_cambiar_password = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "documento": self.documento,
            "nombre_completo": self.nombre_completo,
            "rol": self.rol.value if hasattr(self.rol, "value") else str(self.rol),
            "is_active": self.is_active,
            "debe_cambiar_password": bool(self.debe_cambiar_password),
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
