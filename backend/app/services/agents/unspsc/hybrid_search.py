"""
Motor de búsqueda híbrida para el Agente UNSPSC.
Combina búsqueda léxica BM25 por palabras completas normalizadas
(sin tildes, singular/plural, sin subcadenas espurias)
y embeddings semánticos (si están disponibles),
fusionados mediante Reciprocal Rank Fusion (RRF k=60).
La búsqueda se hace por ítem, no con el texto completo del estudio previo.
"""
import os
import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
import numpy as np

from app.config import settings
from app.utils.logger import logger
from .schemas import DocumentItem
from .texto import normalize_text, tokenize

class HybridSearchEngine:
    def __init__(self, resources_dir: Optional[Path] = None):
        default_resources = Path(__file__).resolve().parent.parent.parent.parent / "resources"
        self.resources_dir = resources_dir or default_resources
        self.index_data = None
        self.codes = []
        self.hierarchical_texts = []
        self.bm25 = None
        self.embeddings = None
        self.embeddings_codes = []
        self.sinonimos = {}
        self._historical_cache = None # Cache de feedback histórico en memoria
        self._load_index()
        self._load_sinonimos()
        self._load_embeddings()

    def _load_index(self):
        index_file = self.resources_dir / "unspsc_bm25_index.pickle"
        if index_file.exists():
            try:
                with open(index_file, "rb") as f:
                    self.index_data = pickle.load(f)
                    self.codes = self.index_data.get("codes", [])
                    self.hierarchical_texts = self.index_data.get("hierarchical_texts", [])
                    self.bm25 = self.index_data.get("bm25")
                    logger.info(f"[HybridSearchEngine] Índice léxico cargado: {len(self.codes)} códigos.")
            except Exception as e:
                logger.error(f"[HybridSearchEngine] Error cargando índice BM25: {e}", exc_info=True)
        else:
            logger.error(f"[HybridSearchEngine] No existe archivo de índice BM25: {index_file}")

    def _load_sinonimos(self):
        sinonimos_file = self.resources_dir / "unspsc_sinonimos.json"
        if sinonimos_file.exists():
            try:
                with open(sinonimos_file, "r", encoding="utf-8") as f:
                    self.sinonimos = json.load(f)
            except Exception as e:
                logger.warning(f"[HybridSearchEngine] Error cargando sinonimos: {e}")
                self.sinonimos = {}

    def _load_embeddings(self):
        emb_file = self.resources_dir / "unspsc_embeddings.npy"
        codes_file = self.resources_dir / "unspsc_embeddings_codes.json"
        if emb_file.exists() and codes_file.exists():
            try:
                self.embeddings = np.load(emb_file)
                with open(codes_file, "r", encoding="utf-8") as f:
                    self.embeddings_codes = json.load(f)
                logger.info(f"[HybridSearchEngine] Embeddings semánticos cargados: {len(self.embeddings)} vectores.")
            except Exception as e:
                logger.warning(f"[HybridSearchEngine] Error cargando embeddings: {e}")
                self.embeddings = None

    def reload_historical_feedback(self):
        """Recarga el historial de feedback en memoria con tokens precalculados."""
        try:
            from app.database import SessionLocal
            from app.models.unspsc import UnspscHistoricalFeedback
            db = SessionLocal()
            try:
                records = db.query(UnspscHistoricalFeedback).all()
                cache = []
                for rec in records:
                    desc_val = str(rec.item_descripcion or "")
                    desc_norm = normalize_text(desc_val)
                    tokens = set(tokenize(desc_norm))
                    cache.append({
                        "codigo": str(rec.codigo_unspsc or ""),
                        "desc_norm": desc_norm,
                        "tokens": tokens
                    })
                self._historical_cache = cache
                logger.info(f"[HybridSearchEngine] Historial de feedback recargado en memoria: {len(cache)} registros.")
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"Historial feedback no cargado: {e}")
            self._historical_cache = []

    def get_historical_boost_codes(self, item_tokens: List[str], query_text: str) -> Set[str]:
        if self._historical_cache is None:
            self.reload_historical_feedback()

        boost_codes = set()
        norm_q = normalize_text(query_text)
        it_tokens_set = set(item_tokens)

        cache = self._historical_cache or []
        for entry in cache:
            shared = it_tokens_set & entry["tokens"]
            if len(shared) >= 2 or norm_q in entry["desc_norm"] or entry["desc_norm"] in norm_q:
                boost_codes.add(entry["codigo"])

        return boost_codes

    def _get_embedding_top_candidates(self, query_text: str, top_n: int = 30) -> List[Tuple[str, float]]:
        """Calcula embedding para la consulta y retorna top_n códigos por similitud coseno."""
        if self.embeddings is None or not settings.GEMINI_API_KEY:
            return []
        try:
            from google import genai
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            resp = client.models.embed_content(
                model="gemini-embedding-001",
                contents=query_text,
                config={"task_type": "RETRIEVAL_QUERY"}
            )
            if not hasattr(resp, "embeddings") or not resp.embeddings:
                return []
            q_vec = np.array(resp.embeddings[0].values, dtype=np.float32)
            # Similitud coseno
            norms = np.linalg.norm(self.embeddings, axis=1) * (np.linalg.norm(q_vec) + 1e-9)
            sims = np.dot(self.embeddings, q_vec) / (norms + 1e-9)
            top_indices = np.argsort(sims)[::-1][:top_n]
            return [(self.embeddings_codes[idx], float(sims[idx])) for idx in top_indices if idx < len(self.embeddings_codes)]
        except Exception as e:
            logger.warning(f"[HybridSearchEngine] Error en búsqueda semántica de embeddings: {e}")
            return []

    def search_candidates_for_item(
        self,
        item: DocumentItem,
        objeto_context: str = "",
        top_k: int = 25
    ) -> List[Dict]:
        """
        Busca los top_k mejores códigos para un ítem concreto.
        Combina BM25 léxico y Embeddings (RRF) con filtros de categoría.
        """
        if not self.bm25 or not self.codes:
            return []

        # Paso 5: Buscar con descripcion + terminos_catalogo
        terminos = " ".join(getattr(item, "terminos_catalogo", []) or [])
        query_text = f"{item.descripcion} {terminos}".strip() if terminos else item.descripcion
        item_tokens = tokenize(query_text)

        # Expansión de sinónimos desde unspsc_sinonimos.json
        item_expanded = list(item_tokens)
        for t in item_tokens:
            if t in self.sinonimos:
                for syn in self.sinonimos[t]:
                    if syn not in item_expanded:
                        item_expanded.append(syn)

        norm_desc_it = normalize_text(item.descripcion)
        norm_ctx_obj = normalize_text(objeto_context or "")
        is_mano_obra_it = (
            norm_desc_it in ("mano de obra", "mano de obra dias", "mano de obra en dias") or
            "mano de obra" in norm_desc_it
        )
        is_visita_tecnica_it = "visita tecnica" in norm_desc_it
        is_installation_or_works = any(k in norm_ctx_obj for k in ["instalacion", "obra", "construccion", "carpinteria", "pasamanos", "barandas"])

        if is_mano_obra_it or is_visita_tecnica_it:
            labor_terms = ["instalacion", "montaje", "carpinteria", "pasamanos", "barandas"]
            if any(k in norm_ctx_obj for k in ["acueducto", "valvula", "tuberia"]):
                labor_terms.extend(["acueducto", "valvulas", "tuberias"])
            item_expanded = labor_terms + [w for w in item_tokens if w not in ("mano", "obra", "dias", "dia")]

        obj_tokens = tokenize(objeto_context) if objeto_context else []

        # Historial de feedback en memoria
        historical_boost_codes = self.get_historical_boost_codes(item_tokens, query_text)

        # 1. Scoring léxico BM25
        scores_item = self.bm25.get_scores(item_expanded)
        scores_obj = self.bm25.get_scores(obj_tokens) if obj_tokens else [0.0] * len(self.codes)

        bm25_ranked = []
        for idx in range(len(self.codes)):
            sc_it = scores_item[idx]
            sc_ob = scores_obj[idx]
            if sc_it <= 0 and sc_ob <= 0:
                continue

            total_score = (sc_it * 2.5) + (sc_ob * 0.5)
            code = self.codes[idx]
            seg = int(code[:2])

            # Bloquear segmento 86 (Entrenamiento) y 90 (Catering) en contratos de instalación u obra
            if is_installation_or_works and (seg in (86, 90) or code.startswith("8610")):
                continue
            if code.startswith("8610"):
                continue

            adj_score = total_score
            # Paso 4: Si la naturaleza es bien o servicio claro, ajustar puntaje. Si es obra o mixto, no castigar
            if item.naturaleza == "bien" and seg >= 70:
                adj_score *= 0.1
            elif item.naturaleza in ("servicio", "consultoria") and seg < 70:
                adj_score *= 0.1

            if (is_mano_obra_it or is_visita_tecnica_it) and code == "72152300":
                adj_score *= 3.0

            desc_norm = normalize_text(self.hierarchical_texts[idx])
            nuclear_matches = sum(1 for w in item_tokens[:3] if f" {w} " in f" {desc_norm} ")
            if nuclear_matches > 0:
                adj_score *= (1.0 + (0.25 * nuclear_matches))

            if code.endswith("00"):
                adj_score *= 1.25

            if item.naturaleza == "bien" and seg == 60:
                adj_score *= 0.3

            if code in historical_boost_codes:
                adj_score *= 1.5

            if adj_score > 0:
                bm25_ranked.append((adj_score, code, idx))

        bm25_ranked.sort(key=lambda x: x[0], reverse=True)
        top_bm25 = bm25_ranked[:100]

        # 2. Búsqueda semántica de embeddings si están disponibles
        sem_ranked = self._get_embedding_top_candidates(f"{query_text} {item.cita_literal}".strip(), top_n=30)

        # 3. Fusión Reciprocal Rank Fusion (RRF k=60) si hay embeddings; de lo contrario ranking BM25
        code_to_idx = {c: i for i, c in enumerate(self.codes)}
        
        if sem_ranked:
            k_rrf = 60
            rrf_scores = {}
            for rank, (score, code, idx) in enumerate(top_bm25):
                rrf_scores[code] = rrf_scores.get(code, 0.0) + (1.0 / (k_rrf + rank + 1))
            for rank, (code, score) in enumerate(sem_ranked):
                if code in code_to_idx:
                    rrf_scores[code] = rrf_scores.get(code, 0.0) + (1.0 / (k_rrf + rank + 1))

            fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
            candidates = []
            for code, sc in fused:
                idx = code_to_idx.get(code)
                if idx is not None:
                    candidates.append({
                        "codigo": code,
                        "jerarquia": self.hierarchical_texts[idx],
                        "score": float(sc)
                    })
            return candidates

        # Si no hay embeddings disponibles, retornar top_k de BM25
        candidates = []
        for sc, code, idx in top_bm25[:top_k]:
            candidates.append({
                "codigo": code,
                "jerarquia": self.hierarchical_texts[idx],
                "score": float(sc)
            })
        return candidates
