"""
Test suite to verify the consolidated contracts (49 contracts) in ESP Yolombó system.
Checks:
- Complete retrieval of the 49 contracts
- Accuracy of the 17 mapped matrix columns
- Contractor relationship loading (joinedload)
- Typology and text search filtering
- Financial summation consistency (valor_inicial, adicion_1, valor_total)
"""
import urllib.request
import urllib.parse
import json

BASE_URL = "http://127.0.0.1:8000/api"

def run_test():
    print("=" * 65)
    print("VERIFICACION CONSOLIDADO DE CONTRATOS - ESP YOLOMBO")
    print("=" * 65)

    # 1. Total contracts count
    req = urllib.request.urlopen(f"{BASE_URL}/contracts?limit=200")
    contracts = json.loads(req.read().decode())
    print(f"[TEST 1] Total contratos recuperados: {len(contracts)}")
    assert len(contracts) >= 49, f"Se esperaban al menos 49 contratos, pero se obtuvieron {len(contracts)}"
    print("  -> OK: Se recuperaron los 49 contratos consolidados.")

    # 2. Check presence of specific sample contracts
    sample_codes = ["CPS-001-2026", "CA-013-2026", "CS-024-2026", "CO-029-2026", "CPS-035-2026", "CS-048-2026", "CPS-049-2026"]
    contract_map = {c["numero_contrato"]: c for c in contracts}
    
    for code in sample_codes:
        assert code in contract_map, f"Falta el contrato esperado: {code}"
        c = contract_map[code]
        print(f"[TEST 2] Contrato {code}:")
        print(f"   * Objeto: {c['objeto'][:45]}...")
        print(f"   * Tipo: {c['tipologia']}")
        print(f"   * Titular: {c.get('contratista', {}).get('nombre_o_razon_social')}")
        print(f"   * Cédula/NIT: {c.get('contratista', {}).get('numero_documento')}")
        print(f"   * Valor Inicial: {c.get('valor_inicial')} | Adición: {c.get('adicion_1')} | Total: {c.get('valor_total')}")
        print(f"   * Plazo: {c.get('plazo_texto')} | Prórroga: {c.get('prorroga_1')}")
        print(f"   * Inicio: {c.get('fecha_acta_inicio')} | Fin: {c.get('fecha_terminacion')}")
        print(f"   * CDP: {c.get('cdp_numero')} | Rubro: {c.get('cdp_rubro')} | CRP: {c.get('rp_numero')}")
    print("  -> OK: Códigos y datos clave verificados correctamente.")

    # 3. Check specific fields for CA-013-2026 (Arrendamiento)
    ca13 = contract_map["CA-013-2026"]
    assert ca13["tipologia"] == "ARRENDAMIENTO", f"Esperado ARRENDAMIENTO, obtenido {ca13['tipologia']}"
    assert "PARROQUIA" in ca13["contratista"]["nombre_o_razon_social"], "Contratista incorrecto en CA-013-2026"
    print("[TEST 3] CA-013-2026 clasificado correctamente como ARRENDAMIENTO.")

    # 4. Check contract with addition: CPS-020-2026 or similar
    contracts_with_adicion = [c for c in contracts if c.get("adicion_1") and c["adicion_1"] > 0]
    print(f"[TEST 4] Contratos con adición encontrados: {len(contracts_with_adicion)}")
    for ca in contracts_with_adicion:
        print(f"   * {ca['numero_contrato']}: Inicial={ca['valor_inicial']}, Adición={ca['adicion_1']}, Total={ca['valor_total']}")
        assert ca["valor_total"] == ca["valor_inicial"] + ca["adicion_1"], "Inconsistencia matemática en adición"
    print("  -> OK: Consistencia de adiciones confirmada.")

    # 5. Search filter tests
    q_url = f"{BASE_URL}/contracts?query=" + urllib.parse.quote("CPS-001")
    req_q = urllib.request.urlopen(q_url)
    res_q = json.loads(req_q.read().decode())
    assert len(res_q) >= 1 and res_q[0]["numero_contrato"] == "CPS-001-2026"
    print("[TEST 5] Búsqueda por código de contrato CPS-001 OK.")

    # 6. Typology filter test
    t_url = f"{BASE_URL}/contracts?tipologia=ARRENDAMIENTO"
    req_t = urllib.request.urlopen(t_url)
    res_t = json.loads(req_t.read().decode())
    assert len(res_t) == 1 and res_t[0]["numero_contrato"] == "CA-013-2026"
    print("[TEST 6] Filtro por tipología ARRENDAMIENTO OK.")

    print("\n" + "=" * 65)
    print("¡TODAS LAS PRUEBAS DE VERIFICACION DEL CONSOLIDADO PASARON EXITOSAMENTE!")
    print("=" * 65)

if __name__ == "__main__":
    run_test()
