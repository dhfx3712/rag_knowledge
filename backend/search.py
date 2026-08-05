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
            vec = [v / norm if norm != 0 else 0.0 for v in vec]
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
                # 确保是 IndexIDMap 类型
                if not hasattr(self.index, 'id_map'):
                    logger.warning("Loaded index is not IndexIDMap, converting...")
                    # 转换为 IndexIDMap
                    flat_index = self.index
                    self.index = faiss.IndexIDMap(faiss.IndexFlatL2(48))
                    if flat_index.ntotal > 0:
                        # 重建 id 映射，这里我们简单处理，实际需要加载旧的 doc_ids
                        logger.warning("Cannot recover old IDs, will rebuild index on next operation")
                doc_ids_path = INDEX_PATH + ".doc_ids.npy"
                if os.path.exists(doc_ids_path):
                    self.doc_ids = np.load(doc_ids_path).tolist()
                logger.info(f"Successfully loaded index with {len(self.doc_ids)} documents")
            except Exception as e:
                logger.error(f"Failed to load index: {str(e)}", exc_info=True)
                self.index = faiss.IndexIDMap(faiss.IndexFlatL2(48))
                self.doc_ids = []
        else:
            logger.info("No existing index found, creating new empty index")
            self.index = faiss.IndexIDMap(faiss.IndexFlatL2(48))
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
            # 如果 ID 已存在，先删除
            if doc_id in self.doc_ids:
                logger.warning(f"Document id={doc_id} already exists, removing old entry first")
                self.index.remove_ids(np.array([doc_id], dtype=np.int64))
                self.doc_ids.remove(doc_id)
            
            # embedding = self.model.encode([content])[0]
            embedding = mock_embed([content])[0]
            self.index.add_with_ids(np.array([embedding]), np.array([doc_id], dtype=np.int64))
            self.doc_ids.append(doc_id)
            self._save_index()
            logger.debug(f"Document id={doc_id} added to index successfully")
        except Exception as e:
            logger.error(f"Failed to add document id={doc_id} to index: {str(e)}", exc_info=True)

    def update_document(self, doc_id: int, content: str, db: Session = None):
        logger.info(f"Updating document id={doc_id} in search index")
        try:
            # 如果 ID 存在，先删除
            if doc_id in self.doc_ids:
                self.index.remove_ids(np.array([doc_id], dtype=np.int64))
                self.doc_ids.remove(doc_id)
            
            # 添加新的
            # embedding = self.model.encode([content])[0]
            embedding = mock_embed([content])[0]
            self.index.add_with_ids(np.array([embedding]), np.array([doc_id], dtype=np.int64))
            self.doc_ids.append(doc_id)
            self._save_index()
            logger.info(f"Document id={doc_id} updated in index successfully")
        except Exception as e:
            logger.error(f"Failed to update document id={doc_id} in index: {str(e)}", exc_info=True)

    def delete_document(self, doc_id: int, db: Session = None):
        logger.info(f"Deleting document id={doc_id} from search index")
        try:
            if doc_id in self.doc_ids:
                self.index.remove_ids(np.array([doc_id], dtype=np.int64))
                self.doc_ids.remove(doc_id)
                self._save_index()
                logger.info(f"Document id={doc_id} deleted from index successfully")
            else:
                logger.warning(f"Document id={doc_id} not found in index, nothing to delete")
        except Exception as e:
            logger.error(f"Failed to delete document id={doc_id} from index: {str(e)}", exc_info=True)

    def rebuild_index(self, db: Session):
        logger.info("Rebuilding search index...")
        try:
            self.index = faiss.IndexIDMap(faiss.IndexFlatL2(48))
            self.doc_ids = []
            doc_count = 0
            if db:
                docs = db.query(Document).all()
                for doc in docs:
                    # embedding = self.model.encode([doc.content])[0]
                    embedding = mock_embed([doc.content])[0]
                    self.index.add_with_ids(np.array([embedding]), np.array([doc.id], dtype=np.int64))
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
            distances, indices = self.index.search(np.array([query_embedding]), min(top_k, self.index.ntotal))
            
            results = []
            seen_doc_ids = set()
            for i, idx in enumerate(indices[0]):
                if 0 <= idx < len(self.doc_ids):
                    doc_id = self.doc_ids[idx]
                    score = float(distances[0][i])
                    # Skip duplicates and invalid scores
                    if doc_id not in seen_doc_ids and score < 1e10:
                        results.append({"doc_id": doc_id, "score": score})
                        seen_doc_ids.add(doc_id)
                        logger.debug(f"Found result: doc_id={doc_id}, score={score:.4f}")
            
            logger.info(f"Semantic search returned {len(results)} unique results")
            return results
        except Exception as e:
            logger.error(f"Failed to perform semantic search: {str(e)}", exc_info=True)
            return []

search_engine = SearchEngine()
