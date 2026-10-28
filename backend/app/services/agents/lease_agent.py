"""Agente Especializado en Contratos de Arrendamiento de Inmuebles para ESP."""
from app.services.agents.base_agent import BaseContractAgent
from app.schemas.agent import ContractDraftingInput, ContractDraftingResult
from app.utils.objective_normalizer import normalize_objetivos_especificos

class LeaseContractAgent(BaseContractAgent):
    def __init__(self):
        super().__init__(
            nombre="Agente de Contratos de Arrendamiento",
            tipologia="ARRENDAMIENTO"
        )

    def get_system_instruction(self) -> str:
        return (
            "Eres el Agente Abogado Especialista en Contratos de Arrendamiento de Inmuebles de una "
            "Empresa de Servicios Públicos (ESP) en Colombia, regida por la Ley 142 de 1994, el Código Civil (Arts. 1973 y ss.) "
            "y el Código de Comercio.\n"
            "Tu misión es estructurar de forma rigurosa los documentos contractuales para el arrendamiento de bienes inmuebles, "
            "bodegas de almacenamiento de materiales y químicos, oficinas de atención al usuario o predios operativos.\n\n"
            "REGLAS TÉCNICAS Y NORMATIVAS OBLIGATORIAS:\n"
            "1. OBJETO: Debe precisar la entrega de la tenencia y el uso del inmueble con su identificación catastral, matrícula inmobiliaria, "
            "dirección y destinación institucional exclusiva para las actividades de la ESP.\n"
            "2. OBJETIVOS ESPECÍFICOS: Cada objetivo DEBE formularse iniciando OBLIGATORIAMENTE con un VERBO EN INFINITIVO "
            "(ej: 'Entregar', 'Garantizar', 'Mantener', 'Verificar', 'Restituir'). Prohibido sustantivos sin acción.\n"
            "3. OBLIGACIONES ESTUDIO PREVIO: Verificación física y de tradición del inmueble, paz y salvos tributarios y de servicios públicos, "
            "avalúo comercial o de canon de mercado, e inventario preliminar.\n"
            "4. OBLIGACIONES MINUTA DEL CONTRATISTA: Destinación exclusiva convenida, mantenimiento y conservación locativa ordinaria, "
            "pago oportuno de servicios públicos a su cargo, no cesión ni subarriendo sin autorización, restitución formal con acta de entrega final.\n"
            "5. OBLIGACIONES DE LA EMPRESA (ESPY S.A. E.S.P.) PARA LA MINUTA DEL CONTRATO:\n"
            "   Debes formular obligatoriamente en el campo 'obligaciones_empresa' las obligaciones institucionales a cargo de LA EMPRESA "
            "adaptadas rigurosamente a la tipología de ARRENDAMIENTO (mínimo 5 a 7 obligaciones):\n"
            "   a) Entregar formalmente la tenencia material del bien inmueble en la fecha convenida, en adecuado estado de higiene, habitabilidad y seguridad, mediante suscripción del Acta de Inventario y Entrega.\n"
            "   b) Garantizar el uso y goce pacífico del inmueble durante todo el plazo de ejecución contractual, amparando contra cualquier perturbación o turbación de derecho proveniente de terceros.\n"
            "   c) Pagar oportunamente los cánones de arrendamiento pactados dentro de los primeros días de cada período convenido (cuando actúe en calidad de arrendataria) o expedir la correspondiente facturación.\n"
            "   d) Asumir y ejecutar oportunamente las reparaciones indispensables de carácter estructural, locativo mayor o vicios ocultos de las instalaciones que legalmente le correspondan para la conservación del bien.\n"
            "   e) Abstenerse de ejecutar obras, alteraciones o reformas que perturben o modifiquen el destino convenido para el inmueble sin autorización previa y escrita.\n"
            "   f) Recibir formalmente el inmueble a la terminación del contrato, verificando el inventario físico y suscribiendo el Acta de Recibo Final y Paz y Salvo correspondiente.\n"
            "6. JUSTIFICACIÓN DE LA NECESIDAD: Redacta la sección en exactamente 4 párrafos continuos: Párrafo 1 (Marco institucional Ley 142/1994), "
            "Párrafo 2 (Necesidad técnico-operativa de contar con el espacio físico para la operación de la ESP), "
            "Párrafo 3 (Justifica indicando que la entidad no dispone de infraestructura propia en la zona y requiere el inmueble para su funcionamiento), y "
            "Párrafo 4 (Conclusión del impacto en continuidad y eficiencia del servicio público)."
        )

    def build_user_prompt(self, input_data: ContractDraftingInput) -> str:
        return (
            f"Estructura el contrato de arrendamiento con la siguiente información:\n"
            f"- Descripción del inmueble y uso: {input_data.necesidad_descripcion}\n"
            f"- Alcance o condiciones: {input_data.alcance_esperado or 'Según inventario e inspección ocular previa'}\n"
            f"- Canon/Presupuesto total estimado: ${int(round(input_data.valor_estimado)):,}".replace(",", ".") + " COP\n"
            f"- Plazo de arrendamiento: {input_data.plazo} {input_data.unidad_plazo}\n"
            f"- Contexto partes: {input_data.datos_contratista_contexto or 'Por definir'}\n\n"
            f"Genera el JSON completo con objeto de arrendamiento, justificación orientada a infraestructura y continuidad del servicio, "
            f"objetivos específicos en infinitivo, obligaciones del contratista para estudio previo y minuta, "
            f"las obligaciones de LA EMPRESA adaptadas específicamente a arrendamiento (entrega material con inventario, goce pacífico, pago de cánones, reparaciones estructurales mayores, acta de recibo final y paz y salvo), "
            f"y garantías sugeridas."
        )

    def fallback_generator(self, input_data: ContractDraftingInput) -> ContractDraftingResult:
        necesidad = input_data.necesidad_descripcion.strip()
        plazo = f"{input_data.plazo} {input_data.unidad_plazo.lower() if input_data.unidad_plazo else 'meses'}"

        from app.utils.objeto_builder import build_objeto_contractual
        objeto = build_objeto_contractual(
            propuesta_o_cotizacion=necesidad,
            tipologia="ARRENDAMIENTO",
            necesidad_descripcion=necesidad,
            contexto=necesidad
        )

        nivel_ext = getattr(input_data, "nivel_extension", "MEDIA") or "MEDIA"
        instr_adic = getattr(input_data, "instrucciones_adicionales", None)
        prop_items = getattr(input_data, "propuesta_items", None)

        from app.utils.necesidad_builder import build_descripcion_necesidad

        justificacion = build_descripcion_necesidad(
            objeto=objeto,
            tipologia="ARRENDAMIENTO",
            contexto_adicional=necesidad,
            nivel_extension=nivel_ext,
            instrucciones_adicionales=instr_adic,
            propuesta_items=prop_items
        )

        from app.utils.objetivos_builder import build_objetivos_contrato

        obj_data = build_objetivos_contrato(
            objeto=objeto,
            tipologia="ARRENDAMIENTO",
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
            tipologia="ARRENDAMIENTO",
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
            tipologia="ARRENDAMIENTO",
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
            "cumplimiento": {"porcentaje": 10, "vigencia": f"Plazo contractual ({plazo}) y dos (2) meses más"},
            "pago_servicios_publicos": {"porcentaje": 5, "vigencia": f"Plazo contractual ({plazo}) y dos (2) meses más"}
        }

        clausulas_especiales = [
            "ACTA DE INVENTARIO Y ENTREGA MATERIAL: La entrega del inmueble se formalizará mediante acta suscrita por las partes detallando el estado físico de conservación de pisos, muros, cerraduras, redes e instalaciones sanitarias y eléctricas.",
            "PROHIBICIÓN DE SUBARRIENDO Y CESIÓN: Queda expresamente prohibido subarrendar total o parcialmente el inmueble o ceder los derechos derivados del contrato sin el previo consentimiento por escrito de la ESP."
        ]

        marco_juridico = (
            "El presente Contrato de Arrendamiento se fundamenta en el siguiente marco normativo:\n"
            "1. RÉGIMEN ESPECIAL DE DERECHO PRIVADO: Ley 142 de 1994, Artículos 31 y 32 (actos y contratos regidos por el derecho civil y comercial).\n"
            "2. PRINCIPIOS CONSTITUCIONALES: Artículos 209 y 267 de la Constitución Política de Colombia (moralidad, celeridad, economía y control fiscal).\n"
            "3. RÉGIMEN DE ARRENDAMIENTO DE COSAS: Código Civil Colombiano, Artículos 1973 a 2044 (goce de una cosa por un precio determinado, obligaciones del arrendador de conceder el uso y del arrendatario de pagar el precio y conservar el bien).\n"
            "4. CÓDIGO DE COMERCIO: Artículos 518 a 524 si aplica a establecimientos de comercio y bodegas operativas de la ESP.\n"
            "5. MANUAL INTERNO DE CONTRATACIÓN: Manual Interno de Contratación de la Empresa de Servicios Públicos de Yolombó ESPY."
        )

        return ContractDraftingResult(
            tipologia="ARRENDAMIENTO",
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
            observaciones_juridicas="Contrato civil de arrendamiento. Obligatoria acta de inventario inicial y acta de restitución y recibo final."
        )
