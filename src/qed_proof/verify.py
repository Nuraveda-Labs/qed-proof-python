"""Offline (and optionally on-chain) verification of a PoAW receipt (poaw/0.1).

This is a port of ``oss/spec/tools/check.py``'s ``check()`` function, not an import of it — the SDK
is self-contained and carries its own copy of the primitives (``_primitives.py``) and the anchor
check (``_anchor.py``). The conformance suite (``tests/test_conformance.py``) proves the two agree on
every vector in the spec's manifest.
"""
from __future__ import annotations

import functools
import json
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

import jsonschema

from . import _primitives as ref

__all__ = ["VerifyReport", "verify_receipt"]


@functools.lru_cache(maxsize=1)
def _schema() -> dict:
    text = resources.files("qed_proof").joinpath("receipt.schema.json").read_text(encoding="utf-8")
    return json.loads(text)


@functools.lru_cache(maxsize=1)
def _validator() -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(_schema())


@dataclass(frozen=True)
class VerifyReport:
    """The result of :func:`verify_receipt`. Field names and values mirror ``check.py``'s report dict exactly,
    including the string values a check can take (``"absent"``, ``"not_checked_offline"``, a failure reason)."""

    checks: dict[str, Any]
    valid: bool
    achieved_trust_level: int
    verdict: str | None
    proven_by: int | None = None
    _anchor_checked: bool = field(default=False, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """Exactly ``check.py``'s report dict shape: ``{"checks": {...}, "valid", "achieved_trust_level", "verdict"}``,
        plus ``proven_by`` (present, even if null, whenever an on-chain anchor check actually ran — matching the
        reference, which only assigns ``report["proven_by"]`` in that branch)."""
        out: dict[str, Any] = {
            "checks": dict(self.checks),
            "valid": self.valid,
            "achieved_trust_level": self.achieved_trust_level,
            "verdict": self.verdict,
        }
        if self._anchor_checked:
            out["proven_by"] = self.proven_by
        return out


def verify_receipt(receipt: dict, keys: dict, rpc_url: str | None = None) -> VerifyReport:
    """Verify a receipt against a keyset (as returned by ``GET /.well-known/poaw-keys.json`` or
    :meth:`QedProof.get_keys`). With ``rpc_url``, also checks the on-chain anchor (SPEC §8.4); without
    it, an anchored receipt reports ``anchor: "not_checked_offline"``. Any doubt fails the check — an
    RPC error, a decode error or a mismatch all give ``"unproven"``-shaped results, never a pass.

    Requires the ``qed-proof[anchor]`` extra when ``rpc_url`` is given.
    """
    report: dict[str, Any] = {"checks": {}}
    c = report["checks"]

    body = receipt.get("body", {}) if isinstance(receipt, dict) else {}
    version = str(body.get("spec_version", ""))
    c["spec_version"] = version.split("/")[0] == "poaw" and version.split("/")[-1].split(".")[0] == "0"
    c["schema"] = not list(_validator().iter_errors(receipt))
    c["integers_only"] = not ref.has_float(receipt)

    sig = receipt.get("signature", {}) if isinstance(receipt, dict) else {}
    key = next((k for k in keys.get("keys", []) if k["key_id"] == sig.get("key_id")), None)
    issued = body.get("issued_at", "")
    key_ok = bool(
        key
        and sig.get("key_id") == body.get("issuer", {}).get("key_id")
        and ref.key_id(ref.b64u_decode(key["public_key"])) == key["key_id"]
        and key["valid_from"] <= issued
        and (key.get("revoked_at") is None or issued < key["revoked_at"])
    )
    c["key"] = key_ok
    c["signature"] = bool(key_ok and ref.verify_signature(ref.b64u_decode(key["public_key"]), body, sig.get("value", "")))
    claim = body.get("claim", {})
    c["claim_digest"] = isinstance(claim, dict) and claim.get("claim_digest") == ref.claim_digest(claim)

    proof = receipt.get("proof")
    if proof is None:
        c["inclusion"] = "absent"
    else:
        root = ref.root_from_inclusion(
            proof["leaf_index"], proof["tree_size"], ref.leaf_hash(receipt),
            [ref.b64u_decode(h) for h in proof["inclusion"]],
        )
        c["inclusion"] = root is not None and ref.b64u(root) == proof["root_hash"]

    proven_by = None
    anchor_checked = False
    if not (proof and proof.get("anchor")):
        c["anchor"] = "absent"
    elif not rpc_url:
        c["anchor"] = "not_checked_offline"
    else:
        try:
            from . import _anchor
        except ImportError as exc:
            raise ImportError(
                "rpc_url was given but the 'anchor' extra is not installed: pip install 'qed-proof[anchor]'"
            ) from exc
        a = _anchor.check_anchor(proof, keys, rpc_url, ref.b64u_decode)
        c["anchor"] = True if a["ok"] else a["reason"]
        proven_by = a["proven_by"]
        anchor_checked = True

    required = ("spec_version", "schema", "integers_only", "key", "signature", "claim_digest")
    valid = all(c[k] is True for k in required) and c["inclusion"] in (True, "absent")
    # SPEC §7: report the ACHIEVED level. L2 needs inclusion AND an anchor verified on-chain (rpc_url given); offline
    # the ceiling is 1.
    achieved = (2 if c["inclusion"] is True and c["anchor"] is True else 1) if valid else 0
    verdict = body.get("verdict", {}).get("value") if valid else None

    return VerifyReport(
        checks=c, valid=valid, achieved_trust_level=achieved, verdict=verdict,
        proven_by=proven_by, _anchor_checked=anchor_checked,
    )
