"""Automated verification test for Multi-Vigencia Management in ESPY.
Tests:
1. Vigencias listing & auto-seeding of 2026 (49 contracts).
2. Opening new contracting era (Vigencia 2027).
3. Consecutives calculation per vigencia and typology (2026 vs 2027).
4. Availability of existing contractors to sign new contracts in 2027 without duplication.
5. Vigencia-segregated contract listings and metrics.
6. Excel matrix generation filtered by vigencia.
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import SessionLocal, engine, Base
from app.models.contract import Contrato, TipologiaContrato, ModalidadSeleccion, EstadoContrato, UnidadPlazo
from app.models.contractor import Contratista
from app.models.vigencia import VigenciaFiscal
from app.routers.contracts import list_vigencias, create_vigencia, activate_vigencia, get_next_contract_number, list_contracts, create_contract
from app.schemas.contract import VigenciaFiscalCreate, ContratoCreate
from app.services.excel_engine import generate_filtered_excel

def run_tests():
    print("=" * 70)
    print("🚀 EJECUTANDO VALIDACIÓN DE GESTIÓN MULTI-VIGENCIA ESPY")
    print("=" * 70)

    # 1. Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Phase 1: Listar vigencias y verificar auto-siembra de 2026
        print("\n[FASE 1] Verificando detección y auto-siembra de Vigencia 2026...")
        vigencias = list_vigencias(db)
        years = [v.year for v in vigencias]
        print(f" -> Vigencias encontradas: {years}")
        assert 2026 in years, "Vigencia 2026 debe estar presente"
        v2026 = next(v for v in vigencias if v.year == 2026)
        print(f" -> Vigencia 2026 contratos: {v2026.total_contratos}, valor: ${v2026.valor_total_contratado:,.0f} COP")
        assert v2026.total_contratos >= 49, f"Se esperaban al menos 49 contratos en 2026, se encontraron {v2026.total_contratos}"
        print("  ✓ FASE 1 COMPLETADA CON ÉXITO")

        # Phase 2: Verificar consecutivos para 2026
        print("\n[FASE 2] Verificando consecutivo inteligente para 2026...")
        next_2026 = get_next_contract_number(vigencia=2026, tipologia=TipologiaContrato.PRESTACION_SERVICIOS, db=db)
        print(f" -> Siguiente sugerido para 2026: {next_2026.sugerido} (consecutivo: {next_2026.consecutivo})")
        assert next_2026.consecutivo >= 50, f"Para 2026 el consecutivo debe ser >= 50, dio {next_2026.consecutivo}"
        print("  ✓ FASE 2 COMPLETADA CON ÉXITO")

        # Phase 3: Aperturar nueva era de contratación (Vigencia 2027)
        print("\n[FASE 3] Aperturando nueva era de contratación (Vigencia 2027)...")
        existing_2027 = db.query(VigenciaFiscal).filter(VigenciaFiscal.year == 2027).first()
        if not existing_2027:
            data_in = VigenciaFiscalCreate(
                year=2027,
                nombre="Vigencia Fiscal 2027",
                descripcion="Plan Anual de Contratación ESP Yolombó - Era 2027",
                presupuesto_base=1800000000.0,
                estado="ABIERTA",
                es_vigencia_actual=True
            )
            v2027 = create_vigencia(data_in, db)
            print(f" -> Vigencia 2027 creada exitosamente: {v2027.nombre}, base ${v2027.presupuesto_base:,.0f} COP")
        else:
            print(" -> Vigencia 2027 ya existía en la base de datos.")

        # Phase 4: Verificar consecutivo limpio para 2027
        print("\n[FASE 4] Verificando consecutivo sugerido para 2027...")
        next_2027 = get_next_contract_number(vigencia=2027, tipologia=TipologiaContrato.PRESTACION_SERVICIOS, db=db)
        print(f" -> Siguiente sugerido para 2027: {next_2027.sugerido} (consecutivo: {next_2027.consecutivo})")
        assert next_2027.consecutivo >= 1, "Para 2027 el consecutivo inicial debe ser >= 1"
        assert "2027" in next_2027.sugerido, "El código sugerido debe incluir el año 2027"
        print("  ✓ FASE 4 COMPLETADA CON ÉXITO")

        # Phase 5: Reutilización de contratistas de 2026 para celebrar contrato en 2027
        print("\n[FASE 5] Celebrando nuevo contrato en 2027 con contratista preexistente...")
        contractor = db.query(Contratista).first()
        assert contractor is not None, "Debe existir al menos un contratista registrado en el sistema"
        print(f" -> Contratista seleccionado: ID {contractor.id} - {contractor.nombre_o_razon_social} (NIT/CC: {contractor.numero_documento})")
        print(f" -> Datos preexistentes: Banco: {contractor.banco_nombre}, Régimen: {contractor.regimen_tributario}")

        contratos_iniciales_total = db.query(Contrato).filter(Contrato.contratista_id == contractor.id).count()
        print(f" -> Contratos previos del contratista: {contratos_iniciales_total}")

        num_contrato_test = f"CPS-TEST-2027"
        # Limpiar contrato test si ya existiera
        db.query(Contrato).filter(Contrato.numero_contrato == num_contrato_test).delete()
        db.commit()

        contract_in = ContratoCreate(
            numero_contrato=num_contrato_test,
            vigencia=2027,
            modalidad_seleccion=ModalidadSeleccion.CONTRATACION_DIRECTA,
            tipologia=TipologiaContrato.PRESTACION_SERVICIOS,
            contratista_id=contractor.id,
            objeto="PRESTACIÓN DE SERVICIOS PROFESIONALES DE APOYO A LA GESTIÓN - VIGENCIA 2027",
            valor_total=36000000.0,
            plazo_ejecucion=12,
            unidad_plazo=UnidadPlazo.MESES,
            supervisor_nombre="Ing. Supervisor Técnico 2027",
            supervisor_cargo="Director Operativo",
            estado=EstadoContrato.BORRADOR
        )
        new_contract = create_contract(contract_in, db)
        print(f" -> Contrato en 2027 creado con éxito: ID {new_contract.id} - {new_contract.numero_contrato}")

        # Verificar que el contratista no fue duplicado
        contractor_count = db.query(Contratista).filter(Contratista.numero_documento == contractor.numero_documento).count()
        assert contractor_count == 1, "El contratista no debe duplicarse bajo ninguna circunstancia"
        print("  ✓ Verificada la no duplicidad del contratista en el directorio")

        # Phase 6: Verificación de segregación de contratos por vigencia
        print("\n[FASE 6] Verificando filtros y segregación por vigencia...")
        contracts_2026 = list_contracts(vigencia=2026, db=db)
        contracts_2027 = list_contracts(vigencia=2027, db=db)
        print(f" -> Contratos en Vigencia 2026: {len(contracts_2026)}")
        print(f" -> Contratos en Vigencia 2027: {len(contracts_2027)}")
        assert len(contracts_2026) >= 49, "Los 49 contratos de 2026 deben permanecer intactos"
        assert len(contracts_2027) >= 1, "Debe haber al menos 1 contrato en 2027"
        print("  ✓ Segregación multianual verificada exitosamente")

        # Phase 7: Exportación y filtro en Matriz Excel
        print("\n[FASE 7] Verificando generación de Excel filtrado por Vigencia 2027...")
        excel_path = generate_filtered_excel(2027, db)
        print(f" -> Archivo Excel generado: {excel_path} (Existe: {excel_path.exists()}, Tamaño: {excel_path.stat().st_size} bytes)")
        assert excel_path.exists(), "El archivo Excel para la vigencia 2027 debe existir"
        assert excel_path.stat().st_size > 0, "El archivo Excel generado debe contener datos"
        print("  ✓ FASE 7 COMPLETADA CON ÉXITO")

        # Limpieza de contrato de prueba
        db.query(Contrato).filter(Contrato.numero_contrato == num_contrato_test).delete()
        db.commit()
        print("\n -> Limpieza del contrato de prueba ejecutada.")

        print("\n" + "=" * 70)
        print("🎉 ¡TODAS LAS FASES DE MULTI-VIGENCIA COMPLETADAS EXITOSAMENTE!")
        print("=" * 70)

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
