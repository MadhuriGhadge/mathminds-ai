
import unittest
import redis
import pymongo
from app.api.deps import get_orchestrator, get_redis_pool, get_mongo_client

class TestConnectionPooling(unittest.TestCase):
    
    def test_shared_pools(self):
        """Test that dependency provider returns shared pools."""
        pool1 = get_redis_pool()
        pool2 = get_redis_pool()
        self.assertIs(pool1, pool2, "Redis pool should be a singleton")
        
        client1 = get_mongo_client()
        client2 = get_mongo_client()
        self.assertIs(client1, client2, "Mongo client should be a singleton")

    def test_orchestrator_shares_pools(self):
        """Test that Orchestrator uses the shared pools."""
        orch1 = get_orchestrator()
        orch2 = get_orchestrator()
        
        # Check Orchestrator singleton
        self.assertIs(orch1, orch2)
        
        # Check that orchestrator components use the shared pool
        shared_redis_pool = get_redis_pool()
        shared_mongo_client = get_mongo_client()
        
        # Depends on internal structure: 
        # orch.cache_manager.redis_client.connection_pool
        # orch.db_manager.client
        
        if orch1.cache_manager.redis_client:
            self.assertIs(
                orch1.cache_manager.redis_client.connection_pool, 
                shared_redis_pool,
                "CacheManager should use the shared Redis connection pool"
            )
            
        if orch1.db_manager.client:
            self.assertIs(
                orch1.db_manager.client, 
                shared_mongo_client,
                "DatabaseManager should use the shared Mongo client"
            )

if __name__ == "__main__":
    unittest.main()
