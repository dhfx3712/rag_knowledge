from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .database import get_db, engine, Base
from .models import Document
from .schemas import DocumentCreate, DocumentUpdate, DocumentInDB, DocumentListItem
from .search import search_engine
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import re

# Configure enhanced logging
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG);
    
    # Format: timestamp - logger_name - level - filename:line - message
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Ensure log directory exists
    os.makedirs('./data', exist_ok=True)
    
    # File handler - rotate daily, keep 30 days of logs
    file_handler = TimedRotatingFileHandler(
        './data/app.log',
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    file_handler.suffix = "%Y-%m-%d"  # Log file suffix
    
    # Stream handler - only INFO and above
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(log_format)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    
    return logging.getLogger(__name__)

logger = setup_logging()

Base.metadata.create_all(bind=engine)

app = FastAPI()

# Helper function to find keyword matches with context
def find_keyword_matches(content, query, context_chars=100, max_matches=10):
    """Find all occurrences of query in content and return with context, up to max_matches"""
    matches = []
    # Case-insensitive search
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    for match in pattern.finditer(content):
        if len(matches) >= max_matches:
            break
        start_idx = max(0, match.start() - context_chars)
        end_idx = min(len(content), match.end() + context_chars)
        
        # Get context
        context_before = content[start_idx:match.start()]
        context_after = content[match.end():end_idx]
        matched_text = content[match.start():match.end()]
        
        matches.append({
            "start": match.start(),
            "end": match.end(),
            "context_before": context_before,
            "matched_text": matched_text,
            "context_after": context_after
        })
    
    return matches

# Middleware to log all requests with detailed timing
import time
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    client_host = request.client.host if request.client else "unknown"
    
    # 更详细的请求监控
    request_id = f"{int(time.time() * 1000000)}"
    logger.info(f"[REQ-{request_id}] Request: {request.method} {request.url} from {client_host}")
    
    try:
        response = await call_next(request)
        total_time = (time.time() - start_time) * 1000
        logger.info(f"[REQ-{request_id}] Response: {response.status_code} | Total: {total_time:.2f}ms | URL: {request.method} {request.url}")
        response.headers["X-Response-Time"] = f"{total_time:.2f}"
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception as e:
        error_time = (time.time() - start_time) * 1000
        logger.error(f"[REQ-{request_id}] Request failed after {error_time:.2f}ms: {request.method} {request.url} - Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# Mount frontend static files with timing monitoring
import time
class TimedStaticFiles(StaticFiles):
    async def __call__(self, scope, receive, send):
        start_time = time.time()
        path = scope.get('path', '')
        try:
            await super().__call__(scope, receive, send)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"[STATIC] Served {path} in {elapsed:.2f}ms")
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"[STATIC] Failed to serve {path} after {elapsed:.2f}ms: {str(e)}", exc_info=True)
            raise

app.mount("/static", TimedStaticFiles(directory="frontend"), name="static")

# Serve frontend
@app.get("/")
async def read_root():
    logger.debug("Serving frontend index.html")
    return FileResponse("frontend/index.html")

# Helper function to get category directory path
def get_category_dir(category):
    category_dir = f"./data/docs/{category}"
    os.makedirs(category_dir, exist_ok=True)
    return category_dir

# Document CRUD endpoints
@app.post("/documents/", response_model=DocumentInDB)
async def create_document(
    title: str = Form(...),
    category: str = Form(...),
    tags: str = Form(...),
    file: UploadFile = File(None),
    content: str = Form(""),
    db: Session = Depends(get_db)
):
    logger.info(f"Creating document: title=\"{title}\", category=\"{category}\", tags=\"{tags}\"")
    try:
        # Read content from file if provided, otherwise use content field
        if file:
            logger.info(f"Reading content from uploaded file: {file.filename}, size: {file.size if file.size else 'unknown'} bytes")
            content_bytes = await file.read()
            content = content_bytes.decode("utf-8")
            logger.debug(f"File content length: {len(content)} characters")
        
        # Create database document
        db_doc = Document(
            title=title,
            content=content,
            category=category,
            tags=tags
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        
        # Save Markdown file
        category_dir = get_category_dir(category)
        doc_path = os.path.join(category_dir, f"{db_doc.id}.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Document saved to file: {doc_path}")
        
        # Add to search index
        search_engine.add_document(db_doc.id, content, db)
        logger.info(f"Document created successfully with id={db_doc.id}")
        return db_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/documents/", response_model=list[DocumentListItem])
def list_documents(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(20, ge=1, le=100, description="每页返回的记录数"),
    db: Session = Depends(get_db)
):
    logger.info(f"Listing documents: skip={skip}, limit={limit}")
    try:
        import time
        db_query_start = time.time()
        documents = db.query(Document).order_by(
            Document.created_at.desc()
        ).offset(skip).limit(limit).all()
        db_query_time = (time.time() - db_query_start) * 1000
        logger.info(f"[DB] Query completed in {db_query_time:.2f}ms | Returning {len(documents)} documents")
        return documents
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/documents/{doc_id}", response_model=DocumentInDB)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    logger.info(f"Getting document with id={doc_id}")
    try:
        db_doc = db.query(Document).filter(Document.id == doc_id).first()
        if db_doc is None:
            logger.warning(f"Document with id={doc_id} not found")
            raise HTTPException(status_code=404, detail="Document not found")
        return db_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document id={doc_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/documents/{doc_id}", response_model=DocumentInDB)
async def update_document(
    doc_id: int,
    title: str = Form(...),
    category: str = Form(...),
    tags: str = Form(...),
    file: UploadFile = File(None),
    content: str = Form(""),
    db: Session = Depends(get_db)
):
    logger.info(f"Updating document with id={doc_id}")
    try:
        db_doc = db.query(Document).filter(Document.id == doc_id).first()
        if db_doc is None:
            logger.warning(f"Document with id={doc_id} not found for update")
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Read content from file if provided, otherwise use content field
        if file:
            logger.info(f"Reading content from uploaded file for update: {file.filename}")
            content_bytes = await file.read()
            content = content_bytes.decode("utf-8")
        
        # Delete old file if category changed
        if db_doc.category != category:
            old_category_dir = get_category_dir(db_doc.category)
            old_doc_path = os.path.join(old_category_dir, f"{doc_id}.md")
            if os.path.exists(old_doc_path):
                os.remove(old_doc_path)
                logger.info(f"Deleted old document file: {old_doc_path}")
        
        # Update database document
        db_doc.title = title
        db_doc.content = content
        db_doc.category = category
        db_doc.tags = tags
        db.commit()
        db.refresh(db_doc)
        
        # Save new Markdown file in new category directory
        category_dir = get_category_dir(category)
        doc_path = os.path.join(category_dir, f"{db_doc.id}.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Updated document saved to file: {doc_path}")
        
        # Update search index
        search_engine.update_document(db_doc.id, content, db)
        logger.info(f"Document updated successfully with id={db_doc.id}")
        return db_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document id={doc_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    logger.info(f"Deleting document with id={doc_id}")
    try:
        db_doc = db.query(Document).filter(Document.id == doc_id).first()
        if db_doc is None:
            logger.warning(f"Document with id={doc_id} not found for deletion")
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete Markdown file first
        category_dir = get_category_dir(db_doc.category)
        doc_path = os.path.join(category_dir, f"{doc_id}.md")
        if os.path.exists(doc_path):
            os.remove(doc_path)
            logger.info(f"Deleted document file: {doc_path}")
        
        # Delete from database
        db.delete(db_doc)
        db.commit()
        
        # Delete from search index
        search_engine.delete_document(doc_id, db)
        logger.info(f"Document deleted successfully with id={doc_id}")
        return {"message": "Document deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document id={doc_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

# Search endpoints
@app.get("/search/")
def search_documents(query: str, db: Session = Depends(get_db)):
    logger.info(f"Searching documents with query='{query}'")
    try:
        import time
        
        # Step 1: 先做关键词搜索，但只获取 ID（减少数据传输）
        keyword_start = time.time()
        keyword_ids = [
            doc.id for doc in db.query(Document.id).filter(
                or_(
                    Document.title.contains(query),
                    Document.content.contains(query)
                )
            ).all()
        ]
        keyword_time = (time.time() - keyword_start) * 1000
        logger.debug(f"Keyword search found {len(keyword_ids)} results in {keyword_time:.2f}ms")
        
        # Step 2: 语义搜索
        semantic_start = time.time()
        semantic_results = search_engine.semantic_search(query)
        semantic_time = (time.time() - semantic_start) * 1000
        logger.debug(f"Semantic search found {len(semantic_results)} results in {semantic_time:.2f}ms")
        
        semantic_doc_ids = [r["doc_id"] for r in semantic_results]
        
        # Step 3: 合并所有需要的文档 ID，去重
        all_doc_ids = list(set(keyword_ids + semantic_doc_ids))
        logger.debug(f"Total unique documents to fetch: {len(all_doc_ids)}")
        
        # Step 4: 一次数据库查询获取所有文档（减少往返）
        fetch_start = time.time()
        all_docs = db.query(Document).filter(Document.id.in_(all_doc_ids)).all()
        fetch_time = (time.time() - fetch_start) * 1000
        logger.debug(f"Fetched {len(all_docs)} documents in {fetch_time:.2f}ms")
        
        # Step 5: 建立文档字典方便查找
        doc_dict = {doc.id: doc for doc in all_docs}
        
        # Step 6: 准备结果
        result_docs = []
        for doc_id in all_doc_ids:
            doc = doc_dict.get(doc_id)
            if not doc:
                continue
                
            matches = find_keyword_matches(doc.content, query)
            result_docs.append({
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "tags": doc.tags,
                "content": doc.content,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "matches": matches,
                "match_count": len(matches),
                "is_keyword_match": doc_id in keyword_ids
            })
        
        # 排序
        result_docs.sort(key=lambda x: x["match_count"], reverse=True)
        
        total_time = (time.time() - keyword_start) * 1000
        logger.info(f"Search returned {len(result_docs)} results in {total_time:.2f}ms total")
        return result_docs
    except Exception as e:
        logger.error(f"Error searching documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# Initialize search index on startup
@app.on_event("startup")
def startup_event():
    logger.info("=" * 50)
    logger.info("Starting up Codex RAG application...")
    logger.info("=" * 50)
    try:
        db = next(get_db())
        search_engine.rebuild_index(db)
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}", exc_info=True)

@app.on_event("shutdown")
def shutdown_event():
    logger.info("=" * 50)
    logger.info("Shutting down Codex RAG application...")
    logger.info("=" * 50)
