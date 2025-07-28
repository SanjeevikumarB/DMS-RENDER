from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException
from sqlalchemy.future import select
from app.db.database import AsyncSessionLocal
from app.db.models import FileRecord, FileStatusEnum, FileACL, PermissionEnum, AdminUser

async def save_file_record_to_db(data: dict):
    async with AsyncSessionLocal() as db:
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
            await db.commit()
            await db.refresh(record)
            return record
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Database insert failed: {str(e)}")

async def update_file_status(s3_key: str, status: FileStatusEnum):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(FileRecord).where(FileRecord.s3_key == s3_key))
            record = result.scalar_one_or_none()
            if not record:
                raise HTTPException(status_code=404, detail="File record not found")
            record.status = status
            await db.commit()
            await db.refresh(record)
            return record
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Status update failed: {str(e)}")

async def add_file_acl(file_id: str, user_id: str, access_type: PermissionEnum, filename: str = None):
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(FileACL).where(FileACL.file_id == file_id, FileACL.user_id == user_id)
            )
            existing_acl = result.scalar_one_or_none()

            if existing_acl:
                # Optionally update filename if it's missing or different
                if filename and existing_acl.filename != filename:
                    existing_acl.filename = filename
                    await db.commit()
                    await db.refresh(existing_acl)
                return existing_acl

            # Insert new record
            acl = FileACL(
                file_id=file_id,
                user_id=user_id,
                access_type=access_type,
                filename=filename
            )
            db.add(acl)
            await db.commit()
            await db.refresh(acl)
            return acl
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"ACL insert failed: {str(e)}")


async def get_user_permission(file_id: str, user_id: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FileACL).where(FileACL.file_id == file_id, FileACL.user_id == user_id)
        )
        acl = result.scalar_one_or_none()
        return acl.access_type if acl else None

async def is_user_admin(user_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None
