from sqlalchemy.exc import SQLAlchemyError
from app.db.database import SessionLocal
from app.db.models import FileRecord, FileStatusEnum
from fastapi import HTTPException

def save_file_record_to_db(data: dict):
    db = SessionLocal()
    try:
        record = FileRecord(
            filename=data["filename"],
            extension=data["extension"],
            content_type=data["content_type"],
            size=data["size"],
            s3_key=data["s3_key"],
            version_id=data.get("version_id"), 
            status=FileStatusEnum(data["status"])
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database insert failed: {str(e)}")
    finally:
        db.close()


def update_file_status(s3_key: str, status: FileStatusEnum):
    db = SessionLocal()
    try:
        record = db.query(FileRecord).filter(FileRecord.s3_key == s3_key).first()
        if not record:
            raise HTTPException(status_code=404, detail="File record not found")
        record.status = status
        db.commit()
        db.refresh(record)
        return record
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Status update failed: {str(e)}")
    finally:
        db.close()
