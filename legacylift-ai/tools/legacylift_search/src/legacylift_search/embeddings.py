"""Embedding providers (HashEmbedder for tests, QwenEmbedder for production).

Implements Milestone 9a of the ExecPlan: Embedder protocol, HashEmbedder,
QwenEmbedder stub, and create_embedder dispatch.
"""

import hashlib
import json
import os
import re
from typing import Protocol


class Embedder(Protocol):
    """Protocol for embedding providers."""

    dimension: int
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        ...


class HashEmbedder:
    """Deterministic hash-based embedder for tests.

    Tokenizes text on whitespace and punctuation, lowercases, hashes each
    token into a fixed bucket, accumulates counts, then L2-normalizes.
    Same input always produces the same vector.
    """

    def __init__(self, dimension: int = 64):
        """Initialize HashEmbedder.

        Args:
            dimension: Size of the embedding vector (default 64).
        """
        self.dimension = dimension
        self.name = "hash"

    def _tokenize(self, text: str) -> list[str]:
        """Split text into lowercase tokens on whitespace/punctuation."""
        # Split on non-alphanumeric, lowercase, filter empty
        tokens = re.split(r'[^a-zA-Z0-9]+', text.lower())
        return [t for t in tokens if t]

    def _hash_to_bucket(self, token: str) -> int:
        """Hash a token to a bucket index in [0, dimension)."""
        # Use blake2b for fast deterministic hashing
        h = hashlib.blake2b(token.encode('utf-8'), digest_size=8)
        return int.from_bytes(h.digest(), 'big') % self.dimension

    def _embed_single(self, text: str) -> list[float]:
        """Embed a single text string."""
        # Initialize zero vector
        vector = [0.0] * self.dimension

        # Tokenize and accumulate counts
        tokens = self._tokenize(text)
        for token in tokens:
            bucket = self._hash_to_bucket(token)
            vector[bucket] += 1.0

        # L2-normalize
        magnitude = sum(x * x for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).
        """
        return [self._embed_single(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector as a list of floats.
        """
        return self._embed_single(text)


class QwenEmbedder:
    """Qwen3-Embedding-0.6B embedder for production.

    Uses sentence-transformers to load and encode with Qwen embeddings.
    Model is loaded lazily on first encode to avoid blocking instantiation.
    """

    def __init__(
        self,
        model: str = "Qwen/Qwen3-Embedding-0.6B",
        dimension: int = 1024,
        normalize: bool = True,
        batch_size: int = 16,
        device: str = "auto",
    ):
        """Initialize QwenEmbedder.

        Args:
            model: Model name (e.g., "Qwen/Qwen3-Embedding-0.6B").
            dimension: Expected embedding dimension.
            normalize: Whether to L2-normalize embeddings.
            batch_size: Batch size for encoding.
            device: Device to use ("auto", "cpu", "cuda", etc.).
        """
        self.model = model
        self.dimension = dimension
        self.normalize = normalize
        self.batch_size = batch_size
        self.device = device
        self.name = "qwen3"
        self._transformer = None

    def _load_model(self):
        """Lazy-load the SentenceTransformer model."""
        if self._transformer is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                f"Failed to load Qwen embedder '{self.model}': {e}. "
                "Use --embedding-provider hash for a local smoke test, or ensure "
                "the model is available to sentence-transformers."
            ) from e

        try:
            # Pass device only if not auto, otherwise let sentence-transformers decide
            device_arg = self.device if self.device != "auto" else None
            self._transformer = SentenceTransformer(self.model, device=device_arg)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load Qwen embedder '{self.model}': {e}. "
                "Use --embedding-provider hash for a local smoke test, or ensure "
                "the model is available to sentence-transformers."
            ) from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats).

        Raises:
            RuntimeError: If model loading fails.
        """
        self._load_model()

        # Encode in batches
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = self._transformer.encode(
                batch,
                normalize_embeddings=self.normalize,
                convert_to_numpy=True,
            )
            # Convert numpy arrays to Python lists
            all_embeddings.extend([emb.tolist() for emb in embeddings])

        return all_embeddings

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            RuntimeError: If model loading fails.
        """
        self._load_model()

        embedding = self._transformer.encode(
            text,
            normalize_embeddings=self.normalize,
            convert_to_numpy=True,
        )
        return embedding.tolist()


class BedrockEmbedder:
    """Hosted Amazon Bedrock embedder (Milestone 20).

    Calls the `bedrock-runtime` `InvokeModel` API one text at a time (Titan
    Text Embeddings accept a single `inputText` per call). Credentials are read
    from the `AWS_BEARER_TOKEN_BEDROCK` env var by botocore automatically — the
    token is never stored in the manifest. The same embedder serves both
    index-time (`embed_documents`) and query-time (`embed_query`) calls so the
    index and query vectors share a model.
    """

    def __init__(
        self,
        model: str = "amazon.titan-embed-text-v2:0",
        dimension: int = 1024,
        region: str = "us-east-2",
        normalize: bool = True,
        batch_size: int = 512,
        max_concurrency: int = 16,
        max_input_bytes: int = 50000,
        client=None,
    ):
        """Initialize BedrockEmbedder.

        Args:
            model: Bedrock model id (e.g. "amazon.titan-embed-text-v2:0").
            dimension: Expected embedding dimension; sent to Titan as the
                requested output size and validated against responses.
            region: Bedrock region (defaults to us-east-2).
            normalize: Request normalized embeddings from the model.
            batch_size: Number of texts processed per embed_documents loop
                iteration (Bedrock Titan embeds one text per request, so this
                only bounds in-flight work, not request size).
            max_concurrency: Max in-flight InvokeModel requests per
                embed_documents call. Titan embeds one text per request, so the
                phase is network-bound; issuing requests concurrently (boto3
                clients are thread-safe) is the main throughput lever. 1 forces
                sequential calls.
            max_input_bytes: First-pass cap on the UTF-8 byte length of
                `inputText` per request. Titan Text Embeddings v2 rejects
                inputs over 50,000 bytes with a ValidationException; an
                oversized chunk would otherwise abort the whole batch (and
                never resolve, since backfill keeps retrying the same chunk).
                Text above this is truncated on a UTF-8 boundary before the
                request. Titan ALSO enforces an 8,192-token cap that a byte cap
                can't guarantee (dense code is ~4 bytes/token), so `_invoke`
                additionally retries with halved input on any residual length
                error until it fits. Either way the full text still lives in
                SQLite/FTS5 for lexical recall, so only the dense vector is
                computed from a bounded prefix (the same way local embedders
                truncate at max_seq_length). 0 disables the byte pre-truncation
                (the token-limit retry still applies).
            client: Optional pre-built bedrock-runtime client (used by tests to
                inject a fake); when None the client is lazily created.
        """
        self.model = model
        self.dimension = dimension
        self.region = region
        self.normalize = normalize
        self.batch_size = batch_size
        self.max_concurrency = max(1, max_concurrency)
        self.max_input_bytes = max_input_bytes
        self.name = f"api:bedrock:{model}"
        self._client = client

    def _truncate_to_byte_limit(self, text: str) -> str:
        """Truncate text so its UTF-8 encoding fits within max_input_bytes.

        Truncation happens on a valid UTF-8 character boundary (decode with
        errors='ignore' drops a trailing partial multibyte sequence).
        """
        if self.max_input_bytes <= 0:
            return text
        encoded = text.encode("utf-8")
        if len(encoded) <= self.max_input_bytes:
            return text
        return encoded[: self.max_input_bytes].decode("utf-8", errors="ignore")

    def _get_client(self):
        """Lazily build the bedrock-runtime client.

        Raises:
            RuntimeError: If boto3 is missing or the bearer token is absent.
        """
        if self._client is not None:
            return self._client

        if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
            raise RuntimeError(
                "Bedrock embedding requires the AWS_BEARER_TOKEN_BEDROCK "
                "environment variable to be set (the Bedrock API key / bearer "
                "token). It is absent. Set it, or use --embedding-provider "
                "hash (or qwen3) for a local embedder."
            )

        try:
            import boto3
        except ImportError as e:
            raise RuntimeError(
                f"Failed to import boto3 for the Bedrock embedder: {e}. "
                "Install boto3, or use --embedding-provider hash (or qwen3) "
                "for a local embedder."
            ) from e

        try:
            # Size the connection pool to the request concurrency so threaded
            # embed_documents calls don't queue on botocore's default pool of
            # 10. read_timeout is generous for cold model invocations.
            from botocore.config import Config as _BotoConfig

            boto_config = _BotoConfig(
                max_pool_connections=max(10, self.max_concurrency),
                retries={"max_attempts": 5, "mode": "adaptive"},
                read_timeout=120,
            )
            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                config=boto_config,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to create the Bedrock client in region "
                f"{self.region!r}: {e}. Use --embedding-provider hash (or "
                "qwen3) for a local embedder."
            ) from e

        return self._client

    @staticmethod
    def _is_length_error(exc: Exception) -> bool:
        """True if a Bedrock error is an input-too-long ValidationException.

        Titan v2 enforces BOTH a byte limit (50,000) and a token limit (8,192).
        The token limit is content-density-dependent, so a fixed byte cap can't
        guarantee it; we detect the length error and retry on a shorter input.
        """
        msg = str(exc).lower()
        if "validationexception" not in msg and "400" not in msg:
            return False
        return (
            "input token" in msg
            or "too many" in msg
            or "maxlength" in msg
            or "max input" in msg
            or "too long" in msg
        )

    def _invoke(self, text: str) -> list[float]:
        """Invoke the model for a single text and return its embedding.

        Oversized inputs are first truncated to the byte cap, then — because
        Titan also enforces a token cap that a byte cap can't guarantee — any
        residual length ValidationException triggers a halving retry until the
        input fits. The full text still lives in SQLite/FTS5 for lexical
        recall; only the dense vector is computed from a bounded prefix.
        """
        client = self._get_client()
        candidate = self._truncate_to_byte_limit(text)

        last_exc: Exception | None = None
        # Bounded retries: halving from ~50KB reaches a few hundred bytes well
        # within ~8 iterations; the cap is a backstop against a pathological
        # model that rejects every non-empty input.
        for _ in range(12):
            body = json.dumps(
                {
                    "inputText": candidate,
                    "dimensions": self.dimension,
                    "normalize": self.normalize,
                }
            )
            try:
                response = client.invoke_model(modelId=self.model, body=body)
                payload = response["body"].read()
                data = json.loads(payload)
            except Exception as e:
                if self._is_length_error(e):
                    last_exc = e
                    if len(candidate) > 1:
                        # Halve on a UTF-8 boundary and retry.
                        half = max(1, len(candidate.encode("utf-8")) // 2)
                        candidate = candidate.encode("utf-8")[:half].decode(
                            "utf-8", errors="ignore"
                        )
                        continue
                    # Already at the floor and still rejected — give up with a
                    # clear length-specific message rather than the generic one.
                    break
                raise RuntimeError(
                    f"Bedrock InvokeModel call failed for model {self.model!r} "
                    f"in region {self.region!r}: {e}. This may be an auth, "
                    "throttle, or access error — verify AWS_BEARER_TOKEN_BEDROCK "
                    "is valid, or use --embedding-provider hash (or qwen3) for "
                    "a local embedder."
                ) from e

            embedding = data.get("embedding")
            if embedding is None:
                raise RuntimeError(
                    f"Bedrock response for model {self.model!r} did not contain "
                    f"an 'embedding' field. Response keys: {sorted(data.keys())}."
                )
            return [float(x) for x in embedding]

        raise RuntimeError(
            f"Bedrock InvokeModel kept rejecting input as too long for model "
            f"{self.model!r} even after truncation: {last_exc}. Use "
            "--embedding-provider hash (or qwen3) for a local embedder."
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each a list of floats), in input order.

        Raises:
            RuntimeError: If credentials are missing or the API call fails.
        """
        if not texts:
            return []

        # Eagerly build (and validate) the client once before fanning out so a
        # missing token / import failure raises clearly rather than inside a
        # worker thread.
        self._get_client()

        if self.max_concurrency == 1 or len(texts) == 1:
            return [self._invoke(text) for text in texts]

        from concurrent.futures import ThreadPoolExecutor

        workers = min(self.max_concurrency, len(texts))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            # map preserves input order; the boto3 client is thread-safe.
            return list(pool.map(self._invoke, texts))

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            RuntimeError: If credentials are missing or the API call fails.
        """
        return self._invoke(text)


def create_embedder(config, provider_override: str | None = None) -> Embedder:
    """Create an embedder instance based on config.

    Args:
        config: EmbeddingConfig with provider, model, dimension, etc.
        provider_override: If set, use this provider instead of config.provider.

    Returns:
        Embedder instance (HashEmbedder or QwenEmbedder).

    Raises:
        ValueError: If provider is unknown.
    """
    # Determine which provider to use
    provider = provider_override if provider_override is not None else config.provider

    # Dispatch based on provider
    if provider == "hash":
        dimension = config.dimension if config.dimension else 64
        return HashEmbedder(dimension=dimension)
    elif provider == "qwen3":
        return QwenEmbedder(
            model=config.model,
            dimension=config.dimension,
            normalize=config.normalize,
            batch_size=config.batch_size,
            device=config.device,
        )
    elif provider == "api":
        # The shared EmbeddingConfig.model default is a Qwen model id; when the
        # user selects the Bedrock provider without overriding model, fall back
        # to a sensible Titan default rather than passing a HF model id to AWS.
        model = config.model
        if not model or model.startswith("Qwen/"):
            model = "amazon.titan-embed-text-v2:0"
        return BedrockEmbedder(
            model=model,
            dimension=config.dimension,
            region=getattr(config, "region", "us-east-2"),
            normalize=config.normalize,
            batch_size=config.batch_size,
            max_concurrency=getattr(config, "max_concurrency", 16),
        )
    else:
        supported = ["hash", "qwen3", "api"]
        raise ValueError(
            f"Unknown embedding provider: {provider!r}. "
            f"Supported providers: {', '.join(supported)}"
        )
