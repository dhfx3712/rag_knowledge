import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/db/kb.db"

# Ensure database directory exists
os.makedirs(os.path.dirname(SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")), exist_ok=True)

logger.info(f"Connecting to database at {SQLALCHEMY_DATABASE_URL}")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        logger.debug("Database session opened")
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}", exc_info=True)
        raise
    finally:
        logger.debug("Database session closed")
        db.close()
