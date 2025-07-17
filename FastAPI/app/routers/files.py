from fastapi import UploadFile, APIRouter, File, Request, Query, Body
from typing import List,Union
from app.service import file_service
from ..service.s3_utils import generate_presigned_upload_url
from app.db.db_utils import save_file_record_to_db

router = APIRouter()

# Function to generate a presigned URL for uploading files
@router.post("/generate-presigned-url/")
async def generate_url(file: UploadFile = File(...)):
    return generate_presigned_upload_url(file)

@router.post("/record-file-metadata/")
async def record_file_metadata(data: dict = Body(...)):
    save_file_record_to_db(data)
    return {"message": "File metadata recorded successfully."}

# Define the router for file operations
@router.post("/upload")
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    return await file_service.upload_single_or_multiple_files(request, files)

@router.get("/list_files")
async def list_all_files():
    return await file_service.list_files()

@router.get("/list_file_versions/{filename}")
async def api_list_file_versions(filename: str):
    return await file_service.list_file_versions(filename)

@router.get("/download_file/{filename}")
async def api_download_file(filename: str, version_id: str = Query(default=None)):
    return await file_service.get_file_response(filename, version_id)

@router.put("/rename_file")
async def rename_file(old_filename: str, new_filename: str):
    return await file_service.rename_existing_file(old_filename, new_filename)

@router.delete("/delete_file/{filename}")
async def delete_file(filename: str, version_id: str = Query(default=None)):
    return await file_service.delete_file_by_name(filename, version_id)
