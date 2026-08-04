from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class DocumentBase(BaseModel):
    title: str
    content: str
    category: str
    tags: str

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(DocumentBase):
    pass

class DocumentInDB(DocumentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
