import os
import boto3
from pathlib import Path
from fastapi import HTTPException
from botocore.exceptions import BotoCoreError, ClientError
from app.service.s3_utils import get_folder_by_extension
from app.core.config import AWS_S3_BUCKET, AWS_REGION

s3_client = boto3.client("s3", region_name=AWS_REGION)

S3_UPLOAD_FOLDER = "uploads/"


def initiate_presigned_multipart_upload(filename: str, content_type: str, record_id: str = None):
    try:
        extension = Path(filename).suffix.lower()
        if not extension:
            raise HTTPException(status_code=400, detail="Filename must have an extension.")

        folder = get_folder_by_extension(extension)
        
        # Include record_id in S3 key for tracking
        if record_id:
            s3_key = f"{S3_UPLOAD_FOLDER}{folder}/{record_id}/{filename}"
        else:
            s3_key = f"{S3_UPLOAD_FOLDER}{folder}/{filename}"

        response = s3_client.create_multipart_upload(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            ContentType=content_type
        )

        return {
            "upload_id": response["UploadId"],
            "key": s3_key,
            "bucket": AWS_S3_BUCKET,
            "record_id": record_id,
            "filename": filename,
            "folder": folder,
            "content_type": content_type,
            "message": "Multipart upload initiated. Use the UploadId and key to upload parts."
        }

    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to initiate multipart upload: {str(e)}")


def get_presigned_part_url(key: str, upload_id: str, part_number: int):
    try:
        return s3_client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": AWS_S3_BUCKET,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number
            },
            ExpiresIn=900 # 15 minutes
        )
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate part URL: {str(e)}")


def complete_presigned_multipart_upload(key: str, upload_id: str, parts: list):
    try:
        response = s3_client.complete_multipart_upload(
            Bucket=AWS_S3_BUCKET,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts}
        )

        return {
            "message": "Multipart upload completed successfully!",
            "location": response.get("Location"),
            "key": key,
            "version_id": response.get("VersionId")
        }
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete multipart upload: {str(e)}")


def abort_presigned_multipart_upload(key: str, upload_id: str):
    """Abort a multipart upload and clean up uploaded parts"""
    try:
        response = s3_client.abort_multipart_upload(
            Bucket=AWS_S3_BUCKET,
            Key=key,
            UploadId=upload_id
        )

        return {
            "message": "Multipart upload aborted successfully!",
            "key": key,
            "upload_id": upload_id
        }
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to abort multipart upload: {str(e)}")
