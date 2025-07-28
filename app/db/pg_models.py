from sqlalchemy import Column, String
from app.db.pg_database import PostgresBase

class FileObject(PostgresBase):
    __tablename__ = "files_fileobject"

    uid = Column(String, primary_key=True)        # File ID
    owner_id = Column(String, nullable=False)     # Owner/User ID
    name = Column(String, nullable=False)         # File name