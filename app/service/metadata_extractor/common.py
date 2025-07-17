import os
from datetime import datetime


# Function to get basic metadata of a file
# This function retrieves basic file information such as filename, extension, size, and timestamps. 

def get_basic_metadata(file_path):
    stat = os.stat(file_path)
    return {
        "filename": os.path.basename(file_path),
        "extension": os.path.splitext(file_path)[1].lower(),
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "accessed_at": datetime.fromtimestamp(stat.st_atime).isoformat(),
    }