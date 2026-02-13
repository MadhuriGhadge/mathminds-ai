
import os
import pymongo
from dotenv import load_dotenv

# Force reload of .env
load_dotenv(override=True)

uri = os.getenv("MONGO_URI")
print(f"Testing URI: {uri}")

try:
    # Need to handle potential "dnspython" requirement for SRV
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
    info = client.server_info()
    print("SUCCESS: Connected to MongoDB Atlas!")
    print(f"Version: {info.get('version')}")
except Exception as e:
    print(f"FAILURE: {e}")
