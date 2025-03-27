from app.db.session import get_db

class FilesRepository:
    def __init__(self):
        self.collection = get_db()["files"]

    async def find_one(self, query):
        return await self.collection.find_one(query)

    async def find_many(self, query, skip=0, limit=10, sort=None):
        cursor = self.collection.find(query)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]

    async def insert_one(self, file):
        result = await self.collection.insert_one(file)
        return result.inserted_id

    async def update_one(self, query, update_data):
        return await self.collection.update_one(query, {"$set": update_data})

    async def delete_one(self, query):
        return await self.collection.delete_one(query)

    async def aggregate(self, pipeline):
        return [doc async for doc in self.collection.aggregate(pipeline)]
