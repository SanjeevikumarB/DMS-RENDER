from app.db.pg_database import AsyncPostgresSessionLocal
from app.db.pg_models import FileObject

def get_file_owners():
    db = AsyncPostgresSessionLocal()
    try:
        return db.query(FileObject.uid, FileObject.owner_id, FileObject.name).all()
    finally:
        db.close()


