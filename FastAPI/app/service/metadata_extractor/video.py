from moviepy import VideoFileClip
from .common import get_basic_metadata


# Function to extract metadata from video files
# This function reads the video file, extracts basic metadata, and includes video-specific information like duration, fps, and resolution.

def extract_video_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    clip = None
    try:
        clip = VideoFileClip(file_path)
        metadata.update({
            "type": "video",
            "duration": clip.duration,
            "fps": clip.fps,
            "width": clip.w,
            "height": clip.h,
            "resolution": f"{clip.w}x{clip.h}",
        })
    except Exception as e:
        metadata["error"] = str(e)
    finally:
        if clip:
            # Safely close video reader
            if hasattr(clip, "reader") and clip.reader:
                clip.reader.close()
            # Safely close audio reader if available
            if clip.audio and hasattr(clip.audio, "reader") and hasattr(clip.audio.reader, "close"):
                try:
                    clip.audio.reader.close()
                except Exception:
                    pass  # Ignore if already closed or not implemented
            clip.close()
    return metadata