"""
Script ejecutor de construcción de índice y embeddings UNSPSC.
Redirige y ejecuta tools/build_unspsc_index.py
"""
import sys
from pathlib import Path

tools_path = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(tools_path))

from build_unspsc_index import build_index

if __name__ == "__main__":
    build_index()
