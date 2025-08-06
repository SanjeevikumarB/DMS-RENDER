import os
from .pdf import extract_pdf_metadata
from .image import extract_image_metadata
from .excel_csv import extract_excel_or_csv_metadata
from .docx import extract_docx_metadata
from .audio import extract_audio_metadata
from .video import extract_video_metadata
from .archive import extract_archive_metadata
from .text import extract_text_metadata


# Dispatcher function to route file metadata extraction based on file type
def extract_metadata(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_pdf_metadata(file_path)
    elif ext in [".jpg", ".jpeg", ".png", ".svg", ".gif"]:
        return extract_image_metadata(file_path)
    elif ext in [".csv", ".xlsx"]:
        return extract_excel_or_csv_metadata(file_path)
    elif ext == ".docx":
        return extract_docx_metadata(file_path)
    elif ext in [".mp3", ".wav"]:
        return extract_audio_metadata(file_path)
    elif ext in [".mp4", ".mkv"]:
        return extract_video_metadata(file_path)
    elif ext in [".zip", ".tar", ".gz", ".tgz"]:
        return extract_archive_metadata(file_path)
    elif ext == ".txt":
        return extract_text_metadata(file_path)
    else:
        return {"error": f"Unsupported file type: {ext}"}  