from fastapi import APIRouter, Query
from app.service.presigned_multipart import (
    initiate_presigned_multipart_upload,
    get_presigned_part_url,
    complete_presigned_multipart_upload,
)

router = APIRouter()

@router.post("/multipart/initiate")
def start_upload(filename: str = Query(...), content_type: str = Query(...)):
    return initiate_presigned_multipart_upload(filename, content_type)

@router.get("/multipart/presign-part")
def presign_part(key: str, upload_id: str, part_number: int):
    return {"url": get_presigned_part_url(key, upload_id, part_number)}

@router.post("/multipart/complete")
def complete_upload(key: str, upload_id: str, parts: list[dict]):
    return complete_presigned_multipart_upload(key, upload_id, parts)
