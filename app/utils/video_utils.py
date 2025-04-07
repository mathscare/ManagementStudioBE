import av
import io
import asyncio
from fastapi import UploadFile
from typing import Optional, Tuple

async def generate_video_thumbnail(
    file: UploadFile, 
    timestamp: float = 1.0  # timestamp in seconds
) -> Optional[Tuple[bytes, str]]:
    """
    Generate a thumbnail from video bytes using PyAV.
    
    Args:
        file: An UploadFile object with the video content.
        timestamp: The time in seconds to capture the thumbnail (default: 1.0).
        
    Returns:
        A tuple (thumbnail_bytes, content_type) or None if extraction fails.
    """
    try:
        # Read the video content from the UploadFile
        file_content = await file.read()
        
        # Wrap the synchronous PyAV thumbnail extraction in a thread
        def extract_thumbnail() -> Optional[bytes]:
            try:
                # Open the video stream from in-memory bytes
                container = av.open(io.BytesIO(file_content))
                # Seek to the desired timestamp (converted to microseconds)
                container.seek(int(timestamp * 1_000_000))
                
                # Decode video frames and return the first available frame
                for frame in container.decode(video=0):
                    # Convert the frame to a PIL image
                    image = frame.to_image()
                    # Save the image to a BytesIO buffer as JPEG
                    buf = io.BytesIO()
                    image.save(buf, format="JPEG")
                    return buf.getvalue()
                # No frame was decoded
                return None
            except Exception as inner_e:
                print(f"PyAV extraction error: {inner_e}")
                return None

        thumbnail_data = await asyncio.to_thread(extract_thumbnail)
        
        if thumbnail_data:
            return thumbnail_data, "image/jpeg"
        else:
            print("No thumbnail generated using PyAV.")
            return None

    except Exception as e:
        print(f"Error generating thumbnail with PyAV: {e}")
        return None
