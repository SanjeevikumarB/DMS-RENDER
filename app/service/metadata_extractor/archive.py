from zipfile import ZipFile
import tarfile
from .common import get_basic_metadata

# Function to extract metadata from archive files (zip, tar, gz, tgz)
# This function reads the archive file, extracts basic metadata, and lists the contents of the archive.

def extract_archive_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        if file_path.endswith(".zip"):
            with ZipFile(file_path, 'r') as zip_ref:
                metadata.update({
                    "type": "zip",
                    "file_list": zip_ref.namelist()
                })
        elif file_path.endswith((".tar", ".gz", ".tgz")):
            with tarfile.open(file_path, 'r') as tar:
                metadata.update({
                    "type": "tar",
                    "file_list": tar.getnames()
                })
        else:
            metadata["error"] = "Unsupported archive format"
    except Exception as e:
        metadata["error"] = str(e)
    return metadata