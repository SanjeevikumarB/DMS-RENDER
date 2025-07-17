import os
from dotenv import load_dotenv

load_dotenv()

# AWS S3 configuration
AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
S3_UPLOAD_FOLDER = os.getenv("S3_UPLOAD_FOLDER", "uploads/")
CDN_DOMAIN = os.getenv("CDN_DOMAIN")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")

# app/core/config.py
DATABASE_URL = os.getenv("DATABASE_URL")
