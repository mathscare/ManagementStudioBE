from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import MONGO_URI, MONGO_DB_NAME

client = AsyncIOMotorClient(MONGO_URI)  # Initialize the MongoDB client globally
db = client[MONGO_DB_NAME]  # Get the database instance

async def ensure_collections_exist():
    """Ensure all required collections exist in the database."""
    existing_collections = await db.list_collection_names()
    
    required_collections = [
        "users", 
        "tenants", 
        "roles", 
        "permissions", 
        "events",
        "tasks",
        "files",
        "tags",
        "emails"  # Add emails collection
    ]
    
    for collection in required_collections:
        if collection not in existing_collections:
            await db.create_collection(collection)
            print(f"Created collection: {collection}")

def get_db():
    return db