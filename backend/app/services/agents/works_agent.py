"""Agente Especializado en Contratos de Obra e Infraestructura para Servicios Públicos."""
from app.services.agents.base_agent import BaseContractAgent
from app.schemas.agent import ContractDraftingInput, ContractDraftingResult
from app.utils.objective_normalizer import normalize_objetivos_especificos

class WorksContractAgent(BaseContractAgent):
    def __init__(self):
        super().__init__(
            nombre="Agente de Contratos de Obra",
            tipologia="OBRA"
        )

    def get_system_instruction(self) -> str:
        return (
            "Eres el Agente Ingeniero y Abogado Especialista en Contratos de Obra e Infraestructura de una "
            "Empresa de Servicios Públicos (ESP) en Colombia (Acueducto, Alcantarillado, Aseo y Energía).\n"
            "Tu misión es redactar la documentación técnica y contractual rigurosa para obras civiles, "
            "mantenimientos de redes, plantas de tratamiento (PTAP/PTAR), tanques de almacenamiento y estaciones de bombeo.\n\n"
            "REGLAS TÉCNICAS Y NORMATIVAS OBLIGATORIAS:\n"
            "1. OBJETO: Debe precisar las actividades físicas de construcción, reposición, adecuación o mantenimiento, "
            "especificando la infraestructura y ubicación técnica.\n"
            "2. OBJETIVOS ESPECÍFICOS: Cada objetivo específico DEBE redactarse iniciando OBLIGATORIAMENTE con un VERBO EN INFINITIVO "
            "(ej: 'Realizar', 'Ejecutar', 'Suministrar', 'Instalar', 'Construir', 'Adecuar', 'Efectuar', 'Demoler', 'Reponer', 'Verificar'). "
            "Queda terminantemente prohibido formular objetivos con sustantivos huérfanos sin verbo rector de acción.\n"
            "3. OBLIGACIONES DEL CONTRATISTA (ESPECÍFICAS Y GENERALES/ADMINISTRATIVAS):\n"
            "   Tu misión es redactar el acápite de 'OBLIGACIONES DEL CONTRATISTA' dividido en Obligaciones Específicas "
            "y Obligaciones Generales/Administrativas, garantizando total trazabilidad y simetría con la 'Descripción de la Necesidad a Satisfacer' "
            "y la propuesta/cotización presentada.\n"
            "   REGLA DE SIMETRÍA Y VERBOS RECTORES:\n"
            "   Toda actividad constructiva u operativa identificada en la Descripción de la Necesidad debe convertirse en una obligación contractual exigible. "
            "Cada obligación DEBE iniciar con un verbo en infinitivo (Ejecutar, Suministrar, Realizar, Garantizar, Entregar, Presentar) "
            "y redactarse de tal forma que la interventoría o supervisión pueda verificar su cumplimiento mediante memorias de cálculo, ensayos de laboratorio o actas.\n"
            "   PASO 1 - TRANSFORMACIÓN PARA OBLIGACIONES ESPECÍFICAS:\n"
            "   - SI ES ESCENARIO A (Propuesta Detallada con múltiples ítems >= 3): Aplica la Regla de Inclusión Total. "
            "Convierte el 100% de las actividades de obra en obligaciones específicas individuales sin omitir ni resumir ninguna.\n"
            "   - SI ES ESCENARIO B (Cotización Escueta o de Una Sola Línea - Ej: 'Mantenimiento de redes a todo costo', 'Adecuación locativa'): "
            "¡PROHIBIDO dejar una sola obligación específica! Desglosa ese renglón en mínimo 6 a 8 obligaciones específicas técnicas y de control: "
            "(1) Obligación constructiva principal literal según la cotización; (2) Levantamiento topográfico, diagnóstico y estado inicial del frente de obra; "
            "(3) Ejecución técnica de demolición, excavación, instalación y acabados; (4) Cláusula de materiales certificados y todo costo directo e indirecto (AIU); "
            "(5) Pruebas técnicas de presión hidrostática, estanqueidad o resistencia de concretos con la supervisión; "
            "(6) Exigencia de memorias de cálculo, planos récord As-Built y registro fotográfico antes y después como requisito indispensable para el pago; "
            "(7) Garantía de estabilidad de la obra y calidad de materiales.\n"
            "   PASO 2 - OBLIGACIONES GENERALES Y ADMINISTRATIVAS (Blindaje de Supervisión):\n"
            "   Incluye siempre el bloque administrativo estándar: Acta de entrega de terreno e inicio; bitácora de obra diaria; informes mensuales; "
            "pago de seguridad social en Riesgo V de ARL y parafiscales (Art. 50 Ley 789/2002); estricto SG-SST y EPP en obra; atención a requerimientos de la interventoría.\n"
            "4. GARANTÍAS OBLIGATORIAS: Póliza de Cumplimiento (20%), Salarios y Prestaciones Sociales (10%), Estabilidad de la Obra (20% por 5 años), "
            "y Responsabilidad Civil Extracontractual (RCE) para amparar daños a terceros e infraestructura contigua.\n"

            "6. JUSTIFICACIÓN DE LA NECESIDAD: Redacta obligatoriamente la sección 'DESCRIPCIÓN DE LA NECESIDAD A SATISFACER' "
            "en exactamente 4 párrafos continuos: Párrafo 1 (Marco institucional Ley 142/1994 y servicios públicos domiciliarios), "
            "Párrafo 2 (Necesidad técnica aplicando la fórmula: 'En materia técnico-operativa, resulta esencial [Acción principal del objeto] "
            "para garantizar [Beneficio directo de ese objeto para la comunidad o la empresa]. La omisión de estas labores generaría riesgos en "
            "[Área específica afectada, NO general].' aplicando la Regla de Oro: Prohibido mencionar acueducto y alcantarillado si la obra no versa "
            "sobre estas materias), Párrafo 3 (Justificación de insuficiencia interna: insertar textualmente el siguiente párrafo exacto: "
            "'Actualmente, la ESPY no cuenta dentro de su planta de personal con el recurso humano suficiente, con disponibilidad de tiempo exclusivo o con la experticia técnica específica para asumir directamente las labores requeridas; razón por la cual resulta necesario acudir a la contratación externa con el fin de garantizar los principios de eficacia, economía y celeridad de la función administrativa consagrados en el artículo 209 de la Constitución Política.'), "
            "y Párrafo 4 (Conclusión del impacto en ejecución de recursos, mitigación de riesgos y continuidad).\n"
            "7. OBLIGACIONES DE LA EMPRESA (ESPY S.A. E.S.P.) PARA LA MINUTA DEL CONTRATO:\n"
            "   Debes formular obligatoriamente en el campo 'obligaciones_empresa' las obligaciones institucionales a cargo de LA EMPRESA "
            "adaptadas rigurosamente a la tipología de OBRA (mínimo 6 a 8 obligaciones):\n"
            "   a) Designar formalmente al Interventor Técnico o Supervisor de la obra para el control, inspección, medición de cantidades y certificación de calidad de los trabajos.\n"
            "   b) Realizar la entrega formal al contratista de los predios, zonas de trabajo, servidumbres y frentes de obra libres de interferencias y gravámenes mediante la suscripción del Acta de Entrega de Terreno.\n"
            "   c) Tramitar y pagar oportunamente las Actas Parciales de Obra debidamente aprobadas por la interventoría/supervisión técnica, aplicando las retenciones de ley y amortizaciones de anticipo pactadas.\n"
            "   d) Gestionar y suministrar los permisos institucionales, licencias de intervención de espacio público o autorizaciones de ocupación de cauce y coordinar las suspensiones programadas del servicio público necesarias para empalmes de redes.\n"
            "   e) Resolver en coordinación con el área de planeación e interventoría las solicitudes de aclaración técnica de planos o especificaciones constructivas formuladas por el contratista.\n"
            "   f) Recibir a satisfacción las obras ejecutadas mediante la suscripción del Acta de Recibo Final, una vez superadas las pruebas de presión, calidad, estanqueidad y funcionamiento y entregados los planos récord As-Built.\n"
            "   g) Suscribir formalmente el Acta de Liquidación Definitiva del contrato de obra en los términos legales establecidos."
        )

    def build_user_prompt(self, input_data: ContractDraftingInput) -> str:
        return (
            f"Estructura el contrato de obra e infraestructura técnica con la siguiente información:\n"
            f"- Descripción de la obra: {input_data.necesidad_descripcion}\n"
            f"- Alcance técnico: {input_data.alcance_esperado or 'Según especificaciones y planos de ingeniería'}\n"
            f"- Presupuesto oficial estimado: ${int(round(input_data.valor_estimado)):,}".replace(",", ".") + " COP\n"
            f"- Plazo de ejecución: {input_data.plazo} {input_data.unidad_plazo}\n"
            f"- Datos del contratista/obra: {input_data.datos_contratista_contexto or 'Por definir'}\n\n"
            f"Genera el JSON completo con objeto de obra, justificación basada en prestación continua del servicio público, "
            f"objetivos técnicos (cada objetivo específico DEBE iniciar con un verbo de acción en infinitivo como Realizar, Ejecutar, Suministrar, Instalar o Construir), "
            f"obligaciones diferenciadas para estudio previo y minuta del contratista, "
            f"las obligaciones institucionales de LA EMPRESA adaptadas específicamente a obra (entrega de terreno, interventoría/supervisión, actas parciales, gestión de permisos y suspensiones de servicio, recibo final As-Built y liquidación), "
            f"AIU, SST y pólizas de estabilidad."
        )

    def fallback_generator(self, input_data: ContractDraftingInput) -> ContractDraftingResult:
        necesidad = input_data.necesidad_descripcion.strip()
        plazo = f"{input_data.plazo} {input_data.unidad_plazo.lower() if input_data.unidad_plazo else 'meses'}"

        from app.utils.objeto_builder import build_objeto_contractual
        objeto = build_objeto_contractual(
            propuesta_o_cotizacion=necesidad,
            tipologia="OBRA",
            necesidad_descripcion=necesidad,
            contexto=input_data.alcance_esperado
        )

        nivel_ext = getattr(input_data, "nivel_extension", "MEDIA") or "MEDIA"
        instr_adic = getattr(input_data, "instrucciones_adicionales", None)
        prop_items = getattr(input_data, "propuesta_items", None)

        from app.utils.necesidad_builder import build_descripcion_necesidad

        justificacion = build_descripcion_necesidad(
            objeto=objeto,
            tipologia="OBRA",
            contexto_adicional=f"{necesidad} {input_data.alcance_esperado or ''}",
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic,
            propuesta_items=prop_items
        )

        from app.utils.objetivos_builder import build_objetivos_contrato

        obj_data = build_objetivos_contrato(
            objeto=objeto,
            tipologia="OBRA",
            contexto=f"{necesidad} {input_data.alcance_esperado or ''}",
            items_propuesta=prop_items,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )
        objetivo_general = obj_data["objetivo_general"]
        objetivos_especificos = obj_data["objetivos_especificos"]

        from app.utils.obligaciones_builder import build_obligaciones_contratista

        oblig_res = build_obligaciones_contratista(
            objeto=objeto,
            tipologia="OBRA",
            items_propuesta=prop_items,
            contexto_adicional=f"{necesidad} {input_data.alcance_esperado or ''}",
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )
        obligaciones_estudio_previo = oblig_res["obligaciones_estudio_previo"]
        obligaciones_minuta = oblig_res["obligaciones_minuta"]

        from app.utils.obligaciones_empresa_builder import build_obligaciones_empresa

        tipo_p = "JURIDICA" if input_data.datos_contratista_contexto and str(input_data.datos_contratista_contexto.get("tipo_persona") or "").upper() in ["JURIDICA", "JURÍDICA", "NIT"] else "NATURAL"
        obligaciones_empresa = build_obligaciones_empresa(
            objeto=objeto,
            tipologia="OBRA",
            plazo_str=plazo,
            plazo_val=input_data.plazo,
            unidad_plazo=input_data.unidad_plazo,
            tipo_persona=tipo_p,
            obligaciones_contratista=obligaciones_minuta,
            contexto_adicional=f"{necesidad} {input_data.alcance_esperado or ''}",
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic
        )

        garantias_sugeridas = {
            "cumplimiento": {"porcentaje": 20, "vigencia": f"Plazo contractual ({plazo}) y seis (6) meses más"},
            "estabilidad_obra": {"porcentaje": 20, "vigencia": "Cinco (5) años contados a partir del acta de entrega y recibo final"},
            "salarios_prestaciones": {"porcentaje": 10, "vigencia": f"Plazo contractual ({plazo}) y tres (3) años más"},
            "responsabilidad_civil_extracontractual": {"porcentaje": 10, "vigencia": f"Plazo contractual ({plazo})"}
        }

        clausulas_especiales = [
            "ADMINISTRACIÓN, IMPREVISTOS Y UTILIDAD (AIU): El valor contractual incluye los costos directos e indirectos correspondientes al AIU pactado, sin lugar a reajustes salvo hechos sobrevinientes debidamente comprobados.",
            "INTERVENTORÍA TÉCNICA Y BITÁCORA: Las decisiones de modificación o autorización de cantidades de obra deberán constar por escrito en el libro oficial de obra debidamente suscrito por el contratista y la interventoría.",
            "PLAN DE MANEJO AMBIENTAL Y DISPOSICIÓN DE ESCOMBROS: Todo el material de excavación o demolición deberá transportarse y disponerse en botaderos legalmente autorizados con certificación ambiental."
        ]

        marco_juridico = (
            "El presente Contrato de Obra se fundamenta en el siguiente marco normativo, técnico y jurisprudencial:\n"
            "1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994 (Régimen de los Servicios Públicos Domiciliarios), Artículos 31 y 32, "
            "que establece el derecho privado para la ejecución de proyectos de infraestructura y saneamiento de las ESP.\n"
            "2. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (igualdad, moralidad, eficacia, economía, celeridad y control fiscal).\n"
            "3. CONTRATO DE CONFECCIÓN DE OBRA MATERIAL: Código Civil Colombiano, Artículos 2053 a 2062, bajo la modalidad de precio global alzado o precios unitarios fijos sin reajuste, asumiendo el contratista la dirección técnica de los trabajos.\n"
            "4. RESPONSABILIDAD DECENAL Y GARANTÍA DE ESTABILIDAD: Artículo 2060 numeral 3 del Código Civil Colombiano, el cual consagra la responsabilidad legal del constructor por ruina total o parcial de la obra durante los diez (10) años siguientes a su entrega por vicios de construcción, suelo o materiales, amparada mediante póliza de estabilidad de la obra no inferior a cinco (5) años.\n"
            "5. REGLAMENTO TÉCNICO DEL SECTOR AGUA POTABLE Y SANEAMIENTO BÁSICO (RAS): Resolución 0330 de 2017 expedida por el Ministerio de Vivienda, Ciudad y Territorio (parámetros de diseño, calidad, pendientes hidráulicas, pruebas de estanqueidad y tuberías para acueducto y alcantarillado).\n"
            "6. NORMA SISMORRESISTENTE NSR-10: Ley 400 de 1997 y Decreto 926 de 2010 para estructuras de almacenamiento, tanques y edificaciones técnicas de la ESP.\n"
            "7. SEGURIDAD Y SALUD EN EL TRABAJO EN CONSTRUCCIÓN (SG-SST): Decreto 1072 de 2015, Resolución 0312 de 2019, Resolución 4272 de 2021 (trabajo en alturas), Resolución 0491 de 2020 (espacios confinados e inspección de pozos) y Resolución 2400 de 1979 (entibados y excavaciones seguras).\n"
            "8. NORMATIVA AMBIENTAL Y MANEJO DE RCD: Decreto 1076 de 2015 (Plan de Manejo Ambiental y permisos de ocupación de cauce/vertimientos) y Resolución 1257 de 2021 para la gestión integral de Residuos de Construcción y Demolición (RCD).\n"
            "9. RÉGIMEN TRIBUTARIO A.I.U.: Artículos 462-1 y 468-3 del Estatuto Tributario, con liquidación de IVA exclusivamente sobre el componente de Utilidad pactado en el contrato de obra civil.\n"
            "10. INHABILIDADES Y MANUAL INTERNO: Artículo 8 Ley 80 de 1993, Sentencia C-066/97 de la Corte Constitucional y Manual Interno de Contratación de la ESPY."
        )

        return ContractDraftingResult(
            tipologia="OBRA",
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
            observaciones_juridicas="Contrato de obra civil. Exige supervisión o interventoría técnica, bitácora y póliza de estabilidad por 5 años."
        )
