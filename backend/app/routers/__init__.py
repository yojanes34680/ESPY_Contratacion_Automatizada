"""Routers package export."""
from app.routers.contractors import router as contractors_router
from app.routers.contracts import router as contracts_router
from app.routers.documents import router as documents_router
from app.routers.agents import router as agents_router
from app.routers.templates import router as templates_router
from app.routers.excel_sync import router as excel_router
from app.routers.additions import router as additions_router
from app.routers.execution import execution_router
from app.routers.auth import router as auth_router
from app.routers.reports import reports_router
from app.routers.apu import router as apu_router
from app.routers.unspsc import router as unspsc_router
from app.routers.cdp import router as cdp_router

__all__ = [
    "contractors_router",
    "contracts_router",
    "documents_router",
    "agents_router",
    "templates_router",
    "excel_router",
    "additions_router",
    "execution_router",
    "auth_router",
    "reports_router",
    "apu_router",
    "unspsc_router",
    "cdp_router",
]


