import os
import boto3
from uuid import uuid4
from fastapi import UploadFile

# Initialize S3 client using environment variables
s3_client = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

BUCKET_NAME = os.getenv("AWS_S3_BUCKET")

def upload_file_to_s3(file: UploadFile, event_name: str) -> str:
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "dat"
    unique_filename = f"{uuid4()}.{file_extension}"
    key = f"{event_name}/{unique_filename}"  # Organize by event name
    s3_client.upload_fileobj(
        file.file,
        BUCKET_NAME,
        key,
        ExtraArgs={"ACL": "public-read"}
    )
    return f"https://{BUCKET_NAME}.s3.amazonaws.com/{key}"
