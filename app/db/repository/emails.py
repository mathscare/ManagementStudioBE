from typing import List, Dict, Any, Optional
from app.db.session import get_db
from datetime import datetime
from uuid import UUID
import copy

class EmailsRepository:
    def __init__(self):
        self.collection_name = "emails"

    async def get_collection(self):
        db = get_db()
        return db[self.collection_name]

    def _prepare_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare document for MongoDB storage by converting UUID objects to strings
        """
        # Create a deep copy to avoid modifying the original
        doc = copy.deepcopy(data)
        
        # Convert _id if it's a UUID
        if '_id' in doc and isinstance(doc['_id'], UUID):
            doc['_id'] = str(doc['_id'])
            
        # Convert tenant_id if it's a UUID
        if 'tenant_id' in doc and isinstance(doc['tenant_id'], UUID):
            doc['tenant_id'] = str(doc['tenant_id'])
            
        return doc

    async def find_one(self, filter_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        collection = await self.get_collection()
        
        # Convert UUID in filter if needed
        if '_id' in filter_dict and isinstance(filter_dict['_id'], UUID):
            filter_dict = copy.deepcopy(filter_dict)
            filter_dict['_id'] = str(filter_dict['_id'])
            
        return await collection.find_one(filter_dict)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        collection = await self.get_collection()
        
        # Convert UUID in filter if needed
        if 'tenant_id' in filter_dict and isinstance(filter_dict['tenant_id'], UUID):
            filter_dict = copy.deepcopy(filter_dict)
            filter_dict['tenant_id'] = str(filter_dict['tenant_id'])
        
        cursor = collection.find(filter_dict).skip(skip).limit(limit)
        
        if sort:
            sort_list = []
            for field, order in sort:
                sort_list.append((field, order))
            cursor = cursor.sort(sort_list)
        
        return await cursor.to_list(length=limit)

    async def insert_one(self, data: Dict[str, Any]) -> str:
        collection = await self.get_collection()
        
        # Prepare document for MongoDB
        doc = self._prepare_document(data)
        
        result = await collection.insert_one(doc)
        return str(result.inserted_id)

    async def update_one(
        self, filter_dict: Dict[str, Any], update_data: Dict[str, Any]
    ) -> int:
        collection = await self.get_collection()
        
        # Convert UUID in filter if needed
        if '_id' in filter_dict and isinstance(filter_dict['_id'], UUID):
            filter_dict = copy.deepcopy(filter_dict)
            filter_dict['_id'] = str(filter_dict['_id'])
        
        # Prepare update data for MongoDB
        update_doc = {"$set": self._prepare_document(update_data)}
        
        result = await collection.update_one(filter_dict, update_doc)
        return result.modified_count

    async def delete_one(self, filter_dict: Dict[str, Any]) -> int:
        collection = await self.get_collection()
        
        # Convert UUID in filter if needed
        if '_id' in filter_dict and isinstance(filter_dict['_id'], UUID):
            filter_dict = copy.deepcopy(filter_dict)
            filter_dict['_id'] = str(filter_dict['_id'])
        
        result = await collection.delete_one(filter_dict)
        return result.deleted_count

    async def count(self, filter_dict: Dict[str, Any]) -> int:
        collection = await self.get_collection()
        
        # Convert UUID in filter if needed
        if 'tenant_id' in filter_dict and isinstance(filter_dict['tenant_id'], UUID):
            filter_dict = copy.deepcopy(filter_dict)
            filter_dict['tenant_id'] = str(filter_dict['tenant_id'])
        
        return await collection.count_documents(filter_dict)
