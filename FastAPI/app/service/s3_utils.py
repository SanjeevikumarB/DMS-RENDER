import os
import boto3
import mimetypes
from botocore.config import Config
from fastapi import HTTPException, UploadFile
from pathlib import Path
from .file_service import get_folder_by_extension

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

def generate_presigned_upload_url(file: UploadFile, expires_in: int = 900):
    try:
        filename = file.filename
        extension = Path(filename).suffix.lower()

        if not extension:
            raise HTTPException(status_code=400, detail="Filename must have an extension.")

        if extension not in mimetypes.types_map:
            raise HTTPException(status_code=400, detail=f"Unsupported extension: {extension}")

        content_type = mimetypes.types_map.get(extension, "application/octet-stream")
        folder = get_folder_by_extension(extension)
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
            "message": f"Upload the file directly to this URL using HTTP PUT. It will be saved under '{folder}/'."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Presigned upload URL generation failed: {str(e)}")