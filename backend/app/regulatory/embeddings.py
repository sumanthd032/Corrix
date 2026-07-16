"""Local embedding model for the regulatory RAG corpus, per the user's
decision to avoid tying every regulatory query to Gemini's free-tier
rate limit (already observed tight during Step 4 testing). Runs
entirely offline after the one-time model download — no API calls, no
rate limit, safe for repeated live-demo Q&A.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    return model.encode(texts, normalize_embeddings=True).tolist()
