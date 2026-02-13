import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from google import genai
from google.genai import types
from app.core.settings import settings

logger = logging.getLogger(__name__)

class SimilarProblemFinder:
    """
    Tool to find similar math problems using Vector Search (Supabase).
    """

    def __init__(self):
        self.supabase: Optional[Client] = None
        self.gemini_client = None
        
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            try:
                self.supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                logger.info("Supabase client initialized.")
            except Exception as e:
                logger.error(f"Failed to init Supabase: {e}")
        else:
            logger.warning("Supabase URL/Key missing. Vector search disabled.")

        if settings.GOOGLE_API_KEY:
             self.gemini_client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    def search(self, query_text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Embeds the query and searches the 'math_problems' table in Supabase.
        """
        if not self.supabase or not self.gemini_client:
            return []

        try:
            # 1. Generate Embedding
            embedding_resp = self.gemini_client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=query_text,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            embedding = embedding_resp.embeddings[0].values

            # 2. RPC call to Supabase (assuming 'match_problems' function acts on 'math_problems' table)
            # We assume a Postgres function match_problems(query_embedding vector, match_threshold float, match_count int)
            response = self.supabase.rpc(
                "match_problems",
                {
                    "query_embedding": embedding,
                    "match_threshold": 0.7,
                    "match_count": limit
                }
            ).execute()
            
            return response.data

        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []

    def index_problem(self, problem_text: str, solution_text: str, metadata: Dict[str, Any]):
        """
        Saves a solved problem and its embedding to Supabase.
        """
        if not self.supabase or not self.gemini_client:
            return

        try:
            # 1. Embed
            embedding_resp = self.gemini_client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=problem_text,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            embedding = embedding_resp.embeddings[0].values

            # 2. Insert
            data = {
                "problem_text": problem_text,
                "solution_text": solution_text,
                "embedding": embedding
            }
            
            self.supabase.table("math_problems").insert(data).execute()
            logger.info("Indexed problem in Vector DB.")
            
        except Exception as e:
            logger.error(f"Failed to index problem: {e}")
            # Do not raise, just log.
            pass
