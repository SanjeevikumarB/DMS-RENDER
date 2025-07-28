from sqlalchemy import select
from app.db.models import FileACL
from app.db.database import AsyncSessionLocal as async_session
from app.db.pg_database import AsyncPostgresSessionLocal as pg_session
from app.db.pg_models import FileObject
from fastapi import HTTPException  
import uuid 

async def has_file_access(user_id: str, file_id: str) -> bool:
    async with async_session() as session:
        query = select(FileACL).where(
            FileACL.user_id == user_id,
            FileACL.file_id == file_id
        )
        result = await session.execute(query)
        acl_entry = result.scalars().first()
        return acl_entry is not None

async def get_user_permission(file_id: str, user_id: str) -> str | None:
    async with async_session() as session:
        result = await session.execute(
            select(FileACL.access_type).where(
                FileACL.file_id == file_id,
                FileACL.user_id == user_id
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
                FileObject.owner_id == user_id
            ).limit(1)
        )
        file_id = result.scalars().first()

    # If not found, try to find file via ACL (shared access)
    if not file_id:
        async with async_session() as session:
            result = await session.execute(
                select(FileObject.uid)
                .join(FileACL, FileACL.file_id == FileObject.uid)
                .where(
                    FileACL.user_id == user_id,
                    FileObject.name == filename
                )
                .limit(1)
            )
            file_id = result.scalars().first()

    if not file_id:
        raise HTTPException(status_code=403, detail="You do not have permission to view this file.")

    return str(file_id)