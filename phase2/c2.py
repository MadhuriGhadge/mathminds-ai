from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

problem = "Solve 2x + 3 = 7"

embedding = model.encode(problem).tolist()

print(len(embedding))   # e.g. 384 numbers
print(embedding)
