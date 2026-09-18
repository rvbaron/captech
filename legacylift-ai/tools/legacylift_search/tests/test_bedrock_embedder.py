"""Tests for the hosted Amazon Bedrock embedding provider (Milestone 20).

These tests never make a live AWS call: a FakeBedrockClient returns
deterministic fixed-dimension vectors, and the missing-token path is exercised
by clearing the AWS_BEARER_TOKEN_BEDROCK env var. Live Bedrock is gated behind
the real env token and is only smoke-tested manually.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import types
from pathlib import Path

import pytest

from legacylift_search.config import EmbeddingConfig, Manifest
from legacylift_search.embeddings import BedrockEmbedder, create_embedder
from legacylift_search.indexer import Indexer
from legacylift_search.store import SQLiteStore


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "polyglot_repo"


class _FakeBody:
    """Mimics the streaming body object botocore returns from invoke_model."""

    def __init__(self, payload: bytes):
        self._buf = io.BytesIO(payload)

    def read(self) -> bytes:
        return self._buf.read()


class FakeBedrockClient:
    """Deterministic stand-in for a boto3 bedrock-runtime client.

    Produces a fixed-dimension vector from the input text so identical text
    yields identical vectors (mirroring a real embedder's contract) and
    records every call for assertions.
    """

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension
        self.calls: list[dict] = []

    def invoke_model(self, modelId: str, body: str):  # noqa: N803 - boto3 kwarg
        request = json.loads(body)
        self.calls.append({"modelId": modelId, "request": request})

        text = request.get("inputText", "")
        dim = int(request.get("dimensions", self.dimension))
        # Deterministic, text-dependent vector.
        seed = sum(ord(c) for c in text)
        vector = [((seed + i) % 17) / 17.0 for i in range(dim)]
        payload = json.dumps(
            {"embedding": vector, "inputTextTokenCount": len(text.split())}
        ).encode("utf-8")
        return {"body": _FakeBody(payload)}


def _api_config(dimension: int = 1024) -> EmbeddingConfig:
    return EmbeddingConfig(
        provider="api",
        model="amazon.titan-embed-text-v2:0",
        dimension=dimension,
        region="us-east-2",
    )


# --------------------------------------------------------------------------
# Config round-trip
# --------------------------------------------------------------------------

def test_embedding_config_api_fields_round_trip():
    """The new provider="api" + region fields survive a JSON round-trip."""
    cfg = _api_config(dimension=512)
    data = cfg.model_dump(mode="json")
    restored = EmbeddingConfig.model_validate(data)

    assert restored.provider == "api"
    assert restored.region == "us-east-2"
    assert restored.model == "amazon.titan-embed-text-v2:0"
    assert restored.dimension == 512


def test_embedding_config_region_default():
    """region defaults to us-east-2 (NOT inherited from AWS_REGION)."""
    cfg = EmbeddingConfig()
    assert cfg.region == "us-east-2"
    assert cfg.max_concurrency == 16


def test_create_embedder_api_passes_max_concurrency():
    cfg = EmbeddingConfig(provider="api", max_concurrency=4)
    embedder = create_embedder(cfg)
    assert isinstance(embedder, BedrockEmbedder)
    assert embedder.max_concurrency == 4


# --------------------------------------------------------------------------
# create_embedder dispatch
# --------------------------------------------------------------------------

def test_create_embedder_api_dispatch():
    embedder = create_embedder(_api_config())
    assert isinstance(embedder, BedrockEmbedder)
    assert embedder.name == "api:bedrock:amazon.titan-embed-text-v2:0"
    assert embedder.dimension == 1024
    assert embedder.region == "us-east-2"


def test_create_embedder_api_falls_back_to_titan_for_qwen_default_model():
    """Selecting provider=api without overriding model (still the Qwen default)
    falls back to a Titan model id rather than sending a HF id to AWS."""
    cfg = EmbeddingConfig(provider="api")  # model stays Qwen default
    embedder = create_embedder(cfg)
    assert isinstance(embedder, BedrockEmbedder)
    assert embedder.model == "amazon.titan-embed-text-v2:0"


def test_create_embedder_unknown_provider_lists_api():
    class FakeConfig:
        provider = "cohere-direct"
        dimension = 1024
        model = "x"
        normalize = True
        batch_size = 16
        device = "auto"
        region = "us-east-2"

    with pytest.raises(ValueError) as excinfo:
        create_embedder(FakeConfig())
    assert "api" in str(excinfo.value)


# --------------------------------------------------------------------------
# embed_documents / embed_query with the fake client
# --------------------------------------------------------------------------

def test_embed_documents_batches_one_request_per_text():
    fake = FakeBedrockClient(dimension=8)
    embedder = BedrockEmbedder(
        model="amazon.titan-embed-text-v2:0", dimension=8, client=fake
    )
    texts = ["alpha", "beta", "gamma"]
    vectors = embedder.embed_documents(texts)

    assert len(vectors) == 3
    for vec in vectors:
        assert len(vec) == 8
    # One InvokeModel call per text.
    assert len(fake.calls) == 3
    # Requested dimension and model propagate to the request body.
    assert fake.calls[0]["modelId"] == "amazon.titan-embed-text-v2:0"
    assert fake.calls[0]["request"]["dimensions"] == 8
    assert fake.calls[0]["request"]["normalize"] is True


def test_embed_documents_concurrent_preserves_order():
    """With max_concurrency > 1 the results still come back in input order."""
    fake = FakeBedrockClient(dimension=8)
    embedder = BedrockEmbedder(dimension=8, max_concurrency=4, client=fake)
    texts = [f"text-{i}" for i in range(20)]
    vectors = embedder.embed_documents(texts)

    assert len(vectors) == 20
    # Compare against a known-sequential embed of the same texts.
    sequential = BedrockEmbedder(
        dimension=8, max_concurrency=1, client=FakeBedrockClient(dimension=8)
    )
    expected = [sequential.embed_query(t) for t in texts]
    assert vectors == expected


def test_embed_query_single_call():
    fake = FakeBedrockClient(dimension=8)
    embedder = BedrockEmbedder(dimension=8, client=fake)
    vec = embedder.embed_query("provider eligibility validation")
    assert len(vec) == 8
    assert len(fake.calls) == 1


def test_oversized_input_truncated_to_byte_limit():
    """A chunk larger than Titan's 50,000-byte maxLength is truncated before
    the request (on a UTF-8 boundary) instead of aborting the batch."""
    fake = FakeBedrockClient(dimension=8)
    embedder = BedrockEmbedder(
        dimension=8, max_input_bytes=100, client=fake
    )
    big = "x" * 5000  # 5000 bytes, well over the 100-byte test cap
    vec = embedder.embed_query(big)

    assert len(vec) == 8
    sent = fake.calls[0]["request"]["inputText"]
    assert len(sent.encode("utf-8")) <= 100


def test_truncation_respects_utf8_char_boundary():
    """Truncation must not split a multibyte character (no UnicodeDecodeError,
    no lone surrogate)."""
    embedder = BedrockEmbedder(dimension=8, max_input_bytes=10)
    # 'é' is 2 bytes in UTF-8; 8 of them = 16 bytes, cap at 10 lands mid-char.
    text = "é" * 8
    truncated = embedder._truncate_to_byte_limit(text)
    # Re-encoding must succeed and stay within the cap.
    assert len(truncated.encode("utf-8")) <= 10
    # All retained chars are whole 'é' (no replacement/garbage).
    assert set(truncated) <= {"é"}


def test_token_limit_triggers_halving_retry():
    """Titan also enforces a token cap a byte cap can't guarantee. A length
    ValidationException must trigger a halving retry until the input fits,
    rather than aborting (and looping forever under backfill)."""

    class TokenLimitClient:
        """Rejects inputText whose token estimate (~bytes/4) exceeds a cap."""

        def __init__(self, max_tokens=8192, dimension=8):
            self.max_tokens = max_tokens
            self.dimension = dimension
            self.calls = 0

        def invoke_model(self, modelId, body):  # noqa: N803
            self.calls += 1
            req = json.loads(body)
            est_tokens = len(req["inputText"].encode("utf-8")) // 4
            if est_tokens > self.max_tokens:
                raise RuntimeError(
                    "An error occurred (ValidationException): 400 Bad Request: "
                    f"Too many input tokens. Max input tokens: {self.max_tokens}, "
                    f"request input token count: {est_tokens}"
                )
            return {"body": _FakeBody(json.dumps({"embedding": [0.1] * self.dimension}).encode())}

    fake = TokenLimitClient(max_tokens=8192, dimension=8)
    # Allow up to 50,000 bytes through the byte cap; the token cap (8192 ~=
    # 32,768 bytes here) is the binding constraint and forces a retry.
    embedder = BedrockEmbedder(
        dimension=8, max_input_bytes=50000, client=fake
    )
    vec = embedder.embed_query("a" * 49000)  # ~12,250 est tokens > 8192
    assert len(vec) == 8
    assert fake.calls >= 2  # at least one rejection then a successful retry


def test_persistent_length_rejection_raises_clear_error():
    """If the model rejects every input as too long, fail with a clear message
    rather than looping or returning garbage."""

    class AlwaysTooLong:
        def invoke_model(self, modelId, body):  # noqa: N803
            raise RuntimeError(
                "An error occurred (ValidationException): Too many input tokens."
            )

    embedder = BedrockEmbedder(dimension=8, client=AlwaysTooLong())
    with pytest.raises(RuntimeError, match="kept rejecting input as too long"):
        embedder.embed_query("anything")


def test_truncation_disabled_when_zero():
    embedder = BedrockEmbedder(dimension=8, max_input_bytes=0)
    text = "x" * 100000
    assert embedder._truncate_to_byte_limit(text) == text


def test_under_limit_text_unchanged():
    embedder = BedrockEmbedder(dimension=8, max_input_bytes=50000)
    text = "short text"
    assert embedder._truncate_to_byte_limit(text) == text


def test_embed_is_deterministic_for_same_text():
    fake = FakeBedrockClient(dimension=8)
    embedder = BedrockEmbedder(dimension=8, client=fake)
    a = embedder.embed_query("same text")
    b = embedder.embed_query("same text")
    assert a == b


# --------------------------------------------------------------------------
# Error paths
# --------------------------------------------------------------------------

def test_missing_bearer_token_raises_clear_error(monkeypatch):
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    embedder = BedrockEmbedder(dimension=8)  # no injected client
    with pytest.raises(RuntimeError) as excinfo:
        embedder.embed_query("x")
    msg = str(excinfo.value)
    assert "AWS_BEARER_TOKEN_BEDROCK" in msg
    assert "hash" in msg


def test_invoke_failure_wrapped_with_fallback_hint():
    class BoomClient:
        def invoke_model(self, modelId, body):  # noqa: N803
            raise RuntimeError("AccessDeniedException")

    embedder = BedrockEmbedder(dimension=8, client=BoomClient())
    with pytest.raises(RuntimeError) as excinfo:
        embedder.embed_query("x")
    msg = str(excinfo.value)
    assert "InvokeModel" in msg
    assert "hash" in msg


def test_missing_embedding_field_raises():
    class NoEmbeddingClient:
        def invoke_model(self, modelId, body):  # noqa: N803
            return {"body": _FakeBody(json.dumps({"foo": "bar"}).encode())}

    embedder = BedrockEmbedder(dimension=8, client=NoEmbeddingClient())
    with pytest.raises(RuntimeError, match="did not contain an 'embedding'"):
        embedder.embed_query("x")


# --------------------------------------------------------------------------
# End-to-end indexer run with the fake client injected
# --------------------------------------------------------------------------

def test_indexer_end_to_end_with_fake_bedrock(tmp_path, monkeypatch):
    """A full index run using provider=api with the Bedrock client patched to
    the fake produces a complete index: vectors_upserted == chunk_count, the
    api:bedrock:... provider name is persisted, and validate-relevant metadata
    is present."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE, dest)

    manifest = Manifest()
    manifest.embedding.provider = "api"
    manifest.embedding.model = "amazon.titan-embed-text-v2:0"
    manifest.embedding.dimension = 16
    manifest.embedding.region = "us-east-2"

    # Patch boto3.client so no network/credentials are needed.
    import legacylift_search.embeddings as emb

    fake = FakeBedrockClient(dimension=16)

    class FakeBoto:
        def client(self, service, region_name=None, **kwargs):
            assert service == "bedrock-runtime"
            assert region_name == "us-east-2"
            return fake

    # `botocore` must be faked alongside `boto3`, because the embedder imports
    # BOTH -- `from botocore.config import Config` sizes the connection pool.
    # Faking only boto3 made this test pass wherever the real botocore happened
    # to be installed (it arrives with the optional `aws` extra) and fail
    # everywhere else with "No module named 'botocore'", which is how it passed
    # on the maintainer's machine for months and failed on the first CI run.
    class _FakeBotoConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_botocore = types.ModuleType("botocore")
    fake_botocore_config = types.ModuleType("botocore.config")
    fake_botocore_config.Config = _FakeBotoConfig
    fake_botocore.config = fake_botocore_config

    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "fake-token")
    monkeypatch.setitem(sys.modules, "boto3", FakeBoto())
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.config", fake_botocore_config)

    stats = Indexer(manifest, dest).run(reset=True)

    assert stats.chunk_count > 0
    assert stats.embedder_name == "api:bedrock:amazon.titan-embed-text-v2:0"
    assert stats.embedding_dimension == 16
    assert stats.vectors_upserted == stats.chunk_count
    # The fake was actually invoked.
    assert len(fake.calls) > 0

    index_dir = dest / "legacylift-docs" / "index" / "code-search"
    store = SQLiteStore(index_dir / "index.sqlite")
    try:
        assert (
            store.get_metadata("embedder_name")
            == "api:bedrock:amazon.titan-embed-text-v2:0"
        )
        assert store.get_metadata("embedding_dimension") == "16"
        assert int(store.get_metadata("vectors_upserted")) == stats.chunk_count
    finally:
        store.close()
