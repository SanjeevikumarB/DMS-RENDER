from .routers import files, multipart
from fastapi import FastAPI
from mangum import Mangum
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from .middleware import AuthMiddleware 

# Initialize FastAPI application
app = FastAPI()

app.include_router(files.router)
# app.include_router(multipart.router)

# handler = Mangum(app)

#### content delivary network (CDN) configuration
# direct downloads from S3   --- DONE
# postman for testing the upload timing   --- DONE
#uploading into chunk  --- DONE
#multiple file upload  --- DONE

#parallel uploading 
#acl in aws
#cdn url public or private
#uploading large files at same time

#list files based on folder
#s3 key --Done
#group by upload
#preview files in the web --Done
#trash bins
#versioning 


#multi proessing
#rate limiting 

#loadbalancer
#acl in aws

#need to store aws logs

#batch processing and cost of restoring files
#s3 bucket policy
#s3 bucket lifecycle policy
app = FastAPI(
    title="DMS FastAPI + S3 Service",
    description="Document Management System with FastAPI and AWS S3 integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on your requirements
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Auth middleware
app.add_middleware(AuthMiddleware)

# Include routers
app.include_router(files.router, prefix="/api/v1", tags=["Files"])
app.include_router(multipart.router, prefix="/api/v1", tags=["Multipart Upload"])

@app.get("/")
async def root(request: Request):
    """Root endpoint with user info"""
    return {
        "message": "DMS FastAPI + S3 Service",
        "version": "1.0.0",
        "user": getattr(request.state, "user", None),
    }