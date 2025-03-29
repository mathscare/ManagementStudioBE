import logging
from app.db.session import get_db

class UsersRepository:
    def __init__(self):
        self.collection = get_db()["users"]

    async def find_one(self, filter_dict):
        print(f"UsersRepository.find_one called with filter: {filter_dict}")
        
        # Check if we need to convert UUID string to UUID object
        if "_id" in filter_dict and isinstance(filter_dict["_id"], str):
            try:
                # Try to treat the ID as string first (direct comparison)
                user = await self.collection.find_one({"_id": filter_dict["_id"]})
                
                if not user:
                    # If not found, try to convert to UUID if it looks like one
                    from uuid import UUID
                    try:
                        uuid_obj = UUID(filter_dict["_id"])
                        user = await self.collection.find_one({"_id": str(uuid_obj)})
                    except ValueError:
                        # Not a valid UUID, continue with other approaches
                        pass
                    
                    # If still not found, try other potential formats
                    if not user:
                        # Some drivers or ODMs might store IDs in different formats
                        # Try a case-insensitive search if your DB supports it
                        import re
                        id_pattern = re.compile(f"^{filter_dict['_id']}$", re.IGNORECASE)
                        user = await self.collection.find_one({"_id": id_pattern})
                        
                        # Log the entire query result for diagnosis
                        if not user:
                            print("User not found. Checking all users in the collection...")
                            cursor = self.collection.find({}, {"_id": 1, "username": 1}).limit(5)
                            sample_users = await cursor.to_list(length=5)
                            print(f"Sample users in the collection: {sample_users}")
                
                return user
            except Exception as e:
                print(f"Error in find_one when processing ID: {str(e)}")
                # Fall back to regular query
                return await self.collection.find_one(filter_dict)
        else:
            # Regular query without ID conversion
            return await self.collection.find_one(filter_dict)

    async def find_many(self, query, limit=10, skip=0, sort=None):
        cursor = self.collection.find(query)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]

    async def insert_one(self, user):
        result = await self.collection.insert_one(user)
        return result.inserted_id

    async def update_one(self, query, update_data):
        return await self.collection.update_one(query, {"$set": update_data})

    async def delete_one(self, query):
        return await self.collection.delete_one(query)

    async def aggregate(self, pipeline):
        return [doc async for doc in self.collection.aggregate(pipeline)]
