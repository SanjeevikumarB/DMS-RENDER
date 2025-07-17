from sqlalchemy import Column, Integer, String, Enum, DateTime
from datetime import datetime
from .database import Base
import enum

class FileStatusEnum(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    failed = "failed"

class FileRecord(Base):
    __tablename__ = "file_metadata"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    extension = Column(String)
    content_type = Column(String)
    size = Column(Integer)
    s3_key = Column(String, unique=True)
    version_id = Column(String)  
    status = Column(Enum(FileStatusEnum), default=FileStatusEnum.uploaded)
    created_at = Column(DateTime, default=datetime.utcnow)
