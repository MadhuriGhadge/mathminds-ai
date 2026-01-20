import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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

    def __init__(self, mongo_uri: Optional[str] = None):
        """
        Initialize the DatabaseManager.

        Args:
            mongo_uri: MongoDB connection string. Defaults to environment variable 
                       MONGO_URI or localhost default.
        """
        self.mongo_uri = mongo_uri or os.getenv("MONGO_URI", "mongodb://localhost:27017/")
        self.client = None
        self.db = None
        self.collection = None
        self._connect()

    def _connect(self):
        """Attempts to establish a connection to MongoDB and ensure indexes."""
        try:
            # simple connect to avoid hanging indefinitely if server is down, use serverSelectionTimeoutMS
            self.client = pymongo.MongoClient(self.mongo_uri, serverSelectionTimeoutMS=5000)
            
            # Force a call to check if the server is available
            self.client.server_info()
            
            # Assuming a default database name 'mathminds_ai' if not present in URI, 
            # but usually it's better to pick one fixed name for the app.
            db_name = "mathminds_ai"
            try:
                # If uri has database name, use it
                uri_db = pymongo.uri_parser.parse_uri(self.mongo_uri).get('database')
                if uri_db:
                    db_name = uri_db
            except Exception:
                pass # Fallback to default

            self.db = self.client[db_name]
            self.collection = self.db["solved_problems"]
            
            # Ensure index on 'hash' field unique=True likely best for deduplication
            # User asked for "Index hash field", but didn't explicitly say unique.
            # Given "problem deduplication" context earlier, unique is safer, but I'll stick to non-unique 
            # unless implied, to be safe. Actually, 'hash' usually implies Uniqueness for lookup.
            # Let's create a regular index for performance as requested.
            index = IndexModel([("hash", ASCENDING)], name="hash_index")
            self.collection.create_indexes([index])
            
            logger.info(f"Successfully connected to MongoDB at {self.mongo_uri} (DB: {db_name})")
        except (PyMongoError, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None
            self.collection = None

    def find_by_hash(self, problem_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a solved problem by its hash.

        Args:
            problem_hash: The has generated for the problem text.

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
