from fastapi import UploadFile, APIRouter, File, Request, Query, Body, HTTPException
from typing import List, Dict
from app.service import file_service
from ..service.s3_utils import generate_presigned_upload_url

router = APIRouter()

# Function to generate a presigned URL for uploading files
@router.post("/generate-presigned-url/")
async def generate_url(file: UploadFile = File(...)):
    return generate_presigned_upload_url(file)  

@router.post("/record-file-metadata/")
async def record_file_metadata(data: dict = Body(...)):
    return await file_service.save_file_metadata_to_db(data)

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
async def api_download_file(request: Request,filename: str,version_id: str = Query(default=None),mode: str = Query(default="download", enum=["view", "download", "auto"]),user_id: str = Query(default=None),file_id: str = Query(default=None),):
    user_id = user_id or getattr(request.state, "user_id", None)
    return await file_service.get_file_response(filename, user_id, version_id, mode, file_id)

@router.put("/rename_file")
async def rename_file(request: Request,old_filename: str,new_filename: str,user_id: str = Query(default=None),file_id: str = Query(default=None)):
    user_id = user_id or getattr(request.state, "user_id", None)   
    return await file_service.rename_existing_file(old_filename=old_filename,new_filename=new_filename,user_id=user_id,file_id=file_id)

@router.delete("/delete_file/{filename}")
async def delete_file(files: List[Dict[str, str]] = Body(...)):
    return await file_service.delete_files_by_name(files)

@router.post("/acl/grant")
async def grant_acl(file_id: str = Body(...), user_id: str = Body(...), permission: str = Body(...)):
    return await file_service.grant_file_permission(file_id, user_id, permission)

@router.get("/acl/check")
async def check_acl(file_id: str = Query(...), user_id: str = Query(...), permission: str = Query(...)):
    return await file_service.check_file_permission(file_id, user_id, permission)

# @router.get("/s3/delete-markers", tags=["S3 Restoring"])
# async def list_s3_delete_markers(prefix: str = None):
#     return await file_service.list_s3_delete_markers(prefix)

# @router.post("/s3/restore-file", tags=["S3 Restoring"])
# async def restore_s3_file_from_delete_marker(key: str = Body(..., embed=True),version_id: str = Body(..., embed=True)):
#     return await file_service.restore_s3_file_from_delete_marker(key, version_id)

@router.post("/s3/archive-version", tags=["S3 Glacier"])
async def archive_version(files: List[Dict[str, str]] = Body(...)):
    return await file_service.archive_files_to_glacier(files)

@router.post("/s3/restore-from-glacier", tags=["S3 Glacier"])
async def restore_from_glacier(files: List[Dict[str, str]] = Body(...)):
    return await file_service.restore_files_from_glacier(files)

# @router.post("/s3/restore-status", tags=["S3 Glacier"])
# async def glacier_restore_status(filename: str = Body(..., embed=True),version_id: str = Body(..., embed=True)):
#     return await file_service.get_glacier_restore_status(filename, version_id)