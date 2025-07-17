from PyPDF2 import PdfReader
from .common import get_basic_metadata


# Function to extract metadata from PDF files
# This function reads the PDF file, extracts basic metadata, and includes PDF-specific information like title, author, creator, keywords, and number of pages.

def extract_pdf_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        reader = PdfReader(file_path)
        info = reader.metadata
        metadata.update({
            "type": "pdf",
            "title": info.title,
            "author": info.author,
            "creator": info.creator,
            "keywords": info.get("/Keywords"),
            "num_pages": len(reader.pages),
        })
    except Exception as e:
        metadata["error"] = str(e)
    return metadata