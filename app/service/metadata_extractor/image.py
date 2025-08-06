import os
from PIL import Image
import xml.etree.ElementTree as ET
from .common import get_basic_metadata


def extract_image_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".svg":
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            metadata.update({
                "type": "image",
                "format": "SVG",
                "width": root.attrib.get("width"),
                "height": root.attrib.get("height"),
                "viewBox": root.attrib.get("viewBox"),
                "root_tag": root.tag,
            })
        except Exception as e:
            metadata["error"] = f"Failed to parse SVG: {str(e)}"

    else:
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
            metadata["error"] = f"Failed to parse raster image: {str(e)}"

    return metadata
