"""Test suite para verificar la regla de nomenclatura institucional de contratos de la ESP Yolombó.

Norma:
- Prestación de Servicios -> Sigla obligatoria: CPS (Ej: CPS-050-2026)
- Suministro             -> Sigla obligatoria: CS  (Ej: CS-054-2026)
- Arrendamiento          -> Sigla obligatoria: CA  (Ej: CA-013-2026)
- Obra                   -> Sigla obligatoria: CO  (Ej: CO-029-2026)
- Consultoría            -> Sigla obligatoria: CC  (Ej: CC-001-2026)
- Interventoría          -> Sigla obligatoria: CI  (Ej: CI-001-2026)
"""
import sys
import unittest
sys.path.insert(0, 'backend')

from app.utils.contract_prefix_helper import get_required_prefix, normalize_contract_code
from app.models.contract import TipologiaContrato, Contrato
from app.database import SessionLocal


class TestContractCodeNomenclatura(unittest.TestCase):

    def test_get_required_prefix(self):
        self.assertEqual(get_required_prefix("PRESTACION_SERVICIOS"), "CPS")
        self.assertEqual(get_required_prefix(TipologiaContrato.PRESTACION_SERVICIOS), "CPS")
        self.assertEqual(get_required_prefix("SUMINISTRO"), "CS")
        self.assertEqual(get_required_prefix(TipologiaContrato.SUMINISTRO), "CS")
        self.assertEqual(get_required_prefix("ARRENDAMIENTO"), "CA")
        self.assertEqual(get_required_prefix(TipologiaContrato.ARRENDAMIENTO), "CA")
        self.assertEqual(get_required_prefix("OBRA"), "CO")
        self.assertEqual(get_required_prefix(TipologiaContrato.OBRA), "CO")
        self.assertEqual(get_required_prefix("CONSULTORIA"), "CC")
        self.assertEqual(get_required_prefix(TipologiaContrato.CONSULTORIA), "CC")
        self.assertEqual(get_required_prefix("INTERVENTORIA"), "CI")
        self.assertEqual(get_required_prefix(TipologiaContrato.INTERVENTORIA), "CI")

    def test_normalize_contract_code_replacements(self):
        # CPS a CS para Suministro (caso exacto solicitado por el usuario)
        self.assertEqual(normalize_contract_code("CPS-054-2026", "SUMINISTRO", 2026), "CS-054-2026")
        self.assertEqual(normalize_contract_code("CPS-054-2026", TipologiaContrato.SUMINISTRO, 2026), "CS-054-2026")

        # CS a CPS para Servicios
        self.assertEqual(normalize_contract_code("CS-050-2026", "PRESTACION_SERVICIOS", 2026), "CPS-050-2026")

        # Cualquier código a CO para Obra
        self.assertEqual(normalize_contract_code("CPS-029-2026", "OBRA", 2026), "CO-029-2026")

        # Cualquier código a CA para Arrendamiento
        self.assertEqual(normalize_contract_code("CPS-013-2026", "ARRENDAMIENTO", 2026), "CA-013-2026")

        # Consecutivos en formato corto
        self.assertEqual(normalize_contract_code("054", "SUMINISTRO", 2026), "CS-054-2026")
        self.assertEqual(normalize_contract_code("54", "SUMINISTRO", 2026), "CS-054-2026")
        self.assertEqual(normalize_contract_code("013-2026", "ARRENDAMIENTO", 2026), "CA-013-2026")
        self.assertEqual(normalize_contract_code("029-2026", "OBRA", 2026), "CO-029-2026")

    def test_contract_56_is_properly_cs_054_2026(self):
        db = SessionLocal()
        try:
            c = db.query(Contrato).filter(Contrato.id == 56).first()
            self.assertIsNotNone(c, "El contrato con ID 56 debe existir")
            self.assertEqual(c.numero_contrato, "CS-054-2026")
            self.assertEqual(c.tipologia.value, "SUMINISTRO")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
