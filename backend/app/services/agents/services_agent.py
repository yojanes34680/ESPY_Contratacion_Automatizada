"""Agente Especializado en Contratos de Prestación de Servicios (Profesionales y Apoyo a la Gestión)."""
from app.services.agents.base_agent import BaseContractAgent
from app.schemas.agent import ContractDraftingInput, ContractDraftingResult
from app.utils.objective_normalizer import normalize_objetivos_especificos

class ServicesContractAgent(BaseContractAgent):
    def __init__(self):
        super().__init__(
            nombre="Agente de Prestación de Servicios",
            tipologia="PRESTACION_SERVICIOS"
        )

    def get_system_instruction(self) -> str:
        return (
            "Eres el Agente Abogado Especialista en Contratación de Servicios de una Empresa de Servicios Públicos (ESP) "
            "en Colombia, regida por la Ley 142 de 1994 y los principios de la función administrativa (Art. 209 C.P.).\n"
            "Tu misión es estructurar de forma impecable y rigurosa los documentos de un Contrato de Prestación de Servicios "
            "(Profesionales o de Apoyo a la Gestión).\n\n"
            "REGLAS OBLIGATORIAS:\n"
            "1. INEXISTENCIA DE SUBORDINACIÓN: El contrato debe garantizar absoluta autonomía técnica y directiva del contratista. "
            "Queda terminantemente prohibido pactar horarios fijos, llamados de atención disciplinarios, o dependencia laboral. "
            "La contraprestación son HONORARIOS, no salario.\n"
            "2. OBJETIVO GENERAL Y OBJETIVOS ESPECÍFICOS ESTRATÉGICOS:\n"
            "   Tu misión es redactar el 'OBJETIVO GENERAL' y los 'OBJETIVOS ESPECÍFICOS' de los Estudios Previos de la ESPY. "
            "Los objetivos deben reflejar el propósito estratégico y los logros técnicos concretos que la entidad alcanzará con la ejecución del contrato, "
            "manteniendo coherencia total con la Descripción de la Necesidad y las Obligaciones Específicas.\n"
            "   REGLAS PROHIBITIVAS ESTRICTAS:\n"
            "   - PROHIBIDO concatenar o incrustar literalmente el objeto del contrato en mayúsculas dentro de frases genéricas "
            "(Ej: NUNCA 'Asegurar las labores para PRESTACIÓN DE SERVICIOS DE...'). Integra el sentido del objeto de forma natural, con redacción fluida y en minúsculas (salvo siglas como ESPY o PGIRS).\n"
            "   - PROHIBIDO poner trámites administrativos como objetivos específicos: Nunca incluyas 'presentar informes mensuales', 'pasar cuentas de cobro', 'asistir a reuniones' o 'pagar seguridad social'.\n"
            "   - PROHIBIDO usar frases comodín vacías: No uses viñetas como 'Ejecutar las actividades programadas en los plazos fijados'. Cada objetivo específico debe hablar de la materia técnica real del contrato.\n"
            "   ESTRUCTURA DE REDACCIÓN:\n"
            "   a) OBJETIVO GENERAL (El 'Qué' + El 'Para qué misional'): En un solo párrafo contundente iniciando con un verbo en infinitivo de alto nivel (Garantizar, Fortalecer, Optimizar, Asegurar, Ejecutar, Proveer): "
            "[Verbo en infinitivo] + [la acción técnica real del contrato redactada de forma natural] + [con el fin de / para] + [el beneficio directo que obtiene la operación de la ESPY o la prestación de los servicios públicos en el municipio de Yolombó].\n"
            "   b) OBJETIVOS ESPECÍFICOS (El 'Cómo técnico' desglosado en 3 a 5 metas): Cada uno iniciando con un verbo en infinitivo bien escrito (sin letras cortadas): "
            "Meta 1 (Diagnóstico/Planeación o Abastecimiento), Meta 2 (Ejecución Nuclear / Intervención), Meta 3 (Calidad / Continuidad Operativa / Mitigación de Riesgos), y Meta 4 (Trazabilidad Técnica / Gestión de Información).\n"

            "3. OBLIGACIONES DEL CONTRATISTA (ESPECÍFICAS Y GENERALES/ADMINISTRATIVAS):\n"
            "   Tu misión es redactar el acápite de 'OBLIGACIONES DEL CONTRATISTA' dividido en Obligaciones Específicas "
            "y Obligaciones Generales/Administrativas, garantizando total trazabilidad y simetría con la 'Descripción de la Necesidad a Satisfacer' "
            "y la propuesta/cotización presentada.\n"
            "   REGLA DE SIMETRÍA Y VERBOS RECTORES:\n"
            "   Toda actividad identificada en la Descripción de la Necesidad debe convertirse en una obligación contractual exigible. "
            "Cada obligación DEBE iniciar con un verbo en infinitivo (Ejecutar, Suministrar, Realizar, Garantizar, Entregar, Presentar) "
            "y debe redactarse de tal forma que el supervisor del contrato pueda verificar su cumplimiento mediante un soporte físico o verificable.\n"
            "   PASO 1 - TRANSFORMACIÓN PARA OBLIGACIONES ESPECÍFICAS:\n"
            "   - SI ES ESCENARIO A (Propuesta Detallada con múltiples ítems >= 3): Aplica la Regla de Inclusión Total. "
            "Convierte el 100% de las actividades o bienes propuestos en obligaciones específicas individuales. "
            "Está ESTRICTAMENTE PROHIBIDO omitir, agrupar o resumir ítems de la propuesta.\n"
            "   - SI ES ESCENARIO B (Cotización Escueta o de Una Sola Línea - Ej: 'Mantenimiento a todo costo', 'Suministro global'): "
            "¡PROHIBIDO dejar una sola obligación específica! Debes proteger jurídicamente a la ESPY desglosando ese renglón único en mínimo 6 a 8 obligaciones "
            "específicas técnicas y de control que incluyan: (1) La obligación principal literal según la cotización; (2) El diagnóstico o levantamiento previo "
            "de información/estado inicial; (3) La ejecución técnica detallada (preventiva/correctiva o entrega material); (4) La cláusula de 'Todo Costo' o "
            "calidad de insumos (repuestos/materiales nuevos, originales o de primera calidad, asumiendo costos directos e indirectos); (5) Las pruebas de "
            "funcionamiento y entrega a satisfacción al almacén o supervisor; (6) La exigencia de soportes técnicos detallados (fichas técnicas por equipo, "
            "registro fotográfico del antes y después, relación de repuestos) como requisito indispensable para el pago; y (7) La garantía técnica sobre el trabajo realizado o bienes suministrados.\n"
            "   PASO 2 - INCLUSIÓN DE OBLIGACIONES GENERALES Y ADMINISTRATIVAS (Blindaje de Supervisión):\n"
            "   Incluye siempre el bloque administrativo estándar de la ESPY adaptado a la naturaleza del contrato: "
            "(a) Suscripción oportuna del Acta de Inicio, Actas Parciales y Acta de Liquidación/Recibo Final; "
            "(b) Presentación de informes de ejecución detallados con evidencias verificables (planillas, fotos, remisiones); "
            "(c) Acreditación mensual de aportes al Sistema de Seguridad Social Integral (Salud, Pensión, ARL) y Parafiscales (Art. 50 Ley 789/2002 y Ley 1150/2007); "
            "(d) Cumplimiento de normas SST y uso de Elementos de Protección Personal (EPP); "
            "(e) Atención oportuna a los requerimientos, observaciones y reuniones citadas por el supervisor del contrato.\n"
            "4. JUSTIFICACIÓN DE LA NECESIDAD: Redacta obligatoriamente la sección 'DESCRIPCIÓN DE LA NECESIDAD A SATISFACER' "
            "aplicando rigurosamente 'El Método del Embudo' en 3 niveles: "
            "Nivel 1 (Marco institucional Ley 142 de 1994 y fines misionales de la ESPY; aplicando la Regla de Oro: Prohibido mencionar acueducto y alcantarillado si el contrato versa sobre aseo, PGIRS o gestión administrativa, y viceversa), "
            "Nivel 2 (Justificación de insuficiencia interna: insertar textualmente el siguiente párrafo exacto: 'Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente, con disponibilidad de tiempo exclusivo o con la experticia técnica específica para asumir directamente las labores requeridas; razón por la cual resulta necesario acudir a la contratación externa con el fin de garantizar los principios de eficacia, economía y celeridad de la función administrativa consagrados en el artículo 209 de la Constitución Política.'), y "
            "Nivel 3 (Requerimiento exacto detallado: traduciendo al lenguaje de necesidad institucional mediante lista con viñetas con el 100% de las actividades sin resumir ni omitir nada, bajo la fórmula obligatoria: "
            "'Por consiguiente, surge la necesidad imperiosa de contratar servicios de apoyo para que se ejecuten en su totalidad las siguientes labores puntuales:\\n- [Lista exhaustiva del 100% de actividades]'). "
            "Regla de tono: Nunca redactar en primera persona ni 'el contratista propone'. Redactar desde la perspectiva de la entidad: 'La ESPY requiere...'. "
            "Regla de discriminación: Las viñetas del Nivel 3 deben contener exclusivamente las labores operativas a ejecutar. NUNCA incluyas títulos de secciones, encabezados de estudios de mercado ni líneas de cuadros comparativos.\n"
            "5. GARANTÍAS: Recomienda amparo de cumplimiento (10% a 20% del valor total) y calidad del servicio si aplica.\n"
            "6. OBLIGACIONES DE LA EMPRESA (ESPY S.A. E.S.P.) PARA LA MINUTA DEL CONTRATO Y ESTUDIOS PREVIOS:\n"
            "   Debes formular obligatoriamente en el campo 'obligaciones_empresa' las obligaciones a cargo de LA EMPRESA "
            "basándote dinámicamente en el OBJETO DEL CONTRATO, el PLAZO y la TIPOLOGÍA, cumpliendo:\n"
            "   a) Generar de 2 a 3 Obligaciones Técnicas Específicas de la ESPY según el Objeto:\n"
            "      - Si es Mantenimiento de herramientas/equipos/vehículos: Obligación de hacer entrega física mediante inventario o relación técnica, informar fallas reportadas y verificar pruebas técnicas y repuestos al momento del recibo. (PROHIBIDO hablar de 'acceso a plataformas o sistemas').\n"
            "      - Si es Trabajo de campo / Sensibilización / PGIRS: Suministrar la programación oficial de rutas, horarios, sectores críticos y lineamientos técnicos ambientales de la ESPY.\n"
            "      - Si es Suministro / Compraventa: Efectuar los requerimientos de entrega, disponer espacio en almacén/planta para la recepción, verificar fichas técnicas/calidad y expedir ingreso a almacén.\n"
            "      - Si es Obra / Redes: Entregar el frente de intervención, suministrar información técnica de redes existentes y verificar cantidades de obra ejecutadas.\n"
            "   b) Obligaciones Administrativas y de Pago de la ESPY:\n"
            "      - Terminología del pago: NO uses 'honorarios' cuando sea mantenimiento a todo costo, servicios técnicos operativos, suministro u obra; usa 'el valor del contrato' o 'el valor de los servicios/bienes ejecutados', indicando 'previa radicación de la factura electrónica o cuenta de cobro (según corresponda al régimen tributario del contratista)'.\n"
            "      - Coherencia con el Plazo (Regla de Periodicidad): Si el plazo es <= 30 días, PROHIBIDO usar 'informes mensuales' o 'pagos mensuales vencidos'. Redacta: 'contra entrega y aprobación del informe final de ejecución' y 'revisará el informe de ejecución'.\n"
            "      - Seguridad Social según Tipo de Persona: Si es Persona Jurídica, incluir verificación de aportes al Sistema de Seguridad Social Integral y Parafiscales (Art. 50 Ley 789 de 2002); si es Persona Natural, verificar aportes a Salud, Pensión y ARL.\n"
            "      - Autonomía técnica y suscripción oportuna de actas de inicio y liquidación final.\n"
        )


    def build_user_prompt(self, input_data: ContractDraftingInput) -> str:
        return (
            f"Estructura el contrato de prestación de servicios con los siguientes datos:\n"
            f"- Necesidad planteada: {input_data.necesidad_descripcion}\n"
            f"- Alcance adicional: {input_data.alcance_esperado or 'Según requerimiento del área usuaria'}\n"
            f"- Valor estimado: ${int(round(input_data.valor_estimado)):,}".replace(",", ".") + " COP\n"
            f"- Plazo previsto: {input_data.plazo} {input_data.unidad_plazo}\n"
            f"- Contexto contratista: {input_data.datos_contratista_contexto or 'Por definir'}\n\n"
            f"Genera el JSON completo con objeto preciso, justificación rigurosa Ley 142/1994, objetivo general, "
            f"objetivos específicos medibles (cada objetivo DEBE iniciar obligatoriamente con un verbo de acción en infinitivo como Realizar, Practicar, Efectuar o Desarrollar), "
            f"un catálogo EXTENSO Y EXHAUSTIVO de obligaciones del contratista para estudio previo y minuta (mínimo 10 a 14 obligaciones en minuta), "
            f"las obligaciones institucionales de LA EMPRESA para la minuta adaptadas específicamente a prestación de servicios (pago oportuno contra informe y seguridad social, supervisor, información institucional, autonomía técnica y actas de inicio/liquidación), "
            f"y amparos de garantía."
        )

    def fallback_generator(self, input_data: ContractDraftingInput) -> ContractDraftingResult:
        import re
        necesidad = input_data.necesidad_descripcion.strip()
        alcance = (input_data.alcance_esperado or "").strip()
        plazo = f"{input_data.plazo} {input_data.unidad_plazo.lower() if input_data.unidad_plazo else 'meses'}"

        # 1. Determinar el Objeto Contractual aplicando la fórmula de 4 bloques en mayúsculas sostenidas
        from app.utils.objeto_builder import build_objeto_contractual
        objeto = build_objeto_contractual(
            propuesta_o_cotizacion=necesidad,
            tipologia="PRESTACION_SERVICIOS",
            necesidad_descripcion=necesidad,
            contexto=alcance
        )

        # 2. Detectar si versa sobre Salud Ocupacional / Exámenes Médicos / SG-SST
        is_med = bool(re.search(r"(?:m[eé]dic|salud\s+ocupacional|osteomuscular|visiometr|audiometr|espirometr|psicosensom|sg-sst)", f"{necesidad} {alcance}", re.IGNORECASE))

        nivel_ext = getattr(input_data, "nivel_extension", "MEDIA") or "MEDIA"
        instr_adic = getattr(input_data, "instrucciones_adicionales", None)
        prop_items = getattr(input_data, "propuesta_items", None)

        from app.utils.necesidad_builder import build_descripcion_necesidad

        justificacion = build_descripcion_necesidad(
            objeto=objeto,
            tipologia="PRESTACION_SERVICIOS",
            contexto_adicional=f"{necesidad} {alcance}",
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic,
            propuesta_items=prop_items
        )

        from app.utils.objetivos_builder import build_objetivos_contrato

        obj_data = build_objetivos_contrato(
            objeto=objeto,
            tipologia="PRESTACION_SERVICIOS",
            contexto=f"{necesidad} {alcance}",
            items_propuesta=prop_items,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )
        objetivo_general = obj_data["objetivo_general"]
        objetivos_especificos = obj_data["objetivos_especificos"]

        from app.utils.obligaciones_builder import build_obligaciones_contratista

        oblig_res = build_obligaciones_contratista(
            objeto=objeto,
            tipologia="PRESTACION_SERVICIOS",
            items_propuesta=prop_items,
            contexto_adicional=f"{necesidad} {alcance}",
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )
        obligaciones_estudio_previo = oblig_res["obligaciones_estudio_previo"]
        obligaciones_minuta = oblig_res["obligaciones_minuta"]

        from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa

        tipo_p = "JURIDICA" if input_data.datos_contratista_contexto and str(input_data.datos_contratista_contexto.get("tipo_persona") or "").upper() in ["JURIDICA", "JURÍDICA", "NIT"] else "NATURAL"
        obligaciones_empresa = build_obligaciones_empresa(
            objeto=objeto,
            tipologia="PRESTACION_SERVICIOS",
            plazo_str=plazo,
            plazo_val=input_data.plazo,
            unidad_plazo=input_data.unidad_plazo,
            tipo_persona=tipo_p,
            obligaciones_contratista=obligaciones_minuta,
            contexto_adicional=f"{necesidad} {alcance}",
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )

        garantias_sugeridas = {
            "cumplimiento": {
                "porcentaje": 10,
                "vigencia": f"Plazo contractual ({plazo}) y cuatro (4) meses más"
            },
            "calidad_servicio": {
                "porcentaje": 10,
                "vigencia": "Seis (6) meses a partir de la liquidación"
            }
        }

        clausulas_especiales = [
            "CLÁUSULA DE INDEPENDENCIA Y NO SUBORDINACIÓN: Las partes declaran expresamente que el presente contrato de prestación de servicios se rige por las normas del Derecho Privado aplicables a las ESP (Ley 142 de 1994, Art. 31), careciendo de carácter laboral, subordinación o jornada de trabajo obligatoria.",
            "PAGO DE APORTES PARAFISCALES: En cumplimiento del Artículo 50 de la Ley 789 de 2002 y la Ley 1562 de 2012, el contratista deberá acreditar mensualmente la afiliación y pago de sus aportes a Salud, Pensión y ARL como independiente."
        ]

        marco_juridico = (
            "El presente Contrato de Prestación de Servicios se fundamenta en el siguiente marco normativo y jurisprudencial:\n"
            "1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994 (Régimen de los Servicios Públicos Domiciliarios), Artículos 31 y 32, "
            "concordantes con las normas de contratación del derecho privado (Código Civil y Código de Comercio), salvo expresa disposición legal en contrario.\n"
            "2. PRINCIPIOS CONSTITUCIONALES DE LA FUNCIÓN ADMINISTRATIVA Y GESTIÓN FISCAL: Artículos 209 y 267 de la Constitución Política de Colombia "
            "(igualdad, moralidad, eficacia, economía, celeridad, imparcialidad y publicidad en la administración de recursos públicos).\n"
            "3. ARRENDAMIENTO DE SERVICIOS INMATERIALES: Código Civil Colombiano, Artículos 2053 a 2069, que regulan la contratación de servicios profesionales, "
            "consultorías y labores técnicas inmateriales con remuneración mediante honorarios.\n"
            "4. AUTONOMÍA TÉCNICA E INEXISTENCIA DE SUBORDINACIÓN LABORAL: Artículo 23 del Código Sustantivo del Trabajo (CST), en concordancia con la "
            "jurisprudencia de la Corte Constitucional (Sentencias C-614 de 2009 y C-171 de 2012) y del Consejo de Estado (Sección Segunda), que prohíben la subordinación "
            "jurídica, imposición de horarios y dependencia laboral, consagrando la plena autonomía directiva y operativa del contratista independiente.\n"
            "5. SEGURIDAD SOCIAL INTEGRAL OBLIGATORIA: Ley 100 de 1993, Ley 797 de 2003, Decreto 1072 de 2015 y Decreto 1273 de 2018, por los cuales el contratista "
            "independiente asume la obligación de afiliarse y cotizar a Salud (12.5%), Pensión (16%) y Riesgos Laborales (ARL) sobre un Ingreso Base de Cotización (IBC) "
            "mínimo del 40% del valor mensualizado del contrato, constituyendo requisito previo e indispensable para el desembolso de cada pago.\n"
            "6. RÉGIMEN DE INHABILIDADES E INCOMPATIBILIDADES: Artículo 8 de la Ley 80 de 1993 y Ley 1150 de 2007, aplicable a las entidades y contratistas de las ESP "
            "por remisión jurisprudencial vinculante de la Corte Constitucional (Sentencia C-066 de 1997).\n"
            "7. ESTATUTO INTERNO: Manual Interno de Contratación de la Empresa de Servicios Públicos de Yolombó ESPY."
        )

        return ContractDraftingResult(
            tipologia="PRESTACION_SERVICIOS",
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
            observaciones_juridicas="Contrato civil/comercial sin relación de subordinación laboral bajo Ley 142 de 1994. Pagos condicionados a informe de supervisión y soporte de planilla PILA."
        )
