"""SPEC conformance: every vector in `tests/vectors/manifest.json` must verify to exactly the
expected report. This is the same manifest and vector files the reference `check.py` uses (vendored
byte-for-byte by `scripts/sync_sdk_spec.py`), so a receipt verifies identically here and in the
spec's own tool."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from qed_proof import verify_receipt

VECTORS_DIR = Path(__file__).parent / "vectors"
MANIFEST = json.loads((VECTORS_DIR / "manifest.json").read_text())
KEYSET = json.loads((VECTORS_DIR / MANIFEST["keyset"]).read_text())


@pytest.mark.parametrize("entry", MANIFEST["vectors"], ids=lambda e: e["file"])
def test_vector_matches_expected_report(entry):
    receipt = json.loads((VECTORS_DIR / entry["file"]).read_text())
    report = verify_receipt(receipt, KEYSET).to_dict()
    assert report == entry["expected"], f"{entry['file']}: {entry['description']}"


def test_manifest_covers_all_twenty_vectors():
    assert len(MANIFEST["vectors"]) == 20
