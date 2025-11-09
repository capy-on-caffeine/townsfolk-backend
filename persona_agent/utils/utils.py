import os
from typing import Any, Dict
from pymongo import MongoClient
from pymongo.collection import Collection

class MongoDBClient:
    """
    A simple MongoDB client wrapper to handle connection, read, and write operations.
    """

    def __init__(self, uri: str = None, db_name: str = None):
        self.uri = uri or os.getenv("MONGODB_URI")
        self.db_name = db_name or os.getenv("MONGODB_DB_NAME")

        if not self.uri:
            raise ValueError("MongoDB URI is missing. Set MONGODB_URI environment variable.")
        if not self.db_name:
            raise ValueError("MongoDB DB name is missing. Set MONGODB_DB_NAME environment variable.")

        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]


    def get_collection(self, name: str) -> Collection:
        return self.db[name]


    def insert_one(self, collection: str, document: Dict[str, Any]) -> Any:
        col = self.get_collection(collection)
        return col.insert_one(document)

    
    def find(self, collection: str, query: Dict[str, Any] = None) -> Any:
        col = self.get_collection(collection)
        return list(col.find(query or {}))


    def find_one(self, collection: str, query: Dict[str, Any] = None) -> Any:
        col = self.get_collection(collection)
        return col.find_one(query or {})


    def update_one(self, collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        col = self.get_collection(collection)
        return col.update_one(query, update)

    def delete_one(self, collection: str, query: Dict[str, Any]) -> Any:
        col = self.get_collection(collection)
        return col.delete_one(query)



_mongo_instance: MongoDBClient = None

def get_mongo_client() -> MongoDBClient:
    global _mongo_instance
    if _mongo_instance is None:
        _mongo_instance = MongoDBClient()
    return _mongo_instance

from google import genai
# fmt: off
PROJECT_ID = "gen-lang-client-0863855409"  # @param {type: "string", placeholder: "[your-project-id]", isTemplate: true}
LOCATION = "global"  # @param {type: "string"}
# fmt: on

if not PROJECT_ID or PROJECT_ID == "gen-lang-client-0863855409":
    PROJECT_ID = str(os.environ.get("GOOGLE_CLOUD_PROJECT"))

# Connect to the Gen AI service on Vertex AI
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)