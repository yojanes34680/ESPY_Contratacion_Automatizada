import re
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.database import get_db
from app.models.user import Usuario, RolUsuario
from app.config import settings
from app.schemas.user import UserLoginInput, UserCreateInput, UserUpdateInput, UserResponse, LoginResponse, ChangePasswordInput
from app.utils.security import hash_password, verify_password, create_access_token, decode_access_token
from app.utils.logger import logger

router = APIRouter(prefix="/auth", tags=["Autenticación y Usuarios"])

def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    db: Session = Depends(get_db)
) -> Usuario:
    """Dependency to extract and validate the authenticated user from JWT token."""
    raw_token = None
    if authorization and authorization.lower().startswith("bearer "):
        raw_token = authorization[7:].strip()
    elif x_auth_token:
        raw_token = x_auth_token.strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación no proporcionado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(raw_token)
    if not payload or "documento" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado. Inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(Usuario).filter(Usuario.documento == str(payload["documento"])).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado en el sistema",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta de usuario está desactivada",
        )

    return user

def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Dependency to restrict route execution exclusively to ADMIN role."""
    rol_str = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol_str != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Esta acción requiere permisos de Administrador",
        )
    return current_user

def require_editor(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Dependency to restrict route execution to ADMIN or EDITOR roles."""
    rol_str = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    if rol_str not in ("ADMIN", "EDITOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Esta acción requiere permisos de Administrador o Editor",
        )
    return current_user



def seed_master_admin(db: Session) -> Usuario:
    """Ensure the master admin and institutional accounts exist (without overwriting changed passwords)."""
    MASTER_DOC = "8156781"
    MASTER_NAME = "Administrador Maestro ESPY"

    GERENTE_DOC = "1152451796"
    GERENTE_NAME = "CAROLINA GIRALDO"

    # Obtener contraseñas iniciales desde configuración/entorno
    admin_initial_pass = settings.ADMIN_INITIAL_PASSWORD or "AdminEspy2026*"
    guest_initial_pass = settings.GUEST_INITIAL_PASSWORD or "GuestEspy2026*"

    # 1. Administrador Maestro (ADMIN)
    admin = db.query(Usuario).filter(Usuario.documento == MASTER_DOC).first()
    if not admin:
        logger.info(f"Sembrando usuario maestro Administrador: {MASTER_DOC}...")
        admin = Usuario(
            documento=MASTER_DOC,
            nombre_completo=MASTER_NAME,
            password_hash=hash_password(admin_initial_pass),
            rol=RolUsuario.ADMIN,
            is_active=True,
            debe_cambiar_password=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        logger.info("Usuario maestro Administrador inicializado exitosamente.")
    else:
        updated = False
        if not admin.is_active:
            admin.is_active = True
            updated = True
        rol_str = admin.rol.value if hasattr(admin.rol, "value") else str(admin.rol)
        if rol_str != "ADMIN":
            admin.rol = RolUsuario.ADMIN
            updated = True
        if updated:
            db.commit()
            db.refresh(admin)

    # 2. Carolina Giraldo (INVITADO)
    carolina = db.query(Usuario).filter(Usuario.documento == GERENTE_DOC).first()
    if not carolina:
        logger.info(f"Sembrando usuario Invitado Carolina: {GERENTE_DOC}...")
        carolina = Usuario(
            documento=GERENTE_DOC,
            nombre_completo=GERENTE_NAME,
            password_hash=hash_password(guest_initial_pass),
            rol=RolUsuario.INVITADO,
            is_active=True,
            debe_cambiar_password=True
        )
        db.add(carolina)
        db.commit()
        db.refresh(carolina)
    else:
        updated_carolina = False
        if not carolina.is_active:
            carolina.is_active = True
            updated_carolina = True
        if updated_carolina:
            db.commit()
            db.refresh(carolina)

    return admin

@router.post("/login", response_model=LoginResponse)
def login(credentials: UserLoginInput, db: Session = Depends(get_db)):
    """Authenticate user with documento/username and password strictly. No auto-registration or password overwrite."""
    doc_raw = (credentials.documento or "").strip()
    pwd_raw = (credentials.password or "").strip()

    # Validación 2: Rechazar campos vacíos
    if not doc_raw or not pwd_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe ingresar su documento y contraseña."
        )

    # Limpieza de caracteres para búsqueda
    doc_clean = re.sub(r"[^\w]", "", doc_raw)
    doc_numeric = re.sub(r"\D", "", doc_raw)
    doc_lower = doc_raw.lower()

    user = None

    # 1. Búsqueda por alias comunes de usuario
    if doc_lower in ("admin", "administrador", "maestro", "root", "superadmin", "soporte", "master"):
        user = db.query(Usuario).filter(Usuario.documento == "8156781").first()
        if not user:
            user = db.query(Usuario).filter(Usuario.rol == RolUsuario.ADMIN).first()
    elif doc_lower in ("carolina", "carolinagiraldo", "gerente", "gerencia", "carolina giraldo", "carolina giraldo gómez", "carolina giraldo gomez"):
        user = db.query(Usuario).filter(Usuario.documento == "1152451796").first()

    # 2. Búsqueda por documento (exacto o dígitos limpios)
    if not user:
        search_terms = [doc_raw]
        if doc_clean and doc_clean not in search_terms:
            search_terms.append(doc_clean)
        if doc_numeric and doc_numeric not in search_terms:
            search_terms.append(doc_numeric)

        user = db.query(Usuario).filter(Usuario.documento.in_(search_terms)).first()

    # 3. Búsqueda por nombre completo exacto
    if not user:
        user = db.query(Usuario).filter(func.lower(Usuario.nombre_completo) == doc_lower).first()

    # Validación 1: Eliminar auto-registro. Si el usuario no existe, denegar acceso.
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acceso denegado: Usuario no autorizado. Solicite creación de cuenta al Administrador del sistema."
        )

    # Validación 4: Respetar estado activo/inactivo
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su cuenta ha sido desactivada por el Administrador."
        )

    # Validación 3: Verificación real y estricta de contraseña (sin sobrescritura)
    if not verify_password(pwd_raw, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas. Verifique su documento y contraseña."
        )

    rol_str = user.rol.value if hasattr(user.rol, "value") else str(user.rol)

    token = create_access_token({
        "sub": user.documento,
        "documento": user.documento,
        "nombre_completo": user.nombre_completo,
        "rol": rol_str,
        "user_id": user.id
    })

    user_resp = UserResponse(
        id=user.id,
        documento=user.documento,
        nombre_completo=user.nombre_completo,
        rol=rol_str,
        is_active=user.is_active,
        debe_cambiar_password=bool(user.debe_cambiar_password),
        created_at=user.created_at
    )

    return LoginResponse(
        success=True,
        token=token,
        access_token=token,
        user=user_resp,
        usuario=user_resp,
        debe_cambiar_password=bool(user.debe_cambiar_password),
        mensaje=f"Bienvenido al sistema, {user.nombre_completo}"
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: Usuario = Depends(get_current_user)):
    """Get profile of current authenticated user."""
    rol_str = current_user.rol.value if hasattr(current_user.rol, "value") else str(current_user.rol)
    return UserResponse(
        id=current_user.id,
        documento=current_user.documento,
        nombre_completo=current_user.nombre_completo,
        rol=rol_str,
        is_active=current_user.is_active,
        debe_cambiar_password=bool(current_user.debe_cambiar_password),
        created_at=current_user.created_at
    )

@router.post("/change-password")
def change_password(
    data: ChangePasswordInput,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambiar la contraseña del usuario autenticado. Requiere mínimo 10 caracteres."""
    if not verify_password(data.password_actual, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual ingresada es incorrecta."
        )
    
    if len(data.password_nueva.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe tener mínimo 10 caracteres."
        )
    
    current_user.password_hash = hash_password(data.password_nueva)
    current_user.debe_cambiar_password = False
    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "mensaje": "Contraseña actualizada exitosamente.",
        "debe_cambiar_password": False
    }

@router.get("/users", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """List all registered users. Restricted to ADMIN."""
    users = db.query(Usuario).order_by(Usuario.id.asc()).all()
    results = []
    for u in users:
        rol_str = u.rol.value if hasattr(u.rol, "value") else str(u.rol)
        results.append(UserResponse(
            id=u.id,
            documento=u.documento,
            nombre_completo=u.nombre_completo,
            rol=rol_str,
            is_active=u.is_active,
            debe_cambiar_password=bool(u.debe_cambiar_password),
            created_at=u.created_at
        ))
    return results

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_guest_user(
    input_data: UserCreateInput,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """Create a new user (default INVITADO). Restricted to ADMIN."""
    doc_clean = input_data.documento.strip()
    if not doc_clean:
        raise HTTPException(status_code=400, detail="El documento de identidad es requerido")
    if not input_data.password or len(input_data.password.strip()) < 4:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 4 caracteres")

    existing = db.query(Usuario).filter(Usuario.documento == doc_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario registrado con el documento {doc_clean}"
        )

    # Rol
    target_rol = RolUsuario.INVITADO
    rol_upper = (input_data.rol or "").upper()
    if rol_upper == "ADMIN":
        target_rol = RolUsuario.ADMIN
    elif rol_upper == "EDITOR":
        target_rol = RolUsuario.EDITOR

    new_user = Usuario(
        documento=doc_clean,
        nombre_completo=input_data.nombre_completo.strip() or f"Usuario {doc_clean}",
        password_hash=hash_password(input_data.password.strip()),
        rol=target_rol,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Usuario {doc_clean} ({new_user.rol}) creado exitosamente por Administrador.")
    
    rol_str = new_user.rol.value if hasattr(new_user.rol, "value") else str(new_user.rol)
    return UserResponse(
        id=new_user.id,
        documento=new_user.documento,
        nombre_completo=new_user.nombre_completo,
        rol=rol_str,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )

@router.put("/users/{user_id}", response_model=UserResponse)
@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    update_data: UserUpdateInput,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(require_admin)
):
    """Update user role, active status, name, or password. Restricted to ADMIN."""
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Si es el Administrador Maestro, proteger de desactivación o cambio de rol
    if user.documento == "8156781":
        if update_data.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede desactivar la cuenta del Administrador Maestro."
            )
        if update_data.rol and update_data.rol.upper() != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El Administrador Maestro debe conservar el rol ADMIN."
            )

    if update_data.nombre_completo is not None:
        user.nombre_completo = update_data.nombre_completo.strip()

    if update_data.password is not None and len(update_data.password.strip()) >= 4:
        user.password_hash = hash_password(update_data.password.strip())

    if update_data.is_active is not None:
        user.is_active = update_data.is_active

    if update_data.rol is not None:
        rol_upper = update_data.rol.upper()
        if rol_upper == "ADMIN":
            user.rol = RolUsuario.ADMIN
        elif rol_upper == "EDITOR":
            user.rol = RolUsuario.EDITOR
        elif rol_upper == "INVITADO":
            user.rol = RolUsuario.INVITADO

    db.commit()
    db.refresh(user)
    logger.info(f"Usuario {user.documento} actualizado por Administrador.")

    rol_str = user.rol.value if hasattr(user.rol, "value") else str(user.rol)
    return UserResponse(
        id=user.id,
        documento=user.documento,
        nombre_completo=user.nombre_completo,
        rol=rol_str,
        is_active=user.is_active,
        created_at=user.created_at
    )

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Usuario = Depends(require_admin)
):
    """Delete or revoke an invitation user. Restricted to ADMIN. Master admin cannot be deleted."""
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.documento == "8156781":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar el usuario Administrador Maestro del sistema."
        )

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puede eliminar su propia cuenta activa."
        )

    db.delete(user)
    db.commit()
    return {"success": True, "message": f"Usuario con documento {user.documento} eliminado correctamente."}
