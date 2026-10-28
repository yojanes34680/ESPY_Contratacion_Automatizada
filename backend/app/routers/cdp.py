"""Router para gestión y consulta de reglas de Certificado de Disponibilidad Presupuestal (CDP)."""
from typing import List
from fastapi import APIRouter, Depends
from app.routers.auth import get_current_user
from app.models.user import Usuario
from app.utils.cdp_cleaner import get_marcas_de_corte_cdp

router = APIRouter(prefix="/cdp", tags=["CDP"])

@router.get("/marcas-corte", response_model=List[str])
def obtener_marcas_corte(current_user: Usuario = Depends(get_current_user)):
    """Devuelve la lista oficial de expresiones y marcas de corte para el saneamiento de textos de CDP.
    Requiere usuario autenticado.
    """
    return get_marcas_de_corte_cdp()
