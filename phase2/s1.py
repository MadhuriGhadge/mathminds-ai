import os
from supabase import create_client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)


# -----------------------------
# Create embedding
# -----------------------------
def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


# -----------------------------
# Insert sample math problems
# -----------------------------
sample_problems = [
    "What is the derivative of x^2?",
    "Solve the equation 2x + 5 = 15",
    "Find the area of a circle with radius 7"
]

def insert_samples():
    for prob in sample_problems:
        emb = get_embedding(prob)
        supabase.table("math_problems").insert({
            "problem_text": prob,
            "embedding": emb
        }).execute()
    print("Inserted sample math problems!")


# -----------------------------
# Search function (vector similarity)
# -----------------------------
def search_similar(problem_text, limit=1):

    # embed the new problem
    query_embedding = get_embedding(problem_text)

    # Use Supabase vector search RPC
    result = supabase.rpc(
        "match_math_problems",
        {
            "query_embedding": query_embedding,
            "match_count": limit
        }
    ).execute()

    return result.data


# -----------------------------
# Setup vector search RPC
# -----------------------------
# Run this SQL in Supabase SQL editor once:
"""
create or replace function match_math_problems(
  query_embedding vector(1536),
  match_count int
)
returns table (
  id bigint,
  problem_text text,
  distance float
)
language plpgsql
as $$
begin
  return query
  select
    id,
    problem_text,
    1 - (embedding <=> query_embedding) as distance
  from math_problems
  order by embedding <=> query_embedding
  limit match_count;
end;
$$;
"""


# -----------------------------
# Run everything
# -----------------------------
if __name__ == "__main__":
    # Run only once
    # insert_samples()

    query = "How do you find the derivative of a polynomial?"
    matches = search_similar(query)

    print("\nQuery Problem:", query)
    print("Most similar problem:")
    print(matches)
