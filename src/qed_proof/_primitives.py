"""Ported, not imported: the poaw/0.1 receipt primitives (SPEC.md sections 3, 5 and 8).

This is a line-for-line port of ``oss/core-python/src/poaw_core/__init__.py`` from the QED Proof
monorepo, trimmed to what a *verifier* needs (no tree-building or consistency-proof helpers, since
the SDK only checks receipts it is handed). Keep this in sync with the reference by hand: the
conformance suite in ``tests/test_conformance.py`` is what actually proves it matches.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SPEC_VERSION = "poaw/0.1"
SIG_DOMAIN = b"POAW-RECEIPT-V0\n"


# --- encoding (SPEC §3) ------------------------------------------------------------------------
def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def jcs(obj: Any) -> bytes:
    return rfc8785.dumps(obj)


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def has_float(obj: Any) -> bool:
    """SPEC §3: receipts carry integers only."""
    if isinstance(obj, bool):
        return False
    if isinstance(obj, float):
        return True
    if isinstance(obj, dict):
        return any(has_float(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_float(v) for v in obj)
    return False


# --- keys + signatures (SPEC §5) ---------------------------------------------------------------
def key_id(pk_raw: bytes) -> str:
    return "ed25519:" + b64u(sha256(pk_raw))


def verify_signature(pk_raw: bytes, body: dict, sig_value: str) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(pk_raw).verify(b64u_decode(sig_value), SIG_DOMAIN + jcs(body))
        return True
    except (InvalidSignature, ValueError):
        return False


def claim_digest(claim: dict) -> str:
    stripped = {k: v for k, v in claim.items() if k != "claim_digest"}
    return b64u(sha256(jcs(stripped)))


# --- Merkle log, RFC 6962 (SPEC §8) -------------------------------------------------------------
def leaf_hash(receipt: dict) -> bytes:
    return sha256(b"\x00" + jcs({"body": receipt["body"], "signature": receipt["signature"]}))


def _node(left: bytes, right: bytes) -> bytes:
    return sha256(b"\x01" + left + right)


def root_from_inclusion(index: int, size: int, leaf: bytes, path: list[bytes]) -> bytes | None:
    """RFC 9162 §2.1.3.2 audit-path verification. Returns the computed root, or None if the path is malformed."""
    if index >= size:
        return None
    fn, sn, r = index, size - 1, leaf
    for p in path:
        if sn == 0:
            return None
        if fn & 1 or fn == sn:
            r = _node(p, r)
            if not fn & 1:
                while fn and not fn & 1:
                    fn >>= 1
                    sn >>= 1
        else:
            r = _node(r, p)
        fn >>= 1
        sn >>= 1
    return r if sn == 0 else None
