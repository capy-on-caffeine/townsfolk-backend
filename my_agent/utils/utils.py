# utils.py
from __future__ import annotations
import os
from typing import Any, Dict, Optional, List
from pymongo import MongoClient
from pymongo.collection import Collection
from google import genai


class MongoDBClient:
    """
    Mongo wrapper that can route to different databases and collections per call.
    """

    def __init__(self, uri: Optional[str] = None, default_db_name: Optional[str] = None):
        self.uri = uri or 'mongodb+srv://arnavanand2004:zDFEdLkQsHztqSpu@townsfolk.okh5mhn.mongodb.net/?appName=townsfolk'
        self.default_db_name = default_db_name or os.getenv("MONGODB_DB_NAME")
        if not self.uri:
            raise ValueError("MongoDB URI is missing. Set MONGODB_URI environment variable.")
        # default_db_name can be None; we allow per-call db selection
        self.client = MongoClient(self.uri)

    def get_db(self, db_name: Optional[str]) -> Any:
        name = db_name or self.default_db_name
        if not name:
            raise ValueError("Database name not provided and no default is configured.")
        return self.client[name]

    def get_collection(self, db_name: Optional[str], coll_name: str) -> Collection:
        if not coll_name:
            raise ValueError("Collection name is required.")
        return self.get_db(db_name)[coll_name]

    def insert_one(self, db_name: Optional[str], collection: str, document: Dict[str, Any]) -> Any:
        return self.get_collection(db_name, collection).insert_one(document)

    def find(self, db_name: Optional[str], collection: str, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return list(self.get_collection(db_name, collection).find(query or {}))

    def find_one(self, db_name: Optional[str], collection: str, query: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        return self.get_collection(db_name, collection).find_one(query or {})

    def update_one(self, db_name: Optional[str], collection: str, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
        return self.get_collection(db_name, collection).update_one(query, update)

    def delete_one(self, db_name: Optional[str], collection: str, query: Dict[str, Any]) -> Any:
        return self.get_collection(db_name, collection).delete_one(query)


# Global singleton (lazy)
_mongo_instance: Optional[MongoDBClient] = None


def get_mongo_client() -> MongoDBClient:
    global _mongo_instance
    if _mongo_instance is None:
        _mongo_instance = MongoDBClient()
    return _mongo_instance


def get_gemini_client(
    use_vertex: bool,
    project_id: Optional[str] = None,
    location: Optional[str] = None,
    api_key: Optional[str] = None,
) -> genai.Client:
    """
    Build a Google GenAI client forced into API-key mode (Gemini API endpoint).
    """
    if use_vertex:
        raise ValueError("Vertex mode is disabled for this agent. Use API key mode instead.")
    else:
        # Direct API key mode
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError("GOOGLE_API_KEY missing. Provide gemini_api_key in state or set env var.")
        # Clear environment hints that would make the SDK assume Vertex mode.
        for var in (
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_CLOUD_PROJECT",
            "GCP_PROJECT",
            "CLOUDSDK_AUTH_ACCESS_TOKEN",
        ):
            os.environ.pop(var, None)
        return genai.Client(api_key=key)
