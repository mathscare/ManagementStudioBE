# app/core/settings.py
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    secret_key: str = "default_secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    database_url: str = "sqlite:///./local_dev.db"
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket: str

    class Config:
        env_file = ".env.production" if os.getenv("ENV") == "production" else ".env.development"

settings = Settings()
