from docx import Document
from .common import get_basic_metadata


# Function to extract metadata from DOCX files
# This function reads the DOCX file, extracts basic metadata, and includes document-specific information like author, title, subject, keywords, and word count.

def extract_docx_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        doc = Document(file_path)
        core = doc.core_properties
        metadata.update({
            "type": "docx",
            "author": core.author,
            "title": core.title,
            "subject": core.subject,
            "keywords": core.keywords,
            "word_count": len(" ".join([p.text for p in doc.paragraphs]).split())
        })
    except Exception as e:
        metadata["error"] = str(e)
    return metadata