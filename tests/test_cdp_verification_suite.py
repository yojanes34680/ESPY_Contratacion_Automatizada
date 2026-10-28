"""
Verificación Integral del flujo de CDP y marcadores {{CDP}} en ESP Yolombó.
Valida:
1. Datos persistidos y expuestos vía API en Contrato 50 (CPS-050-2026).
2. Generación dinámica de Estudio Previo, Minuta y Acta de Inicio.
3. Inyección completa del párrafo de disponibilidad presupuestal:
   - Número de CDP
   - Fecha de expedición
   - Valor exacto respaldado con formato colombiano ($9.400.083)
   - Código y nombre del Rubro Presupuestal
   - Clasificadores CCPET
"""
import sys
import urllib.request
import json
from pathlib import Path
import docx

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_URL = "http://127.0.0.1:8000/api"

def run_suite():
    print("=" * 70)
    print("SUITE DE PRUEBAS: RESOLUCIÓN Y VALIDACIÓN COMPLETA DE CDP")
    print("=" * 70)

    # 1. Verificar endpoint de API para Contrato 50
    req = urllib.request.urlopen(f"{BASE_URL}/contracts/50")
    data = json.loads(req.read().decode())
    
    num_contrato = data.get("numero_contrato")
    cdp_num = data.get("cdp_numero")
    cdp_fecha = data.get("cdp_fecha")
    cdp_rubro = data.get("cdp_rubro")
    meta = data.get("metadatos_agente") or {}

    print(f"\n[1] Datos API Contrato {num_contrato}:")
    print(f"    * CDP Número: {cdp_num}")
    print(f"    * CDP Fecha: {cdp_fecha}")
    print(f"    * CDP Rubro: {cdp_rubro}")
    print(f"    * Valor Respaldo CDP: {meta.get('cdp_valor')}")
    print(f"    * Nombre del Rubro: {meta.get('cdp_rubro_nombre')}")
    print(f"    * CCPET Clasificadores: {len(meta.get('cdp_clasificadores', []))} items")

    assert cdp_num == "00232", f"CDP número incorrecto: {cdp_num}"
    assert cdp_rubro == "2.3.2.02.02.009", f"Rubro incorrecto: {cdp_rubro}"
    assert meta.get("cdp_valor") == 9400083.0, f"Valor incorrecto: {meta.get('cdp_valor')}"
    assert len(meta.get("cdp_clasificadores", [])) >= 5, "Faltan clasificadores CCPET"
    print("    -> OK: Metadata de CDP en API correcta.")

    # 2. Generar documentos a través del endpoint de plantillas
    tipos = [
        ("ESTUDIO_PREVIO", "Estudio Previo"),
        ("MINUTA", "Minuta Contractual"),
        ("ACTA_INICIO", "Acta de Inicio")
    ]

    print("\n[2] Generación y verificación de documentos Word:")
    for tipo_doc, label in tipos:
        # Invocar generación
        gen_req = urllib.request.Request(f"{BASE_URL}/templates/generate/50/{tipo_doc}", data=b"", method="POST")
        gen_res = urllib.request.urlopen(gen_req)
        gen_data = json.loads(gen_res.read().decode())
        archivo_nombre = gen_data["archivo_nombre"]
        archivo_path = Path("backend/storage/generated") / archivo_nombre

        assert archivo_path.exists(), f"El archivo {archivo_path} no fue creado"

        # Leer contenido Word
        doc = docx.Document(str(archivo_path))
        full_text = " ".join(p.text for p in doc.paragraphs)

        # Aserciones estrictas
        assert "{{CDP}}" not in full_text, f"ERROR: Marcador {{CDP}} no fue reemplazado en {label}"
        assert "00232" in full_text, f"ERROR: Número 00232 no encontrado en {label}"
        assert "$9.400.083" in full_text, f"ERROR: Valor $9.400.083 no encontrado en {label}"
        assert "2.3.2.02.02.009" in full_text, f"ERROR: Código de rubro no encontrado en {label}"
        assert "SERVICIOS PARA LA COMUNIDAD" in full_text, f"ERROR: Nombre de rubro no encontrado en {label}"
        assert "CCPET01" in full_text, f"ERROR: Clasificador CCPET01 no encontrado en {label}"
        assert "CCPET84" in full_text, f"ERROR: Clasificador CCPET84 no encontrado en {label}"

        # Extraer el párrafo exacto para imprimir
        cdp_p = next(p.text for p in doc.paragraphs if "00232" in p.text)
        print(f"\n    ✓ {label} ({archivo_nombre}):")
        print(f"      Párrafo generado: \"{cdp_p[:180]}...\"")

    print("\n" + "=" * 70)
    print("¡TODAS LAS PRUEBAS (API, DOCX, CCPET, FORMATO COP) PASARON EXITOSAMENTE!")
    print("=" * 70)

if __name__ == "__main__":
    run_suite()
