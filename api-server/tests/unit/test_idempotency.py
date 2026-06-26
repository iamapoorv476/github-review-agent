import pytest
from app.utils.idempotency import generate_idempotency_key


class TestIdempotencyKey:

    def test_key_is_deterministic(self):
        key1 = generate_idempotency_key(123, 456, 7, "abc123")
        key2 = generate_idempotency_key(123, 456, 7, "abc123")
        assert key1 == key2

    def test_different_sha_produces_different_key(self):
        key1 = generate_idempotency_key(123, 456, 7, "abc123")
        key2 = generate_idempotency_key(123, 456, 7, "def456")
        assert key1 != key2

    def test_different_pr_produces_different_key(self):
        key1 = generate_idempotency_key(123, 456, 7, "abc123")
        key2 = generate_idempotency_key(123, 456, 8, "abc123")
        assert key1 != key2

    def test_different_installation_produces_different_key(self):
        key1 = generate_idempotency_key(123, 456, 7, "abc123")
        key2 = generate_idempotency_key(999, 456, 7, "abc123")
        assert key1 != key2

    def test_key_contains_prefix(self):
        key = generate_idempotency_key(123, 456, 7, "abc123")
        assert key.startswith("gra:idem:")

    def test_key_contains_all_components(self):
        key = generate_idempotency_key(123, 456, 7, "abc123")
        assert "123" in key
        assert "456" in key
        assert "7" in key
        assert "abc123" in key