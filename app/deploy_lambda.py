#!/usr/bin/env python3
"""
Deployment script for AWS Lambda function
This script packages and deploys the Lambda function for S3 event processing
"""

import os
import zipfile
import boto3
import json
from pathlib import Path

def create_lambda_package():
    """
    Create a deployment package for the Lambda function
    """
    # Create a temporary directory for the package
    package_dir = Path("lambda_package")
    package_dir.mkdir(exist_ok=True)
    
    # Copy the app directory
    app_dir = Path("app")
    if app_dir.exists():
        import shutil
        shutil.copytree(app_dir, package_dir / "app", dirs_exist_ok=True)
    
    # Copy requirements and install dependencies
    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        import subprocess
        subprocess.run([
            "pip", "install", "-r", str(requirements_file), 
            "-t", str(package_dir), "--no-deps"
        ])
    
    # Create the main Lambda handler
    lambda_handler_content = '''
import sys
import os
sys.path.append(os.path.dirname(__file__))

from app.lambda_handler import lambda_handler
'''
    
    with open(package_dir / "lambda_function.py", "w") as f:
        f.write(lambda_handler_content)
    
    # Create deployment zip
    zip_path = Path("lambda_deployment.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(package_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(package_dir)
                zipf.write(file_path, arcname)
    
    return zip_path

def deploy_lambda_function(function_name, zip_path, bucket_name):
    """
    Deploy the Lambda function to AWS
    """
    lambda_client = boto3.client('lambda')
    s3_client = boto3.client('s3')
    
    # Upload the deployment package to S3
    s3_key = f"lambda-deployments/{function_name}.zip"
    s3_client.upload_file(str(zip_path), bucket_name, s3_key)
    
    # Create or update the Lambda function
    try:
        # Try to update existing function
        lambda_client.update_function_code(
            FunctionName=function_name,
            S3Bucket=bucket_name,
            S3Key=s3_key
        )
        print(f"Updated Lambda function: {function_name}")
    except lambda_client.exceptions.ResourceNotFoundException:
        # Create new function
        lambda_client.create_function(
            FunctionName=function_name,
            Runtime='python3.9',
            Role='arn:aws:iam::YOUR_ACCOUNT_ID:role/lambda-execution-role',  # Update this
            Handler='lambda_function.lambda_handler',
            Code={
                'S3Bucket': bucket_name,
                'S3Key': s3_key
            },
            Description='S3 file upload metadata extraction handler',
            Timeout=300,
            MemorySize=512,
            Environment={
                'Variables': {
                    'DJANGO_UPDATE_METADATA_URL': os.getenv('DJANGO_UPDATE_METADATA_URL', 'http://127.0.0.1:8000/api/files/update-metadata/')
                }
            }
        )
        print(f"Created Lambda function: {function_name}")
    
    # Add S3 trigger
    try:
        lambda_client.add_permission(
            FunctionName=function_name,
            StatementId='S3Trigger',
            Action='lambda:InvokeFunction',
            Principal='s3.amazonaws.com',
            SourceArn=f'arn:aws:s3:::{bucket_name}'
        )
    except lambda_client.exceptions.ResourceConflictException:
        print("S3 trigger permission already exists")
    
    # Configure S3 bucket notification
    notification_config = {
        'LambdaConfigurations': [
            {
                'LambdaFunctionArn': f'arn:aws:lambda:{os.getenv("AWS_REGION", "eu-north-1")}:{os.getenv("AWS_ACCOUNT_ID")}:function:{function_name}',
                'Events': ['s3:ObjectCreated:*'],
                'Filter': {
                    'Key': {
                        'FilterRules': [
                            {
                                'Name': 'prefix',
                                'Value': 'uploads/'
                            }
                        ]
                    }
                }
            }
        ]
    }
    
    s3_client.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration=notification_config
    )
    
    print(f"Configured S3 trigger for bucket: {bucket_name}")

def main():
    """
    Main deployment function
    """
    # Configuration
    function_name = os.getenv('LAMBDA_FUNCTION_NAME', 'dms-metadata-extractor')
    bucket_name = os.getenv('AWS_S3_BUCKET')
    
    if not bucket_name:
        print("Error: AWS_S3_BUCKET environment variable not set")
        return
    
    print(f"Creating deployment package for {function_name}...")
    zip_path = create_lambda_package()
    
    print(f"Deploying Lambda function to AWS...")
    deploy_lambda_function(function_name, zip_path, bucket_name)
    
    print("Deployment completed successfully!")
    
    # Clean up
    zip_path.unlink()
    import shutil
    shutil.rmtree("lambda_package")

if __name__ == "__main__":
    main() 