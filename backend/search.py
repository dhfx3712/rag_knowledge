import os
import faiss
import numpy as np
# from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from .models import Document

INDEX_PATH = "./data/index/faiss.index"
# MODEL_NAME = "all-MiniLM-L6-v2"

# Mock embedding function for now (replace with Volcengine later)
def mock_embed(texts):
    # Simple hash-based embedding for demonstration
    embeddings = []
    for text in texts:
        h = hash(text)
        vec = [(h >> (i * 8)) & 0xFF for i in range(48)]  # 48-dimensional vector
        # Normalize
        norm = np.linalg.norm(vec)
        if norm == 0:
            vec = [0.0]*48
        else:
            vec = [v / norm for v in vec]
        embeddings.append(vec)
    return np.array(embeddings, dtype=np.float32)

class SearchEngine:
    def __init__(self):
        # self.model = SentenceTransformer(MODEL_NAME)
        self.index = None
        self.doc_ids = []
        self._load_index()

    def _load_index(self):
        if os.path.exists(INDEX_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            doc_ids_path = INDEX_PATH + ".doc_ids.npy"
            if os.path.exists(doc_ids_path):
                self.doc_ids = np.load(doc_ids_path).tolist()
        else:
            self.index = faiss.IndexFlatL2(48)  # 48 dimensions for mock embeddings

    def _save_index(self):
        faiss.write_index(self.index, INDEX_PATH)
        np.save(INDEX_PATH + ".doc_ids.npy", np.array(self.doc_ids))

    def add_document(self, doc_id: int, content: str):
        # embedding = self.model.encode([content])[0]
        embedding = mock_embed([content])[0]
        self.index.add(np.array([embedding]))
        self.doc_ids.append(doc_id)
        self._save_index()

    def update_document(self, doc_id: int, content: str):
        # Rebuild index for simplicity (we can optimize later)
        pass

    def delete_document(self, doc_id: int):
        # Rebuild index for simplicity (we can optimize later)
        pass

    def rebuild_index(self, db: Session):
        self.index = faiss.IndexFlatL2(48)
        self.doc_ids = []
        if db:
            docs = db.query(Document).all()
            for doc in docs:
                # embedding = self.model.encode([doc.content])[0]
                embedding = mock_embed([doc.content])[0]
                self.index.add(np.array([embedding]))
                self.doc_ids.append(doc.id)
        self._save_index()

    def semantic_search(self, query: str, top_k: int = 5):
        if self.index.ntotal == 0:
            return []
        # query_embedding = self.model.encode([query])[0]
        query_embedding = mock_embed([query])[0]
        distances, indices = self.index.search(np.array([query_embedding]), top_k)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.doc_ids):
                results.append({"doc_id": self.doc_ids[idx], "score": float(distances[0][i])})
        return results

search_engine = SearchEngine()
