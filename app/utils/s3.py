import os
import boto3
import aioboto3
from uuid import uuid4
from fastapi import UploadFile
from app.core.config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_BUCKET, FILE_AWS_S3_BUCKET
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Tuple
from botocore.config import Config

# Create a configuration with the correct signature version
s3_config = Config(
    signature_version='s3v4',
    region_name="ap-south-1"
)

# Initialize S3 client using environment variables
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    config=s3_config
)

# Initialize async S3 session
async_session = aioboto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Constants
EVENT_BUCKET_NAME = AWS_S3_BUCKET
FILE_BUCKET_NAME = FILE_AWS_S3_BUCKET
AWS_REGION = "ap-south-1"

# Event file upload
async def upload_file_to_s3(file: UploadFile, event_name: str, bucket: str = None) -> str:
    """
    Upload a file to S3 for events
    
    Args:
        file: The file to upload
        event_name: Name of the event or prefix for organizing files
        bucket: Optional bucket name, defaults to EVENT_BUCKET_NAME
    
    Returns:
        URL of the uploaded file
    """
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "dat"
    unique_filename = f"{uuid4()}.{file_extension}"
    key = f"{event_name}/{unique_filename}"  # Organize by event name
    
    # Use the provided bucket or default to EVENT_BUCKET_NAME
    bucket_name = bucket if bucket else EVENT_BUCKET_NAME
    
    async with async_session.client("s3", config=s3_config) as s3:
        await s3.upload_fileobj(
            file.file,
            bucket_name,
            key,
        )
    
    return f"https://{bucket_name}.s3.amazonaws.com/{key}"

# File module uploads
async def upload_file_with_tags(file: UploadFile) -> str:
    """
    Upload a file to S3 for the file module
    """
    file_uuid = str(uuid4())
    s3_key = f"uploads/{file_uuid}_{file.filename}"
    
    async with async_session.client("s3", config=s3_config) as s3:
        await s3.upload_fileobj(
            file.file,
            FILE_BUCKET_NAME,
            s3_key,
        )
    
    return s3_key

# Generate presigned URL
async def generate_presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for an S3 object
    """
    async with async_session.client("s3", config=s3_config) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in
        )
    
    return url

# Check object metadata
async def head_object(bucket: str, key: str) -> Dict[str, Any]:
    """
    Get metadata for an S3 object
    """
    async with async_session.client("s3", config=s3_config) as s3:
        try:
            head_obj = await s3.head_object(Bucket=bucket, Key=key)
            return head_obj
        except Exception as e:
            raise Exception(f"Failed to head object: {str(e)}")

# Check if object is restored from Glacier
def is_restored(head_object: Dict[str, Any]) -> bool:
    """
    Check if an object has been restored from Glacier
    """
    restore_status = head_object.get("Restore")
    if restore_status and 'ongoing-request="false"' in restore_status:
        return True
    return False

# Restore object from Glacier
async def restore_object(bucket: str, key: str, days: int = 2, tier: str = "Expedited") -> None:
    """
    Restore an object from Glacier
    """
    async with async_session.client("s3", config=s3_config) as s3:
        try:
            await s3.restore_object(
                Bucket=bucket,
                Key=key,
                RestoreRequest={
                    'Days': days,
                    'GlacierJobParameters': {'Tier': tier}
                }
            )
        except Exception as e:
            raise Exception(f"Failed to initiate restoration: {str(e)}")

# Delete object
async def delete_object(bucket: str, key: str) -> None:
    """
    Delete an object from S3
    """
    async with async_session.client("s3", config=s3_config) as s3:
        try:
            await s3.delete_object(Bucket=bucket, Key=key)
        except Exception as e:
            raise Exception(f"Failed to delete object: {str(e)}")

# Handle file download with Glacier support
async def get_download_url(bucket: str, key: str, file_age: timedelta) -> Tuple[str, str]:
    """
    Get a download URL for a file, handling Glacier restoration if needed
    
    Returns:
        Tuple[str, str]: (status, url_or_message)
        status can be "ready" or "pending"
    """
    # For files uploaded within 2 days, simply return the presigned URL
    if file_age < timedelta(days=2):
        url = await generate_presigned_url(bucket, key)
        return "ready", url
    
    # File might be in Glacier, check its restoration status
    try:
        head_obj = await head_object(bucket, key)
    except Exception as e:
        raise Exception(f"Failed to check file status: {str(e)}")
    
    # If not yet restored, initiate restore and return pending
    if not head_obj.get("Restore") or 'ongoing-request="true"' in head_obj.get("Restore"):
        try:
            await restore_object(bucket, key)
        except Exception as e:
            raise Exception(f"Failed to initiate restoration: {str(e)}")
        return "pending", "File restoration is in progress. Please try again in 1 minute."
    
    # If restoration is complete, generate presigned URL valid for 2 days
    url = await generate_presigned_url(bucket, key, expires_in=172800)  # 2 days in seconds
    return "ready", url
 