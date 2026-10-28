import os
import sys
from pathlib import Path
import docx

# Add backend to path
sys.path.insert(0, str(Path("backend").resolve()))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.database import SessionLocal
from app.models.contract import Contrato
from app.services.docx_engine import generate_docx_for_contract
from app.services.agents.apu_agent import apu_agent

def test_incorporacion_estudio_mercado_en_estudio_previo():
    db = SessionLocal()
    try:
        # 1. Obtener un contrato de prueba existente
        contrato = db.query(Contrato).first()
        assert contrato is not None, "Debe haber al menos un contrato en la base de datos para la prueba."
        print(f"\n[TEST] Usando contrato ID={contrato.id}, Nro={contrato.numero_contrato}")

        # Guardar estado original
        original_estudio = contrato.estudio_mercado
        original_meta = dict(contrato.metadatos_agente or {})

        # =====================================================================
        # CASO 1: Contrato SIN Estudio de Mercado
        # =====================================================================
        print("\n--- CASO 1: Generación de Estudio Previo SIN Estudio de Mercado ---")
        contrato.estudio_mercado = None
        if "estudio_mercado" in original_meta:
            del original_meta["estudio_mercado"]
        original_meta["tiene_estudio_mercado"] = False
        contrato.metadatos_agente = original_meta
        db.commit()
        db.refresh(contrato)

        doc_path_sin = generate_docx_for_contract(contrato, "ESTUDIO_PREVIO")
        print(f"Documento generado (sin estudio): {doc_path_sin}")

        doc_sin = docx.Document(str(doc_path_sin))
        textos_sin = [p.text for p in doc_sin.paragraphs]
        all_text_sin = "\n".join(textos_sin)

        # Verificación estricta: NO debe existir el subtítulo ni el acápite
        assert "ANALISIS DE LAS PROPUESTAS DE MERCADO:" not in all_text_sin, (
            "ERROR: 'ANALISIS DE LAS PROPUESTAS DE MERCADO:' no debería aparecer en un contrato sin estudio de mercado."
        )
        print("✓ Confirmado: 'ANALISIS DE LAS PROPUESTAS DE MERCADO:' NO aparece en contratos que no lo requieren.")

        # =====================================================================
        # CASO 2: Contrato CON Estudio de Mercado Incorporado
        # =====================================================================
        print("\n--- CASO 2: Generación de Estudio Previo CON Estudio de Mercado ---")
        mock_estudio = {
            "proceso_config": {
                "objeto_contractual": contrato.objeto or "COMPRAVENTA Y SUMINISTRO DE MATERIALES",
                "tipo_contrato": "Suministro",
                "criterio_seleccion": "Menor precio global del mercado previa auditoría aritmética.",
                "fecha_proceso": "Octubre de 2026",
                "evaluador_nombre": "JOAN ALVAREZ CORREA",
                "evaluador_cargo": "Auxiliar de Contratación"
            },
            "ofertas": [
                {
                    "nombre_razon_social": "DISTRIBUCIONES DEL NORTE S.A.S.",
                    "nit": "900.123.456-7",
                    "representante_legal": "CARLOS MARIO PEREZ",
                    "domicilio": "Yolombó, Antioquia",
                    "valor_total_leido": 24500000.0,
                    "valor_total_corregido": 24500000.0,
                    "diferencia_aritmetica": 0.0,
                    "presenta_inconsistencias": False,
                    "es_ganador": True,
                    "items": [
                        {
                            "item_num": 1,
                            "descripcion": "CEMENTO GRIS TIPO UG BULTO X 50KG",
                            "unidad": "BULTO",
                            "cantidad": 300.0,
                            "precio_unitario": 35000.0,
                            "precio_total": 10500000.0,
                            "apu_componente_a_materiales": 28000.0,
                            "apu_componente_b_mano_obra": 3500.0,
                            "apu_componente_c_transporte_equipos": 3500.0
                        },
                        {
                            "item_num": 2,
                            "descripcion": "ARENA DE PEÑA SELECCIONADA POR M3",
                            "unidad": "M3",
                            "cantidad": 200.0,
                            "precio_unitario": 70000.0,
                            "precio_total": 14000000.0,
                            "apu_componente_a_materiales": 50000.0,
                            "apu_componente_b_mano_obra": 8000.0,
                            "apu_componente_c_transporte_equipos": 12000.0
                        }
                    ]
                },
                {
                    "nombre_razon_social": "FERRETERÍA LA PRINCIPAL S.A.S.",
                    "nit": "901.987.654-3",
                    "representante_legal": "ANA MARIA RESTREPO",
                    "domicilio": "Yolombó, Antioquia",
                    "valor_total_leido": 26800000.0,
                    "valor_total_corregido": 26800000.0,
                    "diferencia_aritmetica": 0.0,
                    "presenta_inconsistencias": False,
                    "es_ganador": False,
                    "items": []
                }
            ],
            "proponente_ganador": {
                "nombre_razon_social": "DISTRIBUCIONES DEL NORTE S.A.S.",
                "nit": "900.123.456-7"
            },
            "valor_total_adjudicado": 24500000.0,
            "items_apu": [
                {
                    "item_num": 1,
                    "descripcion": "CEMENTO GRIS TIPO UG BULTO X 50KG",
                    "unidad": "BULTO",
                    "cantidad": 300.0,
                    "precio_unitario": 35000.0,
                    "precio_total": 10500000.0,
                    "costo_materiales": 28000.0,
                    "costo_mano_obra": 3500.0,
                    "costo_transporte_equipos": 3500.0
                },
                {
                    "item_num": 2,
                    "descripcion": "ARENA DE PEÑA SELECCIONADA POR M3",
                    "unidad": "M3",
                    "cantidad": 200.0,
                    "precio_unitario": 70000.0,
                    "precio_total": 14000000.0,
                    "costo_materiales": 50000.0,
                    "costo_mano_obra": 8000.0,
                    "costo_transporte_equipos": 12000.0
                }
            ]
        }

        contrato.estudio_mercado = mock_estudio
        meta_con = dict(contrato.metadatos_agente or {})
        meta_con["tiene_estudio_mercado"] = True
        meta_con["estudio_mercado"] = mock_estudio
        contrato.metadatos_agente = meta_con
        db.commit()
        db.refresh(contrato)

        doc_path_con = generate_docx_for_contract(contrato, "ESTUDIO_PREVIO")
        print(f"Documento generado (con estudio): {doc_path_con}")

        doc_con = docx.Document(str(doc_path_con))
        textos_con = [p.text for p in doc_con.paragraphs]
        all_text_con = "\n".join(textos_con)

        # 1. Verificar presencia exacta del subtítulo
        target_subtitulo = "ANALISIS DE LAS PROPUESTAS DE MERCADO:"
        assert target_subtitulo in all_text_con, (
            f"ERROR: No se encontró el subtítulo '{target_subtitulo}' en el Estudio Previo generado."
        )
        print(f"✓ Confirmado: Subtítulo '{target_subtitulo}' presente en el documento.")

        # 2. Verificar ubicación: DEBE estar DESPUÉS de las obligaciones del contratista
        # Encontrar índice del subtítulo
        idx_subtitulo = -1
        idx_obligaciones = -1
        for idx, text in enumerate(textos_con):
            if "OBLIGACIONES DEL CONTRATISTA" in text.upper() or "OBLIGACIONES ESPECIFICAS" in text.upper() or "OBLIGACIONES:" in text.upper():
                if idx_obligaciones == -1:
                    idx_obligaciones = idx
            if target_subtitulo in text:
                idx_subtitulo = idx

        print(f"Índice obligaciones: {idx_obligaciones}, Índice subtítulo: {idx_subtitulo}")
        assert idx_subtitulo != -1, "El subtítulo debe existir en los párrafos."
        if idx_obligaciones != -1:
            assert idx_subtitulo > idx_obligaciones, (
                f"ERROR: El subtítulo (índice {idx_subtitulo}) no está después de las obligaciones (índice {idx_obligaciones})."
            )
            print("✓ Confirmado: El subtítulo aparece estrictamente DESPUÉS de las obligaciones del contratista.")

        # 3. Verificar contenido resumido del análisis (oferente ganador, cotizaciones, desglose APU)
        assert "DISTRIBUCIONES DEL NORTE S.A.S." in all_text_con, "El proponente ganador debe estar citado en el texto."
        assert "Componente A" in all_text_con or "Materiales" in all_text_con, "Debe contener el desglose de componentes APU."
        
        # Verificar que se generó la tabla comparativa de cotizaciones
        tablas_text = "\n".join([" | ".join([c.text.strip() for c in r.cells]) for t in doc_con.tables for r in t.rows])
        assert "DISTRIBUCIONES DEL NORTE S.A.S." in tablas_text, "La tabla comparativa debe contener a los oferentes evaluados."
        assert "FERRETERÍA LA PRINCIPAL S.A.S." in tablas_text, "La tabla comparativa debe contener las ofertas del mercado."
        print("✓ Confirmado: Las tablas comparativas de cotizaciones y desglose de precios están presentes y formateadas.")

        # =====================================================================
        # CASO 3: Desvinculación de Estudio de Mercado
        # =====================================================================
        print("\n--- CASO 3: Desvinculación y Verificación de Ausencia ---")
        contrato.estudio_mercado = None
        meta_desv = dict(contrato.metadatos_agente or {})
        meta_desv["tiene_estudio_mercado"] = False
        if "estudio_mercado" in meta_desv:
            del meta_desv["estudio_mercado"]
        contrato.metadatos_agente = meta_desv
        db.commit()
        db.refresh(contrato)

        doc_path_desv = generate_docx_for_contract(contrato, "ESTUDIO_PREVIO")
        doc_desv = docx.Document(str(doc_path_desv))
        all_text_desv = "\n".join(p.text for p in doc_desv.paragraphs)

        assert target_subtitulo not in all_text_desv, (
            "ERROR: Tras desvincular el estudio, el subtítulo volvió a aparecer."
        )
        print("✓ Confirmado: Al desvincular, el Estudio Previo queda limpio sin el acápite.")

        # Restaurar estado original del contrato
        contrato.estudio_mercado = original_estudio
        contrato.metadatos_agente = original_meta
        db.commit()
        print("\n=== ¡TODAS LAS PRUEBAS DE INCORPORACIÓN DEL ESTUDIO DE MERCADO PASARON EXITOSAMENTE! ===")

    finally:
        db.close()

if __name__ == "__main__":
    test_incorporacion_estudio_mercado_en_estudio_previo()
