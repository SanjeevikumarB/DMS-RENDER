import os
from typing import List, Dict
from fastapi import HTTPException, Request
import httpx

from ..service.s3_utils import generate_presigned_upload_url, generate_presigned_download_url

# FastAPI + S3 Architecture:
# - FastAPI: Handles S3 operations (upload, download, presigned URLs)
# - Lambda: Extracts metadata from uploaded files
# - Django: Handles database operations via HTTP API calls
# - No direct PostgreSQL connections in FastAPI

# Configuration
DJANGO_BASE_URL = os.getenv('DJANGO_BASE_URL', 'http://localhost:8000/api')
SKIP_DJANGO_VALIDATION = os.getenv('SKIP_DJANGO_VALIDATION', 'false').lower() in ('1', 'true', 'yes')

# Threshold for single vs multipart upload (100 MB)
SINGLE_UPLOAD_THRESHOLD = 100 * 1024 * 1024

async def get_file_details_from_django(record_id: str, auth_token: str) -> Dict:
    """Get file details from Django using record_id"""
    # Temporary bypass for testing
    if os.getenv("SKIP_DJANGO_VALIDATION", "false").lower() == "true":
        print(f"Skipping Django validation for record_id: {record_id}")
        return {"id": record_id, "name": "mock_file", "owner": "mock_user"}

    try:
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        }
        
        response = httpx.get(
            f"{DJANGO_BASE_URL}/files/file-info/{record_id}/",
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=404, detail="File record not found in Django")
            
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to Django: {str(e)}")

async def generate_presigned_url_service(request, auth_token: str):
    """Generate presigned URL for S3 upload"""
    try:
        # Verify the file record exists in Django
        file_details = await get_file_details_from_django(request.record_id, auth_token)
        
        # Create a mock UploadFile object for compatibility with s3_utils
        class MockUploadFile:
            def __init__(self, filename):
                self.filename = filename
        
        mock_file = MockUploadFile(request.filename)
        
        # Generate presigned URL with record_id for tracking
        result = generate_presigned_upload_url(mock_file, record_id=request.record_id)
        
        # Add file details from Django
        result["file_details"] = file_details
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")

async def presign_auto_service(request, auth_token: str):
    """Automatically generate presigned URL (single or multipart) based on file size."""
    try:
        # Verify the file record exists in Django
        file_details = await get_file_details_from_django(request.record_id, auth_token)

        if request.content_length <= SINGLE_UPLOAD_THRESHOLD:
            # Generate single presigned URL
            class MockUploadFile:
                def __init__(self, filename):
                    self.filename = filename
            mock_file = MockUploadFile(request.filename)
            single_presign_result = generate_presigned_upload_url(mock_file, record_id=request.record_id)
            single_presign_result["strategy"] = "single"
            single_presign_result["file_details"] = file_details
            return single_presign_result
        else:
            # Initiate multipart upload
            from .presigned_multipart import initiate_presigned_multipart_upload
            multipart_init_result = initiate_presigned_multipart_upload(
                request.filename, 
                request.extension, # Pass extension for content_type mapping
                request.record_id
            )
            multipart_init_result["strategy"] = "multipart"
            multipart_init_result["recommended_part_size"] = 8 * 1024 * 1024 # 8MB default part size
            multipart_init_result["file_details"] = file_details
            return multipart_init_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate presigned URL: {str(e)}")

async def download_file_service(filename: str, file_id: str, mode: str = "download", auth_token: str = None):
    """Generate presigned download URL for S3 file"""
    try:
        # For now, use a simple S3 key structure
        s3_key = f"uploads/{filename}"
        
        result = generate_presigned_download_url(s3_key, mode)
        result["file_id"] = file_id
        result["filename"] = filename
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")

async def list_files_service(auth_token: str):
    """List files from S3 (simplified)"""
    try:
        # For now, return a mock response
        return {
            "files": [
                {"filename": "example.pdf", "size": 1024, "uploaded": "2024-01-01T00:00:00Z"}
            ],
            "total": 1
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

async def health_check_service():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "FastAPI S3 Service",
        "django_connection": "configured",
        "s3_connection": "configured",
        "timestamp": "2024-01-01T00:00:00Z"
    }