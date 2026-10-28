"""Agent Dispatcher: Enruta los requerimientos al agente especializado según la tipología contractual."""
from typing import Optional, Dict
from app.schemas.agent import ContractDraftingInput, ContractDraftingResult
from app.services.agents.base_agent import BaseContractAgent
from app.services.agents.services_agent import ServicesContractAgent
from app.services.agents.works_agent import WorksContractAgent
from app.services.agents.supply_agent import SupplyContractAgent
from app.services.agents.lease_agent import LeaseContractAgent
from app.utils.objective_normalizer import normalize_objetivos_especificos
from app.utils.object_normalizer import normalize_objeto_contractual
from app.utils.logger import logger

class ContractAgentDispatcher:
    """Despachador central del sistema Multi-Agente."""

    def __init__(self):
        self._agents: Dict[str, BaseContractAgent] = {
            "PRESTACION_SERVICIOS": ServicesContractAgent(),
            "CONSULTORIA": ServicesContractAgent(),
            "OBRA": WorksContractAgent(),
            "INTERVENTORIA": WorksContractAgent(),
            "SUMINISTRO": SupplyContractAgent(),
            "ARRENDAMIENTO": LeaseContractAgent()
        }

    def get_agent_for_typology(self, tipologia: str) -> BaseContractAgent:
        """Devuelve la instancia del agente asignado a la tipología."""
        normalized = tipologia.upper().strip()
        if normalized in self._agents:
            return self._agents[normalized]
        
        logger.warning(f"Tipología '{tipologia}' no cuenta con agente exclusivo, asignando agente de servicios como fallback.")
        return self._agents["PRESTACION_SERVICIOS"]

    def dispatch_drafting(
        self, 
        input_data: ContractDraftingInput, 
        override_api_key: Optional[str] = None
    ) -> ContractDraftingResult:
        """
        Enruta la petición al agente correspondiente y ejecuta el ciclo de estructuración.
        """
        agent = self.get_agent_for_typology(input_data.tipologia)
        logger.info(f"Despachando redacción de contrato tipología '{input_data.tipologia}' hacia '{agent.nombre}'...")
        
        result = agent.draft(input_data, override_api_key=override_api_key)
        if result and getattr(result, "objetivos_especificos", None):
            result.objetivos_especificos = normalize_objetivos_especificos(result.objetivos_especificos)
        if result and getattr(result, "objeto", None):
            result.objeto = normalize_objeto_contractual(result.objeto, input_data.tipologia)
        return result

dispatcher = ContractAgentDispatcher()
