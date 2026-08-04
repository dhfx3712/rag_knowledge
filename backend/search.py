import os
import logging
import faiss
import numpy as np
# from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from .models import Document

logger = logging.getLogger(__name__)

INDEX_PATH = "./data/index/faiss.index"
# MODEL_NAME = "all-MiniLM-L6-v2"

# Mock embedding function for now (replace with Volcengine later)
def mock_embed(texts):
    # Simple hash-based embedding for demonstration
    logger.debug(f"Generating embeddings for {len(texts)} text(s)")
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
        logger.debug(f"Loading search index from {INDEX_PATH}")
        if os.path.exists(INDEX_PATH):
            try:
                self.index = faiss.read_index(INDEX_PATH)
                doc_ids_path = INDEX_PATH + ".doc_ids.npy"
                if os.path.exists(doc_ids_path):
                    self.doc_ids = np.load(doc_ids_path).tolist()
                logger.info(f"Successfully loaded index with {len(self.doc_ids)} documents")
            except Exception as e:
                logger.error(f"Failed to load index: {str(e)}", exc_info=True)
                self.index = faiss.IndexFlatL2(48)  # 48 dimensions for mock embeddings
                self.doc_ids = []
        else:
            logger.info("No existing index found, creating new empty index")
            self.index = faiss.IndexFlatL2(48)  # 48 dimensions for mock embeddings
            self.doc_ids = []

    def _save_index(self):
        logger.debug(f"Saving search index to {INDEX_PATH}")
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
            faiss.write_index(self.index, INDEX_PATH)
            np.save(INDEX_PATH + ".doc_ids.npy", np.array(self.doc_ids))
            logger.info(f"Successfully saved index with {len(self.doc_ids)} documents")
        except Exception as e:
            logger.error(f"Failed to save index: {str(e)}", exc_info=True)

    def add_document(self, doc_id: int, content: str):
        logger.info(f"Adding document id={doc_id} to search index")
        try:
            # embedding = self.model.encode([content])[0]
            embedding = mock_embed([content])[0]
            self.index.add(np.array([embedding]))
            self.doc_ids.append(doc_id)
            self._save_index()
            logger.debug(f"Document id={doc_id} added to index successfully")
        except Exception as e:
            logger.error(f"Failed to add document id={doc_id} to index: {str(e)}", exc_info=True)

    def update_document(self, doc_id: int, content: str):
        # Rebuild index for simplicity (we can optimize later)
        logger.debug(f"update_document called for doc_id={doc_id} (not implemented yet)")
        pass

    def delete_document(self, doc_id: int):
        # Rebuild index for simplicity (we can optimize later)
        logger.debug(f"delete_document called for doc_id={doc_id} (not implemented yet)")
        pass

    def rebuild_index(self, db: Session):
        logger.info("Rebuilding search index...")
        try:
            self.index = faiss.IndexFlatL2(48)
            self.doc_ids = []
            doc_count = 0
            if db:
                docs = db.query(Document).all()
                for doc in docs:
                    # embedding = self.model.encode([doc.content])[0]
                    embedding = mock_embed([doc.content])[0]
                    self.index.add(np.array([embedding]))
                    self.doc_ids.append(doc.id)
                    doc_count += 1
            self._save_index()
            logger.info(f"Index rebuilt successfully with {doc_count} documents")
        except Exception as e:
            logger.error(f"Failed to rebuild index: {str(e)}", exc_info=True)

    def semantic_search(self, query: str, top_k: int = 5):
        logger.info(f"Performing semantic search for query='{query}', top_k={top_k}")
        try:
            if self.index.ntotal == 0:
                logger.warning("Index is empty, no documents to search")
                return []
            
            # query_embedding = self.model.encode([query])[0]
            query_embedding = mock_embed([query])[0]
            distances, indices = self.index.search(np.array([query_embedding]), top_k)
            
            results = []
            for i, idx in enumerate(indices[0]):
                if idx < len(self.doc_ids):
                    result = {"doc_id": self.doc_ids[idx], "score": float(distances[0][i])}
                    results.append(result)
                    logger.debug(f"Found result: doc_id={result['doc_id']}, score={result['score']:.4f}")
            
            logger.info(f"Semantic search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Failed to perform semantic search: {str(e)}", exc_info=True)
            return []

search_engine = SearchEngine()
