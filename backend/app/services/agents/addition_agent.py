"""Agente Especializado en Adiciones Contractuales para Empresas de Servicios Públicos (ESPY).
Gestiona la estructuración legal, financiera y técnica de adiciones a contratos existentes
bajo el régimen de derecho privado (Ley 142 de 1994, Art. 32).
"""
import re
from datetime import datetime, date
from typing import Dict, Any, Optional, Tuple
from app.utils.num_to_words import numero_a_letras_cop
from app.services.gemini_client import gemini_service
from app.utils.logger import logger

DIAS_LETRAS = {
    1: "un", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
    6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
    11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
    16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve", 20: "veinte",
    21: "veintiún", 22: "veintidós", 23: "veintitrés", 24: "veinticuatro", 25: "veinticinco",
    26: "veintiséis", 27: "veintisiete", 28: "veintiocho", 29: "veintinueve", 30: "treinta",
    31: "treinta y un"
}

MESES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

class AdditionAgent:
    """
    Agente para la generación de adiciones contractuales, consideraciones jurídicas,
    validaciones presupuestales y preparación de minutas Word.
    Rol: Abogado experto en contratación estatal, derecho privado aplicado a Empresas de
    Servicios Públicos Domiciliarios (Ley 142 de 1994) y estructuración de proyectos de la ESPY.
    """

    GENERIC_REASON_PATTERNS = [
        r"^agotamiento\s+del\s+inventario\s+operativo\.?$",
        r"^agotamiento\s+del\s+inventario\.?$",
        r"^se\s+agot[oó]\s+el\s+presupuesto\.?$",
        r"^se\s+acab[oó]\s+(la\s+plata|el\s+presupuesto)\.?$",
        r"^falta\s+de\s+presupuesto\.?$",
        r"^insuficiencia\s+(de\s+recursos|presupuestal)\.?$",
        r"^adici[oó]n\s+(presupuestal|de\s+recursos|de\s+valor)\.?$",
        r"^mayor\s+demanda\.?$",
        r"^continuidad\s+del\s+servicio\.?$",
        r"^sin\s+justificaci[oó]n\.?$"
    ]

    REQUIRED_QUESTIONS = [
        "¿Cuál es el tipo de contrato? (Suministro, Prestación de Servicios, Obra, Arrendamiento, Consultoría).",
        "¿Cuál es el objeto del contrato?",
        "¿Cuál es la razón técnica y específica por la que el presupuesto inicial se agotó o es insuficiente? (Ej: \"Aumentó la turbiedad del río y se necesitó más sulfato\", \"Se encontraron cantidades de obra no previstas en la excavación\", \"Se requiere extender el servicio por 2 meses más debido a X motivo\").",
        "¿Cuál es el valor a adicionar?"
    ]

    def format_legal_date(self, target_date: Optional[Any]) -> Dict[str, str]:
        """
        Convierte una fecha en su representación textual formal para contratos colombianos:
        Ej: 2026-04-15 -> día quince (15) del mes de abril de 2026.
        """
        if not target_date:
            target_date = date.today()
        elif isinstance(target_date, str):
            try:
                target_date = datetime.strptime(target_date[:10], "%Y-%m-%d").date()
            except Exception:
                try:
                    target_date = datetime.strptime(target_date[:10], "%d/%m/%Y").date()
                except Exception:
                    target_date = date.today()

        dia_num = target_date.day
        dia_letras = DIAS_LETRAS.get(dia_num, str(dia_num)).upper()
        mes_nombre = MESES.get(target_date.month, "enero")
        ano_num = str(target_date.year)

        return {
            "dia_letras": dia_letras,
            "dia_numeros": str(dia_num),
            "mes": mes_nombre,
            "ano": ano_num,
            "fecha_iso": target_date.isoformat(),
            "texto_completo": f"el día {dia_letras.lower()} ({dia_num}) del mes de {mes_nombre} de {ano_num}"
        }

    def format_currency_legal(self, amount: float) -> Tuple[str, str, str]:
        """
        Devuelve la terna (formato_numeros, letras_oficial, texto_combinado)
        Ej: ('$ 5.000.000', 'CINCO MILLONES DE PESOS M/CTE.', '$ 5.000.000 (CINCO MILLONES DE PESOS M/CTE.)')
        """
        try:
            val_int = int(round(amount))
            formatted_num = f"${val_int:,.0f}".replace(",", ".")
            words = numero_a_letras_cop(val_int)
            combined = f"{formatted_num} ({words})"
            return formatted_num, words, combined
        except Exception as e:
            logger.warning(f"Error formateando moneda legal: {e}")
            val_clean = f"${int(round(amount)):,}".replace(",", ".") if amount else "$0"
            return val_clean, "", val_clean

    def validate_requirements(
        self,
        tipologia: Optional[str],
        objeto_contrato: Optional[str],
        valor_adicion: Optional[float],
        razon_tecnica: Optional[str]
    ) -> Dict[str, Any]:
        """
        Aplica la Regla de Oro:
        Verifica si se cuenta con los 4 datos técnicos obligatorios para estructurar
        la justificación sin inventar causas ni recurrir a frases genéricas.
        """
        missing_fields = []

        # 1. Tipo de contrato
        tipo_clean = (tipologia or "").strip()
        if not tipo_clean:
            missing_fields.append("tipo_contrato")

        # 2. Objeto del contrato
        objeto_clean = (objeto_contrato or "").strip()
        if not objeto_clean or len(objeto_clean) < 8:
            missing_fields.append("objeto_contrato")

        # 3. Razón técnica específica (insustituible)
        razon_clean = (razon_tecnica or "").strip()
        es_generica = False
        if not razon_clean or len(razon_clean) < 12:
            es_generica = True
        else:
            lower_r = razon_clean.lower()
            for pat in self.GENERIC_REASON_PATTERNS:
                if re.match(pat, lower_r, re.IGNORECASE):
                    es_generica = True
                    break

        if es_generica:
            missing_fields.append("razon_tecnica_especifica")

        # 4. Valor a adicionar
        if valor_adicion is None or valor_adicion <= 0:
            missing_fields.append("valor_adicion")

        is_valid = len(missing_fields) == 0

        # Construir prompt de detención y solicitud de información si falta algún dato
        inquiry_prompt = (
            "Para estructurar la Justificación Técnica, Jurídica y Financiera de la adición contractual "
            "sin incurrir en causas genéricas o inventadas (Regla de Oro), por favor proporcione los siguientes datos indispensables:\n\n"
            "1. ¿Cuál es el tipo de contrato? (Suministro, Prestación de Servicios, Obra, Arrendamiento, Consultoría).\n"
            "2. ¿Cuál es el objeto del contrato?\n"
            "3. ¿Cuál es la razón técnica y específica por la que el presupuesto inicial se agotó o es insuficiente? "
            "(Ej: \"Aumentó la turbiedad del río y se necesitó más sulfato\", \"Se encontraron cantidades de obra no previstas en la excavación\", "
            "\"Se requiere extender el servicio por 2 meses más debido a X motivo\").\n"
            "4. ¿Cuál es el valor a adicionar?"
        )

        return {
            "valid": is_valid,
            "missing_fields": missing_fields,
            "questions": self.REQUIRED_QUESTIONS,
            "inquiry_prompt": inquiry_prompt
        }

    def generate_justification(
        self,
        numero_contrato: str,
        objeto_contrato: str,
        tipologia: str,
        valor_adicion: float,
        necesidad_usuario: Optional[str] = None,
        override_api_key: Optional[str] = None,
        valor_inicial: Optional[float] = None,
        contratista_nombre: Optional[str] = None,
        plazo_texto: Optional[str] = None,
        razon_tecnica: Optional[str] = None
    ) -> str:
        """
        Redacta una justificación jurídica, técnica y financiera rigurosa para la adición de recursos
        en tres apartados específicos, basada estrictamente en la razón técnica suministrada por el usuario,
        el régimen de la Ley 142 de 1994 (art. 31 y 32) y la garantía de continuidad del servicio público de la ESPY.

        Regla de Oro: NUNCA inventa la causa ni usa frases genéricas como 'agotamiento del inventario operativo'
        a menos que el usuario lo indique. Si faltan datos técnicos específicos, se detiene y los pregunta.
        """
        motivo_efectivo = (razon_tecnica or necesidad_usuario or "").strip()

        # Validación estricta de la Regla de Oro
        validation = self.validate_requirements(
            tipologia=tipologia,
            objeto_contrato=objeto_contrato,
            valor_adicion=valor_adicion,
            razon_tecnica=motivo_efectivo
        )

        if not validation["valid"]:
            logger.info("Deteniendo redacción de adición por falta de datos técnicos específicos (Regla de Oro). Solicitando información...")
            return validation["inquiry_prompt"]

        formatted_val, val_letras, _ = self.format_currency_legal(valor_adicion)
        formatted_vini, _, _ = self.format_currency_legal(valor_inicial) if valor_inicial else ("", "", "")

        # Invocación a Gemini AI si está disponible
        client = gemini_service._get_client(override_api_key)
        if client:
            system_prompt = (
                "Rol del Agente:\n"
                "Eres un abogado experto en contratación estatal, derecho privado aplicado a Empresas de Servicios Públicos Domiciliarios "
                "(Ley 142 de 1994) y estructuración de proyectos. Tu tarea es redactar \"Justificaciones Técnicas, Jurídicas y Financieras\" "
                "para la adición de valor a contratos existentes de la Empresa de Servicios Públicos de Yolombó E.S.P. (ESPY).\n\n"
                "Regla de Oro:\n"
                "NUNCA debes inventar la causa de la adición ni usar frases genéricas como \"agotamiento del inventario operativo\" "
                "a menos que el usuario lo indique expresamente. La justificación técnica debe construirse única y exclusivamente sobre el motivo "
                "técnico específico suministrado por el usuario.\n"
                "Si el usuario te pide una justificación y no te proporciona los detalles técnicos específicos, DEBES DETENERTE Y PREGUNTARLE "
                "los siguientes datos antes de redactar el documento:\n"
                "1. ¿Cuál es el tipo de contrato? (Suministro, Prestación de Servicios, Obra, Arrendamiento, Consultoría).\n"
                "2. ¿Cuál es el objeto del contrato?\n"
                "3. ¿Cuál es la razón técnica y específica por la que el presupuesto inicial se agotó o es insuficiente? "
                "(Ej: \"Aumentó la turbiedad del río y se necesitó más sulfato\", \"Se encontraron cantidades de obra no previstas en la excavación\", "
                "\"Se requiere extender el servicio por 2 meses más debido a X motivo\").\n"
                "4. ¿Cuál es el valor a adicionar?\n\n"
                "Estructura del Documento a Generar:\n"
                "Una vez tengas la información solicitada, redactarás la justificación en TRES (3) APARTADOS obligatorios y titulados:\n\n"
                "1. Contexto Contractual (Hechos):\n"
                "Inicia mencionando que, en el marco de la ejecución del contrato (Número y Tipo), cuyo objeto es (Objeto literal), "
                "la empresa ha evaluado el avance físico y financiero.\n\n"
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                "Adapta la redacción estrictamente al TIPO DE CONTRATO y al MOTIVO ESPECÍFICO dado por el usuario:\n"
                "- Si es SUMINISTRO: Enfócate en las fluctuaciones de la demanda, el aumento en la tasa de consumo de insumos/materiales "
                "operativos no previstos inicialmente y la necesidad de mantener el stock para garantizar el servicio.\n"
                "- Si es PRESTACIÓN DE SERVICIOS: Enfócate en el aumento de la carga operativa, la necesidad de dar continuidad a procesos "
                "administrativos/técnicos indispensables, o la aparición de nuevas necesidades misionales que el contratista debe seguir cubriendo.\n"
                "- Si es OBRA: Enfócate en las mayores cantidades de obra ejecutadas que superaron las proyectadas en los diseños iniciales, "
                "o la aparición de ítems no previstos necesarios para la funcionalidad de la infraestructura.\n"
                "- Si es ARRENDAMIENTO: Enfócate en la necesidad de prolongar la tenencia del bien mueble/inmueble para el funcionamiento "
                "ininterrumpido de las áreas operativas.\n"
                "- Si es CONSULTORÍA: Enfócate en la necesidad de profundizar los alcances de los estudios o análisis técnicos especializados "
                "indispensables para la viabilidad de los proyectos de la entidad.\n\n"
                "3. Justificación Jurídica y Financiera (Soporte Legal):\n"
                "Cierra conectando la necesidad técnica con la obligación legal de la empresa. Menciona que, bajo el régimen del derecho privado "
                "(Arts. 31 y 32 de la Ley 142 de 1994) y el deber de asegurar la prestación continua y eficiente de los servicios públicos, "
                "es imperioso adicionar la suma de (Valor a adicionar en números y letras). Aclara siempre que el objeto del contrato original "
                "permanece inalterable.\n\n"
                "ENTREGA ÚNICAMENTE el texto redactado con los tres apartados numerados y titulados exactamente como:\n"
                "1. Contexto Contractual (Hechos):\n"
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                "3. Justificación Jurídica y Financiera (Soporte Legal):"
            )
            user_content = (
                f"Entidad Contratante: Empresa de Servicios Públicos de Yolombó E.S.P. (ESPY)\n"
                f"Contrato No.: {numero_contrato}\n"
                f"Tipo de Contrato: {tipologia}\n"
                f"Contratista: {contratista_nombre or 'Contratista Seleccionado'}\n"
                f"Objeto del Contrato: {objeto_contrato}\n"
                f"Valor Inicial: {formatted_vini or 'Estipulado en minuta original'} COP\n"
                f"Valor a Adicionar: {formatted_val} ({val_letras})\n"
                f"Plazo Pactado: {plazo_texto or 'Vigente'}\n"
                f"Motivo Técnico Específico Suministrado por el Usuario: {motivo_efectivo}\n\n"
                f"Redacta el documento formal en los tres apartados obligatorios respetando estrictamente la Regla de Oro."
            )
            try:
                logger.info(f"Generando justificación jurídica especializada en 3 apartados para adición de {numero_contrato}...")
                resp = client.models.generate_content(
                    model=gemini_service.model_name,
                    contents=user_content,
                    config={
                        "system_instruction": system_prompt,
                        "temperature": 0.25,
                    }
                )
                if resp.text and len(resp.text.strip()) > 80:
                    cleaned_ai = resp.text.strip().replace("```", "").strip()
                    # Verificar que contenga los apartados
                    if "Contexto Contractual" in cleaned_ai and "Justificación Jurídica" in cleaned_ai:
                        return cleaned_ai
            except Exception as e:
                logger.warning(f"Aviso en servicio Gemini para justificación de adición ({e}), activando generador normativo estructurado...")

        # Generador normativo estructurado de 3 apartados (Fallback infalible de alta precisión jurídica)
        return self._generate_normative_fallback(
            numero_contrato=numero_contrato,
            objeto_contrato=objeto_contrato,
            tipologia=tipologia,
            valor_adicion=valor_adicion,
            motivo_especifico=motivo_efectivo,
            valor_inicial=valor_inicial,
            contratista_nombre=contratista_nombre,
            plazo_texto=plazo_texto
        )

    def _generate_normative_fallback(
        self,
        numero_contrato: str,
        objeto_contrato: str,
        tipologia: str,
        valor_adicion: float,
        motivo_especifico: str,
        valor_inicial: Optional[float] = None,
        contratista_nombre: Optional[str] = None,
        plazo_texto: Optional[str] = None
    ) -> str:
        """
        Generador normativo estructurado de justificación técnica, jurídica y financiera en 3 apartados
        para contratos de Empresas de Servicios Públicos Domiciliarios bajo la Ley 142 de 1994.
        Cumple estrictamente la Regla de Oro incorporando el motivo real del usuario sin invenciones genéricas.
        """
        formatted_val, val_letras, _ = self.format_currency_legal(valor_adicion)
        tipo_clean = tipologia.replace("_", " ").lower()
        objeto_clean = (objeto_contrato or "").strip().rstrip(".")
        motivo_clean = motivo_especifico.strip().rstrip(".")

        # Determinar denominación del tipo de contrato
        if "suministro" in tipo_clean:
            tipo_nombre = "Suministro"
        elif "obra" in tipo_clean:
            tipo_nombre = "Obra"
        elif "arrendamiento" in tipo_clean:
            tipo_nombre = "Arrendamiento"
        elif "consultor" in tipo_clean:
            tipo_nombre = "Consultoría"
        elif "interventor" in tipo_clean:
            tipo_nombre = "Interventoría"
        else:
            tipo_nombre = "Prestación de Servicios"

        # 1. Contexto Contractual (Hechos)
        apartado_1 = (
            "1. Contexto Contractual (Hechos):\n"
            f"En el marco de la ejecución del Contrato de {tipo_nombre} No. {numero_contrato}, cuyo objeto "
            f"consiste expresamente en «{objeto_clean}», la Empresa de Servicios Públicos de Yolombó E.S.P. (ESPY) "
            f"ha evaluado rigurosamente el avance físico y financiero de la ejecución contractual, constatando que "
            f"las obligaciones pactadas se han venido desarrollando de acuerdo con los requerimientos previstos y que, "
            f"a fin de garantizar la culminación integral y oportuna de las metas contractuales dentro del plazo estipulado, "
            f"resulta procedente efectuar la correspondiente adecuación presupuestal."
        )

        # 2. Justificación Técnica Específica (El "Por qué" real) según tipología
        if "suministro" in tipo_clean:
            apartado_2 = (
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                f"Tratándose de un contrato de suministro, la adición presupuestal responde directamente a las fluctuaciones "
                f"de la demanda operativa, el aumento imprevisto en la tasa de consumo de insumos y materiales operativos indispensables "
                f"para la marcha de la empresa y la necesidad inaplazable de mantener el stock de seguridad para garantizar la continuidad "
                f"del servicio público, obedeciendo de manera puntual y demostrada a que: {motivo_clean}. La disponibilidad oportuna "
                f"de estos insumos en bodega es condición sine qua non para evitar traumatismos o suspensión en las actividades a cargo de la ESPY."
            )
        elif "obra" in tipo_clean:
            apartado_2 = (
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                f"En lo referente a la ejecución del contrato de obra, la adición de recursos se sustenta técnicamente en las "
                f"mayores cantidades de obra ejecutadas que superaron las inicialmente proyectadas en los diseños e ítems contractuales, "
                f"así como en la necesidad de acometer requerimientos técnicos no previstos indispensables para asegurar la funcionalidad, "
                f"estabilidad y correcta operación de la infraestructura, originado específicamente en que: {motivo_clean}. Estas intervenciones "
                f"en terreno son estrictamente necesarias para garantizar la calidad final de las obras y la idónea prestación de los servicios."
            )
        elif "arrendamiento" in tipo_clean:
            apartado_2 = (
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                f"Respecto al contrato de arrendamiento, la justificación técnica radica en la imperiosa necesidad de prolongar la "
                f"tenencia del bien mueble o inmueble para asegurar el funcionamiento ininterrumpido de las áreas operativas y "
                f"administrativas de la entidad, derivado concretamente de que: {motivo_clean}. Preservar la disposición física del bien "
                f"garantiza la logística y permanencia indispensable para no afectar las actividades misionales de la empresa."
            )
        elif "consultor" in tipo_clean:
            apartado_2 = (
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                f"En el contrato de consultoría, la adición presupuestal se justifica en la necesidad técnica de profundizar y "
                f"extender los alcances analíticos de los estudios, evaluaciones y conceptos técnicos especializados indispensables para "
                f"la viabilidad y estructuración de los proyectos a cargo de la entidad, soportado puntualmente en que: {motivo_clean}. "
                f"Dichos insumos técnicos son determinantes para la correcta toma de decisiones y planeación institucional de la ESPY."
            )
        else:  # PRESTACIÓN DE SERVICIOS
            apartado_2 = (
                "2. Justificación Técnica Específica (El \"Por qué\" real):\n"
                f"Tratándose de un contrato de prestación de servicios, la presente adición se fundamenta técnicamente en el aumento "
                f"de la carga operativa, la necesidad de dar continuidad ininterrumpida a procesos administrativos y técnicos indispensables "
                f"para la entidad, y la aparición de nuevas necesidades misionales que el contratista debe seguir cubriendo, sustentado "
                f"de manera específica en que: {motivo_clean}. La continuidad de estas labores asistenciales y de apoyo especializado "
                f"resulta indispensable para no menoscabar la gestión institucional ni paralizar los frentes de atención a cargo de la empresa."
            )

        # 3. Justificación Jurídica y Financiera (Soporte Legal)
        apartado_3 = (
            "3. Justificación Jurídica y Financiera (Soporte Legal):\n"
            f"De conformidad con el régimen especial de derecho privado aplicable a los actos y contratos de las Empresas de "
            f"Servicios Públicos Domiciliarios consagrado en los artículos 31 y 32 de la Ley 142 de 1994, y en pleno cumplimiento del "
            f"deber legal de asegurar la prestación continua y eficiente de los servicios públicos, es imperioso adicionar al contrato "
            f"la suma de {formatted_val} ({val_letras}). Con estos recursos se restablece la suficiencia financiera requerida para "
            f"culminar cabalmente las obligaciones contractuales, dejando expresa constancia de que el objeto del contrato original "
            f"permanece inalterable, idéntico e incólume, sin que se modifiquen las especificaciones técnicas ni las obligaciones "
            f"originalmente asumidas por el contratista."
        )

        return f"{apartado_1}\n\n{apartado_2}\n\n{apartado_3}"

addition_agent = AdditionAgent()


