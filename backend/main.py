from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .database import get_db, engine, Base
from .models import Document
from .schemas import DocumentCreate, DocumentUpdate, DocumentInDB
from .search import search_engine
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
import re

# Configure enhanced logging
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
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
def find_keyword_matches(content, query, context_chars=100):
    """Find all occurrences of query in content and return with context"""
    matches = []
    # Case-insensitive search
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    for match in pattern.finditer(content):
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

# Middleware to log all requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"Request: {request.method} {request.url} from {client_host}")
    
    try:
        response = await call_next(request)
        process_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Response: {response.status_code} for {request.method} {request.url} (took {process_time:.2f}s)")
        return response
    except Exception as e:
        process_time = (datetime.now() - start_time).total_seconds()
        logger.error(f"Request failed: {request.method} {request.url} - Error: {str(e)} (took {process_time:.2f}s)", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# Mount frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")

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
        
        db_doc = Document(
            title=title,
            content=content,
            category=category,
            tags=tags
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        
        # Save Markdown file in category-specific directory
        category_dir = get_category_dir(category)
        doc_path = os.path.join(category_dir, f"{db_doc.id}.md")
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Document saved to file: {doc_path}")
        
        # Add to search index
        search_engine.add_document(db_doc.id, content)
        logger.info(f"Document created successfully with id={db_doc.id}")
        return db_doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating document: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/documents/", response_model=list[DocumentInDB])
def read_documents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    logger.info(f"Reading documents: skip={skip}, limit={limit}")
    try:
        docs = db.query(Document).offset(skip).limit(limit).all()
        logger.info(f"Found {len(docs)} documents")
        return docs
    except Exception as e:
        logger.error(f"Error reading documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/documents/{doc_id}", response_model=DocumentInDB)
def read_document(doc_id: int, db: Session = Depends(get_db)):
    logger.info(f"Reading document with id={doc_id}")
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if doc is None:
            logger.warning(f"Document with id={doc_id} not found")
            raise HTTPException(status_code=404, detail="Document not found")
        logger.info(f"Found document: id={doc.id}, title=\"{doc.title}\"")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading document id={doc_id}: {str(e)}", exc_info=True)
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
    logger.info(f"Updating document with id={doc_id}: title=\"{title}\", category=\"{category}\"")
    try:
        db_doc = db.query(Document).filter(Document.id == doc_id).first()
        if db_doc is None:
            logger.warning(f"Document with id={doc_id} not found for update")
            raise HTTPException(status_code=404, detail="Document not found")
        
        old_category = db_doc.category
        
        # Read content from file if provided, otherwise use content field
        if file:
            logger.info(f"Reading content from uploaded file: {file.filename}")
            content_bytes = await file.read()
            content = content_bytes.decode("utf-8")
        elif not content:
            # If no file or content provided, keep existing content
            content = db_doc.content
            logger.debug("Keeping existing document content")
        
        # Delete old file if category changed
        if old_category != category:
            old_category_dir = get_category_dir(old_category)
            old_doc_path = os.path.join(old_category_dir, f"{doc_id}.md")
            if os.path.exists(old_doc_path):
                os.remove(old_doc_path)
                logger.info(f"Deleted old document file: {old_doc_path}")
        
        # Update database
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
        
        # Rebuild search index (simple approach for now)
        search_engine.rebuild_index(db)
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
        
        db.delete(db_doc)
        db.commit()
        
        # Delete Markdown file from category directory
        category_dir = get_category_dir(db_doc.category)
        doc_path = os.path.join(category_dir, f"{doc_id}.md")
        if os.path.exists(doc_path):
            os.remove(doc_path)
            logger.info(f"Deleted document file: {doc_path}")
        
        # Rebuild search index
        search_engine.rebuild_index(db)
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
        # Keyword search using SQLite LIKE
        keyword_results = db.query(Document).filter(
            or_(
                Document.title.contains(query),
                Document.content.contains(query)
            )
        ).all()
        logger.debug(f"Keyword search found {len(keyword_results)} results")
        
        # Semantic search
        semantic_results = search_engine.semantic_search(query)
        logger.debug(f"Semantic search found {len(semantic_results)} results")
        
        semantic_doc_ids = [r["doc_id"] for r in semantic_results]
        semantic_docs = db.query(Document).filter(Document.id.in_(semantic_doc_ids)).all()
        
        # Combine and deduplicate results
        combined = {doc.id: doc for doc in keyword_results}
        for doc in semantic_docs:
            if doc.id not in combined:
                combined[doc.id] = doc
        
        # Prepare search results with keyword matches
        result_docs = []
        for doc_id, doc in combined.items():
            # Find keyword matches in content
            matches = find_keyword_matches(doc.content, query)
            result_docs.append({
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "tags": doc.tags,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "matches": matches,
                "match_count": len(matches),
                "is_keyword_match": doc in keyword_results
            })
        
        # Sort by number of matches (descending)
        result_docs.sort(key=lambda x: x["match_count"], reverse=True)
        
        logger.info(f"Search returned {len(result_docs)} results total")
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
