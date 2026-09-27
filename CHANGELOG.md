# Changelog

All notable changes to `qed-proof` are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.1.1] - 2026-09-27

The first version published to PyPI. 0.1.0 was tagged on the public repository but never
published; 0.1.1 has the same library code, released through the gated trusted-publishing workflow.

## [0.1.0] - 2026-09-26 (never published)

Initial release.

### Added

- `QedProof` / `AsyncQedProof` clients: `submit_claim`, `get_claim`, `wait_for_verdict`, `list_claims`,
  `iter_claims`, `get_receipt`, `get_keys`, and a `verify` convenience method.
- `verify_receipt(receipt, keys, rpc_url=None) -> VerifyReport`: a self-contained, offline-capable
  port of the PoAW reference checker (`check.py`, `anchor_check.py` and the `poaw_core` primitives).
  Reproduces all 20 spec conformance vectors exactly.
- Typed action helpers in `qed_proof.actions` for `github.commit.push`, `github.pr.open`,
  `github.checks.pass`, `x.post.publish`, `slack.message.post` and `http.url.status`.
- `qed_proof.types`: TypedDicts for the receipt shape, checked against the vendored JSON Schema.
- Optional `anchor` extra (`eth-abi`, `eth-hash`) for checking a receipt's on-chain EAS anchor against
  a JSON-RPC endpoint.
- Errors: `QedProofError`, `QedProofRateLimited` (exposes `retry_after`), `QedProofTimeout`.
