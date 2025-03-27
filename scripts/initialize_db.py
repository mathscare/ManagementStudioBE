from motor.motor_asyncio import AsyncIOMotorClient
from uuid import uuid4

async def initialize_db():
    client = AsyncIOMotorClient("mongodb://localhost:27017")  # Replace with your MongoDB URI
    db = client["your_database_name"]  # Replace with your database name

    # Ensure collections exist
    required_collections = ["users", "tenants", "roles", "organizations", "permissions", "files", "tags", "events", "tasks"]
    for collection_name in required_collections:
        if collection_name not in await db.list_collection_names():
            await db.create_collection(collection_name)

    # Seed initial data
    if not await db["users"].find_one({"username": "admin"}):
        await db["users"].insert_one({
            "id": str(uuid4()),
            "username": "admin",
            "email": "admin@example.com",
            "hashed_password": "hashed_password",  # Replace with a hashed password
            "tenant_id": str(uuid4()),
            "role_id": str(uuid4())
        })
    print("Database initialized with default data.")

# Run this script to initialize the database
