import sys
import json
import os
from pathlib import Path

# Configurar path al backend
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import settings
from app.schemas.unspsc import UnspscAnalysisInput

def run_evaluation():
    casos_file = backend_path / "tests" / "unspsc_eval" / "casos.json"
    if not casos_file.exists():
        print(f"Error: No se encontró {casos_file}")
        return

    with open(casos_file, "r", encoding="utf-8") as f:
        casos = json.load(f)

    # Cargar línea base para comparación
    baseline_path = backend_path / "tests" / "unspsc_eval" / "baseline_report.json"
    baseline_data = {}
    if baseline_path.exists():
        try:
            with open(baseline_path, "r", encoding="utf-8") as f_b:
                baseline_data = json.load(f_b)
        except Exception:
            pass

    motor = os.getenv("UNSPSC_MOTOR", settings.UNSPSC_MOTOR)

    print(f"\n=======================================================")
    print(f"   EVALUACIÓN DE AGENTE UNSPSC - {len(casos)} CASOS DE PRUEBA")
    print(f"   MOTOR ACTIVO: {motor.upper()} | GEMINI_MODEL: {settings.GEMINI_MODEL}")
    print(f"=======================================================\n")

    if motor == "nuevo":
        from app.services.agents.unspsc.selector import unspsc_selector_agent
        agent_runner = unspsc_selector_agent
    else:
        from app.services.agents.unspsc_agent import unspsc_agent
        agent_runner = unspsc_agent

    total_casos = len(casos)
    top1_hits = 0
    total_esperados = 0
    total_recuperados = 0
    total_prohibidos_hallados = 0

    detalles = []

    for idx, c in enumerate(casos, start=1):
        caso_id = c.get("id", f"caso_{idx}")
        nombre = c.get("nombre", caso_id)
        objeto = c.get("objeto", "")
        estudio_previo = c.get("estudio_previo", "")
        propuesta = c.get("propuesta_economica", "")
        codigos_esperados = set(c.get("codigos_esperados", []))
        codigos_prohibidos = set(c.get("codigos_prohibidos", []))

        tipologia = "SUMINISTRO" if "suministro" in objeto.lower() else "SERVICIOS"

        inp = UnspscAnalysisInput(
            objeto=objeto,
            estudio_previo=estudio_previo,
            propuesta_economica=propuesta
        )

        try:
            result = agent_runner.analyze_contract_unspsc(inp)
            codigos_obtenidos = [item.codigo_unspsc for item in result.codigos_seleccionados]
            objeto_det = result.objeto_detectado or ""
            actividades_ext = result.actividades_propuesta_extraidas or []
            motor_usado = getattr(result, "motor_usado", motor)
            uso_ia = getattr(result, "uso_ia", False)
        except Exception as e:
            print(f"[{idx}/{total_casos}] ERROR en {caso_id}: {e}")
            codigos_obtenidos = []
            objeto_det = "ERROR"
            actividades_ext = []
            motor_usado = motor
            uso_ia = False

        # Métricas individuales
        top1_ok = False
        if codigos_obtenidos and codigos_esperados:
            top1_ok = codigos_obtenidos[0] in codigos_esperados
            if top1_ok:
                top1_hits += 1

        encontrados = set(codigos_obtenidos) & codigos_esperados
        sobrantes = set(codigos_obtenidos) - codigos_esperados
        prohibidos = set(codigos_obtenidos) & codigos_prohibidos
        if prohibidos:
            total_prohibidos_hallados += len(prohibidos)

        total_esperados += len(codigos_esperados)
        total_recuperados += len(encontrados)

        recall_caso = (len(encontrados) / len(codigos_esperados)) if codigos_esperados else 0.0

        detalles.append({
            "id": caso_id,
            "nombre": nombre,
            "top1_ok": top1_ok,
            "codigos_obtenidos": codigos_obtenidos,
            "codigos_esperados": list(codigos_esperados),
            "encontrados": list(encontrados),
            "sobrantes": list(sobrantes),
            "prohibidos_detectados": list(prohibidos),
            "recall": recall_caso,
            "objeto_detectado": objeto_det,
            "actividades_extraidas": actividades_ext,
            "motor_usado": motor_usado,
            "uso_ia": uso_ia
        })

        estado_top1 = "[OK] TOP 1" if top1_ok else "[FALLO] TOP 1"
        print(f"[{idx}/{total_casos}] {nombre} (Motor: {motor_usado} | IA: {uso_ia})")
        print(f"       Objeto Detectado: {objeto_det}")
        print(f"       Ítems/Actividades: {actividades_ext}")
        print(f"       {estado_top1} | Recall: {len(encontrados)}/{len(codigos_esperados)} ({recall_caso*100:.1f}%) | Sobrantes: {len(sobrantes)}")
        print(f"       Códigos Obtenidos: {codigos_obtenidos}")
        print(f"       Códigos Esperados: {list(codigos_esperados)}")
        if prohibidos:
            print(f"       ALERTA PROHIBIDOS: {list(prohibidos)}")
        print("-" * 55)

    # Consolidado
    pct_top1 = (top1_hits / total_casos) * 100 if total_casos else 0
    global_recall = (total_recuperados / total_esperados) * 100 if total_esperados else 0

    print("\n=======================================================")
    print("                TABLA RESUMEN POR CASO                 ")
    print("=======================================================")
    header = f"{'Caso':<32} | {'Top 1':<7} | {'Recall':<8} | {'Sobrantes':<9} | {'Prohibidos':<10}"
    print(header)
    print("-" * len(header))
    for d in detalles:
        t1_str = "OK" if d["top1_ok"] else "FAIL"
        rec_str = f"{d['recall']*100:.1f}%"
        sob_str = str(len(d["sobrantes"]))
        proh_str = str(len(d["prohibidos_detectados"]))
        print(f"{d['id'][:32]:<32} | {t1_str:<7} | {rec_str:<8} | {sob_str:<9} | {proh_str:<10}")

    print("\n=======================================================")
    print("      COMPARACIÓN CON LÍNEA BASE (baseline_report.json)")
    print("=======================================================")
    b_top1 = baseline_data.get("acierto_top1_pct", 16.7)
    b_recall = baseline_data.get("recall_global_pct", 31.8)
    b_prohibidos = baseline_data.get("codigos_prohibidos_total", 3)

    print(f"Métrica                      | Línea Base | Resultado Actual | Diferencia")
    print("-" * 70)
    print(f"Acierto Top 1                | {b_top1:6.1f}%   | {pct_top1:12.1f}%   | {pct_top1 - b_top1:+6.1f}%")
    print(f"Recall Global                | {b_recall:6.1f}%   | {global_recall:12.1f}%   | {global_recall - b_recall:+6.1f}%")
    print(f"Códigos Prohibidos Hallados  | {b_prohibidos:6d}    | {total_prohibidos_hallados:12d}    | {total_prohibidos_hallados - b_prohibidos:+6d}")
    print("=======================================================\n")

    # Guardar reporte de evaluación sin pisar baseline_report.json
    eval_report_path = backend_path / "tests" / "unspsc_eval" / "evaluation_report.json"
    reporte = {
        "motor_evaluado": motor,
        "total_casos": total_casos,
        "acierto_top1_pct": pct_top1,
        "recall_global_pct": global_recall,
        "codigos_prohibidos_total": total_prohibidos_hallados,
        "detalles": detalles
    }
    with open(eval_report_path, "w", encoding="utf-8") as f:
        json.dump(reporte, f, indent=2, ensure_ascii=False)
    print(f"Reporte de evaluación guardado en: {eval_report_path}")

if __name__ == "__main__":
    run_evaluation()
