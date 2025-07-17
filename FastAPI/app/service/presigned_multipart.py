import os
import boto3
from pathlib import Path
from fastapi import HTTPException
from botocore.exceptions import BotoCoreError, ClientError
from app.service.file_service import get_folder_by_extension
from app.core.config import AWS_S3_BUCKET, AWS_REGION

s3_client = boto3.client("s3", region_name=AWS_REGION)

S3_UPLOAD_FOLDER = "uploads/"


def initiate_presigned_multipart_upload(filename: str, content_type: str):
    try:
        extension = Path(filename).suffix.lower()
        if not extension:
            raise HTTPException(status_code=400, detail="Filename must have an extension.")

        folder = get_folder_by_extension(extension)
        s3_key = f"{S3_UPLOAD_FOLDER}{folder}/{filename}"

        response = s3_client.create_multipart_upload(
            Bucket=AWS_S3_BUCKET,
            Key=s3_key,
            ContentType=content_type
        )

        return {
            "upload_id": response["UploadId"],
            "key": s3_key,
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
            "key": key
        }
    except (BotoCoreError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete multipart upload: {str(e)}")
