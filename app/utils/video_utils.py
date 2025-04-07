import os
import tempfile
import asyncio
from fastapi import UploadFile
import io
import shutil
from typing import Optional, Tuple


async def generate_video_thumbnail(
    file: UploadFile, 
    timestamp: str = "00:00:01.000"
) -> Optional[Tuple[bytes, str]]:
    """
    Generate a thumbnail from a video file.
    
    Args:
        file: The video file as UploadFile
        timestamp: The timestamp to extract the thumbnail from (default: 1 second)
        
    Returns:
        Tuple of (thumbnail_bytes, content_type) or None if failed
    """
    # Check if ffmpeg is installed
    if not await _is_ffmpeg_available():
        print("FFmpeg not available, cannot generate thumbnail")
        return None
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    try:
        # Create temporary directory to work in
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create paths for temporary files
            temp_video_path = os.path.join(temp_dir, f"video{file_extension}")
            temp_thumbnail_path = os.path.join(temp_dir, "thumbnail.jpg")
            
            # Save video to temporary file
            file.file.seek(0)
            content = file.file.read()
            
            with open(temp_video_path, "wb") as temp_file:
                temp_file.write(content)
            
            # Build ffmpeg command based on platform
            ffmpeg_cmd = [
                "ffmpeg", 
                "-i", temp_video_path,
                "-ss", timestamp,
                "-vframes", "1",
                "-y",  # Overwrite output files without asking
                temp_thumbnail_path
            ]
            
            # Run ffmpeg command
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Wait for the process to complete
            stdout, stderr = await process.communicate()
            
            # Check if thumbnail was created
            if os.path.exists(temp_thumbnail_path) and os.path.getsize(temp_thumbnail_path) > 0:
                # Read the thumbnail file
                with open(temp_thumbnail_path, "rb") as f:
                    thumbnail_data = f.read()
                return thumbnail_data, "image/jpeg"
            else:
                print(f"FFmpeg stderr: {stderr.decode()}")
                return None
    
    except Exception as e:
        print(f"Error generating thumbnail: {str(e)}")
        return None
    finally:
        # Reset the file pointer for potential reuse
        file.file.seek(0)


async def _is_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in the system."""
    try:
        # Use 'where' on Windows and 'which' on Unix-like systems
        command = "where" if os.name == "nt" else "which"
        
        process = await asyncio.create_subprocess_exec(
            command, "ffmpeg",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        await process.communicate()
        return process.returncode == 0
    except Exception:
        return False
