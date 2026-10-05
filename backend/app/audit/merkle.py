"""Merkle tree over a corpus version's chunk hashes (§6.9, cut-line item #3 — a hash chain
alone already gives tamper-evidence for the audit log; this adds a per-span proof that a
cited chunk is really part of the promoted corpus snapshot).

A plain binary tree: an odd node at a level is carried up unchanged rather than duplicated
(duplicating is the classic Bitcoin-style construction, but it lets a second-preimage
attacker forge a proof for a duplicated leaf — carrying it up avoids that at the cost of a
slightly less balanced tree, which doesn't matter at this scale).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.hashing import sha256_hex


@dataclass
class ProofStep:
    sibling_hash: str
    sibling_is_left: bool  # True if the sibling goes on the left when hashing up


def _hash_pair(left: str, right: str) -> str:
    return sha256_hex(bytes.fromhex(left) + bytes.fromhex(right))


def build_levels(leaf_hashes: list[str]) -> list[list[str]]:
    if not leaf_hashes:
        return [[]]
    levels = [list(leaf_hashes)]
    while len(levels[-1]) > 1:
        current = levels[-1]
        next_level = []
        for i in range(0, len(current) - 1, 2):
            next_level.append(_hash_pair(current[i], current[i + 1]))
        if len(current) % 2 == 1:
            next_level.append(current[-1])
        levels.append(next_level)
    return levels


def merkle_root(leaf_hashes: list[str]) -> str:
    levels = build_levels(leaf_hashes)
    return levels[-1][0] if levels[-1] else sha256_hex(b"")


def merkle_proof(leaf_hashes: list[str], index: int) -> list[ProofStep]:
    levels = build_levels(leaf_hashes)
    proof: list[ProofStep] = []
    idx = index
    for level in levels[:-1]:
        is_right_child = idx % 2 == 1
        sibling_idx = idx - 1 if is_right_child else idx + 1
        if sibling_idx < len(level):
            proof.append(ProofStep(sibling_hash=level[sibling_idx], sibling_is_left=is_right_child))
        idx //= 2
    return proof


def verify_proof(leaf_hash: str, proof: list[ProofStep], root: str) -> bool:
    current = leaf_hash
    for step in proof:
        current = (
            _hash_pair(step.sibling_hash, current) if step.sibling_is_left else _hash_pair(current, step.sibling_hash)
        )
    return current == root
