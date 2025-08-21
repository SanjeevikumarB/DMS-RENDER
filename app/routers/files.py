from fastapi import APIRouter, Request, Query, Body, HTTPException, Depends
from typing import List, Dict, Optional
from app.service import file_service
from pydantic import BaseModel

router = APIRouter()

# Pydantic models for request validation
class PresignedUrlRequest(BaseModel):
    filename: str
    extension: str
    record_id: str

class AutoPresignRequest(BaseModel):
    filename: str
    extension: str
    record_id: str
    content_length: int  # bytes provided by frontend

class FileUploadRequest(BaseModel):
    filename: str
    extension: str
    user_id: str
    folder_path: Optional[str] = None

class FileMetadataUpdate(BaseModel):
    record_id: str
    s3_key: str
    file_size: int
    content_type: str
    version_id: Optional[str] = None

# Helper function to extract auth token from request headers
def get_auth_token(request: Request) -> str:
    """Extract and validate authorization token from request headers"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format. Use 'Bearer <token>'")
    return auth_header.replace("Bearer ", "")

# Core S3 Operations
@router.post("/generate-presigned-url/")
async def generate_presigned_url(request: PresignedUrlRequest, req: Request):
    """
    Generate presigned URL for S3 upload
    
    This endpoint:
    1. Validates the file record exists in Django
    2. Generates a presigned URL for direct S3 upload
    3. Returns upload URL and S3 key information
    """
    try:
        auth_token = get_auth_token(req)
        return await file_service.generate_presigned_url_service(request, auth_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")


@router.post("/presign/auto")
async def auto_presign(request: AutoPresignRequest, req: Request):
    """
    Decide server-side between single PUT presign and multipart based on content_length
    
    - If content_length <= 100MB: returns presigned PUT URL
    - Else: initiates multipart upload and returns {upload_id, key, bucket, recommended_part_size}
    """
    try:
        auth_token = get_auth_token(req)
        return await file_service.presign_auto_service(request, auth_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to auto-presign upload: {str(e)}")


@router.get("/download_file/{filename}")
async def download_file(
    req: Request,
    filename: str,
    version_id: str = Query(default=None, description="Optional version ID"),
    mode: str = Query(default="download", enum=["view", "download", "auto"], description="Download mode"),
    user_id: str = Query(default=None, description="User ID for access control"),
    file_id: str = Query(default=None, description="File ID for database lookup")
):
    """
    Generate presigned download URL for S3 files
    
    This endpoint:
    1. Validates user permissions via Django
    2. Generates a presigned download URL
    3. Returns download URL and file details
    """
    try:
        return await file_service.download_file_service(req, filename, version_id, mode, user_id, file_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")

# File Management (Delegated to Django)
@router.get("/list_files")
async def list_files(req: Request):
    """
    Get list of files from Django
    
    This endpoint delegates to Django service for file listing
    """
    try:
        return await file_service.list_files_service(req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@router.get("/list_file_versions/{filename}")
async def list_file_versions(filename: str, req: Request):
    """
    Get file versions from Django
    
    This endpoint delegates to Django service for version information
    """
    try:
        return await file_service.list_file_versions_service(filename, req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file versions: {str(e)}")

@router.put("/rename_file")
async def rename_file(
    req: Request,
    old_filename: str = Query(..., description="Current filename"),
    new_filename: str = Query(..., description="New filename"),
    user_id: str = Query(default=None, description="User ID for access control"),
    file_id: str = Query(default=None, description="File ID for database lookup")
):
    """
    Rename file (updates in Django)
    
    This endpoint delegates to Django service for file renaming
    """
    try:
        return await file_service.rename_file_service(req, old_filename, new_filename, user_id, file_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename file: {str(e)}")

@router.delete("/delete_file/{filename}")
async def delete_file(
    files: List[Dict[str, str]] = Body(..., description="List of files to delete with filename and file_id"),
    req: Request = None
):
    """
    Delete files (marks as deleted in Django)
    
    This endpoint delegates to Django service for file deletion
    """
    try:
        return await file_service.delete_file_service(files, req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete files: {str(e)}")

# Access Control (Delegated to Django)
@router.post("/acl/grant")
async def grant_acl(
    file_id: str = Body(..., description="File ID to grant access to"),
    user_id: str = Body(..., description="User ID to grant access to"),
    permission: str = Body(..., description="Permission level to grant"),
    req: Request = None
):
    """
    Grant access control permissions
    
    This endpoint delegates to Django service for ACL management
    """
    try:
        return await file_service.grant_acl_service(file_id, user_id, permission, req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to grant ACL: {str(e)}")

@router.get("/acl/check")
async def check_acl(
    file_id: str = Query(..., description="File ID to check access for"),
    user_id: str = Query(..., description="User ID to check access for"),
    permission: str = Query(..., description="Permission level to check"),
    req: Request = None
):
    """
    Check access control permissions
    
    This endpoint delegates to Django service for ACL verification
    """
    try:
        return await file_service.check_acl_service(file_id, user_id, permission, req)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check ACL: {str(e)}")

# S3 Advanced Operations
@router.post("/s3/archive-version", tags=["S3 Glacier"])
async def archive_to_glacier(files: List[Dict[str, str]] = Body(..., description="List of files to archive with filename and version_id")):
    """
    Archive files to S3 Glacier
    
    This endpoint:
    1. Copies files to Glacier Instant Retrieval storage class
    2. Deletes original versions
    3. Returns archive status for each file
    """
    try:
        return await file_service.archive_files_to_glacier(files)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Glacier archiving failed: {str(e)}")

@router.post("/s3/restore-from-glacier", tags=["S3 Glacier"])
async def restore_from_glacier(files: List[Dict[str, str]] = Body(..., description="List of files to restore with filename and version_id")):
    """
    Restore files from S3 Glacier
    
    This endpoint:
    1. Restores files from Glacier IR to Standard storage
    2. Deletes Glacier IR versions
    3. Returns restoration status for each file
    """
    try:
        return await file_service.restore_files_from_glacier(files)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Glacier restoration failed: {str(e)}")

# Health Check
@router.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns service status and connection information
    """
    try:
        return await file_service.health_check_service()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")