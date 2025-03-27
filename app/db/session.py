from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB_NAME

client = AsyncIOMotorClient(MONGO_URI)  # Initialize the MongoDB client globally
db = client[MONGO_DB_NAME]  # Get the database instance

async def ensure_collections_exist():
    required_collections = ["users", "tenants", "roles", "organizations", "permissions", "files", "tags", "events", "tasks"]
    existing_collections = await db.list_collection_names()
    for collection_name in required_collections:
        if collection_name not in existing_collections:
            await db.create_collection(collection_name)

def get_db():
    return db