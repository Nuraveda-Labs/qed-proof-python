"""qed-proof: the Python SDK for QED Proof.

    from qed_proof import QedProof, actions, verify_receipt

    qp = QedProof(api_key="qed_sk_...")
    claim = qp.submit_claim(actions.github_commit_push(target="owner/repo", sha="...", branch="main"),
                            agent_id="my-agent")
    result = qp.wait_for_verdict(claim.claim_id)
    receipt = qp.get_receipt(result.receipt_id)
    report = verify_receipt(receipt, keys=qp.get_keys())
"""
from __future__ import annotations

from . import actions
from .actions import Action
from .client import (
    AsyncQedProof,
    ClaimPage,
    ClaimResult,
    QedProof,
    QedProofError,
    QedProofRateLimited,
    QedProofTimeout,
)
from .verify import VerifyReport, verify_receipt

__version__ = "0.1.2"

__all__ = [
    "Action",
    "actions",
    "AsyncQedProof",
    "ClaimPage",
    "ClaimResult",
    "QedProof",
    "QedProofError",
    "QedProofRateLimited",
    "QedProofTimeout",
    "VerifyReport",
    "verify_receipt",
    "__version__",
]
