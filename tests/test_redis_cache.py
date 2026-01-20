import unittest
import sys
import os
import time

# Ensure app is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.memory.cache import CacheManager

class TestRedisCache(unittest.TestCase):
    def setUp(self):
        # We assume the default localhost URL or whatever is in env
        # If the user said "real", we try to use what's configured.
        self.cache = CacheManager()
        if not self.cache.redis_client:
            self.skipTest("Redis connection failed. Skipping integration test.")

    def test_set_and_get(self):
        """Test setting and getting a value."""
        key = "test_key_123"
        data = {"answer": "42", "reasoning": "Deep Thought"}
        
        # Set
        success = self.cache.set_cached_answer(key, data)
        self.assertTrue(success, "Failed to set cache key")
        
        # Get
        cached_data = self.cache.get_cached_answer(key)
        self.assertEqual(cached_data, data)

    def test_cache_miss(self):
        """Test looking up a non-existent key."""
        key = "non_existent_key_999"
        # Ensure it's not there
        if self.cache.redis_client:
             self.cache.redis_client.delete(key)
             
        result = self.cache.get_cached_answer(key)
        self.assertIsNone(result)

    def test_ttl_expiry(self):
        """Test that TTL works (short duration)."""
        key = "ttl_test_key"
        data = {"temp": "data"}
        # Set with 1 second TTL
        self.cache.set_cached_answer(key, data, ttl=1)
        
        # Verify immediately
        self.assertIsNotNone(self.cache.get_cached_answer(key))
        
        # Wait > 1s
        time.sleep(1.1)
        
        # Verify gone
        self.assertIsNone(self.cache.get_cached_answer(key), "Key should have expired")

if __name__ == '__main__':
    unittest.main()
