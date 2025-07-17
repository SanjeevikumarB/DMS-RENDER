from .routers import files, multipart
from fastapi import FastAPI
from mangum import Mangum

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