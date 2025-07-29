from sqlalchemy import select
from app.db.pg_models import FileObject  # Extend this import as you add more models
from app.db.pg_database import AsyncPostgresSessionLocal as pg_session
from fastapi import HTTPException  
import uuid 
from app.db.pg_models import FileAccessControl

# Placeholder for FileAccessControl, PermissionEnum, etc. to be added to pg_models.py

async def has_file_access(user_id: str, file_id: str) -> bool:
    async with pg_session() as session:
        # Replace FileAccessControl with your actual ACL model
        query = select(FileAccessControl).where(
            FileAccessControl.user_id == user_id,
            FileAccessControl.file_id == file_id
        )
        result = await session.execute(query)
        acl_entry = result.scalars().first()
        return acl_entry is not None

async def get_user_permission(file_id: str, user_id: str) -> str | None:
    async with pg_session() as session:
        result = await session.execute(
            select(FileAccessControl.access_level).where(
                FileAccessControl.file_id == file_id,
                FileAccessControl.user_id == user_id
            )
        )
        permission = result.scalar_one_or_none()
        return permission
    
async def get_file_id_by_filename_and_user(filename: str, user_id: str | uuid.UUID) -> str:
    # Convert user_id to UUID if it's a string
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")

    # First, try to find file as the owner
    async with pg_session() as session:
        result = await session.execute(
            select(FileObject.uid).where(
                FileObject.name == filename,
                FileObject.owner_id == str(user_id)
            ).limit(1)
        )
        file_id = result.scalars().first()

    # If not found, try to find file via ACL (shared access)
    if not file_id:
        async with pg_session() as session:
            result = await session.execute(
                select(FileObject.uid)
                .join(FileAccessControl, FileAccessControl.file_id == FileObject.uid)
                .where(
                    FileAccessControl.user_id == str(user_id),
                    FileObject.name == filename
                )
                .limit(1)
            )
            file_id = result.scalars().first()

    if not file_id:
        raise HTTPException(status_code=403, detail="You do not have permission to view this file.")

    return str(file_id)

async def add_file_access_control(file_id: str, user_id: str, access_level: str):
    async with pg_session() as session:
        acl = FileAccessControl(
            file_id=file_id,
            user_id=user_id,
            access_level=access_level
        )
        session.add(acl)
        await session.commit()
        await session.refresh(acl)
        return acl