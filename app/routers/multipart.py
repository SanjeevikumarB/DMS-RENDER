from fastapi import APIRouter, Query, Body
from pydantic import BaseModel
from typing import List
from app.service.presigned_multipart import (
    initiate_presigned_multipart_upload,
    get_presigned_part_url,
    complete_presigned_multipart_upload,
    abort_presigned_multipart_upload,
)

router = APIRouter()


class Part(BaseModel):
    PartNumber: int
    ETag: str


class CompleteMultipartRequest(BaseModel):
    key: str
    upload_id: str
    parts: List[Part]

@router.post("/multipart/initiate")
def start_upload(
    filename: str = Query(..., description="Name of the file to upload"),
    content_type: str = Query(..., description="MIME type of the file"),
    record_id: str = Query(..., description="Django record ID for tracking; required")
):
    """
    Initiate a multipart upload for large files
    
    This endpoint:
    1. Creates a multipart upload session in S3
    2. Returns upload_id and key for part uploads
    3. Supports files up to 5TB with parallel uploads
    """
    return initiate_presigned_multipart_upload(filename, content_type, record_id)

@router.get("/multipart/presign-part")
def presign_part(
    key: str = Query(..., description="S3 key for the file"),
    upload_id: str = Query(..., description="Multipart upload ID"),
    part_number: int = Query(..., description="Part number (1-10000)")
):
    """
    Generate presigned URL for uploading a specific part
    
    This endpoint:
    1. Generates presigned URL for uploading a specific part
    2. Supports parallel part uploads
    3. Each part can be up to 5GB
    """
    return {"url": get_presigned_part_url(key, upload_id, part_number)}

@router.post("/multipart/complete")
def complete_upload(payload: CompleteMultipartRequest = Body(..., description="Completion payload with key, upload_id, and parts")):
    """
    Complete a multipart upload
    
    This endpoint:
    1. Completes the multipart upload in S3
    2. Combines all uploaded parts into final file
    3. Returns the final S3 location
    """
    parts_payload = [
        {"PartNumber": part.PartNumber, "ETag": part.ETag}
        for part in payload.parts
    ]
    return complete_presigned_multipart_upload(payload.key, payload.upload_id, parts_payload)

@router.delete("/multipart/abort")
def abort_upload(
    key: str = Query(..., description="S3 key for the file"),
    upload_id: str = Query(..., description="Multipart upload ID")
):
    """
    Abort a multipart upload
    
    This endpoint:
    1. Aborts the multipart upload in S3
    2. Cleans up all uploaded parts
    3. Frees up storage space
    """
    return abort_presigned_multipart_upload(key, upload_id)
