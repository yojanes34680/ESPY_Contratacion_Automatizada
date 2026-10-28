"""User schemas for login, user creation, and profile response."""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class UserLoginInput(BaseModel):
    documento: Optional[str] = Field("", description="Número de documento de identidad o usuario")
    password: Optional[str] = Field("", description="Contraseña de acceso")

class UserCreateInput(BaseModel):
    documento: str = Field(..., description="Número de documento de identidad")
    nombre_completo: str = Field(..., description="Nombre completo o cargo")
    password: str = Field(..., description="Contraseña de acceso inicial")
    rol: Optional[str] = Field("INVITADO", description="Rol del usuario: ADMIN, EDITOR o INVITADO")

class UserUpdateInput(BaseModel):
    nombre_completo: Optional[str] = Field(None, description="Nombre completo o cargo")
    password: Optional[str] = Field(None, description="Nueva contraseña (opcional)")
    rol: Optional[str] = Field(None, description="Rol: ADMIN, EDITOR o INVITADO")
    is_active: Optional[bool] = Field(None, description="Estado activo o inactivo")

class ChangePasswordInput(BaseModel):
    password_actual: str = Field(..., description="Contraseña actual")
    password_nueva: str = Field(..., min_length=10, description="Nueva contraseña (mínimo 10 caracteres)")

class UserResponse(BaseModel):
    id: int
    documento: str
    nombre_completo: str
    rol: str
    is_active: bool
    debe_cambiar_password: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class LoginResponse(BaseModel):
    success: bool = True
    token: str
    access_token: Optional[str] = None
    user: Optional[UserResponse] = None
    usuario: UserResponse
    debe_cambiar_password: bool = False
    mensaje: str = "Inicio de sesión exitoso"

