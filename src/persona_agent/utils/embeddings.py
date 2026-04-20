"""Embedding utilities for vector search."""

import logging

logger = logging.getLogger(__name__)


def get_embedding_model():
    """Get an embedding model for generating vectors.

    Returns a sentence-transformers model or a mock model if not available.
    """
    try:
        from sentence_transformers import SentenceTransformer

        # Use a small, efficient model
        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Loaded sentence-transformers embedding model")
        return model
    except ImportError:
        logger.warning("sentence-transformers not available, using mock embeddings")
        return None


class EmbeddingGenerator:
    """Generate embeddings for text using sentence-transformers."""

    def __init__(self):
        """Initialize the embedding generator."""
        self.model = get_embedding_model()

    def generate(self, text: str) -> list[float] | None:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if model not available
        """
        if self.model is None:
            return None

        try:
            embedding = self.model.encode(text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None

    def generate_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors (None for failed embeddings)
        """
        if self.model is None:
            return [None] * len(texts)

        try:
            embeddings = self.model.encode(texts, convert_to_tensor=False)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            return [None] * len(texts)

    @property
    def is_available(self) -> bool:
        """Check if embedding model is available."""
        return self.model is not None

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        if self.model:
            # all-MiniLM-L6-v2 produces 384-dimensional embeddings
            return 384
        return 0


# Global instance
_embedding_generator: EmbeddingGenerator | None = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get the global embedding generator instance."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity in range [-1, 1]

    Raises:
        ValueError: If vectors have different lengths
    """
    if len(vec1) != len(vec2):
        raise ValueError("Vectors must have the same length")

    dot_product = sum(a * b for a, b in zip(vec1, vec2, strict=True))
    magnitude1 = sum(a * a for a in vec1) ** 0.5
    magnitude2 = sum(b * b for b in vec2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)


def normalize_vector(vec: list[float]) -> list[float]:
    """Normalize a vector to unit length.

    Args:
        vec: Vector to normalize

    Returns:
        Normalized vector (zero vector returns itself)
    """
    magnitude = sum(a * a for a in vec) ** 0.5
    if magnitude == 0:
        return vec[:]
    return [a / magnitude for a in vec]


def get_embedding_provider() -> EmbeddingGenerator:
    """Get the global embedding provider instance (alias for get_embedding_generator).

    Returns:
        Singleton EmbeddingGenerator instance
    """
    return get_embedding_generator()
