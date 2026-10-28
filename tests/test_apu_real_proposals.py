import sys
from pathlib import Path
import pytest

# Add backend to sys.path
sys.path.insert(0, str(Path("backend").resolve()))

from app.services.agents.multi_proposal_parser import multi_proposal_parser
from app.services.agents.apu_agent import apu_agent
from app.schemas.apu import EvaluacionComparativaPayload, ProcesoConfig

def test_extract_real_proposals_cispa_and_publicorp():
    """
    Verifica la extracción real de las propuestas económicas del estudio tarifario CRA 1038 de 2026:
    - PubliCorp S.A.S. (PDF digital)
    - CISPA S.A.S. (PDF escaneado)
    - Evaluación comparativa con selección estricta de menor precio (CISPA: $35M vs PubliCorp: $40M).
    """
    path_publi = Path("tests/fixtures/apu_proposals/PROPUESTAS ECONOMICAS_Parte1_1.pdf")
    path_cispa = Path("tests/fixtures/apu_proposals/PROPUESTAS ECONOMICAS_Parte2_1.pdf")

    assert path_publi.exists(), f"No se encontró el archivo {path_publi}"
    assert path_cispa.exists(), f"No se encontró el archivo {path_cispa}"

    # 1. Extracción de PubliCorp S.A.S.
    offers_publi = multi_proposal_parser.extract_offers_from_pdf_bytes(
        path_publi.read_bytes(),
        path_publi.name
    )
    assert len(offers_publi) >= 1, "Debe extraerse al menos una oferta para PubliCorp"
    publi = offers_publi[0]

    assert "PUBLICORP" in publi.nombre_razon_social.upper()
    assert "902.110.927" in publi.nit_cedula or "902110927" in publi.nit_cedula
    assert publi.representante_legal.upper() == "JUAN CARLOS TORO VASQUEZ"
    assert "23 de octubre" in publi.fecha_oferta.lower()
    assert "Caldas" in publi.domicilio
    assert publi.valor_total_oferta == 40000000.0
    assert len(publi.items) == 1

    # 2. Extracción de CISPA S.A.S.
    offers_cispa = multi_proposal_parser.extract_offers_from_pdf_bytes(
        path_cispa.read_bytes(),
        path_cispa.name
    )
    assert len(offers_cispa) >= 1, "Debe extraerse al menos una oferta para CISPA"
    cispa = offers_cispa[0]

    assert "CISPA" in cispa.nombre_razon_social.upper()
    assert "901447854" in cispa.nit_cedula.replace(".", "").replace("-", "")
    assert cispa.representante_legal.upper() == "DIANA MARIA TORRES VERGARA"
    assert "17 de septiembre" in cispa.fecha_oferta.lower()
    assert "Marinilla" in cispa.domicilio
    assert cispa.valor_total_oferta == 35000000.0
    assert len(cispa.items) == 1

    # 3. Evaluación comparativa: ambas cargadas simultáneamente
    payload = EvaluacionComparativaPayload(
        proceso_config=ProcesoConfig(
            objeto_contractual="ESTUDIO TARIFARIO DE ACUEDUCTO Y ALCANTARILLADO CRA 1038 DE 2026",
            tipo_contrato="Consultoría"
        ),
        ofertas=[publi, cispa]
    )

    result = apu_agent.evaluate_proposals(payload)
    assert result.proponente_ganador.nombre_razon_social == cispa.nombre_razon_social
    assert result.proponente_ganador.valor_total_oferta == 35000000.0

    # Verificar banderas de selección y posición de orden
    cispa_res = next(o for o in result.ofertas if o.nombre_razon_social == cispa.nombre_razon_social)
    publi_res = next(o for o in result.ofertas if o.nombre_razon_social == publi.nombre_razon_social)

    assert cispa_res.es_seleccionado is True
    assert cispa_res.posicion_orden == 1

    assert publi_res.es_seleccionado is False
    assert publi_res.posicion_orden == 2
    assert publi_res.desviacion_porcentual > 0
