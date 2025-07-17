from mutagen import File as AudioFile
from .common import get_basic_metadata


# Function to extract metadata from audio files
# This function reads the audio file, extracts basic metadata, and includes audio-specific information like duration,bitrate, and sample rate.

def extract_audio_metadata(file_path):
    metadata = get_basic_metadata(file_path)
    try:
        audio = AudioFile(file_path)
        metadata.update({
            "type": "audio",
            "duration": audio.info.length,
            "bitrate": getattr(audio.info, 'bitrate', None),
            "sample_rate": getattr(audio.info, 'sample_rate', None),
            "title": audio.tags.get("TIT2") if audio.tags else None,
            "artist": audio.tags.get("TPE1") if audio.tags else None,
        })
    except Exception as e:
        metadata["error"] = str(e)
    return metadata
