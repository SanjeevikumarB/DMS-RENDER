import os
import boto3
import mimetypes
from botocore.config import Config
from fastapi import HTTPException, UploadFile
from pathlib import Path

from ..core.config import S3_UPLOAD_FOLDER, AWS_S3_BUCKET

AWS_REGION = "eu-north-1"
AWS_BUCKET = os.getenv("AWS_S3_BUCKET")

s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=Config(signature_version="s3v4")
)

def get_folder_by_extension(extension: str) -> str:
    """Get folder name based on file extension for organized S3 storage"""
    folder_map = {
        ".pdf": "documents", ".docx": "documents",
        ".csv": "spreadsheets", ".xlsx": "spreadsheets",
        ".jpg": "images", ".jpeg": "images", ".png": "images", ".svg": "images", ".gif": "images",
        ".mp3": "audio", ".wav": "audio",
        ".mp4": "videos", ".mkv": "videos",
        ".zip": "archives", ".tar": "archives", ".gz": "archives", ".tgz": "archives",
        ".txt": "text"
    }
    return folder_map.get(extension, "others")

def generate_presigned_upload_url(file: UploadFile, expires_in: int = 900, record_id: str = None):
    """
    Generate presigned URL for S3 upload
    """
    try:
        filename = file.filename
        extension = Path(filename).suffix.lower()

        if not extension:
            raise HTTPException(status_code=400, detail="Filename must have an extension.")

        if extension not in mimetypes.types_map:
            raise HTTPException(status_code=400, detail=f"Unsupported extension: {extension}")

        content_type = mimetypes.types_map.get(extension, "application/octet-stream")
        folder = get_folder_by_extension(extension)
        
        # Include record_id in S3 key for better tracking
        if record_id:
            s3_key = f"{S3_UPLOAD_FOLDER}{folder}/{record_id}/{filename}"
        else:
            s3_key = f"{S3_UPLOAD_FOLDER}{folder}/{filename}"

        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": AWS_S3_BUCKET,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in
        )

        return {
            "upload_url": presigned_url,
            "key": s3_key,
            "folder": folder,
            "content_type": content_type,
            "record_id": record_id,
            "bucket": AWS_S3_BUCKET,
            "expires_in": expires_in,
            "message": f"Upload the file directly to this URL using HTTP PUT. It will be saved under '{folder}/'."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presigned upload URL generation failed: {str(e)}")

def generate_presigned_download_url(s3_key: str, expires_in: int = 3600):
    """
    Generate presigned URL for S3 download
    """
    try:
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": AWS_S3_BUCKET,
                "Key": s3_key,
            },
            ExpiresIn=expires_in
        )

        return {
            "download_url": presigned_url,
            "key": s3_key,
            "bucket": AWS_S3_BUCKET,
            "expires_in": expires_in
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presigned download URL generation failed: {str(e)}")

def upload_file_to_s3(file_content: bytes, s3_key: str, content_type: str = None):
    """
    Upload file content directly to S3
    """
    try:
        if not content_type:
            content_type = "application/octet-stream"
        
        s3_client.put_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type
        )
        
        return {
            "success": True,
            "key": s3_key,
            "bucket": AWS_S3_BUCKET,
            "url": f"https://{AWS_S3_BUCKET}.s3.amazonaws.com/{s3_key}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {str(e)}")

def delete_file_from_s3(s3_key: str):
    """
    Delete file from S3
    """
    try:
        s3_client.delete_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key
        )
        
        return {
            "success": True,
            "key": s3_key,
            "message": "File deleted from S3"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 delete failed: {str(e)}")

def copy_file_in_s3(source_key: str, dest_key: str):
    """
    Copy file within S3
    """
    try:
        copy_source = {
            'Bucket': AWS_S3_BUCKET,
            'Key': source_key
        }
        
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=AWS_S3_BUCKET,
            Key=dest_key
        )
        
        return {
            "success": True,
            "source_key": source_key,
            "dest_key": dest_key,
            "message": "File copied in S3"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 copy failed: {str(e)}")

def get_file_metadata_from_s3(s3_key: str):
    """
    Get file metadata from S3
    """
    try:
        response = s3_client.head_object(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key
        )
        
        return {
            "size": response.get('ContentLength', 0),
            "content_type": response.get('ContentType', ''),
            "etag": response.get('ETag', ''),
            "last_modified": response.get('LastModified'),
            "version_id": response.get('VersionId'),
            "storage_class": response.get('StorageClass', 'STANDARD'),
            "metadata": response.get('Metadata', {})
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get S3 metadata: {str(e)}")

def list_files_in_s3(prefix: str = None, max_keys: int = 1000):
    """
    List files in S3 bucket with optional prefix
    """
    try:
        params = {
            'Bucket': AWS_S3_BUCKET,
            'MaxKeys': max_keys
        }
        
        if prefix:
            params['Prefix'] = prefix
        
        response = s3_client.list_objects_v2(**params)
        
        files = []
        for obj in response.get('Contents', []):
            files.append({
                "key": obj['Key'],
                "size": obj['Size'],
                "last_modified": obj['LastModified'],
                "storage_class": obj.get('StorageClass', 'STANDARD')
            })
        
        return {
            "files": files,
            "is_truncated": response.get('IsTruncated', False),
            "next_continuation_token": response.get('NextContinuationToken')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list S3 files: {str(e)}")