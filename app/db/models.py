# app/db/models.py

from sqlalchemy import Column, Integer, String, Enum, DateTime
from .database import Base
from datetime import datetime
import enum

class FileStatusEnum(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    failed = "failed"

class PermissionEnum(str, enum.Enum):
    read = "read"
    write = "write"
    owner = "owner"
    admin = "admin"

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

class FileACL(Base):
    __tablename__ = "file_acl"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(255), nullable=False)
    user_id = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=True)
    access_type = Column(Enum(PermissionEnum), nullable=False)

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(255), unique=True, nullable=False)
