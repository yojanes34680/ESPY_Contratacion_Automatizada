"""Prueba exhaustiva para la Regla de Oro y la Estructura en 3 Apartados del Agente de Adiciones."""
import os
import sys

# Asegurar backend en sys.path
sys.path.insert(0, os.path.abspath("backend"))

from app.services.agents.addition_agent import addition_agent
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_addition_agent():
    print("=" * 60)
    print("INICIANDO PRUEBAS DE LA REGLA DE ORO DEL AGENTE DE ADICIONES")
    print("=" * 60)

    # -------------------------------------------------------------
    # PRUEBA 1: Detención obligatoria si falta motivo técnico específico
    # -------------------------------------------------------------
    print("\n1. Probando detención ante causas vacías o genéricas (Regla de Oro)...")
    val_empty = addition_agent.validate_requirements(
        tipologia="SUMINISTRO",
        objeto_contrato="Suministro de insumos químicos para la potabilización del agua",
        valor_adicion=13200000.0,
        razon_tecnica=""
    )
    assert not val_empty["valid"], "Debe rechazar motivo vacío"
    assert "razon_tecnica_especifica" in val_empty["missing_fields"]
    print("   -> Motivo vacío rechazado correctamente.")

    val_generic = addition_agent.validate_requirements(
        tipologia="SUMINISTRO",
        objeto_contrato="Suministro de insumos químicos para la potabilización del agua",
        valor_adicion=13200000.0,
        razon_tecnica="Agotamiento del inventario operativo"
    )
    assert not val_generic["valid"], "Debe rechazar frase genérica prohibida"
    print("   -> Frase genérica 'Agotamiento del inventario operativo' rechazada correctamente.")

    # Verificar que generate_justification se detiene y formula las 4 preguntas
    detencion_texto = addition_agent.generate_justification(
        numero_contrato="CS-004-2026",
        objeto_contrato="Suministro de insumos químicos para la potabilización del agua",
        tipologia="SUMINISTRO",
        valor_adicion=13200000.0,
        razon_tecnica=""
    )
    assert "¿Cuál es el tipo de contrato?" in detencion_texto
    assert "¿Cuál es el objeto del contrato?" in detencion_texto
    assert "¿Cuál es la razón técnica y específica" in detencion_texto
    assert "¿Cuál es el valor a adicionar?" in detencion_texto
    print("   -> El Agente se detuvo y preguntó los 4 datos técnicos obligatorios.")

    # -------------------------------------------------------------
    # PRUEBA 2: Generación en 3 apartados para SUMINISTRO con motivo real
    # -------------------------------------------------------------
    print("\n2. Probando generación para SUMINISTRO con motivo específico real...")
    motivo_suministro = "Aumentó la turbiedad del río por temporada de lluvias y se necesitó más sulfato de aluminio"
    just_suministro = addition_agent.generate_justification(
        numero_contrato="CS-004-2026",
        objeto_contrato="Suministro de insumos químicos para la planta de tratamiento de agua potable",
        tipologia="SUMINISTRO",
        valor_adicion=13200000.0,
        razon_tecnica=motivo_suministro
    )
    
    assert "1. Contexto Contractual (Hechos):" in just_suministro, "Debe contener el Apartado 1"
    assert "2. Justificación Técnica Específica" in just_suministro, "Debe contener el Apartado 2"
    assert "3. Justificación Jurídica y Financiera (Soporte Legal):" in just_suministro, "Debe contener el Apartado 3"
    assert "sulfato de aluminio" in just_suministro.lower(), "Debe incorporar la causa específica del usuario"
    assert "fluctuaciones de la demanda" in just_suministro.lower(), "Debe enfocar en fluctuaciones de demanda"
    assert "stock" in just_suministro.lower(), "Debe enfocar en stock para garantizar el servicio"
    assert "Ley 142 de 1994" in just_suministro, "Debe citar la Ley 142 de 1994"
    assert "permanece inalterable" in just_suministro.lower(), "Debe certificar objeto inalterable"
    print("   -> Apartados 1, 2 y 3 para Suministro estructurados exitosamente.")

    # -------------------------------------------------------------
    # PRUEBA 3: Generación en 3 apartados para OBRA
    # -------------------------------------------------------------
    print("\n3. Probando generación para OBRA...")
    motivo_obra = "Se encontraron cantidades de obra no previstas en la excavación de la red matriz de acueducto"
    just_obra = addition_agent.generate_justification(
        numero_contrato="CO-010-2026",
        objeto_contrato="Construcción y optimización de redes de acueducto y alcantarillado",
        tipologia="OBRA",
        valor_adicion=25000000.0,
        razon_tecnica=motivo_obra
    )
    assert "1. Contexto Contractual" in just_obra
    assert "2. Justificación Técnica Específica" in just_obra
    assert "3. Justificación Jurídica y Financiera" in just_obra
    assert "mayores cantidades de obra" in just_obra.lower(), "Debe enfocar en mayores cantidades de obra"
    assert "excavación" in just_obra.lower(), "Debe incorporar el motivo del usuario"
    print("   -> Estructuración para Obra validada exitosamente.")

    # -------------------------------------------------------------
    # PRUEBA 4: Generación en 3 apartados para PRESTACIÓN DE SERVICIOS
    # -------------------------------------------------------------
    print("\n4. Probando generación para PRESTACIÓN DE SERVICIOS...")
    motivo_servicios = "Se requiere extender el servicio por 2 meses más debido al incremento de operativos en campo"
    just_servicios = addition_agent.generate_justification(
        numero_contrato="CPS-020-2026",
        objeto_contrato="Prestación de servicios de apoyo técnico y operativo a la gestión comercial",
        tipologia="PRESTACION_SERVICIOS",
        valor_adicion=8500000.0,
        razon_tecnica=motivo_servicios
    )
    assert "carga operativa" in just_servicios.lower()
    assert "continuidad" in just_servicios.lower()
    assert "2 meses más" in just_servicios.lower()
    print("   -> Estructuración para Prestación de Servicios validada exitosamente.")

    # -------------------------------------------------------------
    # PRUEBA 5: Endpoint API /api/additions/generate-justification
    # -------------------------------------------------------------
    print("\n5. Probando API /api/additions/generate-justification...")
    resp_list = client.get("/api/additions/contracts-list")
    c_id = resp_list.json()[0]["id"]

    # 5.1 Caso sin motivo -> Debe responder requires_information
    resp_req = client.post("/api/additions/generate-justification", json={
        "contrato_id": c_id,
        "valor_adicion": 13200000.0,
        "necesidad_usuario": ""
    })
    assert resp_req.status_code == 200
    data_req = resp_req.json()
    assert data_req["status"] == "requires_information"
    assert len(data_req["preguntas_obligatorias"]) == 4
    print("   -> API detiene y pregunta correctamente si falta motivo técnico.")

    # 5.2 Caso con motivo específico -> Debe generar 3 apartados
    resp_ok = client.post("/api/additions/generate-justification", json={
        "contrato_id": c_id,
        "valor_adicion": 13200000.0,
        "necesidad_usuario": "Aumentó la turbiedad del río y se necesitó más sulfato"
    })
    assert resp_ok.status_code == 200
    data_ok = resp_ok.json()
    assert data_ok["status"] == "success"
    assert "1. Contexto Contractual (Hechos):" in data_ok["justificacion"]
    assert "2. Justificación Técnica Específica" in data_ok["justificacion"]
    assert "3. Justificación Jurídica y Financiera (Soporte Legal):" in data_ok["justificacion"]
    print("   -> API genera justificación en 3 apartados con éxito.")

    print("\n" + "=" * 60)
    print(">>> TODAS LAS PRUEBAS DE LA REGLA DE ORO PASARON CON ÉXITO (100%)")
    print("=" * 60)

if __name__ == "__main__":
    test_addition_agent()
