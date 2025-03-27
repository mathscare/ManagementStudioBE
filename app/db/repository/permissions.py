from app.db.session import get_db

class PermissionsRepository:
    def __init__(self):
        self.collection = get_db()["permissions"]

    def find_one(self, query):
        return self.collection.find_one(query)

    def find_many(self, query):
        return list(self.collection.find(query))

    def insert_one(self, permission):
        return self.collection.insert_one(permission)

    def update_one(self, query, update_data):
        return self.collection.update_one(query, {"$set": update_data})

    def delete_one(self, query):
        return self.collection.delete_one(query)

    def aggregate(self, pipeline):
        return list(self.collection.aggregate(pipeline))
