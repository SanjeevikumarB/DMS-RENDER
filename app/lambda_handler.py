import json
import boto3
import os
import tempfile
import httpx
from botocore.exceptions import ClientError

# Metadata extraction is optional in Lambda. If extractor deps (e.g., PyPDF2) are
# not packaged, we fall back to an empty metadata dict so Lambda still succeeds.
try:
    from .service.metadata_extractor.dispatcher import extract_metadata as _extract_metadata_impl
    _EXTRACTOR_AVAILABLE = True
except Exception as _import_err:
    _EXTRACTOR_AVAILABLE = False
    _EXTRACT_IMPORT_ERROR = str(_import_err)

def extract_metadata_safe(file_path: str) -> dict:
    """Best-effort metadata extraction. Returns {} if extractor unavailable/disabled/errors."""
    # Allow forcing disable via env var
    if os.getenv('DISABLE_EXTRACTION', '').lower() in ('1', 'true', 'yes'):
        return {}
    if not _EXTRACTOR_AVAILABLE:
        print(f"Metadata extractor not available: {_EXTRACT_IMPORT_ERROR}")
        return {}
    try:
        return _extract_metadata_impl(file_path)
    except Exception as e:
        print(f"Metadata extraction failed: {e}")
        return {}

# Initialize S3 client
s3_client = boto3.client('s3')

# Configuration
DJANGO_BASE_URL = os.getenv('DJANGO_BASE_URL', 'http://localhost:8000/api')
DJANGO_UPDATE_METADATA_URL = f"{DJANGO_BASE_URL}/files/update-metadata/"

def lambda_handler(event, context):
    """
    AWS Lambda function handler for S3 upload events
    Step 5 & 6: Extract metadata and send to Django
    
    This function is triggered when a file is uploaded to S3.
    It downloads the file, extracts metadata, and sends it back to Django.
    """
    try:
        # Parse S3 event
        s3_event = event['Records'][0]['s3']
        bucket_name = s3_event['bucket']['name']
        object_key = s3_event['object']['key']
        
        print(f"Processing S3 event: {bucket_name}/{object_key}")
        
        # Extract record_id from object key
        record_id = extract_record_id_from_key(object_key)
        
        if not record_id:
            print(f"Could not extract record_id from key: {object_key}")
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Could not extract record_id from S3 key'})
            }
        
        # Download file from S3 to temporary location
        temp_file_path = download_file_from_s3(bucket_name, object_key)
        
        if not temp_file_path:
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Failed to download file from S3'})
            }
        
        try:
            # Extract metadata from the file (best-effort)
            file_metadata = extract_metadata_safe(temp_file_path)
            
            # Get S3 object metadata
            s3_metadata = get_s3_object_metadata(bucket_name, object_key)
            
            # Prepare data to send to Django
            django_data = {
                'record_id': record_id,
                'metadata': file_metadata,
                's3_metadata': s3_metadata
            }
            
            # Send metadata to Django
            success = send_metadata_to_django(django_data)
            
            if success:
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Metadata extracted and sent to Django successfully',
                        'record_id': record_id,
                        'metadata': file_metadata,
                        's3_metadata': s3_metadata
                    })
                }
            else:
                return {
                    'statusCode': 500,
                    'body': json.dumps({'error': 'Failed to send metadata to Django'})
                }
                
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Lambda execution failed: {str(e)}'})
        }

def extract_record_id_from_key(object_key):
    """
    Extract record_id from S3 object key
    Expected format: uploads/{folder}/{record_id}/{filename}
    """
    try:
        parts = object_key.split('/')
        if len(parts) >= 3:
            # Format: uploads/documents/{record_id}/filename.ext
            return parts[2]
        
        # Alternative: extract from filename if it contains the record_id
        filename = os.path.basename(object_key)
        if '_' in filename:
            # Format: record_id_filename.ext
            return filename.split('_')[0]
            
        return None
    except Exception as e:
        print(f"Error extracting record_id: {str(e)}")
        return None

def download_file_from_s3(bucket_name, object_key):
    """
    Download file from S3 to temporary location
    """
    try:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        temp_file_path = temp_file.name
        temp_file.close()
        
        # Download file from S3
        s3_client.download_file(bucket_name, object_key, temp_file_path)
        
        return temp_file_path
        
    except ClientError as e:
        print(f"Error downloading file from S3: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error downloading file: {str(e)}")
        return None

def get_s3_object_metadata(bucket_name, object_key):
    """
    Get S3 object metadata
    """
    try:
        response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        
        return {
            'bucket': bucket_name,
            'key': object_key,
            'size': response.get('ContentLength', 0),
            'content_type': response.get('ContentType', ''),
            'etag': response.get('ETag', ''),
            'last_modified': response.get('LastModified', '').isoformat() if response.get('LastModified') else None,
            'version_id': response.get('VersionId'),
            'url': f"https://{bucket_name}.s3.amazonaws.com/{object_key}",
            'storage_class': response.get('StorageClass', 'STANDARD')
        }
        
    except ClientError as e:
        print(f"Error getting S3 object metadata: {str(e)}")
        return {}

def send_metadata_to_django(django_data):
    """
    Send metadata to Django API
    """
    try:
        # Add authentication if needed (you can configure this)
        headers = {
            'Content-Type': 'application/json',
            # Add any required authentication headers
            # 'Authorization': 'Bearer your-lambda-token'
        }
        
        # Add Lambda-specific headers for security
        lambda_headers = {
            'X-Lambda-Source': 's3-metadata-extractor',
            'X-Lambda-Version': '1.0'
        }
        headers.update(lambda_headers)
        
        response = httpx.post(
            DJANGO_UPDATE_METADATA_URL,
            json=django_data,
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code == 200:
            print(f"Successfully sent metadata to Django for record_id: {django_data['record_id']}")
            return True
        else:
            print(f"Failed to send metadata to Django. Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"Error sending metadata to Django: {str(e)}")
        return False

# Additional helper functions for S3 operations
def list_s3_objects(bucket_name, prefix=None):
    """
    List objects in S3 bucket with optional prefix
    """
    try:
        if prefix:
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        else:
            response = s3_client.list_objects_v2(Bucket=bucket_name)
        
        return response.get('Contents', [])
        
    except ClientError as e:
        print(f"Error listing S3 objects: {str(e)}")
        return []

def delete_s3_object(bucket_name, object_key):
    """
    Delete object from S3
    """
    try:
        response = s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        return response.get('DeleteMarker', False)
        
    except ClientError as e:
        print(f"Error deleting S3 object: {str(e)}")
        return False

def copy_s3_object(source_bucket, source_key, dest_bucket, dest_key):
    """
    Copy object within S3
    """
    try:
        copy_source = {'Bucket': source_bucket, 'Key': source_key}
        s3_client.copy_object(CopySource=copy_source, Bucket=dest_bucket, Key=dest_key)
        return True
        
    except ClientError as e:
        print(f"Error copying S3 object: {str(e)}")
        return False 