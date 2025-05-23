# app/core/settings.py
from pydantic_settings import BaseSettings
import os
from dotenv import load_dotenv
load_dotenv()  # This will load variables from a .env file in the current directory


class Settings(BaseSettings):
    secret_key: str = os.getenv("SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    database_url: str = os.getenv("DATABASE_URL")
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_S3_BUCKET: str = os.getenv("AWS_S3_BUCKET")
    Google_maps_key : str = os.getenv("Google_maps_key")
    FILE_AWS_S3_BUCKET : str = os.getenv("FILE_AWS_S3_BUCKET")
    TASKS_FILE_AWS_S3_BUCKET : str = os.getenv("TASKS_FILE_AWS_S3_BUCKET")
    MONGO_URI : str = os.getenv("MONGO_URI")
    MONGO_DB_NAME : str = os.getenv("MONGO_DB_NAME")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")


settings = Settings()
