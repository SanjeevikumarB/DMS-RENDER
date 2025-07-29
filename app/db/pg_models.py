from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text, BigInteger, JSON, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.pg_database import PostgresBase
import uuid
import enum

class FileObject(PostgresBase):
    __tablename__ = "files_fileobject"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(UUID(as_uuid=True), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(10), nullable=False)
    description = Column(Text, nullable=True)
    extension = Column(String(20), nullable=True)
    size = Column(BigInteger, default=0)
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    accessed_at = Column(DateTime)
    file_metadata = Column(JSON, nullable=True)
    uploaded_url = Column(String, nullable=True)
    presigned_url = Column(String, nullable=True)
    latest_version_id = Column(String(255), nullable=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=True)
    tags = Column(Text, nullable=True)
    trashed_at = Column(DateTime, nullable=True)
    # relationships
    parent = relationship('FileObject', remote_side=[uid], backref='children')

class FileVersion(PostgresBase):
    __tablename__ = "files_fileversion"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=False)
    version_number = Column(Integer)
    action = Column(String(50))
    metadata_snapshot = Column(JSON)
    s3_version_id = Column(String(255), nullable=True)
    created_at = Column(DateTime)
    created_by_id = Column(UUID(as_uuid=True), nullable=True)

class TrashAutoCleanQueue(PostgresBase):
    __tablename__ = "files_trashautocleanqueue"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=False)
    scheduled_delete_at = Column(DateTime)
    status = Column(String(50))
    deleted_at = Column(DateTime, nullable=True)
    restored_at = Column(DateTime, nullable=True)

class StarredFile(PostgresBase):
    __tablename__ = "files_starredfile"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=False)
    starred_at = Column(DateTime)

class FileAccessControl(PostgresBase):
    __tablename__ = "sharing_fileaccesscontrol"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    access_level = Column(String(20))
    granted_by_id = Column(UUID(as_uuid=True), nullable=True)
    granted_at = Column(DateTime)
    inherited = Column(Boolean, default=False)
    inherited_from_id = Column(UUID(as_uuid=True), nullable=True)

class FileShareRequest(PostgresBase):
    __tablename__ = "sharing_filesharerequest"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=False)
    requester_id = Column(UUID(as_uuid=True), nullable=False)
    access_type = Column(String(20))
    status = Column(String(20))
    reason = Column(Text, nullable=True)
    reviewed_by_id = Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime)

class ShareableLink(PostgresBase):
    __tablename__ = "sharing_shareablelink"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=False)
    link_type = Column(String(20))
    created_by_id = Column(UUID(as_uuid=True), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    url_token = Column(String(100), unique=True)
    created_at = Column(DateTime)

class Notification(PostgresBase):
    __tablename__ = "notifications_notification"
    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    recipient_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(String(50))
    title = Column(String(255))
    message = Column(Text)
    related_file_id = Column(UUID(as_uuid=True), ForeignKey('files_fileobject.uid'), nullable=True)
    created_at = Column(DateTime)
    read = Column(Boolean, default=False)