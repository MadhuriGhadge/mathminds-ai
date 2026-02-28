import redis
import os
from dotenv import load_dotenv

load_dotenv()
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

def check_redis():
    print(f"Checking Redis at: {redis_url}")
    try:
        r = redis.from_url(redis_url)
        r.ping()
        print("✅ Redis is UP!")
    except Exception as e:
        print(f"❌ Redis is DOWN or unreachable: {e}")

if __name__ == "__main__":
    check_redis()
