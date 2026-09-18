"""Tests for embeddings module (Milestone 9a)."""

import pytest
from legacylift_search.embeddings import (
    Embedder,
    HashEmbedder,
    QwenEmbedder,
    create_embedder,
)


class TestHashEmbedder:
    """Tests for HashEmbedder."""

    def test_hash_embedder_deterministic(self):
        """HashEmbedder produces the same vector for the same text."""
        embedder = HashEmbedder(dimension=64)
        text = "provider enrollment reclaim validation"

        # Embed the same text twice
        vec1 = embedder.embed_query(text)
        vec2 = embedder.embed_query(text)

        # Vectors should be identical
        assert vec1 == vec2
        assert len(vec1) == 64
        assert len(vec2) == 64

    def test_hash_embedder_unit_norm(self):
        """HashEmbedder vectors are L2-normalized (unit norm ≈ 1.0)."""
        embedder = HashEmbedder(dimension=64)
        text = "eligibility service check provider"

        vec = embedder.embed_query(text)

        # Compute L2 norm
        l2_norm = sum(x * x for x in vec) ** 0.5

        # Should be approximately 1.0
        assert abs(l2_norm - 1.0) < 1e-6

    def test_hash_embedder_different_texts(self):
        """Different texts produce different vectors."""
        embedder = HashEmbedder(dimension=64)
        text1 = "provider enrollment"
        text2 = "customer service"

        vec1 = embedder.embed_query(text1)
        vec2 = embedder.embed_query(text2)

        # Vectors should not be identical
        assert vec1 != vec2

    def test_hash_embedder_embed_documents_batch(self):
        """HashEmbedder can embed multiple documents."""
        embedder = HashEmbedder(dimension=32)
        texts = [
            "eligibility check",
            "provider validation",
            "enrollment reclaim",
        ]

        vectors = embedder.embed_documents(texts)

        assert len(vectors) == 3
        for vec in vectors:
            assert len(vec) == 32
            # Each should be unit-norm
            l2_norm = sum(x * x for x in vec) ** 0.5
            assert abs(l2_norm - 1.0) < 1e-6

    def test_hash_embedder_custom_dimension(self):
        """HashEmbedder respects custom dimension."""
        embedder = HashEmbedder(dimension=128)
        text = "some sample text"

        vec = embedder.embed_query(text)

        assert len(vec) == 128
        assert embedder.dimension == 128
        assert embedder.name == "hash"


class TestQwenEmbedder:
    """Tests for QwenEmbedder."""

    def test_qwen_embedder_attributes_set(self):
        """QwenEmbedder initializes with correct attributes."""
        embedder = QwenEmbedder(
            model="Qwen/Qwen3-Embedding-0.6B",
            dimension=1024,
            normalize=True,
            batch_size=16,
            device="cpu",
        )

        # Check attributes are set
        assert embedder.model == "Qwen/Qwen3-Embedding-0.6B"
        assert embedder.dimension == 1024
        assert embedder.normalize is True
        assert embedder.batch_size == 16
        assert embedder.device == "cpu"
        assert embedder.name == "qwen3"


class TestCreateEmbedder:
    """Tests for create_embedder dispatch function."""

    def test_create_embedder_hash(self):
        """create_embedder returns HashEmbedder for provider='hash'."""
        # Create a minimal config-like object
        class FakeConfig:
            provider = "hash"
            dimension = 64
            model = None
            normalize = True
            batch_size = 16
            device = "auto"

        config = FakeConfig()
        embedder = create_embedder(config)

        assert isinstance(embedder, HashEmbedder)
        assert embedder.dimension == 64
        assert embedder.name == "hash"

    def test_create_embedder_qwen3(self):
        """create_embedder returns QwenEmbedder for provider='qwen3'."""
        # Create a minimal config-like object
        class FakeConfig:
            provider = "qwen3"
            dimension = 1024
            model = "Qwen/Qwen3-Embedding-0.6B"
            normalize = True
            batch_size = 16
            device = "auto"

        config = FakeConfig()
        embedder = create_embedder(config)

        assert isinstance(embedder, QwenEmbedder)
        assert embedder.dimension == 1024
        assert embedder.name == "qwen3"

    def test_create_embedder_unknown_provider_raises(self):
        """create_embedder raises ValueError for unknown provider."""
        class FakeConfig:
            provider = "openai"
            dimension = 1536
            model = "text-embedding-ada-002"
            normalize = True
            batch_size = 16
            device = "auto"

        config = FakeConfig()

        with pytest.raises(ValueError, match="Unknown embedding provider"):
            create_embedder(config)

        # Check the error message lists supported providers
        try:
            create_embedder(config)
        except ValueError as e:
            assert "hash" in str(e)
            assert "qwen3" in str(e)

    def test_create_embedder_provider_override(self):
        """create_embedder uses provider_override when set."""
        # Config says qwen3, but override to hash
        class FakeConfig:
            provider = "qwen3"
            dimension = 1024
            model = "Qwen/Qwen3-Embedding-0.6B"
            normalize = True
            batch_size = 16
            device = "auto"

        config = FakeConfig()
        embedder = create_embedder(config, provider_override="hash")

        # Should get HashEmbedder, not QwenEmbedder
        assert isinstance(embedder, HashEmbedder)
        assert embedder.name == "hash"
        # Dimension should come from config
        assert embedder.dimension == 1024

    def test_create_embedder_hash_default_dimension(self):
        """create_embedder uses dimension=64 default for hash when config.dimension is None."""
        class FakeConfig:
            provider = "hash"
            dimension = None
            model = None
            normalize = True
            batch_size = 16
            device = "auto"

        config = FakeConfig()
        embedder = create_embedder(config)

        assert isinstance(embedder, HashEmbedder)
        assert embedder.dimension == 64
