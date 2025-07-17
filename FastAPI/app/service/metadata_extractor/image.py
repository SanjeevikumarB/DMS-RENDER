from PIL import Image
from .common import get_basic_metadata


# Function to extract metadata from image files
# This function reads the image file, extracts basic metadata, and includes image-specific information like format, mode, width, and height.

def extract_image_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        with Image.open(file_path) as img:
            metadata.update({
                "type": "image",
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
            })
    except Exception as e:
        metadata["error"] = str(e)
    return metadata