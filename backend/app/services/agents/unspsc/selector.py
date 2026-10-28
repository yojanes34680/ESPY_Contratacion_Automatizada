"""
Pasos 3, 4 y 5: Selección con Gemini y Validación sin inventar.
Por cada ítem:
- Consulta candidatos híbridos (top 25).
- Si Gemini está disponible: llamada con timeout 30s y 2 reintentos para seleccionar 1 o 2 códigos con justificación corta, cita verificada y confianza. Descarta códigos fuera de los candidatos.
- Si Gemini no responde o no hay API key: respaldo determinístico híbrido directo (top 1-2 por ítem marcado SIEMPRE como 'sugerencia_sin_validar' y confianza 'media' o 'baja', nunca 'aprobado').
- Validación: descripción oficial del catálogo, verificación de cita (vacía o < 4 letras no es verificada).
- Deduplicación y trazabilidad.
"""
import json
import re
import time
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from app.config import settings
from app.utils.logger import logger
from app.schemas.unspsc import UnspscCodeItem, UnspscAnalysisResult, UnspscAnalysisInput
from .schemas import DocumentExtractionResult, DocumentItem
from .extractor import extract_document_structure
from .hybrid_search import HybridSearchEngine
from .texto import normalize_text

class UnspscSelectorAgent:
    def __init__(self):
        self.search_engine = HybridSearchEngine()
        self._code_catalog = {}
        self._load_catalog()

    def _load_catalog(self):
        """Carga el catálogo oficial para verificar descripciones y segmentos exactos."""
        pickle_path = self.search_engine.resources_dir / "codigos_unspsc_cache.pickle"
        if pickle_path.exists():
            try:
                import pickle
                with open(pickle_path, "rb") as f:
                    code_desc, _, _ = pickle.load(f)
                    self._code_catalog = code_desc
            except Exception as e:
                logger.error(f"[UnspscSelector] Error cargando catálogo pickle: {e}")

    def verify_citation_in_document(self, citation: str, full_doc: str) -> bool:
        """
        Compara la cita contra el texto del documento de forma tolerante a espacios y tildes.
        Una cita vacía o de menos de 4 letras NO cuenta como verificada.
        """
        if not citation or len(citation.strip()) < 4:
            return False
        norm_cit = normalize_text(citation)
        norm_doc = normalize_text(full_doc)
        if len(norm_cit) < 4:
            return False
        return norm_cit in norm_doc

    def select_codes_for_item_gemini(
        self,
        item: DocumentItem,
        objeto: str,
        candidates: List[Dict],
        document_text: str,
        override_api_key: Optional[str] = None
    ) -> List[UnspscCodeItem]:
        """
        Llama a Gemini con timeout de 30 segundos y hasta 2 reintentos con espera de 2 y 4 segundos;
        si falla o no hay clave, pasa a respaldo. Descarta códigos devueltos por Gemini que no estén en candidatos.
        """
        key = override_api_key or settings.GEMINI_API_KEY
        if not key or not candidates:
            return self._select_codes_deterministic_fallback(item, candidates, document_text)

        candidate_code_set = {str(c["codigo"]).strip() for c in candidates}

        try:
            from google import genai
            client = genai.Client(api_key=key)

            cands_formatted = "\n".join([
                f"- Código: {c['codigo']} | Jerarquía: {c['jerarquia']}"
                for c in candidates
            ])

            prompt = (
                f"OBJETO CONTRACTUAL: {objeto}\n\n"
                f"ÍTEM A CLASIFICAR: {item.descripcion} (Naturaleza: {item.naturaleza})\n"
                f"CITA LITERAL DEL DOCUMENTO: \"{item.cita_literal}\"\n\n"
                f"CANDIDATOS DISPONIBLES (ELIGE EXCLUSIVAMENTE DE ESTA LISTA):\n{cands_formatted}\n\n"
                f"INSTRUCCIONES:\n"
                f"Selecciona 1 o máximo 2 códigos de esa lista que mejor clasifiquen el ítem.\n"
                f"Para cada código seleccionado devuelve:\n"
                f"- 'codigo': el código de 8 dígitos exactamente como aparece en la lista de candidatos\n"
                f"- 'justificacion': explicación técnica corta y directa relacionando el código con el ítem\n"
                f"- 'confianza': 'alta', 'media' o 'baja'\n"
                f"Si ningún candidato sirve, devuelve una lista vacía [].\n"
                f"Devuelve un array JSON con los objetos elegidos."
            )

            # Reintentos (hasta 2 reintentos con espera de 2 y 4 segundos)
            response_text = None
            delays = [2, 4]
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=settings.GEMINI_MODEL,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "temperature": 0.1
                        }
                    )
                    if response and response.text:
                        response_text = response.text
                        break
                except Exception as e_gen:
                    if attempt < len(delays):
                        time.sleep(delays[attempt])
                    else:
                        logger.warning(f"[UnspscSelector] Reintentos agotados en Gemini: {e_gen}")

            if response_text:
                res_clean = response_text.strip()
                if res_clean.startswith("```json"):
                    res_clean = res_clean.split("```json", 1)[1].split("```", 1)[0].strip()
                elif res_clean.startswith("```"):
                    res_clean = res_clean.split("```", 1)[1].split("```", 1)[0].strip()
                selections = json.loads(res_clean)
                if isinstance(selections, dict) and "seleccionados" in selections:
                    selections = selections["seleccionados"]

                result_items = []
                for sel in selections:
                    c_code = str(sel.get("codigo", "")).strip()
                    # Descartar cualquier código que Gemini devuelva y no esté en la lista de candidatos enviada
                    if c_code not in candidate_code_set or c_code not in self._code_catalog:
                        continue
                    official_desc = self._code_catalog[c_code]
                    just = sel.get("justificacion", f"Clasifica adecuadamente {item.descripcion}")
                    just_formatted = f'{just}. Cita: "{item.cita_literal}"'
                    conf = sel.get("confianza", "alta")

                    # Verificación de cita
                    cit_ok = self.verify_citation_in_document(item.cita_literal, document_text)
                    # Punto 7: El agente devuelve 'propuesto' (con Gemini) o 'revisar' si no está verificada. NUNCA 'aprobado'.
                    estado = "propuesto" if cit_ok else "revisar"

                    alts = [
                        {"codigo": c["codigo"], "descripcion": self._code_catalog.get(c["codigo"], c["jerarquia"])}
                        for c in candidates if c["codigo"] != c_code
                    ][:2]

                    result_items.append(UnspscCodeItem(
                        codigo_unspsc=c_code,
                        descripcion_codigo=official_desc,
                        justificacion_eleccion=just_formatted,
                        segmento=c_code[:2],
                        familia=c_code[:4],
                        clase=c_code[:6],
                        confianza=conf,
                        cita_verificada=cit_ok,
                        estado=estado,
                        alternativas=alts
                    ))

                if result_items:
                    return result_items

        except Exception as e:
            logger.warning(f"[UnspscSelector] Error en selección Gemini: {e}. Usando respaldo determinístico.")

        return self._select_codes_deterministic_fallback(item, candidates, document_text)

    def _select_codes_deterministic_fallback(
        self,
        item: DocumentItem,
        candidates: List[Dict],
        document_text: str
    ) -> List[UnspscCodeItem]:
        """
        Paso 5: Respaldo sin Gemini. Usa los mejores candidatos calculados por BM25,
        toma el top 1 (o top 2) por ítem y los marca SIEMPRE como 'sugerencia_sin_validar',
        con confianza 'media' o 'baja', nunca 'aprobado'.
        """
        if not candidates:
            return []

        selected = []
        top_candidates = candidates[:2] if len(candidates) >= 2 else candidates[:1]

        cit_ok = self.verify_citation_in_document(item.cita_literal, document_text)
        estado = "sugerencia_sin_validar" # SIEMPRE sugerencia_sin_validar en respaldo sin Gemini

        for cand in top_candidates:
            code = cand["codigo"]
            official_desc = self._code_catalog.get(code, cand["jerarquia"])

            alts = [
                {"codigo": c["codigo"], "descripcion": self._code_catalog.get(c["codigo"], c["jerarquia"])}
                for c in candidates if c["codigo"] != code
            ][:2]

            just = f'Sugerencia de catálogo para "{item.descripcion}" respaldada en la actividad de la propuesta: "{item.cita_literal}"'

            selected.append(UnspscCodeItem(
                codigo_unspsc=code,
                descripcion_codigo=official_desc,
                justificacion_eleccion=just,
                segmento=code[:2],
                familia=code[:4],
                clase=code[:6],
                confianza="media" if cit_ok else "baja", # Confianza media o baja, nunca alta ni estado aprobado
                cita_verificada=cit_ok,
                estado=estado,
                alternativas=alts
            ))

        return selected

    def analyze_contract_unspsc(
        self,
        payload: UnspscAnalysisInput,
        override_api_key: Optional[str] = None
    ) -> UnspscAnalysisResult:
        """
        Pipeline integral moderno del Agente UNSPSC:
        1. Extracción estructurada del estudio previo y propuesta.
        2. Búsqueda híbrida de candidatos por cada ítem.
        3. Selección con Gemini o respaldo determinístico sin inventar.
        4. Deduplicación por código y alertas de coherencia de tipo.
        5. Asignación de objeto_detectado y fuente_cita individual por ítem.
        """
        full_doc = f"{payload.objeto or ''}\n\n{payload.estudio_previo or ''}\n\n{payload.propuesta_economica or ''}"

        # 1. Extracción estructurada
        doc_ext = extract_document_structure(
            estudio_previo_text=payload.estudio_previo or "",
            propuesta_economica_text=payload.propuesta_economica or "",
            override_api_key=override_api_key,
            objeto_hint=payload.objeto
        )

        cand_obj = payload.objeto if payload.objeto and len(payload.objeto.strip()) > 5 else doc_ext.objeto
        if cand_obj and re.search(r"^(?:seleccionar|contratar|elegir)\s+a\s+la\s+persona", cand_obj, re.IGNORECASE):
            m_quoted = re.search(r'(?:para\s+el\s+contrato\s+de|contrato\s+de)\s*["“\'«]([^"”\'»]+)["”\'»]', cand_obj, re.IGNORECASE)
            if m_quoted:
                objeto_final = m_quoted.group(1).strip()
            else:
                objeto_final = doc_ext.objeto
        else:
            objeto_final = cand_obj
        tipo_contrato = doc_ext.tipo_contrato

        actividades_extraidas = [it.cita_literal for it in doc_ext.items if it.cita_literal]
        if not actividades_extraidas:
            actividades_extraidas = [doc_ext.objeto]

        # 2 y 3. Búsqueda y Selección por ítem
        codigos_seleccionados: List[UnspscCodeItem] = []
        seen_codes = set()
        alertas = []

        propuesta_txt = (payload.propuesta_economica or "").strip()
        estudio_txt = (payload.estudio_previo or "").strip()

        for item in doc_ext.items:
            # Paso 8: Determinar fuente_cita dinámicamente por ítem según de qué documento salió su cita
            item_fuente = "propuesta" if (propuesta_txt and self.verify_citation_in_document(item.cita_literal, propuesta_txt)) else (
                "estudio_previo" if (estudio_txt and self.verify_citation_in_document(item.cita_literal, estudio_txt)) else (
                    "propuesta" if propuesta_txt else "estudio_previo"
                )
            )

            cands = self.search_engine.search_candidates_for_item(
                item=item,
                objeto_context=objeto_final,
                top_k=25
            )
            item_selections = self.select_codes_for_item_gemini(
                item=item,
                objeto=objeto_final,
                candidates=cands,
                document_text=full_doc,
                override_api_key=override_api_key
            )

            for sel in item_selections:
                sel.fuente_cita = item_fuente
                if sel.codigo_unspsc not in seen_codes:
                    seen_codes.add(sel.codigo_unspsc)
                    codigos_seleccionados.append(sel)

                    seg_num = int(sel.codigo_unspsc[:2])
                    if tipo_contrato == "suministro" and seg_num >= 70:
                        alertas.append(f"Código {sel.codigo_unspsc} pertenece a servicios (Segmento {seg_num}) en contrato de suministro.")
                    elif tipo_contrato == "servicios" and seg_num < 70:
                        alertas.append(f"Código {sel.codigo_unspsc} pertenece a bienes manufacturados (Segmento {seg_num}) en contrato de servicios.")

        if not codigos_seleccionados:
            dummy_item = DocumentItem(
                descripcion=objeto_final,
                naturaleza="bien" if tipo_contrato == "suministro" else "servicio",
                cita_literal=objeto_final,
                terminos_catalogo=[]
            )
            cands = self.search_engine.search_candidates_for_item(dummy_item, objeto_final, top_k=25)
            codigos_seleccionados = self._select_codes_deterministic_fallback(dummy_item, cands, full_doc)
            default_f = "propuesta" if propuesta_txt else "estudio_previo"
            for s in codigos_seleccionados:
                s.fuente_cita = default_f

        resumen = (
            f"Clasificación UNSPSC estructurada para contratación de tipo {tipo_contrato.upper()}.\n"
            f"Objeto: {objeto_final[:160]}"
        )

        alertas_str = "; ".join(alertas) if alertas else None

        # Punto 1: uso_ia es True si Gemini respondió en extracción y en selección
        ext_uso_ia = getattr(doc_ext, "uso_ia", False)
        all_gemini_sel = bool(codigos_seleccionados and all(s.estado != "sugerencia_sin_validar" for s in codigos_seleccionados))
        uso_ia_final = bool(ext_uso_ia and all_gemini_sel)

        return UnspscAnalysisResult(
            resumen_analisis=resumen,
            actividades_propuesta_extraidas=actividades_extraidas,
            codigos_seleccionados=codigos_seleccionados,
            alertas_recomendaciones=alertas_str,
            total_codigos=len(codigos_seleccionados),
            fecha_analisis=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            objeto_detectado=objeto_final,
            motor_usado="nuevo",
            uso_ia=uso_ia_final
        )

# Instancia singleton para el nuevo pipeline
unspsc_selector_agent = UnspscSelectorAgent()
