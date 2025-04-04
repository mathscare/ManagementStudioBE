from app.db.session import get_db

class TagsRepository:
    def __init__(self):
        self.collection = get_db()["tags"]

    async def find_one(self, query):
        return await self.collection.find_one(query)

    async def find_many(self, query, skip=0, limit=100, sort=None):
        cursor = self.collection.find(query)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]

    async def insert_one(self, tag):
        result = await self.collection.insert_one(tag)
        return result.inserted_id

    async def update_one(self, query, update_data):
        return await self.collection.update_one(query, {"$set": update_data})

    async def delete_one(self, query):
        return await self.collection.delete_one(query)

    async def aggregate(self, pipeline):
        return [doc async for doc in self.collection.aggregate(pipeline)]

    async def get_tag_suggestions(self, tenant_id, query, tag_ids=None, skip=0, limit=10):
        """
        Get tag suggestions using MongoDB aggregation.
        
        If tag_ids are provided:
        1. Find files that have ALL the specified tag_ids
        2. Extract ALL tag IDs from those files
        3. Search for tags that match the query, but only from the extracted set
        """
        pipeline = []
        
        # If tag_ids are provided, get all unique tag IDs from files that contain ALL specified tags
        if tag_ids and len(tag_ids) > 0:
            # Get the files collection
            files_collection = get_db()["files"]
            
            # First get all unique tag IDs from files that contain ALL specified tags
            tag_ids_pipeline = [
                {
                    "$match": {
                        "tenant_id": tenant_id,
                        "tags": {"$all": tag_ids}
                    }
                },
                {
                    "$unwind": "$tags"
                },
                {
                    "$group": {
                        "_id": None,
                        "all_tag_ids": {"$addToSet": "$tags"}
                    }
                }
            ]
            
            # Execute the pipeline to get all unique tag IDs
            tag_ids_result = await files_collection.aggregate(tag_ids_pipeline).to_list(1)
            
            if tag_ids_result:
                all_tag_ids = tag_ids_result[0]["all_tag_ids"]
                # Add a match stage to filter by the extracted tag IDs
                pipeline.append({
                    "$match": {
                        "_id": {"$in": all_tag_ids}
                    }
                })
            else:
                # No files found with all specified tags, return empty result
                return []
        
        # Add tenant filter and text search
        pipeline.extend([
            { "$match": { 
                "tenant_id": tenant_id,
                "name": { "$regex": query, "$options": "i" }
            }},
            { "$skip": skip },
            { "$limit": limit },
            { "$project": {
                "_id": 1,
                "name": 1,
                "type": 1
            }}
        ])
        
        return await self.aggregate(pipeline)
