import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import pymongo
from pymongo import IndexModel, ASCENDING
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

# Configure logging
logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Manages MongoDB operations for the AI system.
    Handles persistent storage of solved problems and connection management.
    """

    def __init__(self, mongo_uri: Optional[str] = None, client: Optional[pymongo.MongoClient] = None):
        """
        Initialize the DatabaseManager.

        Args:
            mongo_uri: MongoDB connection string.
            client: Existing PyMongo client (shared pool).
        """
        self.mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.client = None
        self.db = None
        self.collection = None
        
        try:
            if client:
                self.client = client
            else:
                # Create new client with specific pool settings if not provided
                self.client = pymongo.MongoClient(
                    self.mongo_uri, 
                    serverSelectionTimeoutMS=5000,
                    minPoolSize=1,  # Keep at least one connection open
                    maxPoolSize=50  # Limit max connections
                )
            
            # Force a call to check if the server is available
            self.client.server_info()
            
            # Setup DB and collection
            db_name = "mathminds_ai"
            try:
                uri_db = pymongo.uri_parser.parse_uri(self.mongo_uri).get('database')
                if uri_db:
                    db_name = uri_db
            except Exception:
                pass

            self.db = self.client[db_name]
            self.collection = self.db["solved_problems"]
            
            # Ensure index
            index = IndexModel([("hash", ASCENDING)], name="hash_index")
            self.collection.create_indexes([index])
            
            logger.info(f"Successfully connected to MongoDB at {self.mongo_uri} (DB: {db_name})")
            
        except (PyMongoError, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            self.collection = None

    # _connect is merged into __init__

    def find_by_hash(self, problem_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a solved problem by its hash.

        Args:
            problem_hash: The hash generated for the problem text.

        Returns:
            Optional[Dict[str, Any]]: The document if found, else None.
        """
        if self.collection is None:
            logger.warning("MongoDB collection not available. Skipping lookup.")
            return None

        try:
            doc = self.collection.find_one({"hash": problem_hash})
            return doc
        except PyMongoError as e:
            logger.error(f"Error finding problem by hash {problem_hash}: {e}")
            return None

    def save_problem(self, problem_dict: Dict[str, Any], answer_dict: Dict[str, Any]) -> bool:
        """
        Save a solved problem and its answer to the database.

        Args:
            problem_dict: Dictionary containing problem details.
                          Must contain 'hash' if not in answer_dict? 
                          Ideally we assume one of them or we merge them.
                          The user requested save_problem(problem_dict, answer_dict).
            answer_dict: Dictionary containing the answer details.

        Returns:
            bool: True if successful, False otherwise.
        """
        if self.collection is None:
            logger.warning("MongoDB collection not available. Skipping save.")
            return False

        try:
            # Construct the document
            # Expecting 'hash' to be somewhere. If not provided, we can't index it effectively 
            # for 'find_by_hash'. I will assume it is passed in problem_dict or we generate/extract it.
            # But the signature didn't ask for hash arg.
            # I will assume problem_dict contains the 'hash' key.
            
            document = {
                "problem": problem_dict,
                "answer": answer_dict,
                "created_at": datetime.now(timezone.utc),
                # Lift hash to top level for easier indexing/querying if present in problem_dict
            }
            
            problem_hash = problem_dict.get("hash")
            if problem_hash:
                document["hash"] = problem_hash

            result = self.collection.insert_one(document)
            logger.info(f"Saved problem with ID: {result.inserted_id}")
            return True
        except PyMongoError as e:
            logger.error(f"Failed to save problem: {e}")
            return False

    def create_session(self, session_id: str, title: str = "New Chat") -> bool:
        """
        Initialize a new chat session.
        """
        if self.db is None:
            return False
        try:
            self.db["chat_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$setOnInsert": {
                        "session_id": session_id,
                        "title": title,
                        "created_at": datetime.now(timezone.utc),
                        "messages": []
                    }
                },
                upsert=True
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return False

    def get_chat_history(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent messages for a session.
        """
        if self.db is None:
            return []
        try:
            # Get the session document with sliced messages
            doc = self.db["chat_sessions"].find_one(
                {"session_id": session_id},
                {"messages": {"$slice": -limit}}
            )
            if doc and "messages" in doc:
                return doc["messages"]
            return []
        except PyMongoError as e:
            logger.error(f"Failed to get history for {session_id}: {e}")
            return []

    def save_chat_message(self, session_id: str, role: str, content: str) -> bool:
        """
        Append a message to the session history.
        Also updates the session title if it's the first user message.
        """
        if self.db is None:
            return False
        try:
            # logic to update title if it's currently "New Chat" and this is a user message
            if role == "user":
                session = self.db["chat_sessions"].find_one({"session_id": session_id})
                if session and session.get("title") == "New Chat":
                    # Generate title from content (truncate)
                    new_title = content[:50] + "..." if len(content) > 50 else content
                    self.db["chat_sessions"].update_one(
                        {"session_id": session_id},
                        {"$set": {"title": new_title}}
                    )

            # Push the new message
            self.db["chat_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "messages": {
                            "role": role, 
                            "content": content, 
                            "timestamp": datetime.now(timezone.utc)
                        }
                    }
                },
                upsert=True
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to save message to {session_id}: {e}")
            return False
