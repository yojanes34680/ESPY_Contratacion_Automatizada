"""
Utilidades unificadas de normalización y tokenización para el clasificador UNSPSC.
Garantiza coherencia entre el índice BM25, la búsqueda híbrida y la selección.
"""
import re
import unicodedata
from typing import List

# Palabras vacías canónicas para la clasificación de bienes y servicios
STOPWORDS_UNSPSC = {
    "para", "con", "por", "sobre", "del", "las", "los", "una", "uno", "unos", "unas",
    "que", "cual", "cuales", "como", "sin", "sus", "mas", "menos", "entre", "hacia",
    "desde", "hasta", "durante", "mediante", "segun", "ademas", "tipo", "clase",
    "suministro", "suministros", "adquisicion", "compra", "prestacion", "servicio",
    "servicios", "contratacion", "empresa", "publicos", "publicas", "municipio"
}

def normalize_text(text: str) -> str:
    """Normaliza texto: minúsculas, sin acentos/tildes, limpia caracteres no alfanuméricos."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    no_acc = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r'[^a-z0-9\s]', ' ', no_acc.lower()).strip()

def tokenize(text: str) -> List[str]:
    """
    Tokeniza texto en palabras léxicas relevantes (longitud >= 3, sin stopwords)
    y genera formas morfológicas (singular / plural en español).
    """
    norm = normalize_text(text)
    raw_words = [w for w in norm.split() if len(w) >= 3 and w not in STOPWORDS_UNSPSC]
    
    tokens = []
    for w in raw_words:
        if w not in tokens:
            tokens.append(w)
        # Reglas morfológicas para singular y plural
        if w.endswith("es") and len(w) > 4:
            singular = w[:-2]
            if singular not in tokens:
                tokens.append(singular)
        elif w.endswith("s") and not w.endswith("es") and len(w) > 3:
            singular = w[:-1]
            if singular not in tokens:
                tokens.append(singular)
        else:
            if w.endswith(("a", "e", "i", "o", "u")):
                plural = w + "s"
                if plural not in tokens:
                    tokens.append(plural)
            else:
                plural = w + "es"
                if plural not in tokens:
                    tokens.append(plural)
                    
    return tokens
