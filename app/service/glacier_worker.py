import asyncio
from sqlalchemy import select
from app.db.pg_database import AsyncPostgresSessionLocal as pg_session
from app.db.pg_models import FileVersion
from app.service.file_service import s3_client, AWS_S3_BUCKET

async def poll_glacier_restore():
    while True:
        async with pg_session() as session:
            restoring_versions = await session.execute(
                select(FileVersion).where(FileVersion.restore_status == "restoring")
            )
            for version in restoring_versions.scalars():
                try:
                    # Check S3 for restore status
                    response = await asyncio.to_thread(
                        s3_client.head_object,
                        Bucket=AWS_S3_BUCKET,
                        Key=version.s3_key,
                        VersionId=version.version_id
                    )
                    # If 'Restore' header exists and contains 'ongoing-request="false"', it's restored
                    restore_header = response.get('Restore')
                    if restore_header and 'ongoing-request="false"' in restore_header:
                        version.restore_status = "restored"
                        await session.commit()
                except Exception:
                    pass  # Optionally log error
        await asyncio.sleep(300)  # Poll every 5 minutes