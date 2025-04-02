from app.db.session import get_db
from typing import Optional, Dict, Any, List


class CountriesRepository:
    def __init__(self):
        self.collection = get_db()["countries"]

    async def find_many(self, query: Dict[str, Any], skip: int = 0, limit: int = 100, sort=None, projection=None):
        """
        Find countries with support for pagination, sorting, and field projection
        
        Args:
            query: The MongoDB query to execute
            skip: Number of documents to skip (pagination offset)
            limit: Maximum number of documents to return
            sort: Optional sorting criteria
            projection: Fields to include or exclude in the result
            
        Returns:
            List of documents matching the query with pagination applied
        """
        cursor = self.collection.find(query, projection)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]

    async def count(self, query: Dict[str, Any]) -> int:
        """Count documents matching the query"""
        return await self.collection.count_documents(query)

    async def find_one(self, query: Dict[str, Any], projection=None):
        """Find a single country"""
        return await self.collection.find_one(query, projection)


class StatesRepository:
    def __init__(self):
        self.collection = get_db()["states"]

    async def find_many(self, query: Dict[str, Any], skip: int = 0, limit: int = 100, sort=None, projection=None):
        """
        Find states with support for pagination, sorting, and field projection
        
        Args:
            query: The MongoDB query to execute
            skip: Number of documents to skip (pagination offset)
            limit: Maximum number of documents to return
            sort: Optional sorting criteria
            projection: Fields to include or exclude in the result
            
        Returns:
            List of documents matching the query with pagination applied
        """
        cursor = self.collection.find(query, projection)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]

    async def count(self, query: Dict[str, Any]) -> int:
        """Count documents matching the query"""
        return await self.collection.count_documents(query)

    async def find_one(self, query: Dict[str, Any], projection=None):
        """Find a single state"""
        return await self.collection.find_one(query, projection)


class CitiesRepository:
    def __init__(self):
        self.collection = get_db()["cities"]

    async def find_many(self, query: Dict[str, Any], skip: int = 0, limit: int = 100, sort=None, projection=None):
        """
        Find cities with support for pagination, sorting, and field projection
        
        Args:
            query: The MongoDB query to execute
            skip: Number of documents to skip (pagination offset)
            limit: Maximum number of documents to return
            sort: Optional sorting criteria
            projection: Fields to include or exclude in the result
            
        Returns:
            List of documents matching the query with pagination applied
        """
        cursor = self.collection.find(query, projection)
        
        if sort:
            cursor = cursor.sort(sort)
        
        cursor = cursor.skip(skip).limit(limit)
        return [doc async for doc in cursor]

    async def count(self, query: Dict[str, Any]) -> int:
        """Count documents matching the query"""
        return await self.collection.count_documents(query)

    async def find_one(self, query: Dict[str, Any], projection=None):
        """Find a single city"""
        return await self.collection.find_one(query, projection)
