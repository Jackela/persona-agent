"""Tests for embeddings utility."""

import pytest

from persona_agent.utils.embeddings import (
    cosine_similarity,
    get_embedding_provider,
    normalize_vector,
)


class TestCosineSimilarity:
    """Tests for cosine_similarity function."""

    def test_identical_vectors(self):
        """Test cosine similarity of identical vectors."""
        vec = [1.0, 2.0, 3.0]
        result = cosine_similarity(vec, vec)
        assert result == 1.0

    def test_orthogonal_vectors(self):
        """Test cosine similarity of orthogonal vectors."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        result = cosine_similarity(vec1, vec2)
        assert result == 0.0

    def test_opposite_vectors(self):
        """Test cosine similarity of opposite vectors."""
        vec1 = [1.0, 2.0]
        vec2 = [-1.0, -2.0]
        result = cosine_similarity(vec1, vec2)
        assert result == pytest.approx(-1.0)

    def test_different_lengths(self):
        """Test error on different length vectors."""
        vec1 = [1.0, 2.0]
        vec2 = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError):
            cosine_similarity(vec1, vec2)


class TestNormalizeVector:
    """Tests for normalize_vector function."""

    def test_normalize_unit_vector(self):
        """Test normalizing a unit vector."""
        vec = [1.0, 0.0, 0.0]
        result = normalize_vector(vec)
        assert result == [1.0, 0.0, 0.0]

    def test_normalize_non_unit_vector(self):
        """Test normalizing a non-unit vector."""
        vec = [3.0, 4.0]
        result = normalize_vector(vec)
        assert result[0] == 0.6
        assert result[1] == 0.8

    def test_normalize_zero_vector(self):
        """Test normalizing a zero vector."""
        vec = [0.0, 0.0, 0.0]
        result = normalize_vector(vec)
        assert result == [0.0, 0.0, 0.0]


class TestGetEmbeddingProvider:
    """Tests for get_embedding_provider function."""

    def test_returns_provider(self):
        """Test that function returns a provider."""
        provider = get_embedding_provider()
        assert provider is not None

    def test_provider_singleton(self):
        """Test that provider is a singleton."""
        provider1 = get_embedding_provider()
        provider2 = get_embedding_provider()
        assert provider1 is provider2
