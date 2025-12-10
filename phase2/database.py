from pymongo import MongoClient
#client = MongoClient("mongodb://localhost:27017")

client = MongoClient("")

db = client["mathminds"]
problems_collection = db["problems"]
