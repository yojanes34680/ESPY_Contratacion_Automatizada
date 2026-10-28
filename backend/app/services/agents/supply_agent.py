"""Agente Especializado en Contratos de Suministro y Adquisición de Bienes para ESP."""
from app.services.agents.base_agent import BaseContractAgent
from app.schemas.agent import ContractDraftingInput, ContractDraftingResult
from app.utils.objective_normalizer import normalize_objetivos_especificos

class SupplyContractAgent(BaseContractAgent):
    def __init__(self):
        super().__init__(
            nombre="Agente de Contratos de Suministro",
            tipologia="SUMINISTRO"
        )

    def get_system_instruction(self) -> str:
        return (
            "Eres el Agente Especialista en Contratos de Suministro y Adquisición de Bienes de una Empresa "
            "de Servicios Públicos (ESP) en Colombia.\n"
            "Tu misión es estructurar contratos de suministro de insumos críticos para la operación de acueducto, alcantarillado, "
            "aseo y energía (ej. químicos para potabilización: cloro gas, sulfato de aluminio, PAC, polímeros; tuberías de polietileno, "
            "micromedidores volumétricos, hidrantes, válvulas de control, herramientas operativas y uniformes/EPI).\n\n"
            "REGLAS TÉCNICAS Y NORMATIVAS OBLIGATORIAS:\n"
            "1. OBJETO: Debe precisar la entrega a satisfacción de los bienes, materiales o consumibles con sus especificaciones técnicas de fábrica.\n"
            "2. OBJETIVOS ESPECÍFICOS: Cada objetivo DEBE formularse iniciando OBLIGATORIAMENTE con un VERBO EN INFINITIVO "
            "(ej: 'Suministrar', 'Entregar', 'Verificar', 'Proveer', 'Garantizar', 'Realizar'). Queda prohibido redactar objetivos como sustantivos huérfanos sin acción.\n"
            "3. OBLIGACIONES DEL CONTRATISTA (ESPECÍFICAS Y GENERALES/ADMINISTRATIVAS):\n"
            "   Tu misión es redactar el acápite de 'OBLIGACIONES DEL CONTRATISTA' dividido en Obligaciones Específicas "
            "y Obligaciones Generales/Administrativas, garantizando total trazabilidad y simetría con la 'Descripción de la Necesidad a Satisfacer' "
            "y la propuesta/cotización presentada.\n"
            "   REGLA DE SIMETRÍA Y VERBOS RECTORES:\n"
            "   Toda actividad o bien identificado en la Descripción de la Necesidad debe convertirse en una obligación contractual exigible. "
            "Cada obligación DEBE iniciar con un verbo en infinitivo (Ejecutar, Suministrar, Realizar, Garantizar, Entregar, Presentar) "
            "y redactarse de tal forma que el supervisor pueda verificar su cumplimiento mediante soportes físicos o verificables.\n"
            "   PASO 1 - TRANSFORMACIÓN PARA OBLIGACIONES ESPECÍFICAS:\n"
            "   - SI ES ESCENARIO A (Propuesta Detallada con múltiples ítems >= 3): Aplica la Regla de Inclusión Total. "
            "Convierte el 100% de los bienes propuestos en obligaciones específicas individuales sin omitir ni resumir ninguno.\n"
            "   - SI ES ESCENARIO B (Cotización Escueta o de Una Sola Línea - Ej: 'Suministro global de papelería', 'Insumos de oficina'): "
            "¡PROHIBIDO dejar una sola obligación específica! Desglosa ese renglón en mínimo 6 a 8 obligaciones específicas técnicas y de control: "
            "(1) Obligación principal literal según la cotización; (2) Levantamiento previo de fichas técnicas y especificaciones; "
            "(3) Ejecución de entregas materiales DDP en almacén; (4) Cláusula de calidad total y bienes nuevos de primera calidad con asunción de costos directos e indirectos; "
            "(5) Pruebas técnicas y verificación física con el Almacenista y supervisor; (6) Exigencia de remisiones firmadas, fichas técnicas y certificados como requisito para el pago; "
            "(7) Garantía técnica de fábrica no inferior a 12 meses con reposición en 48 horas.\n"
            "   PASO 2 - OBLIGACIONES GENERALES Y ADMINISTRATIVAS (Blindaje de Supervisión):\n"
            "   Incluye siempre el bloque administrativo estándar: Acta de inicio y liquidación final; informes de ejecución y remisiones; "
            "seguridad social mensual y parafiscales (Art. 50 Ley 789/2002); normas SST en descargue; atención oportuna al supervisor.\n"
            "4. GARANTÍAS: Póliza de Calidad y Correcto Funcionamiento de los Bienes (20% por mínimo 1 año), Cumplimiento (20%), "
            "y Transporte de mercancías si aplica.\n"
            "5. JUSTIFICACIÓN DE LA NECESIDAD: Redacta obligatoriamente la sección 'DESCRIPCIÓN DE LA NECESIDAD A SATISFACER' "
            "aplicando rigurosamente 'El Método del Embudo' en 3 niveles: "
            "Nivel 1 (Marco institucional Ley 142 de 1994 y continuidad de los servicios públicos; aplicando la Regla de Oro: Prohibido mencionar acueducto y alcantarillado si el suministro es de aseo, PGIRS o áreas administrativas, y viceversa), "
            "Nivel 2 (Justificación de insuficiencia interna de almacén: insertar textualmente el siguiente párrafo exacto: 'Actualmente, la ESPY presenta agotamiento en las existencias de su almacén y no produce por sí misma los bienes, materiales e insumos requeridos para el desarrollo normal de sus operaciones; razón por la cual resulta necesario acudir a la contratación externa de suministro con el fin de garantizar los principios de eficacia, economía y celeridad de la función administrativa consagrados en el artículo 209 de la Constitución Política.'), y "
            "Nivel 3 (Requerimiento exacto detallado: traduciendo al lenguaje de necesidad institucional mediante lista con viñetas con el 100% de los bienes e insumos sin resumir ni omitir nada, bajo la fórmula obligatoria: "
            "'Por consiguiente, surge la necesidad imperiosa de adquirir los siguientes bienes e insumos para garantizar la continuidad operativa:\\n- [Lista exhaustiva del 100% de bienes/cantidades]'). "
            "Regla de tono: Nunca redactar en primera persona ni 'el proponente cotiza'. Redactar desde la perspectiva de la entidad: 'La ESPY requiere adquirir...'. "
            "Regla de discriminación: Las viñetas del Nivel 3 deben contener exclusivamente los bienes o insumos cotizados con sus cantidades. NUNCA incluyas títulos de secciones, encabezados de estudios de mercado ni líneas de cuadros comparativos.\n"
            "6. OBLIGACIONES DE LA EMPRESA (ESPY S.A. E.S.P.) PARA LA MINUTA DEL CONTRATO:\n"
            "   Debes formular obligatoriamente en el campo 'obligaciones_empresa' las obligaciones institucionales a cargo de LA EMPRESA "
            "adaptadas rigurosamente a la tipología de SUMINISTRO (mínimo 5 a 7 obligaciones):\n"
            "   a) Designar al supervisor técnico del contrato y al funcionario de Almacén General encargado de la recepción, inspección física y pruebas de los bienes.\n"
            "   b) Recibir los bienes e insumos en las bodegas o Almacén General de LA EMPRESA siempre que cumplan a cabalidad con las cantidades, especificaciones técnicas de fábrica y condiciones de empaque y rotulado.\n"
            "   c) Suscribir formalmente el Acta de Entrada al Almacén y Recibo a Satisfacción una vez verificada la conformidad técnica de los bienes, o notificar por escrito al proveedor cualquier inconformidad, daño o faltante dentro de las cuarenta y ocho (48) horas siguientes a la entrega.\n"
            "   d) Tramitar y pagar el valor de los bienes suministrados en los plazos y cuentas convenidas, previa radicación de la factura electrónica validada por la DIAN, acta de entrada al almacén y constancias de pago de seguridad social y parafiscales.\n"
            "   e) Brindar al transportador o personal del proveedor las facilidades logísticas y de acceso necesarias en las bodegas de la entidad para el adecuado descargue de los elementos.\n"
            "   f) Suscribir oportunamente en debida forma las actas de recibo y el Acta de Liquidación Definitiva del contrato de suministro."

        )

    def build_user_prompt(self, input_data: ContractDraftingInput) -> str:
        return (
            f"Estructura el contrato de suministro con los siguientes datos:\n"
            f"- Descripción de los bienes/insumos: {input_data.necesidad_descripcion}\n"
            f"- Especificaciones o cantidades: {input_data.alcance_esperado or 'Según ficha técnica y cuadro de cantidades anexo'}\n"
            f"- Presupuesto estimado: ${int(round(input_data.valor_estimado)):,}".replace(",", ".") + " COP\n"
            f"- Plazo de entrega: {input_data.plazo} {input_data.unidad_plazo}\n"
            f"- Datos del proveedor: {input_data.datos_contratista_contexto or 'Por definir'}\n\n"
            f"Genera el JSON completo con objeto de suministro, justificación orientada a insumos de operación continua, "
            f"objetivos de abastecimiento (cada objetivo específico DEBE iniciar con un verbo de acción en infinitivo como Suministrar, Entregar o Verificar), "
            f"obligaciones de almacén/fábrica para estudio previo y minuta, "
            f"las obligaciones de LA EMPRESA adaptadas específicamente al contrato de suministro (inspección de almacén, suscripción de acta de entrada, trámite de pago contra factura electrónica DIAN, facilidades de descargue y liquidación), "
            f"y garantías de calidad."
        )

    def fallback_generator(self, input_data: ContractDraftingInput) -> ContractDraftingResult:
        necesidad = input_data.necesidad_descripcion.strip()
        plazo = f"{input_data.plazo} {input_data.unidad_plazo.lower() if input_data.unidad_plazo else 'meses'}"

        from app.utils.objeto_builder import build_objeto_contractual
        objeto = build_objeto_contractual(
            propuesta_o_cotizacion=necesidad,
            tipologia="SUMINISTRO",
            necesidad_descripcion=necesidad,
            contexto=necesidad
        )

        nivel_ext = getattr(input_data, "nivel_extension", "MEDIA") or "MEDIA"
        instr_adic = getattr(input_data, "instrucciones_adicionales", None)
        prop_items = getattr(input_data, "propuesta_items", None)

        from app.utils.necesidad_builder import build_descripcion_necesidad

        justificacion = build_descripcion_necesidad(
            objeto=objeto,
            tipologia="SUMINISTRO",
            contexto_adicional=necesidad,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic,
            propuesta_items=prop_items
        )

        from app.utils.objetivos_builder import build_objetivos_contrato

        obj_data = build_objetivos_contrato(
            objeto=objeto,
            tipologia="SUMINISTRO",
            contexto=necesidad,
            items_propuesta=prop_items,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )
        objetivo_general = obj_data["objetivo_general"]
        objetivos_especificos = obj_data["objetivos_especificos"]

        from app.utils.obligaciones_builder import build_obligaciones_contratista

        oblig_res = build_obligaciones_contratista(
            objeto=objeto,
            tipologia="SUMINISTRO",
            items_propuesta=prop_items,
            contexto_adicional=necesidad,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )
        obligaciones_estudio_previo = oblig_res["obligaciones_estudio_previo"]
        obligaciones_minuta = oblig_res["obligaciones_minuta"]

        from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa

        tipo_p = "JURIDICA" if input_data.datos_contratista_contexto and str(input_data.datos_contratista_contexto.get("tipo_persona") or "").upper() in ["JURIDICA", "JURÍDICA", "NIT"] else "NATURAL"
        obligaciones_empresa = build_obligaciones_empresa(
            objeto=objeto,
            tipologia="SUMINISTRO",
            plazo_str=plazo,
            plazo_val=input_data.plazo,
            unidad_plazo=input_data.unidad_plazo,
            tipo_persona=tipo_p,
            obligaciones_contratista=obligaciones_minuta,
            contexto_adicional=necesidad,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )

        garantias_sugeridas = {
            "cumplimiento": {"porcentaje": 20, "vigencia": f"Plazo contractual ({plazo}) y cuatro (4) meses más"},
            "calidad_bienes": {"porcentaje": 20, "vigencia": "Un (1) año contado a partir del acta de recibo a satisfacción en almacén"},
            "correcto_funcionamiento": {"porcentaje": 10, "vigencia": "Un (1) año a partir de la entrega formal"}
        }

        clausulas_especiales = [
            "CONDICIONES DE RECIBO A SATISFACCIÓN Y ALMACÉN: La recepción de los bienes se formalizará únicamente mediante el Acta de Entrada al Almacén, debidamente suscrita por el Almacenista y el Supervisor tras la inspección física y técnica.",
            "GARANTÍA DE FÁBRICA Y REPOSICIÓN: El contratista responderá por los defectos de fabricación o vicios ocultos de los bienes entregados por un lapso no inferior a doce (12) meses, obligándose a su reposición inmediata sin costo para la ESP.",
            "FLETES Y TRANSPORTE: Todos los gastos de embalaje, fletes, peajes, póliza de transporte y descargue en el lugar de destino pactado serán de cuenta exclusiva del contratista."
        ]

        marco_juridico = (
            "El presente Contrato de Suministro se fundamenta en el siguiente marco normativo y comercial:\n"
            "1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994, Artículos 31 y 32 (actos y contratos regidos por el derecho privado y comercial de las ESP).\n"
            "2. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (moralidad, celeridad, eficacia, economía e imparcialidad).\n"
            "3. CONTRATO MERCANTIL DE SUMINISTRO: Código de Comercio de Colombia, Artículos 968 a 980 (prestaciones periódicas o continuadas de cosas o insumos a favor de la ESP, fijación de precios, plazos de entrega y resolución contractual).\n"
            "4. RÉGIMEN DE COMPRAVENTA MERCANTIL: Código de Comercio, Artículos 905 y concordantes; deber legal de entrega material en almacén, transferencia de dominio, saneamiento por evicción y garantía de indemnidad por vicios redhibitorios u ocultos (Art. 934 C.Co.).\n"
            "5. CONTROL DE CALIDAD DEL AGUA Y REACTIVOS QUÍMICOS: Decreto 1575 de 2007 y Resolución 2115 de 2007 del Ministerio de la Protección Social y de Ambiente (especificaciones fisicoquímicas, pureza de coagulantes y desinfectantes para potabilización de agua apta para consumo humano).\n"
            "6. SISTEMA GLOBALMENTE ARMONIZADO (SGA): Ley 55 de 1993 y Decreto 1496 de 2018 (etiquetado de seguridad, pictogramas y Fichas de Datos de Seguridad - MSDS obligatorias para reactivos y sustancias químicas).\n"
            "7. NORMAS TÉCNICAS COLOMBIANAS E INTERNACIONALES: Normas NTC, AWWA e ISO 4064 para micromedición, accesorios de polietileno/PVC y válvulas de control de acueducto.\n"
            "8. CONDICIÓN DE ENTREGA DDP: Entrega de bienes en el Almacén General de la ESP bajo condición DDP (Delivered Duty Paid), con cargue, transporte, seguros y descargue a cargo exclusivo del contratista.\n"
            "9. INHABILIDADES Y MANUAL INTERNO: Artículo 8 Ley 80 de 1993, Sentencia C-066/97 de la Corte Constitucional y Manual Interno de Contratación de la ESPY."
        )

        return ContractDraftingResult(
            tipologia="SUMINISTRO",
            agente_nombre=self.nombre,
            objeto=objeto,
            justificacion_necesidad=justificacion,
            marco_juridico=marco_juridico,
            objetivo_general=objetivo_general,
            objetivos_especificos=normalize_objetivos_especificos(objetivos_especificos),
            obligaciones_estudio_previo=obligaciones_estudio_previo,
            obligaciones_minuta=obligaciones_minuta,
            obligaciones_empresa=obligaciones_empresa,
            garantias_sugeridas=garantias_sugeridas,
            clausulas_especiales=clausulas_especiales,
            observaciones_juridicas="Contrato de suministro de bienes. Obligatoria acta de entrada al almacén y póliza de calidad de bienes por mínimo 12 meses."
        )
