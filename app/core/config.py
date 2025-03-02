# app/core/config.py
from app.core.settings import settings

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
DATABASE_URL = settings.database_url
AWS_S3_BUCKET = settings.AWS_S3_BUCKET
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
Google_maps_key = settings.Google_maps_key
