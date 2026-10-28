"""Base class and common contract drafting definitions for specialized agents."""
from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.agent import ContractDraftingInput, ContractDraftingResult
from app.services.gemini_client import gemini_service
from app.utils.objective_normalizer import normalize_objetivos_especificos

class BaseContractAgent(ABC):
    """Clase base para agentes de redacción y estructuración contractual."""

    def __init__(self, nombre: str, tipologia: str):
        self.nombre = nombre
        self.tipologia = tipologia

    @abstractmethod
    def get_system_instruction(self) -> str:
        """Instrucción de sistema especializada para el agente LLM."""
        pass

    @abstractmethod
    def build_user_prompt(self, input_data: ContractDraftingInput) -> str:
        """Construye el prompt detallado con el contexto de la contratación."""
        pass

    @abstractmethod
    def fallback_generator(self, input_data: ContractDraftingInput) -> ContractDraftingResult:
        """Generador normativo determinista si no hay conexión al LLM."""
        pass

    def draft(
        self, 
        input_data: ContractDraftingInput, 
        override_api_key: Optional[str] = None
    ) -> ContractDraftingResult:
        """Orquesta la redacción del contrato invocando al LLM o su fallback normativo."""
        system_instruction = self.get_system_instruction()
        user_prompt = self.build_user_prompt(input_data)

        result = gemini_service.generate_agent_structured_draft(
            system_instruction=system_instruction,
            user_prompt=user_prompt,
            schema_class=ContractDraftingResult,
            fallback_factory=lambda: self.fallback_generator(input_data),
            override_api_key=override_api_key
        )
        if result and getattr(result, "objetivos_especificos", None):
            result.objetivos_especificos = normalize_objetivos_especificos(result.objetivos_especificos)
        return result
