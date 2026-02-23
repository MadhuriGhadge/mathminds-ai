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
            self.sessions_collection = self.db["chat_sessions"]
            self.users_collection = self.db["users"]
            
            # Ensure indexes
            self.collection.create_index([("hash", ASCENDING)], name="hash_index")
            self.sessions_collection.create_index([("user_id", ASCENDING)], name="user_id_index")
            self.sessions_collection.create_index([("session_id", ASCENDING)], name="session_id_index", unique=True)
            self.users_collection.create_index([("email", ASCENDING)], name="email_index", unique=True)
            self.users_collection.create_index([("user_id", ASCENDING)], name="user_id_index", unique=True)
            
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

    def create_session(self, user_id: str, session_id: str, title: str = "New Chat") -> bool:
        """
        Create a new chat session for a user.
        Uses upsert with $setOnInsert to be idempotent.
        """
        if self.sessions_collection is None:
            return False
        try:
            self.sessions_collection.update_one(
                {"session_id": session_id},
                {
                    "$setOnInsert": {
                        "session_id": session_id,
                        "user_id": user_id,
                        "title": title,
                        "created_at": datetime.now(timezone.utc),
                        "messages": []
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            # If it's a duplicate key error, it means another thread just inserted it.
            # That's fine, we consider the session "created" or at least existing.
            if "E11000" in str(e) or "duplicate key" in str(e).lower():
                return True
            logger.error(f"Failed to create session {session_id} for user {user_id}: {e}")
            return False

    def list_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all sessions for a specific user.
        """
        if self.sessions_collection is None:
            return []
        try:
            cursor = self.sessions_collection.find(
                {"user_id": user_id},
                {"session_id": 1, "title": 1, "created_at": 1, "_id": 0}
            ).sort("created_at", -1)
            return list(cursor)
        except PyMongoError as e:
            logger.error(f"Failed to list sessions for user {user_id}: {e}")
            return []

    def get_chat_history(self, user_id: str, session_id: str, limit: int = 50) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve recent messages for a session, ensuring it belongs to the user.
        Returns None if session not found or not owned by user.
        """
        if self.sessions_collection is None:
            return None
        try:
            doc = self.sessions_collection.find_one(
                {"session_id": session_id, "user_id": user_id},
                {"messages": {"$slice": -limit}, "_id": 0}
            )
            if doc is not None:
                return doc.get("messages", [])
            return None
        except PyMongoError as e:
            logger.error(f"Failed to get history for {session_id} (user: {user_id}): {e}")
            return None

    def save_chat_message(self, user_id: str, session_id: str, role: str, content: str, **kwargs) -> bool:
        """
        Append a message to the session history.
        Only succeeds if the session belongs to the user_id.
        """
        if self.sessions_collection is None:
            return False
        try:
            # logic to update title if it's currently "New Chat" and this is a user message
            if role == "user":
                session = self.sessions_collection.find_one({"session_id": session_id, "user_id": user_id})
                if session and (session.get("title") == "New Chat" or session.get("title") == "New Session" or session.get("title") == "Untitled"):
                    new_title = content[:50] + "..." if len(content) > 50 else content
                    self.sessions_collection.update_one(
                        {"session_id": session_id, "user_id": user_id},
                        {"$set": {"title": new_title}}
                    )

            # Push the new message
            msg = {
                "role": role, 
                "content": content, 
                "timestamp": datetime.now(timezone.utc)
            }
            msg.update(kwargs)
            
            result = self.sessions_collection.update_one(
                {"session_id": session_id, "user_id": user_id},
                {"$push": {"messages": msg}}
            )
            # return True if we found the document to update
            return result.matched_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to save message to {session_id} for user {user_id}: {e}")
            return False

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """
        Delete a session belonging to a user.
        """
        if self.sessions_collection is None:
            return False
        try:
            result = self.sessions_collection.delete_one({"session_id": session_id, "user_id": user_id})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to delete session {session_id} for user {user_id}: {e}")
            return False

    def rename_session(self, user_id: str, session_id: str, new_title: str) -> bool:
        """
        Rename a session belonging to a user.
        """
        if self.sessions_collection is None:
            return False
        try:
            result = self.sessions_collection.update_one(
                {"session_id": session_id, "user_id": user_id},
                {"$set": {"title": new_title}}
            )
            # return True if we found the document to update (even if title was same)
            return result.matched_count > 0
        except PyMongoError as e:
            logger.error(f"Failed to rename session {session_id} for user {user_id}: {e}")
            return False

    # -------------------------------------------------------------------------
    # User Profile Management
    # -------------------------------------------------------------------------
    def create_user(self, user_data: Dict[str, Any]) -> bool:
        """
        Create a new user in the database.
        """
        if self.users_collection is None:
            return False
        try:
            self.users_collection.insert_one(user_data)
            return True
        except PyMongoError as e:
            logger.error(f"Failed to create user: {e}")
            return False

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a user by email.
        """
        if self.users_collection is None:
            return None
        try:
            return self.users_collection.find_one({"email": email})
        except PyMongoError as e:
            logger.error(f"Failed to get user by email {email}: {e}")
            return None

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve user profile by ID (Firebase UID or local UID).
        """
        if self.users_collection is None:
            return None
        try:
            return self.users_collection.find_one({"user_id": user_id})
        except PyMongoError as e:
            logger.error(f"Failed to get profile for {user_id}: {e}")
            return None

    def update_user_profile(self, user_id: str, data: Dict[str, Any]) -> bool:
        """
        Update or create user profile.
        """
        if self.users_collection is None:
            return False
        try:
            self.users_collection.update_one(
                {"user_id": user_id},
                {"$set": {**data, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to update profile for {user_id}: {e}")
            return False
