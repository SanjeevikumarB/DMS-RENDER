import os
import tempfile
from typing import List, Union
from fastapi import UploadFile, HTTPException, File, Request
from starlette.responses import StreamingResponse
from botocore.exceptions import BotoCoreError, ClientError
from botocore.config import Config
import boto3

from ..core.config import AWS_S3_BUCKET, S3_UPLOAD_FOLDER, CDN_DOMAIN
from ..service.metadata_extractor.dispatcher import extract_metadata

from app.db.db_utils import save_file_record_to_db, update_file_status
from app.db.models import FileStatusEnum



ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".csv", ".xlsx",
    ".jpg", ".jpeg", ".png", ".mp3", ".wav",
    ".mp4", ".mkv", ".zip", ".tar", ".gz", ".tgz", ".txt"
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

        metadata = extract_metadata(tmp_path)

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
    save_file_record_to_db(metadata)
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


# Function to get a file response for download
async def get_file_response(filename: str, version_id: str = None):
    try:
        s3_key = find_s3_key(filename)
        get_object_args = {
            "Bucket": AWS_S3_BUCKET,
            "Key": s3_key
        }

        if version_id:
            get_object_args["VersionId"] = version_id

        s3_object = s3_client.get_object(**get_object_args)
        file_stream = s3_object["Body"]

        return StreamingResponse(
            file_stream,
            media_type=s3_object["ContentType"],
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Download error: {str(e)}")

# Function to rename an existing file
async def rename_existing_file(old_filename: str, new_filename: str):
    try:
        old_key = find_s3_key(old_filename)
        old_extension = os.path.splitext(old_filename)[1]
        new_filename = os.path.splitext(new_filename)[0] + old_extension
        folder = os.path.dirname(old_key).replace(S3_UPLOAD_FOLDER, "")
        new_key = f"{S3_UPLOAD_FOLDER}{folder}/{new_filename}"

        s3_client.copy_object(
            Bucket=AWS_S3_BUCKET,
            CopySource={"Bucket": AWS_S3_BUCKET, "Key": old_key},
            Key=new_key
        )
        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=old_key)

        return {
            "message": "File renamed successfully!",
            "old_filename": old_filename,
            "new_filename": new_filename,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rename failed: {str(e)}")


# Function to delete a file (optionally by version ID)
async def delete_file_by_name(filename: str, version_id: str = None):
    try:
        key = find_s3_key(filename)

        if version_id:
            s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=key, VersionId=version_id)
            msg = "Specific version deleted."
        else:
            s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=key)
            msg = "File soft-deleted (delete marker added)."

        return {
            "filename": filename,
            "version_id": version_id,
            "message": msg,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

    

