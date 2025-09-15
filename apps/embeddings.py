import os
from typing import List
from dotenv import load_dotenv
load_dotenv()

PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hf")

if PROVIDER == "openai":
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    openai_client = OpenAI(api_key=api_key) if api_key else None
    local_model = None

elif PROVIDER == "hf":
    HF_MODEL = os.getenv("HF_MODEL", "sentence-transformers/all-mpnet-base-v2")
    HF_DIM = int(os.getenv("HF_DIM", "768"))
    from sentence_transformers import SentenceTransformer
    local_model = SentenceTransformer(HF_MODEL)
    EMBEDDING_MODEL = HF_MODEL   
    EMBEDDING_DIM = HF_DIM
    openai_client = None



def embed_texts(texts: List[str]) -> List[List[float]]:
    """Return embeddings for a list of texts, depending on provider."""
    if PROVIDER == "openai" and openai_client:
        resp = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        return [d.embedding for d in resp.data]

    if PROVIDER == "hf" and local_model:
        return local_model.encode(texts, normalize_embeddings=True).tolist()

    # fallback
    dim = HF_DIM if PROVIDER == "hf" else EMBEDDING_DIM
    return [[0.0] * dim for _ in texts]
