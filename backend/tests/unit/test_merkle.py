"""Unit tests for audit/merkle.py (§6.9)."""

from __future__ import annotations

from app.audit.merkle import merkle_proof, merkle_root, verify_proof
from app.core.hashing import sha256_hex

LEAVES_EVEN = [sha256_hex(f"chunk-{i}") for i in range(8)]
LEAVES_ODD = [sha256_hex(f"chunk-{i}") for i in range(5)]


def test_every_leaf_proof_verifies_even_count() -> None:
    root = merkle_root(LEAVES_EVEN)
    for i, leaf in enumerate(LEAVES_EVEN):
        proof = merkle_proof(LEAVES_EVEN, i)
        assert verify_proof(leaf, proof, root)


def test_every_leaf_proof_verifies_odd_count() -> None:
    root = merkle_root(LEAVES_ODD)
    for i, leaf in enumerate(LEAVES_ODD):
        proof = merkle_proof(LEAVES_ODD, i)
        assert verify_proof(leaf, proof, root)


def test_tampered_leaf_fails_verification() -> None:
    root = merkle_root(LEAVES_EVEN)
    proof = merkle_proof(LEAVES_EVEN, 3)
    tampered_leaf = sha256_hex("not the real chunk text")
    assert not verify_proof(tampered_leaf, proof, root)


def test_single_leaf_tree() -> None:
    leaves = [sha256_hex("only-chunk")]
    root = merkle_root(leaves)
    assert root == leaves[0]
    assert verify_proof(leaves[0], merkle_proof(leaves, 0), root)


def test_empty_tree_root_is_stable() -> None:
    assert merkle_root([]) == sha256_hex(b"")
