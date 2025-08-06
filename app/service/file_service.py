import os
import tempfile
import datetime
from typing import List, Union, Dict
from fastapi import UploadFile, HTTPException, File, Request
from starlette.responses import StreamingResponse
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
import boto3
import asyncio 
from io import BytesIO

from ..core.config import AWS_S3_BUCKET, S3_UPLOAD_FOLDER, CDN_DOMAIN
from ..service.metadata_extractor.dispatcher import extract_metadata

from app.db.pg_models import FileObject, FileVersion
from app.db.pg_database import AsyncPostgresSessionLocal as pg_session
from sqlalchemy import select

from app.service.acl_utils import get_file_id_by_filename_and_user, get_user_permission, has_file_access, add_file_access_control
# from app.db.pg_models import PermissionEnum  # Define this in pg_models.py to match Django


ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".csv", ".xlsx",
    ".jpg", ".jpeg", ".png", ".mp3", ".wav",
    ".mp4", ".mkv", ".zip", ".tar", ".gz", ".tgz", ".txt"
}

INLINE_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "text/plain",
    "text/html",
    "video/mp4"
}

# Define the chunk size for multipart uploads
CHUNK_SIZE = 100 * 1024 * 1024  # 100MB

# Initialize the S3 client
s3_client = boto3.client(
    "s3",
    region_name="eu-north-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    use_ssl=True,
    config=Config(signature_version='s3v4', retries={'max_attempts': 3, 'mode': 'standard'})
)

# Function to get the folder name based on file extension
def get_folder_by_extension(extension: str) -> str:
    folder_map = {
        ".pdf": "pdfs", ".docx": "documents",
        ".csv": "spreadsheets", ".xlsx": "spreadsheets",
        ".jpg": "images", ".jpeg": "images", ".png": "images",
        ".mp3": "audio", ".wav": "audio",
        ".mp4": "videos", ".mkv": "videos",
        ".zip": "archives", ".tar": "archives", ".gz": "archives", ".tgz": "archives",
        ".txt": "text"
    }
    return folder_map.get(extension, "others")


# Function to upload a single or multiple files
async def upload_single_or_multiple_files(request: Request, files: Union[UploadFile, List[UploadFile]]):
    if isinstance(files, list):
        return [await save_file(file) for file in files]
    return await save_file(files)


# Function to save a file to S3
async def save_file(file: UploadFile):
    extension = os.path.splitext(file.filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

    folder = get_folder_by_extension(extension)
    s3_key = f"{S3_UPLOAD_FOLDER}{folder}/{file.filename}"

    content = await file.read()

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = tmp.name

        if os.path.getsize(tmp_path) <= CHUNK_SIZE:
            with open(tmp_path, "rb") as f:
                response = s3_client.put_object(
                    Bucket=AWS_S3_BUCKET,
                    Key=s3_key,
                    Body=f,
                    ContentType=file.content_type
                )
                version_id = response.get("VersionId")
        else:
            version_id = await multipart_upload_to_s3(s3_key, tmp_path, file.content_type)

        metadata = await asyncio.to_thread(extract_metadata, tmp_path)

    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        
    cdn_relative_path = s3_key.replace(f"{S3_UPLOAD_FOLDER}", "")
    cdn_url = f"https://{CDN_DOMAIN}/{cdn_relative_path}"

    metadata.update({
        "filename": file.filename,
        "extension": extension,
        "content_type": file.content_type,
        "size": len(content),
        "s3_key": s3_key,
        "cdn_url": cdn_url,
        "version_id": version_id,
        "status": "uploaded", 
        "message": "File uploaded to S3 successfully!"
    })
    # await save_file_record_to_db(metadata) # This line is removed as per the edit hint
    return metadata


# Function to handle multipart uploads for large files
async def multipart_upload_to_s3(s3_key: str, file_path: str, content_type: str) -> str:
    upload_id = s3_client.create_multipart_upload(
        Bucket=AWS_S3_BUCKET,
        Key=s3_key,
        ContentType=content_type
    )["UploadId"]

    parts = []
    part_number = 1
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                response = s3_client.upload_part(
                    Bucket=AWS_S3_BUCKET,
                    Key=s3_key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk
                )
                parts.append({
                    "PartNumber": part_number,
                    "ETag": response["ETag"]
                })
                part_number += 1

        complete_response = s3_client.complete_multipart_upload(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts}
        )

        return complete_response.get("VersionId") 

    except Exception as e:
        s3_client.abort_multipart_upload(Bucket=AWS_S3_BUCKET, Key=s3_key, UploadId=upload_id)
        raise HTTPException(status_code=500, detail=f"Multipart upload failed: {str(e)}")



async def save_file_metadata_to_db(data: dict):
    async with pg_session() as session:
        file_obj = FileObject(
            uid=data.get("uid"),
            name=data.get("filename") or data.get("name"),
            type=data.get("type", "file"),
            description=data.get("description"),
            extension=data.get("extension"),
            size=data.get("size"),
            created_at=data.get("created_at"),
            modified_at=data.get("modified_at"),
            accessed_at=data.get("accessed_at"),
            file_metadata=data.get("metadata"),
            uploaded_url=data.get("uploaded_url"),
            presigned_url=data.get("presigned_url"),
            tags=data.get("tags"),
            trashed_at=data.get("trashed_at"),
            owner_id=data.get("owner_id"),
            parent_id=data.get("parent_id"),
            latest_version_id=data.get("latest_version_id"),
            storage_class=data.get("storage_class", "STANDARD") 
        )
        session.add(file_obj)
        await session.commit()
        await session.refresh(file_obj)
    return {"message": "File metadata recorded successfully.", "file_id": str(file_obj.uid)}


# Function to list all files in the S3 bucket
async def list_files():
    try:
        response = s3_client.list_objects_v2(Bucket=AWS_S3_BUCKET, Prefix=S3_UPLOAD_FOLDER)
        if "Contents" not in response:
            return []
        return [obj["Key"] for obj in response["Contents"] if not obj["Key"].endswith("/")]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

# Function to list all versions of a file
async def list_file_versions(filename: str):
    try:
        s3_key = find_s3_key(filename)
        response = s3_client.list_object_versions(Bucket=AWS_S3_BUCKET, Prefix=s3_key)

        versions = []
        for version in response.get("Versions", []):
            if version["Key"] == s3_key:
                versions.append({
                    "version_id": version["VersionId"],
                    "is_latest": version["IsLatest"],
                    "last_modified": version["LastModified"].isoformat(),
                    "size": version["Size"]
                })

        return {
            "filename": filename,
            "s3_key": s3_key,
            "versions": versions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list file versions: {str(e)}")


# Function to find the S3 key for a given filename
def find_s3_key(filename: str) -> str:
    response = s3_client.list_objects_v2(Bucket=AWS_S3_BUCKET, Prefix=S3_UPLOAD_FOLDER)
    for obj in response.get("Contents", []):
        if obj["Key"].endswith(filename):
            return obj["Key"]
    raise HTTPException(status_code=404, detail="File not found")


async def get_file_response(filename: str,user_id: str,version_id: str = None, mode: str = "download", file_id: str = None):
    try:
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID required to access the file.")

        # Prefer file_id from input (testing) or resolve from DB
        file_id = file_id or await get_file_id_by_filename_and_user(filename, user_id)

        permission = await get_user_permission(file_id, user_id)
        # is_admin = await is_user_admin(user_id) # This line is removed as per the edit hint

        # if not is_admin and (not permission or permission not in [
        #     PermissionEnum.read, PermissionEnum.write, PermissionEnum.owner
        # ]): # This line is removed as per the edit hint
        #     raise HTTPException(status_code=403, detail="You do not have permission to view this file.") # This line is removed as per the edit hint
        
        # Directly stream from S3
        s3_key = find_s3_key(filename)
        get_object_args = {
            "Bucket": AWS_S3_BUCKET,
            "Key": s3_key
        }
        if version_id:
            get_object_args["VersionId"] = version_id

        # Run blocking boto3 call in thread
        s3_object = await asyncio.to_thread(s3_client.get_object, **get_object_args)
        file_data = await asyncio.to_thread(lambda: s3_object["Body"].read())
        file_stream = BytesIO(file_data)
        content_type = s3_object.get("ContentType", "application/octet-stream")

        if mode == "view" or (mode == "auto" and content_type in INLINE_MIME_TYPES):
            disposition = f'inline; filename="{filename}"'
        else:
            disposition = f'attachment; filename="{filename}"'

        return StreamingResponse(
            file_stream,
            media_type=content_type,
            headers={"Content-Disposition": disposition}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Download error: {str(e)}")


async def rename_existing_file(old_filename: str, new_filename: str, user_id: str,file_id: str = None):
    try:
        file_id = file_id or old_filename.split("_")[0] 
        permission = await get_user_permission(file_id, user_id)
        # is_admin = await is_user_admin(user_id) # This line is removed as per the edit hint

        # if not is_admin and (not permission or permission not in [ PermissionEnum.write, PermissionEnum.owner]): # This line is removed as per the edit hint
        #     raise HTTPException(status_code=403, detail="You do not have permission to view this file.") # This line is removed as per the edit hint

        old_key = find_s3_key(old_filename)
        old_extension = os.path.splitext(old_filename)[1]
        new_filename = os.path.splitext(new_filename)[0] + old_extension
        folder = os.path.dirname(old_key).replace(S3_UPLOAD_FOLDER, "")
        new_key = f"{S3_UPLOAD_FOLDER}{folder}/{new_filename}"

        # Use asyncio.to_thread for blocking operations
        await asyncio.to_thread(
            s3_client.copy_object,
            Bucket=AWS_S3_BUCKET,
            CopySource={"Bucket": AWS_S3_BUCKET, "Key": old_key},
            Key=new_key
        )
        await asyncio.to_thread(
            s3_client.delete_object,
            Bucket=AWS_S3_BUCKET,
            Key=old_key
        )

        return {
            "message": "File renamed successfully!",
            "old_filename": old_filename,
            "new_filename": new_filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rename failed: {str(e)}")


async def delete_single_file(file_entry: Dict[str, str], semaphore: asyncio.Semaphore) -> Dict[str, any]:
    """Delete a single file version with semaphore control"""
    async with semaphore:
        filename = file_entry.get("filename")
        version_id = file_entry.get("version_id")

        if not filename or not version_id:
            return {
                "filename": filename,
                "error": "Both filename and version_id are required"
            }

        try:
            key = find_s3_key(filename)

            # Validate the version exists
            response = await asyncio.to_thread(
                s3_client.list_object_versions,
                Bucket=AWS_S3_BUCKET,
                Prefix=key
            )

            valid_version = any(
                v["VersionId"] == version_id and v["Key"] == key
                for v in response.get("Versions", [])
            )

            if not valid_version:
                return {
                    "filename": filename,
                    "version_id": version_id,
                    "error": "Version not found"
                }

            # Delete the specific version
            await asyncio.to_thread(
                s3_client.delete_object,
                Bucket=AWS_S3_BUCKET,
                Key=key,
                VersionId=version_id
            )

            return {
                "filename": filename,
                "version_id": version_id,
                "status": "deleted"
            }

        except Exception as e:
            return {
                "filename": filename,
                "version_id": version_id,
                "error": str(e)
            }

async def delete_files_by_name(file_list: List[Dict[str, str]], max_concurrent: int = 10):
    """Delete files with semaphore-based concurrency control"""
    if not file_list:
        return {"deleted": [], "errors": []}
    
    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create tasks for all files
    tasks = [delete_single_file(file_entry, semaphore) for file_entry in file_list]
    
    # Execute all tasks concurrently with semaphore control
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    deleted = []
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Handle unexpected exceptions
            filename = file_list[i].get("filename", "unknown")
            version_id = file_list[i].get("version_id", "unknown")
            errors.append({
                "filename": filename,
                "version_id": version_id,
                "error": f"Unexpected error: {str(result)}"
            })
        elif "error" in result:
            errors.append(result)
        else:
            deleted.append(result)

    return {
        "deleted": deleted,
        "errors": errors,
        "summary": {
            "total_requested": len(file_list),
            "successful_deletions": len(deleted),
            "failed_deletions": len(errors)
        }
    }


async def archive_single_file(file_entry: Dict[str, str], semaphore: asyncio.Semaphore) -> Dict[str, any]:
    """Archive a single file to Glacier with semaphore control"""
    async with semaphore:
        filename = file_entry.get("filename")
        version_id = file_entry.get("version_id")

        if not filename or not version_id:
            return {
                "filename": filename,
                "error": "Both filename and version_id are required"
            }

        try:
            key = find_s3_key(filename)

            # Step 1: Copy to Glacier_IR
            copy_response = await asyncio.to_thread(
                s3_client.copy_object,
                Bucket=AWS_S3_BUCKET,
                CopySource={
                    "Bucket": AWS_S3_BUCKET,
                    "Key": key,
                    "VersionId": version_id
                },
                Key=key,
                StorageClass="GLACIER_IR",
                MetadataDirective="COPY"
            )

            new_version_id = copy_response["VersionId"]

            # Step 2: Delete original version
            await asyncio.to_thread(
                s3_client.delete_object,
                Bucket=AWS_S3_BUCKET,
                Key=key,
                VersionId=version_id
            )

            # Step 3: Get file_id from DB
            async with pg_session() as session:
                result = await session.execute(
                    select(FileVersion.file_id).where(FileVersion.s3_version_id == version_id)
                )
                file_id = result.scalar_one_or_none()

            if not file_id:
                return {
                    "filename": filename,
                    "version_id": version_id,
                    "error": "File ID not found for given version ID"
                }

            return {
                "filename": filename,
                "file_id": file_id,
                "archived_version_id": new_version_id,
                "deleted_original_version_id": version_id
            }

        except Exception as e:
            return {
                "filename": filename,
                "version_id": version_id,
                "error": str(e)
            }

async def archive_files_to_glacier(file_list: List[Dict[str, str]], max_concurrent: int = 10):
    """Archive files to Glacier with semaphore-based concurrency control"""
    if not file_list:
        return {"archived": [], "errors": []}
    
    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create tasks for all files
    tasks = [archive_single_file(file_entry, semaphore) for file_entry in file_list]
    
    # Execute all tasks concurrently with semaphore control
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    archived = []
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Handle unexpected exceptions
            filename = file_list[i].get("filename", "unknown")
            version_id = file_list[i].get("version_id", "unknown")
            errors.append({
                "filename": filename,
                "version_id": version_id,
                "error": f"Unexpected error: {str(result)}"
            })
        elif "error" in result:
            errors.append(result)
        else:
            archived.append(result)

    return {
        "archived": archived,
        "errors": errors,
        "summary": {
            "total_requested": len(file_list),
            "successful_archives": len(archived),
            "failed_archives": len(errors)
        }
    }
async def restore_single_file(file_entry: Dict[str, str], semaphore: asyncio.Semaphore) -> Dict[str, any]:
    """Restore a single file from Glacier Instant Retrieval with semaphore control"""
    async with semaphore:
        filename = file_entry.get("filename")
        version_id = file_entry.get("version_id")

        if not filename or not version_id:
            return {
                "filename": filename,
                "error": "Both filename and version_id are required"
            }

        try:
            key = find_s3_key(filename)

            # Check if the object exists and is in Glacier IR
            try:
                head_response = await asyncio.to_thread(
                    s3_client.head_object,
                    Bucket=AWS_S3_BUCKET,
                    Key=key,
                    VersionId=version_id
                )
                
                storage_class = head_response.get('StorageClass', 'STANDARD')
                
                # Check if it's in Glacier IR
                if storage_class != 'GLACIER_IR':
                    return {
                        "filename": filename,
                        "version_id": version_id,
                        "status": "not_in_glacier_ir",
                        "current_storage_class": storage_class,
                        "message": f"File is not in Glacier IR (current storage class: {storage_class}). Files in Glacier IR are instantly accessible."
                    }

                # For Glacier IR, files are instantly accessible - restore to Standard
                copy_response = await asyncio.to_thread(
                    s3_client.copy_object,
                    Bucket=AWS_S3_BUCKET,
                    CopySource={
                        "Bucket": AWS_S3_BUCKET,
                        "Key": key,
                        "VersionId": version_id
                    },
                    Key=key,
                    StorageClass="STANDARD",
                    MetadataDirective="COPY"
                )

                new_version_id = copy_response["VersionId"]

                # Delete the Glacier IR version
                await asyncio.to_thread(
                    s3_client.delete_object,
                    Bucket=AWS_S3_BUCKET,
                    Key=key,
                    VersionId=version_id
                )

                # Update database if needed
                async with pg_session() as session:
                    result = await session.execute(
                        select(FileVersion.file_id).where(FileVersion.s3_version_id == version_id)
                    )
                    file_id = result.scalar_one_or_none()

                return {
                    "filename": filename,
                    "file_id": file_id,
                    "old_version_id": version_id,
                    "new_version_id": new_version_id,
                    "old_storage_class": "GLACIER_IR",
                    "new_storage_class": "STANDARD",
                    "status": "restored",
                    "message": "File successfully restored from Glacier IR to Standard storage (instantly accessible)"
                }

            except Exception as e:
                if "NoSuchKey" in str(e) or "NoSuchVersion" in str(e):
                    return {
                        "filename": filename,
                        "version_id": version_id,
                        "error": "File version not found"
                    }
                raise e

        except Exception as e:
            return {
                "filename": filename,
                "version_id": version_id,
                "error": str(e)
            }

async def restore_files_from_glacier(file_list: List[Dict[str, str]], max_concurrent: int = 10):
    """Restore files from Glacier IR with semaphore-based concurrency control"""
    if not file_list:
        return {"restored": [], "errors": []}
    
    # Create semaphore to limit concurrent operations
    semaphore = asyncio.Semaphore(max_concurrent)
    
    # Create tasks for all files
    tasks = [restore_single_file(file_entry, semaphore) for file_entry in file_list]
    
    # Execute all tasks concurrently with semaphore control
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    restored = []
    errors = []
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Handle unexpected exceptions
            filename = file_list[i].get("filename", "unknown")
            version_id = file_list[i].get("version_id", "unknown")
            errors.append({
                "filename": filename,
                "version_id": version_id,
                "error": f"Unexpected error: {str(result)}"
            })
        elif "error" in result:
            errors.append(result)
        else:
            restored.append(result)

    return {
        "restored": restored,
        "errors": errors,
        "summary": {
            "total_requested": len(file_list),
            "successful_restorations": len(restored),
            "failed_restorations": len(errors),
            "note": "Files restored from Glacier IR to Standard storage are instantly accessible"
        }
    }

async def get_glacier_restore_status(filename: str, version_id: str):
    try:
        return {"status": "restored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check restore status: {str(e)}")
    
async def grant_file_permission(file_id: str, user_id: str, permission: str):
    # Implement logic to add FileAccessControl entry using PostgreSQL
    # Placeholder: you need to implement add_file_access_control in pg_utils or similar
    acl_entry = await add_file_access_control(file_id, user_id, permission)
    return {
        "message": "Permission granted.",
        "file_id": acl_entry.file_id,
        "user_id": acl_entry.user_id,
        "access_type": acl_entry.access_level
    }

async def check_file_permission(file_id: str, user_id: str, permission: str):
    user_perm = await get_user_permission(file_id, user_id)
    if user_perm is None:
        return {"has_permission": False, "reason": "No ACL entry"}

    # Implement permission logic based on your access_level scheme
    if permission == "viewer":
        return {"has_permission": user_perm in ["viewer", "editor"]}
    elif permission == "editor":
        return {"has_permission": user_perm == "editor"}
    return {"has_permission": False}

async def list_s3_delete_markers(prefix: str = None):
    """
    List all delete markers in the S3 bucket (optionally filtered by prefix).
    Returns a list of dicts with Key, VersionId, LastModified, and IsLatest.
    """
    try:
        kwargs = {'Bucket': AWS_S3_BUCKET}
        if prefix:
            kwargs['Prefix'] = prefix
        delete_markers = []
        while True:
            response = s3_client.list_object_versions(**kwargs)
            for marker in response.get('DeleteMarkers', []):
                delete_markers.append({
                    'key': marker['Key'],
                    'version_id': marker['VersionId'],
                    'last_modified': marker['LastModified'].isoformat(),
                    'is_latest': marker['IsLatest']
                })
            if response.get('IsTruncated'):
                kwargs['KeyMarker'] = response.get('NextKeyMarker')
                kwargs['VersionIdMarker'] = response.get('NextVersionIdMarker')
            else:
                break
        return delete_markers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list delete markers: {str(e)}")

async def restore_s3_file_from_delete_marker(key: str, version_id: str):
    """
    Remove the delete marker for the given key/version_id, restoring the file.
    """
    try:
        # Check if the key exists as a delete marker
        response = s3_client.list_object_versions(Bucket=AWS_S3_BUCKET, Prefix=key)
        found = False
        for marker in response.get('DeleteMarkers', []):
            if marker['Key'] == key and marker['VersionId'] == version_id:
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail=f"Delete marker not found for key: {key} and version_id: {version_id}")
        # Remove the delete marker
        del_response = s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=key, VersionId=version_id)
        # Log the response for debugging
        print(f"Delete marker removal response: {del_response}")
        # Double-check if the delete marker is gone
        post_response = s3_client.list_object_versions(Bucket=AWS_S3_BUCKET, Prefix=key)
        still_exists = any(m['Key'] == key and m['VersionId'] == version_id for m in post_response.get('DeleteMarkers', []))
        if still_exists:
            raise HTTPException(status_code=500, detail=f"Delete marker was not removed. S3 response: {del_response}")
        return {"message": f"Restored {key} by removing delete marker {version_id}", "s3_response": del_response}
    except Exception as e:
        print(f"Error removing delete marker: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restore file: {str(e)}")