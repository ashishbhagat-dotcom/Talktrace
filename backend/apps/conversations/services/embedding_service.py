import logging
from typing import Optional

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformer model...")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Sentence-transformer model loaded.")
    return _model


def generate_embedding(text: str) -> Optional[list[float]]:
    if not text or not text.strip():
        return None
    try:
        model = _get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        return None
