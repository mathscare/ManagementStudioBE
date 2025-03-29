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

    async def files_with_tags(self, tenant_id, skip=0, limit=10, sort=None,id=None):
        pipeline = []
        if id:
            pipeline.append({"$match": {"_id": id}})
        pipeline.append([
            {"$match": {"tenant_id": tenant_id}},
            {"$skip": skip},
            {"$limit": limit},
            {"$lookup": {
                "from": "tags",
                "localField": "tags",
                "foreignField": "_id",
                "as": "tag_details"
            }},
            {"$project": {
                "_id": 1,
                "file_name": 1,
                "created_at": 1,
                "s3_key": 1,
                "tags": {
                    "$map": {
                        "input": "$tag_details",
                        "as": "tag",
                        "in": {
                            "id": "$$tag._id",
                            "name": "$$tag.name",
                            "type": "$$tag.type"
                        }
                    }
                }
            }}
        ])
        if sort:
            pipeline.insert(1, {"$sort": sort})
        return await self.aggregate(pipeline)