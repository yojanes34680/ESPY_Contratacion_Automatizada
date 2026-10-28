"""Herramienta de auditoría y prueba de solo lectura para archivos OCR de CDP.
Pasa la lógica de extracción y saneamiento limpiar_texto_cdp por todos los archivos
*CDP*.ocr.txt y cdp*_ocr.txt de backend/storage y genera el reporte auditoria_cdp_ocr.md.
"""
import os
import re
import glob
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
import sys
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.gemini_client import gemini_service
from app.utils.cdp_cleaner import limpiar_texto_cdp



def main():
    storage_dir = BACKEND_DIR / "storage"
    files = []
    for pattern in ["*CDP*.ocr.txt", "cdp*_ocr.txt", "*cdp*.ocr.txt"]:
        files.extend(list(storage_dir.rglob(pattern)))
    
    # Eliminar duplicados manteniendo orden
    seen = set()
    unique_files = []
    for f in sorted(files, key=lambda p: p.name.lower()):
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique_files.append(f)

    print(f"Total archivos OCR de CDP encontrados: {len(unique_files)}")

    report_lines = [
        "# Auditoría y Validación de Saneamiento de CDP sobre Archivos OCR Reales",
        "",
        f"**Fecha de ejecución:** 26 de octubre de 2026  ",
        f"**Total de archivos analizados:** {len(unique_files)}  ",
        "",
        "---",
        "",
        "## Resumen Ejecutivo",
        "",
        "| Métrica | Cantidad |",
        "|---|---|",
    ]

    total_correctos = 0
    sin_codigo_rubro = 0
    sin_nombre_rubro = 0
    casos_a_revisar = []

    detalles = []

    rubro_code_regex = re.compile(r"\b([1-3]\.[0-9]+(?:\.[0-9]+){2,8})\b")

    for fpath in unique_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            content = ""

        # Ejecutar extracción heurística local
        extracted_obj = gemini_service._heuristic_contractor_extraction(content)
        metadata = extracted_obj.model_dump() if hasattr(extracted_obj, "model_dump") else (extracted_obj.dict() if hasattr(extracted_obj, "dict") else dict(extracted_obj))

        
        texto_extraido_bruto = metadata.get("cdp_texto_completo") or ""

        cdp_numero = metadata.get("cdp_numero") or "N/D"
        cdp_rubro = metadata.get("cdp_rubro") or ""
        cdp_rubro_nombre = metadata.get("cdp_rubro_nombre") or ""

        # Aplicar saneador
        texto_limpio = limpiar_texto_cdp(texto_extraido_bruto) if texto_extraido_bruto else ""

        # Validaciones de calidad
        tiene_cod = bool(cdp_rubro or rubro_code_regex.search(texto_limpio))
        tiene_nom = bool(cdp_rubro_nombre and len(cdp_rubro_nombre.strip()) > 3)

        observaciones = []
        if not tiene_cod:
            observaciones.append("Falta código de rubro presupuestal")
            sin_codigo_rubro += 1
        if not tiene_nom:
            observaciones.append("Falta nombre descriptivo del rubro")
            sin_nombre_rubro += 1

        if not observaciones:
            total_correctos += 1
            estado_badge = "✅ CORRECTO"
        else:
            estado_badge = "⚠️ REVISAR"
            casos_a_revisar.append({
                "archivo": fpath.name,
                "motivos": ", ".join(observaciones),
                "numero": cdp_numero
            })

        rel_path = fpath.relative_to(ROOT_DIR)
        detalles.append(f"### {fpath.name} ({estado_badge})")
        detalles.append(f"- **Ubicación:** `{rel_path}`")
        detalles.append(f"- **Número CDP Detectado:** `{cdp_numero}`")
        detalles.append(f"- **Código de Rubro:** `{cdp_rubro or 'No detectado'}`")
        detalles.append(f"- **Nombre de Rubro:** `{cdp_rubro_nombre or 'No detectado'}`")
        if observaciones:
            detalles.append(f"- **Observación:** ⚠️ {', '.join(observaciones)}")
        detalles.append(f"- **Texto Generado/Extraído:**")
        detalles.append(f"  > {texto_extraido_bruto if texto_extraido_bruto else '*(Vacío)*'}")
        detalles.append(f"- **Texto Limpio Final (Saneado):**")
        detalles.append(f"  > **{texto_limpio if texto_limpio else '*(Vacío)*'}**")
        detalles.append("")

    report_lines.append(f"| Archivos con rubro y nombre completos (Correctos) | {total_correctos} |")
    report_lines.append(f"| Archivos con falta de código de rubro | {sin_codigo_rubro} |")
    report_lines.append(f"| Archivos con falta de nombre de rubro | {sin_nombre_rubro} |")
    report_lines.append(f"| Casos que requieren atención | {len(casos_a_revisar)} |")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")

    if casos_a_revisar:
        report_lines.append("## Casos que Requieren Atención")
        report_lines.append("")
        for c in casos_a_revisar:
            report_lines.append(f"- **Archivo:** `{c['archivo']}` | **CDP:** `{c['numero']}` | **Motivo:** {c['motivos']}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    report_lines.append("## Detalle Individual por Archivo")
    report_lines.append("")
    report_lines.extend(detalles)

    out_file = ROOT_DIR / "auditoria_cdp_ocr.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"[OK] Informe de auditoria escrito exitosamente en: {out_file}")
    print(f"Correctos: {total_correctos} / {len(unique_files)}")
    print(f"A revisar: {len(casos_a_revisar)}")


if __name__ == "__main__":
    main()
