from pymongo import MongoClient
#client = MongoClient("mongodb://localhost:27017")

client = MongoClient("mongodb+srv://ghadgemadhuri92_db_user:qHEAHrBLcGIXvCIl@phase2.vp7vtyu.mongodb.net/")

db = client["mathminds"]
problems_collection = db["problems"]
