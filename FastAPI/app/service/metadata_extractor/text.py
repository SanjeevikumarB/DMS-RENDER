import chardet
from .common import get_basic_metadata


# Function to extract metadata from text files
# This function reads the text file, extracts basic metadata, and includes text-specific information like encoding,word count, and a preview of the content.

def extract_text_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        with open(file_path, 'rb') as f:
            raw = f.read()
            encoding = chardet.detect(raw)['encoding']
            text = raw.decode(encoding)
            metadata.update({
                "type": "text",
                "encoding": encoding,
                "word_count": len(text.split()),
                "preview": text[:100]
            })
    except Exception as e:
        metadata["error"] = str(e)
    return metadata