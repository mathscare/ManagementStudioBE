# app/core/settings.py
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    secret_key: str = os.getenv("SECRET_KEY")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    database_url: str = os.getenv("sqlite:///./local_dev.db")
    AWS_ACCESS_KEY_ID: str = os.getenv("AKIA5IJOW2W3NRO2FT4U")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("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")
    AWS_S3_BUCKET: str = os.getenv("gpdashboard-events-attachments")


settings = Settings()
