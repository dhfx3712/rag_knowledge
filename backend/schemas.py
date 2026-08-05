from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class DocumentBase(BaseModel):
    title: str
    category: str
    tags: str

class DocumentCreate(DocumentBase):
    content: str

class DocumentUpdate(DocumentBase):
    content: str

class DocumentInDB(DocumentBase):
    id: int
    content: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DocumentListItem(DocumentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
