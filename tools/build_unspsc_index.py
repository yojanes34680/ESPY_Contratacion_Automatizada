"""
Script de construcción del índice de catálogo UNSPSC y embeddings.
Incluye jerarquía oficial (Segmento, Familia, Clase y Producto).
Calcula y guarda:
- Textos jerárquicos por código.
- Índice BM25 tokenizado y normalizado usando texto.py.
- Embeddings semánticos con Gemini (gemini-embedding-001 o text-embedding-004) si hay API key configurada.
"""
import os
import sys
import pickle
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Configurar path a backend
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.config import settings
from app.utils.logger import logger
from app.services.agents.unspsc.texto import normalize_text, tokenize

def load_hierarchy_names() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Carga los nombres de segmentos y clases para enriquecer el contexto jerárquico."""
    segmentos = {}
    csv_path = backend_path / "app" / "resources" / "unspsc_jerarquia.csv"
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) >= 3 and parts[1].strip() == "Segmento":
                    seg_code = parts[0].strip().zfill(2)
                    segmentos[seg_code] = parts[2].strip()

    # Cargar clases desde el pickle existente
    clases = {}
    pickle_path = backend_path / "app" / "resources" / "codigos_unspsc_cache.pickle"
    if pickle_path.exists():
        with open(pickle_path, "rb") as f:
            code_desc, _, _ = pickle.load(f)
            for c, d in code_desc.items():
                if c.endswith("00"):
                    clases[c] = d

    return segmentos, clases

def build_index():
    pickle_path = backend_path / "app" / "resources" / "codigos_unspsc_cache.pickle"
    if not pickle_path.exists():
        print(f"Error: No se encontró {pickle_path}")
        return

    print("Cargando catálogo oficial UNSPSC...")
    with open(pickle_path, "rb") as f:
        code_desc, _, _ = pickle.load(f)

    segmentos_map, clases_map = load_hierarchy_names()
    print(f"Segmentos cargados: {len(segmentos_map)} | Clases cargadas: {len(clases_map)}")

    codes_list = []
    texts_hierarchical = []
    tokenized_corpus = []

    for code, desc in code_desc.items():
        seg_id = code[:2]
        cla_id = code[:6] + "00"

        seg_nombre = segmentos_map.get(seg_id, "")
        cla_nombre = clases_map.get(cla_id, "")

        # Formato: "<descripción del código> | Clase: <nombre de la clase> | Segmento: <nombre>"
        h_text = desc
        if cla_nombre and cla_nombre != desc:
            h_text += f" | Clase: {cla_nombre}"
        if seg_nombre:
            h_text += f" | Segmento: {seg_nombre}"

        codes_list.append(code)
        texts_hierarchical.append(h_text)
        tokenized_corpus.append(tokenize(h_text))

    print(f"Construyendo índice BM25 sobre {len(codes_list)} códigos...")
    from rank_bm25 import BM25Okapi
    bm25 = BM25Okapi(tokenized_corpus)

    # Guardar índice BM25 y textos jerárquicos
    index_out = backend_path / "app" / "resources" / "unspsc_bm25_index.pickle"
    with open(index_out, "wb") as f:
        pickle.dump({
            "codes": codes_list,
            "hierarchical_texts": texts_hierarchical,
            "bm25": bm25
        }, f)
    print(f"Índice léxico BM25 guardado con éxito en: {index_out}")

    # Paso 6: Embeddings semánticos con gemini-embedding-001 en lotes de 100 con checkpoint
    key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    emb_out = backend_path / "app" / "resources" / "unspsc_embeddings.npy"
    codes_order_out = backend_path / "app" / "resources" / "unspsc_embeddings_codes.json"
    checkpoint_out = backend_path / "app" / "resources" / "unspsc_embeddings_progress.json"

    if key:
        print("API Key detectada. Procediendo a verificar/calcular embeddings con Gemini...")
        try:
            import numpy as np
            from google import genai

            client = genai.Client(api_key=key)

            # Cargar progreso si existe
            start_idx = 0
            all_embeddings = []
            if checkpoint_out.exists() and emb_out.exists():
                try:
                    with open(checkpoint_out, "r", encoding="utf-8") as f_chk:
                        chk_data = json.load(f_chk)
                        start_idx = chk_data.get("next_idx", 0)
                    all_embeddings = list(np.load(emb_out))
                    print(f"Reanudando cálculo de embeddings desde el índice {start_idx}...")
                except Exception as e_chk:
                    print(f"Aviso al reanudar checkpoint: {e_chk}. Iniciando desde cero.")
                    start_idx = 0
                    all_embeddings = []

            batch_size = 100
            total_items = len(texts_hierarchical)
            
            for i in range(start_idx, total_items, batch_size):
                batch_texts = texts_hierarchical[i:i + batch_size]
                # Reintentos con espera exponencial
                max_retries = 3
                batch_embs = None
                for attempt in range(max_retries):
                    try:
                        response = client.models.embed_content(
                            model="gemini-embedding-001",
                            contents=batch_texts,
                            config={"task_type": "RETRIEVAL_DOCUMENT"}
                        )
                        # Extraer vectores
                        if hasattr(response, "embeddings"):
                            batch_embs = [e.values for e in response.embeddings]
                        break
                    except Exception as e_emb:
                        if attempt == max_retries - 1:
                            print(f"Error permanente en lote {i}-{i+len(batch_texts)}: {e_emb}")
                            raise
                        time.sleep(2 * (attempt + 1))

                if batch_embs:
                    all_embeddings.extend(batch_embs)
                    # Guardar avance periódico
                    np.save(emb_out, np.array(all_embeddings, dtype=np.float32))
                    with open(checkpoint_out, "w", encoding="utf-8") as f_chk:
                        json.dump({"next_idx": i + len(batch_texts), "total": total_items}, f_chk)
                    print(f"Progreso embeddings: {len(all_embeddings)} / {total_items}")

            # Guardar orden de códigos final
            with open(codes_order_out, "w", encoding="utf-8") as f_co:
                json.dump(codes_list, f_co)
            print(f"Cálculo de embeddings finalizado exitosamente ({len(all_embeddings)} vectores).")
        except Exception as e_total:
            print(f"Aviso durante el cálculo de embeddings: {e_total}")
    else:
        print("Aviso: No se detectó GEMINI_API_KEY configurada. El índice léxico jerárquico BM25 está completamente listo y operativo.")

if __name__ == "__main__":
    build_index()
