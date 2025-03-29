import os
import boto3
import aioboto3
import re
import json
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

AWS_REGION = "ap-south-1"

def get_valid_bucket_name(tenant_id: str) -> str:
    """
    Convert a tenant ID to a valid S3 bucket name.
    
    S3 bucket naming rules:
    - Bucket names must be between 3 and 63 characters long
    - Bucket names can consist only of lowercase letters, numbers, dots (.), and hyphens (-)
    - Bucket names must begin and end with a letter or number
    - Bucket names must not contain two adjacent periods
    - Bucket names must not be formatted as an IP address
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        A valid S3 bucket name
    """
    # Remove any UUID dashes and use as base
    base_name = re.sub(r'[^a-zA-Z0-9]', '', tenant_id).lower()
    
    # Add a prefix to ensure uniqueness and appropriate length
    bucket_name = f"tenant-{base_name}"
    
    # Ensure name is not too long (S3 bucket names must be <= 63 chars)
    if len(bucket_name) > 63:
        bucket_name = bucket_name[:63]
    
    # Ensure name doesn't end with a hyphen or dot
    bucket_name = re.sub(r'[-.]$', '0', bucket_name)
    
    return bucket_name

async def upload_file_to_s3(file: UploadFile, key:str = None, bucket: str = None) -> str:
    """
    Upload a file to S3 and ensure it's publicly accessible.
    Uses multiple approaches to maximize the chance of public access.
    
    Args:
        file: The file to upload
        bucket: The bucket name (will be sanitized)
        
    Returns:
        URL of the uploaded file
    """
    # Sanitize bucket name
    valid_bucket = get_valid_bucket_name(bucket) if bucket else bucket
    
    # Generate a unique key for the file
    unique_filename = f"{uuid4()}.{file.filename}"
    key = unique_filename if not key else key
    
    # Get content type
    content_type = getattr(file, 'content_type', 'application/octet-stream')
    
    # Use standard boto3 for better error handling
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name="ap-south-1"
    )
    
    try:
        # Upload the file
        file.file.seek(0)
        s3.upload_fileobj(
            file.file,
            valid_bucket,
            key,
            ExtraArgs={
                'ContentType': content_type
            }
        )
        
        # Try to make the object public via ACL
        try:
            s3.put_object_acl(
                Bucket=valid_bucket,
                Key=key,
                ACL='public-read'
            )
            print(f"Set object ACL to public-read for {key}")
        except Exception as e:
            print(f"Could not set object ACL, it might still be private: {str(e)}")
        
        # Generate direct URL for the object
        url = f"https://{valid_bucket}.s3.{AWS_REGION}.amazonaws.com/{key}"
        print(f"File URL: {url}")
        
        return url
        
    except Exception as e:
        raise Exception(f"Failed to upload file: {str(e)}")

async def generate_presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    """
    Generate a presigned URL for an S3 object
    """
    # Convert tenant bucket name if needed
    valid_bucket = get_valid_bucket_name(bucket) if bucket else bucket
    
    async with async_session.client("s3", config=s3_config) as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": valid_bucket, "Key": key},
            ExpiresIn=expires_in
        )
    
    return url

async def delete_object(bucket: str, key: str) -> None:
    """
    Delete an object from S3
    """
    # Convert tenant bucket name if needed
    valid_bucket = get_valid_bucket_name(bucket) if bucket else bucket
    
    async with async_session.client("s3", config=s3_config) as s3:
        try:
            await s3.delete_object(Bucket=valid_bucket, Key=key)
        except Exception as e:
            raise Exception(f"Failed to delete object: {str(e)}")

async def create_s3_bucket(bucket_name: str) -> str:
    """
    Create a new S3 bucket in ap-south-1 if it doesn't already exist and
    configure it for maximum public accessibility.
    
    Args:
        bucket_name: Desired bucket name (will be sanitized)
        
    Returns:
        The actual (valid) bucket name created
    """
    # Sanitize bucket name to meet S3 requirements
    valid_bucket = get_valid_bucket_name(bucket_name)
    
    # Use standard boto3 client for better error handling
    s3 = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name="ap-south-1"
    )
    
    try:
        # Check if bucket exists first
        try:
            s3.head_bucket(Bucket=valid_bucket)
            print(f"Bucket {valid_bucket} already exists")
        except:
            # Create the bucket without any custom settings first
            s3.create_bucket(
                Bucket=valid_bucket,
                CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}
            )
            print(f"Created bucket: {valid_bucket}")
        
        # Remove all bucket public access blocks
        s3.put_public_access_block(
            Bucket=valid_bucket,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': False,
                'RestrictPublicBuckets': False
            }
        )
        print(f"Removed public access blocks on bucket: {valid_bucket}")
        
        # Set the bucket policy to allow public read
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PublicReadGetObject",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": ["s3:GetObject", "s3:ListBucket"],
                    "Resource": [
                        f"arn:aws:s3:::{valid_bucket}",
                        f"arn:aws:s3:::{valid_bucket}/*"
                    ]
                }
            ]
        }
        
        # Set the bucket policy
        s3.put_bucket_policy(
            Bucket=valid_bucket,
            Policy=json.dumps(bucket_policy)
        )
        print(f"Set bucket policy for {valid_bucket}")
        
        # Try to set the ownership to allow ACLs
        try:
            s3.put_bucket_ownership_controls(
                Bucket=valid_bucket,
                OwnershipControls={
                    'Rules': [{'ObjectOwnership': 'ObjectWriter'}]
                }
            )
            print(f"Set ownership controls for {valid_bucket}")
        except Exception as e:
            print(f"Could not set ownership controls, objects might still be private: {str(e)}")
            
        # Try to set the ACL to public-read
        try:
            s3.put_bucket_acl(
                Bucket=valid_bucket,
                ACL='public-read'
            )
            print(f"Set bucket ACL to public-read for {valid_bucket}")
        except Exception as e:
            print(f"Could not set bucket ACL: {str(e)}")
            
        # Generate a direct public URL for testing
        url = f"https://{valid_bucket}.s3.{AWS_REGION}.amazonaws.com/"
        print(f"Bucket public URL: {url}")
            
    except Exception as e:
        print(f"Error creating/configuring bucket: {str(e)}")
        # Still return the bucket name for further operations
    
    return valid_bucket

async def set_public_bucket_policy(bucket_name: str) -> None:
    """
    Set a bucket policy that allows public read access to all objects.
    
    Args:
        bucket_name: The name of the bucket to set the policy on
    """
    # Create a policy that allows public read access
    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }
    
    # Convert the policy to JSON
    bucket_policy_json = json.dumps(bucket_policy)
    
    # Apply the policy to the bucket
    async with async_session.client("s3", config=s3_config) as s3:
        try:
            await s3.put_bucket_policy(
                Bucket=bucket_name,
                Policy=bucket_policy_json
            )
            print(f"Set public access policy on bucket: {bucket_name}")
        except Exception as e:
            print(f"Error setting bucket policy: {str(e)}")
            # Continue even if policy setting fails - files can still be made public individually
