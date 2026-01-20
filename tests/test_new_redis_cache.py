import unittest
import sys
import os
import time

# Ensure backend path is included
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.cache.redis_cache import RedisCache

class TestNewRedisCache(unittest.TestCase):
    def setUp(self):
        self.cache = RedisCache()
        # Check connection
        if not self.cache.client:
             self.skipTest("Redis not available")

    def test_set_get(self):
        key = "test_new_cache"
        val = {"foo": "bar"}
        self.assertTrue(self.cache.set(key, val))
        self.assertEqual(self.cache.get(key), val)

    def test_expiry(self):
        key = "test_expiry"
        val = "temp"
        self.cache.set(key, val, ttl=1)
        time.sleep(1.2)
        self.assertIsNone(self.cache.get(key))

if __name__ == '__main__':
    unittest.main()
