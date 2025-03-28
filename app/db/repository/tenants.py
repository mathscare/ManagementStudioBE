from app.db.session import get_db

class TenantsRepository:
    def __init__(self):
        self.collection = get_db()["tenants"]

    async def find_one(self, query):
        return await self.collection.find_one(query)

    async def find_many(self, query):
        return [doc async for doc in self.collection.find(query)]

    async def insert_one(self, tenant):
        result = await self.collection.insert_one(tenant)
        return result.inserted_id

    async def update_one(self, query, update_data):
        return await self.collection.update_one(query, {"$set": update_data})

    async def delete_one(self, query):
        return await self.collection.delete_one(query)

    async def aggregate(self, pipeline):
        return [doc async for doc in self.collection.aggregate(pipeline)]
    
    async def find_many(self, query, limit=10, skip=0, sort=None):
        cursor = self.collection.find(query)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]
