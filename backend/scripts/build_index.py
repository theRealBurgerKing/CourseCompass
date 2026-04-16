"""Pre-build the FAISS vector index from the UNSW course CSV.

Run from the backend/ directory:
    python -m scripts.build_index
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.rag.vectorstore import build_vectorstore

if __name__ == "__main__":
    build_vectorstore()
    print("Index build complete.")
